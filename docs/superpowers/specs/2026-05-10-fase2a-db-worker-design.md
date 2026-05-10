# Spec: Fase 2a — DB Layer + Worker Core

**Fecha:** 2026-05-10
**Estado:** Aprobado (Revisión 2 — confidence-check aplicado)
**Scope:** `apps/api/app/{models,repositories,services,config,crypto,database}/` + `apps/worker/` + Alembic migrations
**Rama:** `feat/fase2a-db-worker`

---

## 1. Contexto

La Fase 1 entregó `packages/core/` con toda la lógica de dominio: `ImapGenericProvider`, `EmailParser`, `RuleEngine`, `LLMClient`. Fase 2a construye la capa de persistencia y el worker ARQ que une esas piezas con una base de datos real.

**Salida de Fase 2a:** Con `docker compose up` corriendo (Postgres + Redis + Greenmail), el worker procesa emails de forma autónoma cada 5 minutos: los clasifica, los mueve a carpetas IMAP y guarda borradores de respuesta. Todo el estado persiste en Postgres.

**Fuera de scope en Fase 2a (se hacen en 2b):**
- Endpoints HTTP REST (`/accounts`, `/rules`, `/cycles`, etc.)
- Autenticación JWT / Better Auth
- Tablas `users`, `memberships`, `writing_styles`, `templates`, `corrections`
- Backoff exponencial IMAP y circuit breaker LLM
- Configuración de intervalos por cuenta vía API

---

## 2. Decisiones de diseño

| Decisión | Elección | Razón |
|----------|----------|-------|
| DB target | **Postgres-first** (asyncpg) | SQLite dual-mode llega en Fase 4 (self-host). Una sola config ahora. |
| Arquitectura | **Service + Repository pattern** | CycleService reutilizable por worker ARQ y futuro endpoint `/cycles/trigger` |
| Credenciales | **Fernet desde el principio** | Evita deuda técnica de seguridad. Una función de 2 líneas. |
| Worker scope | **Loop completo** | Fase 2a entrega valor real: emails clasificados y borradores guardados |
| Scheduler | **ARQ cron cada 5 min** | Sin intervención manual; per-account intervals configurables en 2b |
| Resiliencia | **try/except + audit_log** | Backoff/circuit breaker llegan en 2b cuando el API expone configuración |
| Worker deps | **mailflow-worker depende de mailflow-api** | Consistente con "mismo paquete, distinto entry point" del plan. Worker es thin. |

---

## 3. Estructura de archivos

```
apps/api/
├── alembic.ini                        # config Alembic (se ejecuta desde apps/api/)
├── alembic/
│   ├── env.py                         # async engine + importa todos los modelos
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py      # única migración en Fase 2a
├── pyproject.toml                     # añadir pytest-asyncio, anyio
└── app/
    ├── config.py                      # Pydantic BaseSettings
    ├── database.py                    # create_async_engine + async_sessionmaker
    ├── crypto.py                      # encrypt(dict) / decrypt(str) → dict con Fernet
    ├── models/
    │   ├── __init__.py                # re-exports para Alembic
    │   ├── base.py                    # DeclarativeBase, uuid_pk helper
    │   ├── organization.py            # Organization
    │   ├── email_account.py           # EmailAccount (con relationship llm_provider)
    │   ├── llm_provider.py            # LLMProvider
    │   ├── rules.py                   # DomainRule, KeywordRule, InternalDomain
    │   ├── processed_email.py         # ProcessedEmail
    │   └── audit_log.py               # AuditLog
    ├── repositories/
    │   ├── __init__.py
    │   ├── account.py                 # AccountRepository
    │   └── cycle.py                   # CycleRepository
    └── services/
        ├── __init__.py
        └── cycle.py                   # CycleService + _build_llm_client + _build_draft_bytes

apps/worker/
├── pyproject.toml                     # añadir mailflow-api como dep
└── worker/
    ├── __init__.py
    └── main.py                        # ARQ WorkerSettings + process_account_cycle + cron

packages/core/mailflow_core/
└── (sin cambios en Fase 2a — ver §4)
```

---

## 4. Cambio cross-package: ninguno necesario

`LLMConfig` existe en `packages/core/mailflow_core/classification/llm_client.py` y ya incluye `api_key: str | None = None`. No hay cambios en `packages/core` en Fase 2a.

Ubicación exacta para referencia del implementador:

```python
# packages/core/mailflow_core/classification/llm_client.py
@dataclass
class LLMConfig:
    model_id: str
    api_base: str | None = None
    api_key: str | None = None   # None → LiteLLM usa variable de entorno
    timeout: float = 30.0
    max_retries: int = 2

class LLMClient:
    def __init__(self, config: LLMConfig) -> None: ...
    def generate_draft(self, original_email: ParsedEmail, request: DraftRequest) -> str: ...
    def classify(self, email: ParsedEmail, available_labels: list[str]) -> ClassificationResult: ...
```

`AccountConfig`, `DomainRule`, `KeywordRule` viven en `mailflow_core.classification.rule_engine`:

```python
# packages/core/mailflow_core/classification/rule_engine.py
@dataclass(frozen=True)
class DomainRule:
    domain: str
    label: str
    rule_id: str

@dataclass(frozen=True)
class KeywordRule:
    keywords: tuple[str, ...]
    label: str
    rule_id: str
    match_all: bool = False

@dataclass
class AccountConfig:
    account_id: str
    internal_domains: list[str] = field(default_factory=list)
    client_domain_rules: list[DomainRule] = field(default_factory=list)
    keyword_rules: list[KeywordRule] = field(default_factory=list)
```

`ClassificationResult.method` Literal válido: `"domain_internal" | "domain_client" | "thread" | "keyword" | "llm" | "fallback"` — **no existe `"thread_inheritance"`**.

---

## 5. DB Schema — 8 tablas

### 5.1 `organizations`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
name        VARCHAR(255) NOT NULL
slug        VARCHAR(100) NOT NULL UNIQUE
plan        VARCHAR(20) NOT NULL DEFAULT 'free'   -- 'free' | 'pro' | 'team'
created_at  TIMESTAMP NOT NULL DEFAULT now()
```

### 5.2 `email_accounts`

```sql
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE
provider_type         VARCHAR(20) NOT NULL DEFAULT 'imap'   -- 'imap' | 'm365' | 'gmail'
imap_host             VARCHAR(255) NOT NULL
imap_port             INTEGER NOT NULL DEFAULT 993
use_ssl               BOOLEAN NOT NULL DEFAULT true
username              VARCHAR(255) NOT NULL
encrypted_credentials TEXT NOT NULL   -- Fernet({"password": "..."})
inbox_folder          VARCHAR(255) NOT NULL DEFAULT 'INBOX'
unclassified_folder   VARCHAR(255) NOT NULL DEFAULT 'Sin_Clasificar'
drafts_folder         VARCHAR(255) NOT NULL DEFAULT 'Drafts'
interval_minutes      INTEGER NOT NULL DEFAULT 5
is_active             BOOLEAN NOT NULL DEFAULT true
last_cycle_at         TIMESTAMP NULL
llm_provider_id       UUID NULL REFERENCES llm_providers(id) ON DELETE SET NULL
created_at            TIMESTAMP NOT NULL DEFAULT now()
```

### 5.3 `llm_providers`

```sql
id                           UUID PRIMARY KEY DEFAULT gen_random_uuid()
org_id                       UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE
label                        VARCHAR(100) NOT NULL
type                         VARCHAR(50) NOT NULL   -- 'ollama' | 'openai' | 'anthropic' | 'custom'
base_url                     VARCHAR(500) NOT NULL
encrypted_api_key            TEXT NULL    -- Fernet({"api_key": "..."}) | NULL si Ollama local
default_classification_model VARCHAR(200) NOT NULL
default_generation_model     VARCHAR(200) NOT NULL
is_active                    BOOLEAN NOT NULL DEFAULT true
created_at                   TIMESTAMP NOT NULL DEFAULT now()
```

### 5.4 `domain_rules`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_id  UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE
domain      VARCHAR(255) NOT NULL
label       VARCHAR(255) NOT NULL    -- destination folder name
rule_id     VARCHAR(100) NOT NULL    -- ID único para logging/debugging
priority    INTEGER NOT NULL DEFAULT 0   -- ORDER BY priority ASC
created_at  TIMESTAMP NOT NULL DEFAULT now()
```

### 5.5 `keyword_rules`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_id  UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE
keywords    TEXT[] NOT NULL            -- Postgres ARRAY → tuple() en core
label       VARCHAR(255) NOT NULL
rule_id     VARCHAR(100) NOT NULL
match_all   BOOLEAN NOT NULL DEFAULT false
priority    INTEGER NOT NULL DEFAULT 0
created_at  TIMESTAMP NOT NULL DEFAULT now()
```

### 5.6 `internal_domains`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_id  UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE
domain      VARCHAR(255) NOT NULL
```

### 5.7 `processed_emails`

```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_id          UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE
uid                 BIGINT NOT NULL            -- IMAP UID (unsigned 32-bit → BIGINT seguro)
folder              VARCHAR(255) NOT NULL      -- carpeta IMAP donde estaba
uidvalidity         BIGINT NOT NULL
message_id          VARCHAR(500) NULL          -- Message-ID header (para thread-inheritance)
from_email          VARCHAR(500) NOT NULL
subject             TEXT NOT NULL DEFAULT ''
destination_folder  VARCHAR(255) NOT NULL
method              VARCHAR(50) NOT NULL       -- 'domain_internal' | 'domain_client' | 'thread' | 'keyword' | 'llm' | 'fallback'
confidence          FLOAT NOT NULL
draft_saved         BOOLEAN NOT NULL DEFAULT false
cycle_id            UUID NOT NULL
processed_at        TIMESTAMP NOT NULL DEFAULT now()

UNIQUE (account_id, uid, uidvalidity)   -- idempotencia: ON CONFLICT DO NOTHING
INDEX  (account_id, message_id)         -- thread lookup
```

### 5.8 `audit_log`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_id       UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE
cycle_id         UUID NOT NULL UNIQUE
emails_processed INTEGER NOT NULL DEFAULT 0
drafts_saved     INTEGER NOT NULL DEFAULT 0
error_count      INTEGER NOT NULL DEFAULT 0
error_detail     TEXT NULL          -- traza del último error, si hubo
duration_ms      INTEGER NULL       -- NULL hasta que finaliza
created_at       TIMESTAMP NOT NULL DEFAULT now()
finalized_at     TIMESTAMP NULL     -- NULL = ciclo aún en curso o crashó
```

---

## 6. Config + Crypto

### `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str  # Generar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

### `app/crypto.py`

```python
import json
from cryptography.fernet import Fernet

def encrypt(data: dict, key: str) -> str:
    """Serializa dict a JSON, cifra con Fernet, devuelve token string."""
    return Fernet(key.encode()).encrypt(json.dumps(data).encode()).decode()

def decrypt(token: str, key: str) -> dict:
    """Descifra token Fernet, deserializa JSON, devuelve dict."""
    return json.loads(Fernet(key.encode()).decrypt(token.encode()))
```

Uso en repositories:
```python
from app.crypto import decrypt
from app.config import settings

creds = decrypt(account.encrypted_credentials, settings.SECRET_KEY)
password = creds["password"]

if account.llm_provider and account.llm_provider.encrypted_api_key:
    llm_creds = decrypt(account.llm_provider.encrypted_api_key, settings.SECRET_KEY)
    api_key = llm_creds["api_key"]
else:
    api_key = None
```

---

## 7. Database setup

### `app/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

---

## 8. Alembic setup

Ubicación: `apps/api/` (todos los comandos se ejecutan desde ahí).

### `alembic.ini` (en `apps/api/`)
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow
```

### `alembic/env.py` (patrón async correcto)

```python
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Importar todos los modelos para que Base.metadata los conozca
from app.models.base import Base
from app.models import (  # noqa: F401 — side-effect imports
    organization, email_account, llm_provider, rules, processed_email, audit_log
)

target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    url = context.config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

run_migrations_online()
```

**Comandos:**
```bash
cd apps/api
alembic upgrade head                          # aplicar todas las migrations
alembic revision --autogenerate -m "msg"      # generar nueva migración
alembic downgrade -1                          # revertir última
```

---

## 9. ORM Models — extractos clave

### `app/models/base.py`

```python
import uuid
from sqlalchemy import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column, MappedColumn

class Base(DeclarativeBase):
    pass

def uuid_pk() -> MappedColumn:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

### `app/models/email_account.py`

```python
from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk

class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[UUID] = uuid_pk()
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[str] = mapped_column(String(255))
    encrypted_credentials: Mapped[str] = mapped_column(String)
    inbox_folder: Mapped[str] = mapped_column(String(255), default="INBOX")
    unclassified_folder: Mapped[str] = mapped_column(String(255), default="Sin_Clasificar")
    drafts_folder: Mapped[str] = mapped_column(String(255), default="Drafts")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_cycle_at: Mapped[datetime | None] = mapped_column(nullable=True)
    llm_provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True
    )

    # Relationship: cargado explícitamente con selectinload en AccountRepository.
    # lazy="noload" para evitar N+1 accidentales.
    llm_provider: Mapped[LLMProvider | None] = relationship(
        "LLMProvider",
        foreign_keys=[llm_provider_id],
        lazy="noload",
    )
```

### `app/models/rules.py`

```python
# IMPORTANTE: DomainRule y KeywordRule aquí son los modelos SQLAlchemy (ORM).
# En packages/core/mailflow_core/classification/rule_engine.py existen dataclasses
# homónimas. Usar alias en imports para evitar colisión:
#
#   from app.models.rules import DomainRule as DbDomainRule, KeywordRule as DbKeywordRule
#   from mailflow_core.classification.rule_engine import (
#       DomainRule as CoreDomainRule, KeywordRule as CoreKeywordRule, AccountConfig,
#   )

from uuid import UUID
from sqlalchemy import ARRAY, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, uuid_pk

class DomainRule(Base):
    __tablename__ = "domain_rules"
    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)

class KeywordRule(Base):
    __tablename__ = "keyword_rules"
    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    match_all: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)

class InternalDomain(Base):
    __tablename__ = "internal_domains"
    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))
```

---

## 10. Repository layer

### `repositories/account.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import cast, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.email_account import EmailAccount
from app.models.rules import DomainRule as DbDomainRule, KeywordRule as DbKeywordRule, InternalDomain
from mailflow_core.classification.rule_engine import (
    AccountConfig,
    DomainRule as CoreDomainRule,
    KeywordRule as CoreKeywordRule,
)


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_accounts_due(self, now: datetime) -> list[EmailAccount]:
        """Cuentas activas donde el ciclo toca según interval_minutes."""
        stmt = select(EmailAccount).where(
            EmailAccount.is_active == True,
            or_(
                EmailAccount.last_cycle_at.is_(None),
                EmailAccount.last_cycle_at + cast(
                    EmailAccount.interval_minutes * text("interval '1 minute'"),
                    Interval
                ) <= now,
            ),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def claim_cycle(self, account_id: UUID, now: datetime) -> bool:
        """Atomic UPDATE: marca last_cycle_at=now solo si el ciclo sigue siendo elegible.
        Devuelve True si esta instancia ganó la carrera; False si otro worker se adelantó.
        Previene la race condition TOCTOU: dos workers no procesan la misma cuenta."""
        stmt = (
            update(EmailAccount)
            .where(
                EmailAccount.id == account_id,
                or_(
                    EmailAccount.last_cycle_at.is_(None),
                    EmailAccount.last_cycle_at + cast(
                        EmailAccount.interval_minutes * text("interval '1 minute'"),
                        Interval
                    ) <= now,
                ),
            )
            .values(last_cycle_at=now)
            .returning(EmailAccount.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one_or_none() is not None

    async def get_full_config(
        self, account_id: UUID
    ) -> tuple[EmailAccount, AccountConfig, LLMProvider | None]:
        """Carga account con todas sus reglas y llm_provider en queries eficientes.
        Devuelve (account_model, account_config_core, llm_provider_model | None).

        IMPORTANTE — colisión de nombres:
          - DbDomainRule / DbKeywordRule → modelos SQLAlchemy (app.models.rules)
          - CoreDomainRule / CoreKeywordRule → dataclasses de packages/core (rule_engine.py)
        """
        # 1. Account + llm_provider (eager load, evita N+1)
        stmt = (
            select(EmailAccount)
            .options(selectinload(EmailAccount.llm_provider))
            .where(EmailAccount.id == account_id)
        )
        account = (await self._session.execute(stmt)).scalar_one()

        # 2. domain_rules ORDER BY priority
        db_domain = list((await self._session.execute(
            select(DbDomainRule)
            .where(DbDomainRule.account_id == account_id)
            .order_by(DbDomainRule.priority)
        )).scalars())

        # 3. keyword_rules ORDER BY priority
        db_kw = list((await self._session.execute(
            select(DbKeywordRule)
            .where(DbKeywordRule.account_id == account_id)
            .order_by(DbKeywordRule.priority)
        )).scalars())

        # 4. internal_domains
        db_int = list((await self._session.execute(
            select(InternalDomain).where(InternalDomain.account_id == account_id)
        )).scalars())

        # 5. Construir AccountConfig de packages/core
        account_config = AccountConfig(
            account_id=str(account_id),
            internal_domains=[d.domain for d in db_int],
            client_domain_rules=[
                CoreDomainRule(domain=r.domain, label=r.label, rule_id=r.rule_id)
                for r in db_domain
            ],
            keyword_rules=[
                CoreKeywordRule(
                    keywords=tuple(r.keywords),
                    label=r.label,
                    rule_id=r.rule_id,
                    match_all=r.match_all,
                )
                for r in db_kw
            ],
        )

        return account, account_config, account.llm_provider
```

### `repositories/cycle.py`

```python
class CycleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_audit_log(self, account_id: UUID, cycle_id: UUID) -> AuditLog:
        """Inserta fila audit_log con finalized_at=NULL (ciclo en curso)."""
        log = AuditLog(account_id=account_id, cycle_id=cycle_id)
        self._session.add(log)
        await self._session.flush()
        return log

    async def finalize_audit_log(
        self, cycle_id: UUID, emails: int, drafts: int, errors: int,
        error_detail: str | None, duration_ms: int,
    ) -> None:
        """Actualiza audit_log con resultados finales y finalized_at=now()."""
        await self._session.execute(
            update(AuditLog)
            .where(AuditLog.cycle_id == cycle_id)
            .values(
                emails_processed=emails,
                drafts_saved=drafts,
                error_count=errors,
                error_detail=error_detail,
                duration_ms=duration_ms,
                finalized_at=datetime.now(tz=timezone.utc),
            )
        )

    async def insert_processed(
        self, account_id: UUID, uid: int, folder: str, uidvalidity: int,
        message_id: str | None, from_email: str, subject: str,
        destination_folder: str, method: str, confidence: float,
        draft_saved: bool, cycle_id: UUID,
    ) -> None:
        """INSERT con ON CONFLICT (account_id, uid, uidvalidity) DO NOTHING.
        Garantiza idempotencia si el worker retrocede y reprocesa."""
        stmt = pg_insert(ProcessedEmail).values(
            account_id=account_id, uid=uid, folder=folder,
            uidvalidity=uidvalidity, message_id=message_id,
            from_email=from_email, subject=subject,
            destination_folder=destination_folder,
            method=method, confidence=confidence,
            draft_saved=draft_saved, cycle_id=cycle_id,
        ).on_conflict_do_nothing(
            index_elements=["account_id", "uid", "uidvalidity"]
        )
        await self._session.execute(stmt)

    async def find_thread_folder(
        self, account_id: UUID, message_id: str
    ) -> str | None:
        """Busca en processed_emails si el message_id fue clasificado antes.
        Retorna destination_folder o None si no existe. Usa INDEX (account_id, message_id)."""
        stmt = (
            select(ProcessedEmail.destination_folder)
            .where(
                ProcessedEmail.account_id == account_id,
                ProcessedEmail.message_id == message_id,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
```

---

## 11. CycleService — orquestación completa

```python
# apps/api/app/services/cycle.py
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.crypto import decrypt
from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.repositories.account import AccountRepository
from app.repositories.cycle import CycleRepository
from mailflow_core.classification.llm_client import LLMClient, LLMConfig
from mailflow_core.classification.rule_engine import AccountConfig, RuleEngine
from mailflow_core.email_parser import EmailParser
from mailflow_core.exceptions import IMAPConnectionError
from mailflow_core.providers.base import EmailData
from mailflow_core.providers.imap_generic import ImapGenericProvider
from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail

log = logging.getLogger("mailflow.cycle")


@dataclass
class CycleResult:
    cycle_id: UUID
    emails_processed: int
    drafts_saved: int
    errors: int


class CycleService:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def run(self, account_id: UUID) -> CycleResult:
        cycle_id = uuid4()
        start = time.monotonic()
        stats = {"emails": 0, "drafts": 0, "errors": 0, "last_error": None}

        # ── 0. Claim cycle — guard TOCTOU atómico ──────────────────────────
        # UPDATE ... WHERE last_cycle_at + interval <= now RETURNING id
        # Si otro worker ya actualizó last_cycle_at, el UPDATE no afecta ninguna fila
        # y claim_cycle() retorna False → abortamos sin hacer nada.
        now = datetime.now(tz=timezone.utc)
        async with self._sf() as session:
            won = await AccountRepository(session).claim_cycle(account_id, now)
        if not won:
            log.info("Cycle for account %s already claimed, skipping", account_id)
            return CycleResult(cycle_id=cycle_id, emails_processed=0, drafts_saved=0, errors=0)

        # ── 1. Crear audit_log ──────────────────────────────────────────────
        async with self._sf() as session:
            await CycleRepository(session).create_audit_log(account_id, cycle_id)
            await session.commit()

        # ── 2. Cargar config (transacción breve, sin IMAP abierto) ──────────
        async with self._sf() as session:
            account, account_config, llm_provider = (
                await AccountRepository(session).get_full_config(account_id)
            )
            # expire_on_commit=False → objetos accesibles tras cerrar sesión
            await session.commit()

        # ── 3. Construir herramientas de dominio ────────────────────────────
        password = decrypt(account.encrypted_credentials, settings.SECRET_KEY)["password"]
        provider = ImapGenericProvider(
            host=account.imap_host,
            port=account.imap_port,
            username=account.username,
            password=password,
            use_ssl=account.use_ssl,
        )
        parser = EmailParser()
        # ADR-007: modelos distintos para clasificación y generación
        classify_client = _build_llm_client(llm_provider, for_generation=False)
        generate_client = _build_llm_client(llm_provider, for_generation=True)
        rule_engine = RuleEngine(account_config, llm_client=classify_client)

        # ── 4. Fetch + loop (sin sesión DB abierta durante IMAP) ────────────
        # Capturamos Exception (no solo IMAPConnectionError) para cubrir también
        # UIDValidityChanged y cualquier error IMAP inesperado.
        # provider.disconnect() al final es seguro incluso si connect() falló
        # porque verifica self._client internamente.
        emails: list[EmailData] = []
        try:
            provider.connect()
            emails = provider.fetch_unprocessed_emails()
        except Exception as exc:
            stats["last_error"] = str(exc)
            stats["errors"] += 1
            log.exception("IMAP fetch failed for account %s: %s", account_id, exc)

        for email_data in emails:
            try:
                await _process_one(
                    email_data, account, cycle_id,
                    provider, parser, rule_engine, generate_client,
                    stats, self._sf,
                )
            except Exception as exc:
                stats["errors"] += 1
                stats["last_error"] = str(exc)
                log.exception("Error processing email uid=%s: %s", email_data.uid, exc)

        provider.disconnect()

        # ── 5. Finalizar audit_log ──────────────────────────────────────────
        duration_ms = int((time.monotonic() - start) * 1000)
        async with self._sf() as session:
            await CycleRepository(session).finalize_audit_log(
                cycle_id,
                emails=stats["emails"],
                drafts=stats["drafts"],
                errors=stats["errors"],
                error_detail=stats["last_error"],
                duration_ms=duration_ms,
            )
            await session.commit()

        return CycleResult(cycle_id, stats["emails"], stats["drafts"], stats["errors"])


async def _process_one(
    email_data: EmailData,
    account: EmailAccount,
    cycle_id: UUID,
    provider: ImapGenericProvider,
    parser: EmailParser,
    rule_engine: RuleEngine,
    generate_client: LLMClient | None,
    stats: dict,
    sf: async_sessionmaker,
) -> None:
    """Procesa un email individual. Lanza excepción si falla; el caller la captura."""

    # a. Parse → ParsedEmail
    parsed: ParsedEmail = parser.parse(email_data)

    # b. Thread-inheritance check (lectura rápida de DB, sesión independiente)
    thread_folder: str | None = None
    if parsed.in_reply_to:
        async with sf() as session:
            thread_folder = await CycleRepository(session).find_thread_folder(
                account.id, parsed.in_reply_to
            )

    # c. Clasificar
    if thread_folder:
        # method="thread" es el único valor Literal válido para este caso
        result = ClassificationResult(label=thread_folder, confidence=0.95, method="thread")
    else:
        result = rule_engine.classify(parsed)

    destination = result.label if result.label != "unclassified" else account.unclassified_folder

    # d. Marcar en IMAP ANTES de mover.
    # INVARIANTE de orden: mark_as_processed(uid) DEBE ir antes de move_email(uid).
    # Tras move_email, el UID ya no existe en INBOX y cualquier operación sobre él falla.
    provider.mark_as_processed(email_data.uid)

    # e. Mover a carpeta destino
    provider.move_email(email_data.uid, destination)

    # f. Generar borrador (solo para emails no internos y clasificados)
    draft_saved = False
    if result.method != "domain_internal" and result.label != "unclassified" and generate_client:
        draft_request = DraftRequest(
            in_reply_to_uid=str(email_data.uid),
            # _drafts_folder es privado pero de nuestra propia clase.
            # Tech debt (Fase 2a): Fase 2b añadirá ImapGenericProvider.drafts_folder property.
            folder=provider._drafts_folder,
            subject=parsed.subject_normalized,
            body_text=parsed.body_text,
            body_html=parsed.body_html or None,
            classification=result,
        )
        # generate_draft(original_email: ParsedEmail, request: DraftRequest) → str
        # Devuelve el cuerpo del email como texto plano. Necesitamos construir
        # el envelope RFC2822 completo antes de llamar a provider.save_draft().
        draft_text: str = generate_client.generate_draft(parsed, draft_request)
        if draft_text:
            draft_bytes = _build_draft_bytes(
                subject=parsed.subject_normalized,
                from_email=account.username,
                to_email=email_data.from_email,
                body_text=draft_text,
                in_reply_to=email_data.message_id,
            )
            draft_saved = provider.save_draft(draft_bytes)

    # g. Persistir en DB (commit por email → idempotencia ON CONFLICT DO NOTHING)
    async with sf() as session:
        await CycleRepository(session).insert_processed(
            account_id=account.id,
            uid=email_data.uid,
            folder=account.inbox_folder,
            # _uidvalidity es privado pero de nuestra propia clase.
            # Tech debt (Fase 2a): Fase 2b añadirá ImapGenericProvider.get_uidvalidity(folder).
            uidvalidity=provider._uidvalidity.get(account.inbox_folder, 0),
            message_id=email_data.message_id,
            from_email=email_data.from_email,
            subject=email_data.subject,
            destination_folder=destination,
            method=result.method,
            confidence=result.confidence,
            draft_saved=draft_saved,
            cycle_id=cycle_id,
        )
        await session.commit()

    stats["emails"] += 1
    if draft_saved:
        stats["drafts"] += 1


def _build_llm_client(
    llm_provider: LLMProvider | None,
    *,
    for_generation: bool,
) -> LLMClient | None:
    """Construye LLMClient con LLMConfig descifrado del provider.
    Retorna None si no hay provider o está inactivo.

    Args:
        llm_provider: modelo ORM LLMProvider cargado de DB.
        for_generation: True → usa default_generation_model;
                        False → usa default_classification_model.
    """
    if llm_provider is None or not llm_provider.is_active:
        return None

    api_key: str | None = None
    if llm_provider.encrypted_api_key:
        api_key = decrypt(llm_provider.encrypted_api_key, settings.SECRET_KEY)["api_key"]

    model_id = (
        llm_provider.default_generation_model
        if for_generation
        else llm_provider.default_classification_model
    )
    return LLMClient(LLMConfig(
        model_id=model_id,
        api_base=llm_provider.base_url,
        api_key=api_key,
    ))


def _build_draft_bytes(
    subject: str,
    from_email: str,
    to_email: str,
    body_text: str,
    in_reply_to: str | None = None,
) -> bytes:
    """Construye un email RFC2822 mínimo listo para guardar como borrador IMAP.

    generate_draft() devuelve solo el cuerpo del email (str).
    provider.save_draft() necesita bytes RFC2822 completos (headers + body).
    Esta función hace la conversión.
    """
    msg = MIMEMultipart("alternative")
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["Subject"] = reply_subject
    msg["From"] = from_email
    msg["To"] = to_email
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return msg.as_bytes()
```

---

## 12. Worker ARQ

### `apps/worker/worker/main.py`

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.database import async_session_factory
from app.repositories.account import AccountRepository
from app.services.cycle import CycleService

log = logging.getLogger("mailflow.worker")


async def on_startup(ctx: dict) -> None:
    ctx["session_factory"] = async_session_factory


async def process_account_cycle(ctx: dict, account_id: str) -> dict:
    """Job ARQ principal. account_id como str para serialización Redis."""
    service = CycleService(ctx["session_factory"])
    result = await service.run(UUID(account_id))
    return {
        "account_id": account_id,
        "cycle_id": str(result.cycle_id),
        "emails_processed": result.emails_processed,
        "drafts_saved": result.drafts_saved,
        "errors": result.errors,
    }


async def schedule_cycles(ctx: dict) -> None:
    """Cron cada 5 min: encola ciclos para cuentas que toca procesar."""
    now = datetime.now(tz=timezone.utc)
    async with ctx["session_factory"]() as session:
        accounts = await AccountRepository(session).get_accounts_due(now)

    redis = ctx["redis"]
    for account in accounts:
        await redis.enqueue_job(
            "process_account_cycle",
            str(account.id),
            _job_id=f"cycle-{account.id}",  # deduplicación ARQ: no encola si ya está
        )
    log.info("Scheduled %d account cycles", len(accounts))


class WorkerSettings:
    functions = [process_account_cycle]
    cron_jobs = [
        cron(schedule_cycles, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55})
    ]
    on_startup = on_startup
    queue_name = "mailflow:default"
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
```

### `apps/worker/pyproject.toml` (cambio)

```toml
[project]
name = "mailflow-worker"
dependencies = [
    "arq>=0.26",
    "redis>=5.2",
    "mailflow-core",
    "mailflow-api",        # ← añadir: worker importa services/repositories
]
```

---

## 13. Testing strategy

### Unit tests — `apps/api/tests/unit/`

| Test | Qué mockea | Qué verifica |
|------|-----------|-------------|
| `test_cycle_service.py` | `AccountRepository`, `CycleRepository`, `ImapGenericProvider`, `LLMClient` | Orden correcto: `mark_as_processed` ANTES que `move_email` |
| `test_cycle_service.py` | `claim_cycle()` retorna `False` | `CycleService.run()` aborta sin procesar ningún email |
| `test_cycle_service.py` | `provider.connect()` lanza `IMAPConnectionError` | Error queda en audit_log; `emails_processed=0` |
| `test_cycle_service.py` | Email con `in_reply_to` en `find_thread_folder` | `method="thread"`, `confidence=0.95` |
| `test_cycle_service.py` | `generate_client.generate_draft()` retorna string no vacío | `provider.save_draft()` recibe `bytes` (no str); `draft_saved=True` |
| `test_crypto.py` | — | `encrypt→decrypt` roundtrip; clave incorrecta lanza `InvalidToken` |
| `test_repositories.py` | Postgres real (fixture) | `AccountRepository.get_full_config()` construye `AccountConfig` correcto |
| `test_build_draft_bytes.py` | — | `_build_draft_bytes()` produce bytes parseables como `email.message_from_bytes()`; headers `Subject`, `From`, `To`, `In-Reply-To` presentes |

### Integration test — `apps/api/tests/integration/test_full_cycle.py`

```
Requiere: Postgres (Docker) + Greenmail (Docker) + LLM mockeado (respx)

1. Fixture: crear Organization + EmailAccount (credenciales Greenmail) + DomainRule para "external.com"
2. Enviar email via SMTP a test@localhost (remitente: sender@external.com)
3. Llamar CycleService.run(account_id)
4. Assert:
   - processed_emails: 1 registro con destination_folder="Clients/External", method="domain_client"
   - audit_log: finalized_at NOT NULL, emails_processed=1
   - Greenmail: email movido a "Clients/External" (verificar via IMAP)
```

### Config pytest async — `apps/api/pyproject.toml`

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "anyio>=4.0",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Fixture DB para tests de repositories

```python
# apps/api/tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow_test"

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture()
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()   # cada test arranca con DB limpia
```

---

## 14. Comandos de desarrollo

```bash
# Arrancar infraestructura
cd infrastructure && docker compose -f docker-compose.dev.yml up -d postgres redis greenmail

# Crear base de datos de tests (ejecutar una sola vez tras iniciar postgres)
docker compose -f infrastructure/docker-compose.dev.yml exec postgres \
    psql -U mailflow -c "CREATE DATABASE mailflow_test;"

# Migrations
cd apps/api
uv sync --extra dev
alembic upgrade head

# Arrancar worker
cd apps/worker
uv run arq worker.main.WorkerSettings

# Tests unitarios
cd apps/api
uv run pytest tests/unit/ -q

# Tests integración (requiere Docker corriendo)
uv run pytest tests/integration/ -v -m integration

# Lint
uv run ruff check app/ tests/
uv run ruff format app/ tests/
```

---

## 15. Deuda técnica explícita (Fase 2a → 2b)

| Item | Descripción | Solución en Fase 2b |
|------|-------------|---------------------|
| `provider._uidvalidity` | Acceso a atributo privado de clase propia | Añadir `ImapGenericProvider.get_uidvalidity(folder: str) -> int` |
| `provider._drafts_folder` | Idem | Añadir `ImapGenericProvider.drafts_folder: str` property |
| Backoff IMAP | Sin reintentos en `connect()`/`move_email()` | Exponential backoff + circuit breaker cuando API exponga config |
| LLM circuit breaker | Sin fallback si LLM falla más de N veces | Circuit breaker por account en Fase 2b |

---

## 16. Tablas diferidas (Fase 2b+)

| Tabla | Fase |
|-------|------|
| `users` | 2b (Better Auth gestiona login) |
| `memberships` | 2b (API crea/gestiona) |
| `writing_styles` | 3 (personalización de estilo) |
| `templates` | 3 (biblioteca de plantillas) |
| `corrections` | 3 (feedback loop) |
| `folder_state` | Opcional — optimización de sync incremental |
| `drafts_meta` | 3 (tracking de borradores generados) |
