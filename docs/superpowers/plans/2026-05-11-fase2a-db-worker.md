# Fase 2a — DB Layer + Worker Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la capa de persistencia (Postgres + SQLAlchemy + Alembic) y el worker ARQ que ejecuta el loop completo de clasificación y borradores cada 5 minutos.

**Architecture:** Service + Repository pattern. `CycleService` orquesta el loop usando `AccountRepository` y `CycleRepository` para DB. El worker ARQ es un thin wrapper que llama `CycleService.run()`. Las credenciales IMAP y LLM se cifran con Fernet.

**Tech Stack:** SQLAlchemy 2.0 asyncio + asyncpg + Alembic + ARQ + cryptography (Fernet) + pytest-asyncio 0.24

**Spec:** `docs/superpowers/specs/2026-05-10-fase2a-db-worker-design.md`

**Branch:** Trabajar en `feat/fase2a-db-worker` (crear desde `main`).

---

## Mapa de archivos

```
CREAR:
apps/api/
  alembic.ini
  alembic/env.py
  alembic/script.py.mako              ← generado por alembic init
  alembic/versions/001_initial_schema.py
  app/config.py
  app/crypto.py
  app/database.py
  app/models/__init__.py
  app/models/base.py
  app/models/organization.py
  app/models/llm_provider.py
  app/models/email_account.py
  app/models/rules.py
  app/models/processed_email.py
  app/models/audit_log.py
  app/repositories/__init__.py
  app/repositories/account.py
  app/repositories/cycle.py
  app/services/__init__.py
  app/services/cycle.py
  tests/__init__.py
  tests/conftest.py
  tests/unit/__init__.py
  tests/unit/test_crypto.py
  tests/unit/test_models.py
  tests/unit/test_account_repository.py
  tests/unit/test_cycle_repository.py
  tests/unit/test_cycle_helpers.py
  tests/unit/test_cycle_service.py
  tests/integration/__init__.py
  tests/integration/test_full_cycle.py

MODIFICAR:
  pyproject.toml (root)               ← añadir asyncio_mode = "auto"
  apps/api/pyproject.toml             ← añadir cryptography, anyio
  apps/worker/pyproject.toml          ← añadir mailflow-api
  apps/worker/worker/main.py          ← reemplazar stub
```

---

## Task 1: Dependencias + Config + Crypto

**Files:**
- Modify: `pyproject.toml` (root, añadir `asyncio_mode`)
- Modify: `apps/api/pyproject.toml` (añadir `cryptography`, `anyio`)
- Modify: `apps/worker/pyproject.toml` (añadir `mailflow-api`)
- Create: `apps/api/app/config.py`
- Create: `apps/api/app/crypto.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/unit/__init__.py`
- Test: `apps/api/tests/unit/test_crypto.py`

- [ ] **Step 1: Crear rama de trabajo**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo"
git checkout -b feat/fase2a-db-worker
```

Expected: `Switched to a new branch 'feat/fase2a-db-worker'`

- [ ] **Step 2: Actualizar `pyproject.toml` (root) — añadir asyncio_mode**

En `pyproject.toml` (raíz del repo), añadir a `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["packages/core/tests", "apps/api/tests"]
asyncio_mode = "auto"
addopts = "--cov=mailflow_core --cov-fail-under=80"
```

- [ ] **Step 3: Actualizar `apps/api/pyproject.toml` — añadir deps**

```toml
[project]
name = "mailflow-api"
version = "0.1.0"
description = "MailFlow Core API — FastAPI backend"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.14",
    "asyncpg>=0.30",
    "aiosqlite>=0.20",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "cryptography>=43.0",
    "litellm>=1.55",
    "arq>=0.26",
    "redis>=5.2",
    "imapclient>=3.0",
    "msal>=1.31",
    "google-auth>=2.38",
    "google-auth-oauthlib>=1.2",
    "email-reply-parser>=0.5",
    "beautifulsoup4>=4.12",
    "mailflow-core",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "anyio>=4.0",
    "httpx>=0.28",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 4: Actualizar `apps/worker/pyproject.toml`**

```toml
[project]
name = "mailflow-worker"
version = "0.1.0"
description = "MailFlow Worker — ARQ async job runner"
requires-python = ">=3.13"
dependencies = [
    "arq>=0.26",
    "redis>=5.2",
    "mailflow-core",
    "mailflow-api",
]
```

- [ ] **Step 5: Sincronizar dependencias**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo"
uv sync
```

Expected: sin errores.

- [ ] **Step 6: Escribir test fallido para crypto**

Crear `apps/api/tests/__init__.py` (vacío) y `apps/api/tests/unit/__init__.py` (vacío).

Crear `apps/api/tests/unit/test_crypto.py`:

```python
"""Tests para app.crypto — encrypt/decrypt con Fernet."""
import pytest
from cryptography.fernet import InvalidToken


def test_encrypt_decrypt_roundtrip():
    from app.crypto import decrypt, encrypt
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    data = {"password": "secret123", "extra": 42}

    token = encrypt(data, key)
    assert isinstance(token, str)
    assert token != str(data)

    recovered = decrypt(token, key)
    assert recovered == data


def test_decrypt_wrong_key_raises():
    from app.crypto import decrypt, encrypt
    from cryptography.fernet import Fernet

    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    token = encrypt({"x": 1}, key1)

    with pytest.raises(InvalidToken):
        decrypt(token, key2)


def test_encrypt_returns_different_tokens_each_call():
    """Fernet usa nonce aleatorio — mismo input produce tokens distintos."""
    from app.crypto import encrypt
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    data = {"password": "pw"}
    assert encrypt(data, key) != encrypt(data, key)
```

- [ ] **Step 7: Ejecutar test — verificar que falla**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_crypto.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.crypto'`

- [ ] **Step 8: Crear `apps/api/app/config.py`**

```python
"""Configuración de la aplicación vía variables de entorno."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

- [ ] **Step 9: Crear `apps/api/app/crypto.py`**

```python
"""Cifrado simétrico con Fernet para credenciales almacenadas en DB."""
from __future__ import annotations

import json

from cryptography.fernet import Fernet


def encrypt(data: dict, key: str) -> str:
    """Serializa dict a JSON, cifra con Fernet, devuelve token string."""
    return Fernet(key.encode()).encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str, key: str) -> dict:
    """Descifra token Fernet, deserializa JSON, devuelve dict.

    Raises:
        cryptography.fernet.InvalidToken: si la clave es incorrecta o el token está corrupto.
    """
    return json.loads(Fernet(key.encode()).decrypt(token.encode()))
```

- [ ] **Step 10: Ejecutar test — verificar que pasa**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_crypto.py -v
```

Expected:
```
tests/unit/test_crypto.py::test_encrypt_decrypt_roundtrip PASSED
tests/unit/test_crypto.py::test_decrypt_wrong_key_raises PASSED
tests/unit/test_crypto.py::test_encrypt_returns_different_tokens_each_call PASSED
3 passed
```

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml apps/api/pyproject.toml apps/worker/pyproject.toml \
        apps/api/app/config.py apps/api/app/crypto.py \
        apps/api/tests/__init__.py apps/api/tests/unit/__init__.py \
        apps/api/tests/unit/test_crypto.py
git commit -m "feat: config + crypto module (Fernet encrypt/decrypt)"
```

---

## Task 2: ORM Models (8 tablas)

**Files:**
- Create: `apps/api/app/models/base.py`
- Create: `apps/api/app/models/organization.py`
- Create: `apps/api/app/models/llm_provider.py`
- Create: `apps/api/app/models/email_account.py`
- Create: `apps/api/app/models/rules.py`
- Create: `apps/api/app/models/processed_email.py`
- Create: `apps/api/app/models/audit_log.py`
- Create: `apps/api/app/models/__init__.py`
- Test: `apps/api/tests/unit/test_models.py`

- [ ] **Step 1: Escribir test fallido para modelos**

Crear `apps/api/tests/unit/test_models.py`:

```python
"""Smoke tests: todos los modelos importan y están registrados en Base.metadata."""


def test_all_tables_registered():
    from app.models import Base

    expected = {
        "organizations",
        "llm_providers",
        "email_accounts",
        "domain_rules",
        "keyword_rules",
        "internal_domains",
        "processed_emails",
        "audit_log",
    }
    assert expected == set(Base.metadata.tables.keys())


def test_email_account_has_llm_provider_relationship():
    from app.models.email_account import EmailAccount

    assert hasattr(EmailAccount, "llm_provider")


def test_keyword_rule_has_array_column():
    from app.models.rules import KeywordRule
    from sqlalchemy.dialects.postgresql import ARRAY

    col = KeywordRule.__table__.c["keywords"]
    assert isinstance(col.type, ARRAY)
```

- [ ] **Step 2: Ejecutar test — verificar que falla**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Crear `apps/api/app/models/base.py`**

```python
"""Base declarativa + helper uuid_pk para todos los modelos SQLAlchemy."""
from __future__ import annotations

import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> MappedColumn:
    """Primary key UUID generado en Python (no en DB) para consistencia."""
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

- [ ] **Step 4: Crear `apps/api/app/models/organization.py`**

```python
"""Modelo Organization — tenant raíz del sistema."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk
from uuid import UUID


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Crear `apps/api/app/models/llm_provider.py`**

```python
"""Modelo LLMProvider — configuración de proveedor LLM por organización."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[UUID] = uuid_pk()
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))  # 'ollama'|'openai'|'anthropic'|'custom'
    base_url: Mapped[str] = mapped_column(String(500))
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    default_classification_model: Mapped[str] = mapped_column(String(200))
    default_generation_model: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 6: Crear `apps/api/app/models/email_account.py`**

```python
"""Modelo EmailAccount — cuenta de email gestionada por MailFlow."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[UUID] = uuid_pk()
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    provider_type: Mapped[str] = mapped_column(String(20), default="imap")
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
    last_cycle_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    llm_provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Nunca auto-loaded; usar selectinload explícito en AccountRepository.get_full_config
    llm_provider: Mapped["LLMProvider | None"] = relationship(
        "LLMProvider",
        foreign_keys=[llm_provider_id],
        lazy="noload",
    )
```

- [ ] **Step 7: Crear `apps/api/app/models/rules.py`**

```python
"""Modelos DomainRule, KeywordRule, InternalDomain.

IMPORTANTE — colisión de nombres:
  Estos son los modelos SQLAlchemy (ORM).
  En packages/core/mailflow_core/classification/rule_engine.py existen
  dataclasses homónimas. Importar con alias:
    from app.models.rules import DomainRule as DbDomainRule
    from mailflow_core.classification.rule_engine import DomainRule as CoreDomainRule
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class DomainRule(Base):
    __tablename__ = "domain_rules"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    domain: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class KeywordRule(Base):
    __tablename__ = "keyword_rules"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    match_all: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class InternalDomain(Base):
    __tablename__ = "internal_domains"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    domain: Mapped[str] = mapped_column(String(255))
```

- [ ] **Step 8: Crear `apps/api/app/models/processed_email.py`**

```python
"""Modelo ProcessedEmail — registro idempotente de cada email procesado."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"
    __table_args__ = (
        UniqueConstraint("account_id", "uid", "uidvalidity", name="uq_processed_email"),
        Index("ix_processed_email_msg_id", "account_id", "message_id"),
    )

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    uid: Mapped[int] = mapped_column(BigInteger)
    folder: Mapped[str] = mapped_column(String(255))
    uidvalidity: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_email: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String, default="")
    destination_folder: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)
    draft_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("audit_log.cycle_id"))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 9: Crear `apps/api/app/models/audit_log.py`**

```python
"""Modelo AuditLog — registro de cada ciclo de procesamiento."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    cycle_id: Mapped[UUID] = mapped_column(unique=True)
    emails_processed: Mapped[int] = mapped_column(Integer, default=0)
    drafts_saved: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 10: Crear `apps/api/app/models/__init__.py`**

```python
"""Re-exports para que Alembic pueda descubrir todos los modelos via Base.metadata."""
from app.models.base import Base
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.models.organization import Organization
from app.models.processed_email import ProcessedEmail
from app.models.rules import DomainRule, InternalDomain, KeywordRule

__all__ = [
    "Base",
    "AuditLog",
    "DomainRule",
    "EmailAccount",
    "InternalDomain",
    "KeywordRule",
    "LLMProvider",
    "Organization",
    "ProcessedEmail",
]
```

- [ ] **Step 11: Ejecutar test — verificar que pasa**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_models.py -v
```

Expected:
```
tests/unit/test_models.py::test_all_tables_registered PASSED
tests/unit/test_models.py::test_email_account_has_llm_provider_relationship PASSED
tests/unit/test_models.py::test_keyword_rule_has_array_column PASSED
3 passed
```

- [ ] **Step 12: Commit**

```bash
git add apps/api/app/models/
git add apps/api/tests/unit/test_models.py
git commit -m "feat: ORM models — 8 tablas SQLAlchemy 2.0"
```

---

## Task 3: Database + Alembic

**Files:**
- Create: `apps/api/app/database.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/001_initial_schema.py`

**Prerrequisito:** Docker con Postgres corriendo:
```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/infrastructure"
docker compose -f docker-compose.dev.yml up -d postgres
```

- [ ] **Step 1: Crear `apps/api/app/database.py`**

```python
"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Dependency injection para FastAPI (Fase 2b)."""
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 2: Inicializar Alembic**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run alembic init alembic
```

Expected: crea `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 3: Reemplazar `apps/api/alembic.ini`**

Abrir el `alembic.ini` generado y reemplazar la línea `sqlalchemy.url`:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow
```

(Dejar el resto del archivo tal como lo generó `alembic init`.)

- [ ] **Step 4: Reemplazar `apps/api/alembic/env.py`**

```python
"""Alembic env.py — configurado para SQLAlchemy async + autodescubrimiento de modelos."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Importar todos los modelos para registrarlos en Base.metadata
from app.models import Base  # noqa: F401 — side-effect: registra todos los modelos

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
```

- [ ] **Step 5: Crear `apps/api/alembic/versions/001_initial_schema.py`**

```python
"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    # 2. llm_providers (referencia organizations)
    op.create_table(
        "llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("encrypted_api_key", sa.String, nullable=True),
        sa.Column("default_classification_model", sa.String(200), nullable=False),
        sa.Column("default_generation_model", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3. email_accounts (referencia organizations + llm_providers)
    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_type", sa.String(20), nullable=False, server_default="imap"),
        sa.Column("imap_host", sa.String(255), nullable=False),
        sa.Column("imap_port", sa.Integer, nullable=False, server_default="993"),
        sa.Column("use_ssl", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("encrypted_credentials", sa.String, nullable=False),
        sa.Column("inbox_folder", sa.String(255), nullable=False, server_default="INBOX"),
        sa.Column(
            "unclassified_folder",
            sa.String(255),
            nullable=False,
            server_default="Sin_Clasificar",
        ),
        sa.Column("drafts_folder", sa.String(255), nullable=False, server_default="Drafts"),
        sa.Column("interval_minutes", sa.Integer, nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_cycle_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "llm_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_providers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 4. domain_rules
    op.create_table(
        "domain_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
    )

    # 5. keyword_rules
    op.create_table(
        "keyword_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keywords", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("match_all", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
    )

    # 6. internal_domains
    op.create_table(
        "internal_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(255), nullable=False),
    )

    # 7. audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("emails_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("drafts_saved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_detail", sa.String, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 8. processed_emails (referencia email_accounts + audit_log.cycle_id)
    op.create_table(
        "processed_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uid", sa.BigInteger, nullable=False),
        sa.Column("folder", sa.String(255), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.String(500), nullable=True),
        sa.Column("from_email", sa.String(500), nullable=False),
        sa.Column("subject", sa.String, nullable=False, server_default=""),
        sa.Column("destination_folder", sa.String(255), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("draft_saved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_log.cycle_id"),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "account_id", "uid", "uidvalidity", name="uq_processed_email"
        ),
    )
    op.create_index(
        "ix_processed_email_msg_id",
        "processed_emails",
        ["account_id", "message_id"],
    )


def downgrade() -> None:
    op.drop_table("processed_emails")
    op.drop_table("audit_log")
    op.drop_table("internal_domains")
    op.drop_table("keyword_rules")
    op.drop_table("domain_rules")
    op.drop_table("email_accounts")
    op.drop_table("llm_providers")
    op.drop_table("organizations")
```

- [ ] **Step 6: Aplicar migración**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run alembic upgrade head
```

Expected:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, initial schema
```

- [ ] **Step 7: Verificar tablas en Postgres**

```bash
docker compose -f infrastructure/docker-compose.dev.yml exec postgres \
    psql -U mailflow -c "\dt"
```

Expected: 8 tablas listadas (organizations, llm_providers, email_accounts, etc.)

- [ ] **Step 8: Crear base de datos de tests**

```bash
docker compose -f "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/infrastructure/docker-compose.dev.yml" \
    exec postgres psql -U mailflow -c "CREATE DATABASE mailflow_test;"
```

Expected: `CREATE DATABASE`

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/database.py apps/api/alembic.ini apps/api/alembic/
git commit -m "feat: database setup + Alembic migration (8 tablas)"
```

---

## Task 4: Test DB fixtures (conftest.py)

**Files:**
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/integration/__init__.py`

- [ ] **Step 1: Crear `apps/api/tests/integration/__init__.py`** (vacío)

- [ ] **Step 2: Crear `apps/api/tests/conftest.py`**

```python
"""Fixtures compartidas para tests de apps/api.

Para tests de repositorios se necesita Postgres corriendo (Docker).
Arrancar con:
  docker compose -f infrastructure/docker-compose.dev.yml up -d postgres
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow_test"


@pytest.fixture(scope="session")
async def db_engine():
    """Engine de test: crea todas las tablas al inicio, las borra al final."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def session(db_engine) -> AsyncSession:
    """Sesión de test con rollback automático — cada test arranca con DB limpia."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture()
def session_factory(db_engine):
    """async_sessionmaker real apuntando a mailflow_test."""
    return async_sessionmaker(db_engine, expire_on_commit=False)
```

- [ ] **Step 3: Verificar fixture importa correctamente**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/ --collect-only -q 2>&1 | head -20
```

Expected: sin errores de importación.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/conftest.py apps/api/tests/integration/__init__.py
git commit -m "test: fixtures DB para tests de repositorios (session, session_factory)"
```

---

## Task 5: AccountRepository

**Files:**
- Create: `apps/api/app/repositories/__init__.py`
- Create: `apps/api/app/repositories/account.py`
- Test: `apps/api/tests/unit/test_account_repository.py`

- [ ] **Step 1: Escribir tests fallidos**

Crear `apps/api/tests/unit/test_account_repository.py`:

```python
"""Tests de AccountRepository con Postgres real.

Requiere: docker compose up -d postgres
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.organization import Organization
from app.models.email_account import EmailAccount
from app.models.rules import DomainRule as DbDomainRule, KeywordRule as DbKeywordRule, InternalDomain
from app.repositories.account import AccountRepository
from mailflow_core.classification.rule_engine import AccountConfig


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
async def org(session):
    o = Organization(name="Test Org", slug=f"test-{uuid4().hex[:8]}")
    session.add(o)
    await session.commit()
    return o


@pytest.fixture()
async def account(session, org):
    from app.crypto import encrypt
    acc = EmailAccount(
        org_id=org.id,
        imap_host="localhost",
        imap_port=1143,
        use_ssl=False,
        username="test",
        encrypted_credentials=encrypt({"password": "pw"}, "test-key-32-bytes-padded-here!"),
        interval_minutes=5,
    )
    session.add(acc)
    await session.commit()
    return acc


# ── Tests get_accounts_due ───────────────────────────────────────────────────

async def test_get_accounts_due_includes_never_run(session, account):
    repo = AccountRepository(session)
    now = datetime.now(tz=timezone.utc)
    result = await repo.get_accounts_due(now)
    ids = [a.id for a in result]
    assert account.id in ids


async def test_get_accounts_due_includes_overdue(session, account):
    # last_cycle_at hace 10 min, interval=5 → debe estar en la lista
    account.last_cycle_at = datetime.now(tz=timezone.utc) - timedelta(minutes=10)
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id in [a.id for a in result]


async def test_get_accounts_due_excludes_recent(session, account):
    # last_cycle_at hace 2 min, interval=5 → NO debe estar
    account.last_cycle_at = datetime.now(tz=timezone.utc) - timedelta(minutes=2)
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id not in [a.id for a in result]


async def test_get_accounts_due_excludes_inactive(session, account):
    account.is_active = False
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id not in [a.id for a in result]


# ── Tests claim_cycle ────────────────────────────────────────────────────────

async def test_claim_cycle_returns_true_first_call(session, account):
    repo = AccountRepository(session)
    now = datetime.now(tz=timezone.utc)
    won = await repo.claim_cycle(account.id, now)
    assert won is True


async def test_claim_cycle_returns_false_second_call(session_factory, account):
    """Dos workers intentan claim al mismo tiempo → solo uno gana."""
    now = datetime.now(tz=timezone.utc)
    async with session_factory() as s1:
        won1 = await AccountRepository(s1).claim_cycle(account.id, now)
    async with session_factory() as s2:
        # last_cycle_at ya fue marcado por s1 → s2 no gana
        won2 = await AccountRepository(s2).claim_cycle(account.id, now)
    assert won1 is True
    assert won2 is False


# ── Tests get_full_config ────────────────────────────────────────────────────

async def test_get_full_config_builds_account_config(session, account):
    # Insertar reglas
    session.add(DbDomainRule(
        account_id=account.id,
        domain="client.com", label="Clients/Client", rule_id="r1", priority=0,
    ))
    session.add(DbKeywordRule(
        account_id=account.id,
        keywords=["urgent", "ASAP"], label="Urgent", rule_id="r2", match_all=False, priority=1,
    ))
    session.add(InternalDomain(account_id=account.id, domain="company.com"))
    await session.commit()

    repo = AccountRepository(session)
    acc_model, config, llm_prov = await repo.get_full_config(account.id)

    assert isinstance(config, AccountConfig)
    assert config.account_id == str(account.id)
    assert "company.com" in config.internal_domains
    assert len(config.client_domain_rules) == 1
    assert config.client_domain_rules[0].domain == "client.com"
    assert len(config.keyword_rules) == 1
    assert config.keyword_rules[0].keywords == ("urgent", "ASAP")
    assert llm_prov is None  # no llm_provider configurado
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_account_repository.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.repositories'`

- [ ] **Step 3: Crear `apps/api/app/repositories/__init__.py`** (vacío)

- [ ] **Step 4: Crear `apps/api/app/repositories/account.py`**

```python
"""AccountRepository — consultas de cuentas de email y config completa."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.models.rules import DomainRule as DbDomainRule, InternalDomain, KeywordRule as DbKeywordRule
from mailflow_core.classification.rule_engine import (
    AccountConfig,
    DomainRule as CoreDomainRule,
    KeywordRule as CoreKeywordRule,
)


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _due_condition(self, now: datetime):
        """WHERE clause compartida: cuenta activa cuyo intervalo ya venció."""
        interval_expr = EmailAccount.interval_minutes * text("INTERVAL '1 minute'")
        return or_(
            EmailAccount.last_cycle_at.is_(None),
            EmailAccount.last_cycle_at + interval_expr <= now,
        )

    async def get_accounts_due(self, now: datetime) -> list[EmailAccount]:
        """Retorna cuentas activas cuyo ciclo toca según interval_minutes."""
        stmt = select(EmailAccount).where(
            EmailAccount.is_active.is_(True),
            self._due_condition(now),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def claim_cycle(self, account_id: UUID, now: datetime) -> bool:
        """Atomic UPDATE: marca last_cycle_at=now solo si el ciclo sigue elegible.

        Retorna True si esta instancia ganó la carrera; False si otro worker
        se adelantó (TOCTOU guard).
        """
        interval_expr = EmailAccount.interval_minutes * text("INTERVAL '1 minute'")
        stmt = (
            update(EmailAccount)
            .where(
                EmailAccount.id == account_id,
                EmailAccount.is_active.is_(True),
                or_(
                    EmailAccount.last_cycle_at.is_(None),
                    EmailAccount.last_cycle_at + interval_expr <= now,
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
        """Carga account + reglas + llm_provider en queries eficientes.

        COLISIÓN DE NOMBRES: DbDomainRule/DbKeywordRule = modelos SQLAlchemy.
        CoreDomainRule/CoreKeywordRule = dataclasses de packages/core.
        """
        # 1. Account + llm_provider (eager load con selectinload)
        stmt = (
            select(EmailAccount)
            .options(selectinload(EmailAccount.llm_provider))
            .where(EmailAccount.id == account_id)
        )
        account = (await self._session.execute(stmt)).scalar_one()

        # 2. domain_rules ORDER BY priority ASC
        db_domain = list(
            (
                await self._session.execute(
                    select(DbDomainRule)
                    .where(DbDomainRule.account_id == account_id)
                    .order_by(DbDomainRule.priority)
                )
            ).scalars()
        )

        # 3. keyword_rules ORDER BY priority ASC
        db_kw = list(
            (
                await self._session.execute(
                    select(DbKeywordRule)
                    .where(DbKeywordRule.account_id == account_id)
                    .order_by(DbKeywordRule.priority)
                )
            ).scalars()
        )

        # 4. internal_domains
        db_int = list(
            (
                await self._session.execute(
                    select(InternalDomain).where(InternalDomain.account_id == account_id)
                )
            ).scalars()
        )

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

- [ ] **Step 5: Ejecutar tests — verificar que pasan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_account_repository.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/repositories/ apps/api/tests/unit/test_account_repository.py
git commit -m "feat: AccountRepository (get_accounts_due, claim_cycle, get_full_config)"
```

---

## Task 6: CycleRepository

**Files:**
- Create: `apps/api/app/repositories/cycle.py`
- Test: `apps/api/tests/unit/test_cycle_repository.py`

- [ ] **Step 1: Escribir tests fallidos**

Crear `apps/api/tests/unit/test_cycle_repository.py`:

```python
"""Tests de CycleRepository con Postgres real."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.models.organization import Organization
from app.models.email_account import EmailAccount
from app.models.audit_log import AuditLog
from app.repositories.cycle import CycleRepository
from app.crypto import encrypt


@pytest.fixture()
async def org(session):
    o = Organization(name="Org", slug=f"org-{uuid4().hex[:8]}")
    session.add(o)
    await session.commit()
    return o


@pytest.fixture()
async def account(session, org):
    acc = EmailAccount(
        org_id=org.id,
        imap_host="localhost",
        imap_port=1143,
        use_ssl=False,
        username="test",
        encrypted_credentials=encrypt({"password": "pw"}, "test-key-32-bytes-padded-here!"),
    )
    session.add(acc)
    await session.commit()
    return acc


async def test_create_audit_log(session, account):
    repo = CycleRepository(session)
    cycle_id = uuid4()
    log = await repo.create_audit_log(account.id, cycle_id)
    await session.commit()

    assert log.cycle_id == cycle_id
    assert log.account_id == account.id
    assert log.finalized_at is None
    assert log.emails_processed == 0


async def test_finalize_audit_log(session, account):
    cycle_id = uuid4()
    repo = CycleRepository(session)
    await repo.create_audit_log(account.id, cycle_id)
    await session.commit()

    await repo.finalize_audit_log(
        cycle_id, emails=3, drafts=1, errors=0,
        error_detail=None, duration_ms=1500,
    )
    await session.commit()

    from sqlalchemy import select
    log = (
        await session.execute(select(AuditLog).where(AuditLog.cycle_id == cycle_id))
    ).scalar_one()
    assert log.emails_processed == 3
    assert log.drafts_saved == 1
    assert log.duration_ms == 1500
    assert log.finalized_at is not None


async def test_insert_processed_idempotent(session, account):
    cycle_id = uuid4()
    session.add(AuditLog(account_id=account.id, cycle_id=cycle_id))
    await session.commit()

    repo = CycleRepository(session)
    kwargs = dict(
        account_id=account.id, uid=42, folder="INBOX", uidvalidity=1000,
        message_id="<msg@test>", from_email="a@b.com", subject="Hi",
        destination_folder="Clients/B", method="domain_client", confidence=0.95,
        draft_saved=False, cycle_id=cycle_id,
    )
    await repo.insert_processed(**kwargs)
    await session.commit()
    # Segunda inserción idempotente (ON CONFLICT DO NOTHING)
    await repo.insert_processed(**kwargs)
    await session.commit()

    from sqlalchemy import select, func
    from app.models.processed_email import ProcessedEmail
    count = (
        await session.execute(
            select(func.count()).where(ProcessedEmail.account_id == account.id)
        )
    ).scalar_one()
    assert count == 1


async def test_find_thread_folder_returns_folder(session, account):
    cycle_id = uuid4()
    session.add(AuditLog(account_id=account.id, cycle_id=cycle_id))
    await session.commit()

    repo = CycleRepository(session)
    await repo.insert_processed(
        account_id=account.id, uid=10, folder="INBOX", uidvalidity=999,
        message_id="<original@test>", from_email="x@y.com", subject="Orig",
        destination_folder="Clients/X", method="domain_client", confidence=0.95,
        draft_saved=False, cycle_id=cycle_id,
    )
    await session.commit()

    result = await repo.find_thread_folder(account.id, "<original@test>")
    assert result == "Clients/X"


async def test_find_thread_folder_returns_none_if_not_found(session, account):
    repo = CycleRepository(session)
    result = await repo.find_thread_folder(account.id, "<nonexistent@test>")
    assert result is None
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_repository.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.repositories.cycle'`

- [ ] **Step 3: Crear `apps/api/app/repositories/cycle.py`**

```python
"""CycleRepository — audit_log y processed_emails."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.processed_email import ProcessedEmail


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
        self,
        cycle_id: UUID,
        emails: int,
        drafts: int,
        errors: int,
        error_detail: str | None,
        duration_ms: int,
    ) -> None:
        """Actualiza audit_log con resultados finales."""
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
        self,
        account_id: UUID,
        uid: int,
        folder: str,
        uidvalidity: int,
        message_id: str | None,
        from_email: str,
        subject: str,
        destination_folder: str,
        method: str,
        confidence: float,
        draft_saved: bool,
        cycle_id: UUID,
    ) -> None:
        """INSERT con ON CONFLICT (account_id, uid, uidvalidity) DO NOTHING.

        Garantiza idempotencia si el worker reprocesa un email ya visto.
        """
        stmt = (
            pg_insert(ProcessedEmail)
            .values(
                account_id=account_id,
                uid=uid,
                folder=folder,
                uidvalidity=uidvalidity,
                message_id=message_id,
                from_email=from_email,
                subject=subject,
                destination_folder=destination_folder,
                method=method,
                confidence=confidence,
                draft_saved=draft_saved,
                cycle_id=cycle_id,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "uid", "uidvalidity"]
            )
        )
        await self._session.execute(stmt)

    async def find_thread_folder(
        self, account_id: UUID, message_id: str
    ) -> str | None:
        """Busca si message_id fue clasificado antes. Usa INDEX (account_id, message_id)."""
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

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_repository.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/repositories/cycle.py apps/api/tests/unit/test_cycle_repository.py
git commit -m "feat: CycleRepository (audit_log + processed_emails)"
```

---

## Task 7: CycleService helpers

**Files:**
- Create: `apps/api/app/services/__init__.py`
- Create: `apps/api/app/services/cycle.py` (solo helpers por ahora)
- Test: `apps/api/tests/unit/test_cycle_helpers.py`

- [ ] **Step 1: Escribir tests fallidos**

Crear `apps/api/tests/unit/test_cycle_helpers.py`:

```python
"""Tests unitarios para _build_llm_client y _build_draft_bytes."""
from __future__ import annotations

import email as email_module
from unittest.mock import MagicMock, patch


# ── _build_draft_bytes ───────────────────────────────────────────────────────

def test_build_draft_bytes_returns_valid_rfc2822():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="Question about invoice",
        from_email="worker@company.com",
        to_email="sender@client.com",
        body_text="Thank you for your email.",
        in_reply_to="<msg-123@client.com>",
    )

    assert isinstance(result, bytes)
    msg = email_module.message_from_bytes(result)
    assert msg["Subject"] == "Re: Question about invoice"
    assert msg["From"] == "worker@company.com"
    assert msg["To"] == "sender@client.com"
    assert msg["In-Reply-To"] == "<msg-123@client.com>"
    assert msg["References"] == "<msg-123@client.com>"
    payload = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
    assert "Thank you for your email." in payload


def test_build_draft_bytes_no_double_re_prefix():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="Re: Already prefixed",
        from_email="a@b.com",
        to_email="c@d.com",
        body_text="Body",
    )
    msg = email_module.message_from_bytes(result)
    assert msg["Subject"] == "Re: Already prefixed"


def test_build_draft_bytes_no_in_reply_to():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="New topic",
        from_email="a@b.com",
        to_email="c@d.com",
        body_text="Hello",
    )
    msg = email_module.message_from_bytes(result)
    assert msg["In-Reply-To"] is None
    assert msg["References"] is None


# ── _build_llm_client ────────────────────────────────────────────────────────

def test_build_llm_client_returns_none_for_none_provider():
    from app.services.cycle import _build_llm_client

    assert _build_llm_client(None, for_generation=True) is None


def test_build_llm_client_returns_none_for_inactive_provider():
    from app.services.cycle import _build_llm_client

    mock_provider = MagicMock()
    mock_provider.is_active = False
    assert _build_llm_client(mock_provider, for_generation=True) is None


def test_build_llm_client_generation_uses_generation_model():
    from app.services.cycle import _build_llm_client
    from mailflow_core.classification.llm_client import LLMClient

    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = None
    provider.base_url = "http://localhost:11434"
    provider.default_generation_model = "ollama/llama3"
    provider.default_classification_model = "ollama/llama3:8b"

    client = _build_llm_client(provider, for_generation=True)

    assert isinstance(client, LLMClient)
    assert client._config.model_id == "ollama/llama3"
    assert client._config.api_base == "http://localhost:11434"
    assert client._config.api_key is None


def test_build_llm_client_classify_uses_classification_model():
    from app.services.cycle import _build_llm_client
    from mailflow_core.classification.llm_client import LLMClient

    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = None
    provider.base_url = "http://localhost:11434"
    provider.default_generation_model = "ollama/llama3"
    provider.default_classification_model = "ollama/llama3:8b"

    client = _build_llm_client(provider, for_generation=False)

    assert isinstance(client, LLMClient)
    assert client._config.model_id == "ollama/llama3:8b"


def test_build_llm_client_decrypts_api_key():
    from app.services.cycle import _build_llm_client
    from cryptography.fernet import Fernet
    from app.crypto import encrypt

    key = Fernet.generate_key().decode()
    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = encrypt({"api_key": "sk-test-123"}, key)
    provider.base_url = "https://api.openai.com"
    provider.default_generation_model = "gpt-4o"
    provider.default_classification_model = "gpt-4o-mini"

    with patch("app.services.cycle.settings") as mock_settings:
        mock_settings.SECRET_KEY = key
        client = _build_llm_client(provider, for_generation=True)

    assert client._config.api_key == "sk-test-123"
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_helpers.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: Crear `apps/api/app/services/__init__.py`** (vacío)

- [ ] **Step 4: Crear `apps/api/app/services/cycle.py` (helpers únicamente)**

```python
"""CycleService — orquestación del loop de clasificación y borradores.

Este módulo contiene:
  - CycleResult: dataclass con resultado del ciclo
  - CycleService: orquestador principal
  - _process_one: procesa un email individual
  - _build_llm_client: construye LLMClient desde LLMProvider ORM model
  - _build_draft_bytes: convierte body text a email RFC2822 completo
"""
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


def _build_llm_client(
    llm_provider: LLMProvider | None,
    *,
    for_generation: bool,
) -> LLMClient | None:
    """Construye LLMClient con LLMConfig descifrado del provider.

    Args:
        llm_provider: modelo ORM LLMProvider (puede ser None).
        for_generation: True → default_generation_model;
                        False → default_classification_model.

    Returns:
        LLMClient configurado, o None si no hay provider activo.
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
    """Construye email RFC2822 mínimo listo para guardar como borrador IMAP.

    generate_draft() devuelve str (cuerpo del email).
    provider.save_draft() necesita bytes RFC2822 completos (headers + body).
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


# CycleService y _process_one se añaden en Task 8
```

- [ ] **Step 5: Ejecutar tests — verificar que pasan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_helpers.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/ apps/api/tests/unit/test_cycle_helpers.py
git commit -m "feat: CycleService helpers (_build_llm_client, _build_draft_bytes)"
```

---

## Task 8: CycleService.run() + _process_one

**Files:**
- Modify: `apps/api/app/services/cycle.py` (añadir CycleService + _process_one)
- Test: `apps/api/tests/unit/test_cycle_service.py`

- [ ] **Step 1: Escribir tests fallidos**

Crear `apps/api/tests/unit/test_cycle_service.py`:

```python
"""Tests unitarios de CycleService — todo mockeado (sin DB ni IMAP real)."""
from __future__ import annotations

import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

from mailflow_core.classification.rule_engine import AccountConfig
from mailflow_core.providers.base import EmailData
from mailflow_core.types import ClassificationResult

ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_sf(session=None):
    """Mock session factory que siempre devuelve la misma sesión mock."""
    if session is None:
        session = AsyncMock()

    @asynccontextmanager
    async def sf():
        yield session

    return sf


def make_email(uid: int = 42, in_reply_to: str | None = None) -> EmailData:
    return EmailData(
        uid=uid,
        message_id=f"<msg-{uid}@test>",
        subject="Test subject",
        from_email="sender@external.com",
        to_emails=["worker@company.com"],
        body_text="Hello, need help.",
        body_html="",
        in_reply_to=in_reply_to,
    )


def make_account():
    acc = MagicMock()
    acc.id = ACCOUNT_ID
    acc.imap_host = "localhost"
    acc.imap_port = 1143
    acc.use_ssl = False
    acc.username = "test"
    acc.encrypted_credentials = "tok"
    acc.inbox_folder = "INBOX"
    acc.unclassified_folder = "Sin_Clasificar"
    acc.drafts_folder = "Drafts"
    acc.llm_provider = None
    return acc


# ── claim_cycle → False: abort ───────────────────────────────────────────────

@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
async def test_run_aborts_when_claim_cycle_fails(MockCycleRepo, MockAccountRepo):
    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=False)

    from app.services.cycle import CycleService
    result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 0
    assert result.errors == 0
    MockAccountRepo.return_value.claim_cycle.assert_awaited_once()
    MockCycleRepo.return_value.create_audit_log.assert_not_awaited()


# ── IMAP connect falla ───────────────────────────────────────────────────────

@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_imap_connect_failure(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from mailflow_core.exceptions import IMAPConnectionError
    from app.services.cycle import CycleService

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    MockProvider.return_value.connect.side_effect = IMAPConnectionError("timeout")

    result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 0
    assert result.errors == 1
    MockCycleRepo.return_value.finalize_audit_log.assert_awaited_once()


# ── mark_as_processed ANTES de move_email ───────────────────────────────────

@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_mark_before_move(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [make_email(uid=42)]
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value=None)
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    call_order: list[str] = []
    MockProvider.return_value.mark_as_processed.side_effect = lambda uid: call_order.append(f"mark:{uid}")
    MockProvider.return_value.move_email.side_effect = lambda uid, dest: call_order.append(f"move:{uid}")

    with patch("app.services.cycle.decrypt", return_value={"password": "pw"}):
        result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 1
    assert call_order == ["mark:42", "move:42"]


# ── Thread inheritance → method="thread" ────────────────────────────────────

@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_thread_inheritance(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    # Email es reply → in_reply_to presente
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [
        make_email(uid=99, in_reply_to="<original@test>")
    ]
    # find_thread_folder devuelve carpeta previa
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value="Clients/X")
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    await CycleService(make_sf()).run(ACCOUNT_ID)

    # Verificar que insert_processed recibió method="thread"
    call_kwargs = MockCycleRepo.return_value.insert_processed.call_args.kwargs
    assert call_kwargs["method"] == "thread"
    assert call_kwargs["confidence"] == 0.95
    assert call_kwargs["destination_folder"] == "Clients/X"


# ── Draft generation → save_draft recibe bytes ──────────────────────────────

@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client")
async def test_run_draft_bytes_passed_to_save_draft(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    account = make_account()
    # account con domain rule para "external.com" → method=domain_client
    from mailflow_core.classification.rule_engine import AccountConfig, DomainRule as CoreDomainRule
    config = AccountConfig(
        account_id=str(ACCOUNT_ID),
        client_domain_rules=[CoreDomainRule(domain="external.com", label="Clients/Ext", rule_id="r1")],
    )

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(account, config, None)
    )
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [make_email(uid=55)]
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value=None)
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    mock_generate_client = MagicMock()
    mock_generate_client.generate_draft.return_value = "Estimado cliente, gracias por su consulta."
    mock_build.side_effect = [None, mock_generate_client]  # classify=None, generate=mock

    saved_bytes: list = []
    MockProvider.return_value.save_draft.side_effect = lambda b: saved_bytes.append(b) or True

    await CycleService(make_sf()).run(ACCOUNT_ID)

    assert len(saved_bytes) == 1
    assert isinstance(saved_bytes[0], bytes)
    # Verificar que los bytes son un email RFC2822 válido
    import email as email_module
    msg = email_module.message_from_bytes(saved_bytes[0])
    assert "Re:" in msg["Subject"]
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_service.py -v
```

Expected: `ImportError` o `AttributeError` (CycleService no existe aún)

- [ ] **Step 3: Añadir CycleService y _process_one a `apps/api/app/services/cycle.py`**

Añadir al final del archivo (después de `_build_draft_bytes`):

```python
class CycleService:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def run(self, account_id: UUID) -> CycleResult:
        cycle_id = uuid4()
        start = time.monotonic()
        stats: dict = {"emails": 0, "drafts": 0, "errors": 0, "last_error": None}

        # ── 0. Claim cycle — guard TOCTOU atómico ──────────────────────────
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

        # ── 2. Cargar config (sesión breve, sin IMAP) ───────────────────────
        async with self._sf() as session:
            account, account_config, llm_provider = (
                await AccountRepository(session).get_full_config(account_id)
            )
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
                log.exception("Error processing uid=%s: %s", email_data.uid, exc)

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
    """Procesa un email individual. Excepciones propagadas — caller las captura."""

    # a. Parse → ParsedEmail
    parsed: ParsedEmail = parser.parse(email_data)

    # b. Thread-inheritance check
    thread_folder: str | None = None
    if parsed.in_reply_to:
        async with sf() as session:
            thread_folder = await CycleRepository(session).find_thread_folder(
                account.id, parsed.in_reply_to
            )

    # c. Clasificar
    if thread_folder:
        result = ClassificationResult(label=thread_folder, confidence=0.95, method="thread")
    else:
        result = rule_engine.classify(parsed)

    destination = result.label if result.label != "unclassified" else account.unclassified_folder

    # d. INVARIANTE: mark ANTES de move. Tras move, el UID no existe en INBOX.
    provider.mark_as_processed(email_data.uid)
    provider.move_email(email_data.uid, destination)

    # e. Generar borrador (solo emails no-internos y clasificados)
    draft_saved = False
    if result.method != "domain_internal" and result.label != "unclassified" and generate_client:
        draft_request = DraftRequest(
            in_reply_to_uid=str(email_data.uid),
            # _drafts_folder es privado — tech debt Phase 2a (ver spec §15)
            folder=provider._drafts_folder,
            subject=parsed.subject_normalized,
            body_text=parsed.body_text,
            body_html=parsed.body_html or None,
            classification=result,
        )
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

    # f. Persistir en DB (commit por email → idempotencia ON CONFLICT DO NOTHING)
    async with sf() as session:
        await CycleRepository(session).insert_processed(
            account_id=account.id,
            uid=email_data.uid,
            folder=account.inbox_folder,
            # _uidvalidity es privado — tech debt Phase 2a (ver spec §15)
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
```

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_cycle_service.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/cycle.py apps/api/tests/unit/test_cycle_service.py
git commit -m "feat: CycleService.run() + _process_one (loop completo clasificación + borradores)"
```

---

## Task 9: Worker ARQ

**Files:**
- Modify: `apps/worker/worker/main.py` (reemplazar stub)
- Test: `apps/api/tests/unit/test_worker.py`

- [ ] **Step 1: Escribir test fallido**

Crear `apps/api/tests/unit/test_worker.py`:

```python
"""Smoke test del worker ARQ — verifica configuración sin arrancar Redis."""


def test_worker_settings_queue_name():
    from worker.main import WorkerSettings

    assert WorkerSettings.queue_name == "mailflow:default"


def test_worker_settings_has_process_function():
    from worker.main import WorkerSettings, process_account_cycle

    assert process_account_cycle in WorkerSettings.functions


def test_worker_settings_has_cron():
    from worker.main import WorkerSettings, schedule_cycles

    assert len(WorkerSettings.cron_jobs) == 1
    cron_job = WorkerSettings.cron_jobs[0]
    assert cron_job.coroutine is schedule_cycles
```

- [ ] **Step 2: Ejecutar test — verificar que falla**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_worker.py -v
```

Expected: `ImportError` (worker no tiene las funciones nuevas)

- [ ] **Step 3: Reemplazar `apps/worker/worker/main.py`**

```python
"""ARQ worker entry point — reemplaza el stub de Fase 1."""
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
    """Inicializa recursos compartidos en el contexto ARQ."""
    ctx["session_factory"] = async_session_factory


async def process_account_cycle(ctx: dict, account_id: str) -> dict:
    """Job ARQ principal. account_id como str para serialización JSON/Redis."""
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
    """Cron cada 5 min: encola ciclos para cuentas que toca procesar.

    ARQ deduplicación: _job_id=f"cycle-{account.id}" evita encolar
    la misma cuenta dos veces si el cron se solapa.
    """
    now = datetime.now(tz=timezone.utc)
    async with ctx["session_factory"]() as session:
        accounts = await AccountRepository(session).get_accounts_due(now)

    redis = ctx["redis"]
    for account in accounts:
        await redis.enqueue_job(
            "process_account_cycle",
            str(account.id),
            _job_id=f"cycle-{account.id}",
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

- [ ] **Step 4: Sincronizar deps del worker**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo"
uv sync
```

- [ ] **Step 5: Ejecutar test — verificar que pasa**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/test_worker.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add apps/worker/worker/main.py apps/api/tests/unit/test_worker.py
git commit -m "feat: worker ARQ — process_account_cycle + schedule_cycles cron"
```

---

## Task 10: Integration test + lint + coverage

**Files:**
- Create: `apps/api/tests/integration/test_full_cycle.py`

**Prerrequisitos:** Docker con Postgres + Greenmail corriendo:
```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/infrastructure"
docker compose -f docker-compose.dev.yml up -d postgres greenmail
```

- [ ] **Step 1: Crear `apps/api/tests/integration/test_full_cycle.py`**

```python
"""Test de integración: ciclo completo con Greenmail (IMAP real) + Postgres real.

El test NO usa LLM — la cuenta no tiene llm_provider configurado,
por lo que no se generan borradores. Se verifica:
  - Email clasificado por domain_client rule
  - processed_emails: 1 registro con method="domain_client"
  - audit_log: finalized_at NOT NULL
  - Greenmail: email movido a la carpeta destino
"""
from __future__ import annotations

import imaplib
import smtplib
import time
from email.mime.text import MIMEText
from uuid import uuid4

import pytest

from app.crypto import encrypt
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.models.rules import DomainRule as DbDomainRule
from app.repositories.cycle import CycleRepository
from app.services.cycle import CycleService

# Credenciales Greenmail de docker-compose.dev.yml
GREENMAIL_HOST = "localhost"
GREENMAIL_IMAP_PORT = 3143
GREENMAIL_SMTP_PORT = 3025
GREENMAIL_USER = "test"
GREENMAIL_PASS = "password"
GREENMAIL_EMAIL = "test@localhost"

SECRET_KEY = "test-secret-key-32bytes-padded!!"


@pytest.fixture()
async def full_account(session):
    """Crea Organization + EmailAccount con DomainRule para external.com."""
    org = Organization(name="IntegrationOrg", slug=f"int-{uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    acc = EmailAccount(
        org_id=org.id,
        imap_host=GREENMAIL_HOST,
        imap_port=GREENMAIL_IMAP_PORT,
        use_ssl=False,
        username=GREENMAIL_USER,
        encrypted_credentials=encrypt({"password": GREENMAIL_PASS}, SECRET_KEY),
        inbox_folder="INBOX",
        unclassified_folder="Sin_Clasificar",
        is_active=True,
        interval_minutes=5,
    )
    session.add(acc)
    await session.flush()

    rule = DbDomainRule(
        account_id=acc.id,
        domain="external.com",
        label="Clients/External",
        rule_id="r-ext",
        priority=0,
    )
    session.add(rule)
    await session.commit()
    return acc


def send_test_email(subject: str = "Integration test") -> None:
    """Envía un email a test@localhost vía SMTP Greenmail."""
    msg = MIMEText("This is a test email from external.com")
    msg["Subject"] = subject
    msg["From"] = "sender@external.com"
    msg["To"] = GREENMAIL_EMAIL

    with smtplib.SMTP(GREENMAIL_HOST, GREENMAIL_SMTP_PORT) as smtp:
        smtp.sendmail("sender@external.com", [GREENMAIL_EMAIL], msg.as_bytes())

    # Greenmail necesita un momento para entregar el mensaje
    time.sleep(0.5)


def get_imap_folder_messages(folder: str) -> list[str]:
    """Devuelve los UIDs de mensajes en la carpeta IMAP especificada."""
    client = imaplib.IMAP4(GREENMAIL_HOST, GREENMAIL_IMAP_PORT)
    client.login(GREENMAIL_USER, GREENMAIL_PASS)
    status, _ = client.select(folder)
    if status != "OK":
        return []
    _, data = client.uid("SEARCH", "ALL")
    client.logout()
    uids = data[0].decode().split() if data[0] else []
    return uids


@pytest.mark.integration
async def test_full_cycle_classifies_and_moves_email(session, session_factory, full_account):
    """Ciclo completo: email → classify → move → audit_log finalizado."""
    # 1. Enviar email desde external.com
    send_test_email("Invoice inquiry")

    # 2. Override SECRET_KEY para que CycleService descifre las credenciales
    import app.services.cycle as cycle_module
    original_settings = cycle_module.settings

    class FakeSettings:
        SECRET_KEY = SECRET_KEY
        DATABASE_URL = original_settings.DATABASE_URL
        REDIS_URL = original_settings.REDIS_URL

    cycle_module.settings = FakeSettings()

    try:
        service = CycleService(session_factory)
        result = await service.run(full_account.id)
    finally:
        cycle_module.settings = original_settings

    # 3. Verificar resultado del ciclo
    assert result.emails_processed >= 1
    assert result.errors == 0

    # 4. Verificar processed_emails en DB
    from sqlalchemy import select
    from app.models.processed_email import ProcessedEmail
    records = list(
        (
            await session.execute(
                select(ProcessedEmail).where(ProcessedEmail.account_id == full_account.id)
            )
        ).scalars()
    )
    assert len(records) >= 1
    rec = records[0]
    assert rec.destination_folder == "Clients/External"
    assert rec.method == "domain_client"

    # 5. Verificar audit_log finalizado
    from app.models.audit_log import AuditLog
    log = (
        await session.execute(
            select(AuditLog).where(AuditLog.cycle_id == result.cycle_id)
        )
    ).scalar_one()
    assert log.finalized_at is not None
    assert log.emails_processed >= 1

    # 6. Verificar que el email fue movido en Greenmail
    # (puede tardar un momento en reflejarse)
    time.sleep(0.5)
    uids_in_dest = get_imap_folder_messages("Clients/External")
    assert len(uids_in_dest) >= 1
```

- [ ] **Step 2: Ejecutar test de integración**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/integration/test_full_cycle.py -v -m integration
```

Expected: 1 test PASSED (requiere Docker con postgres + greenmail)

- [ ] **Step 3: Ejecutar todos los unit tests**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run pytest tests/unit/ -v
```

Expected: todos los tests pasan.

- [ ] **Step 4: Ejecutar lint**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo/apps/api"
uv run ruff check app/ tests/
uv run ruff format app/ tests/ --check
```

Expected: 0 errores. Si hay errores de formato: `uv run ruff format app/ tests/`.

- [ ] **Step 5: Ejecutar también los tests de packages/core para verificar no hay regresiones**

```bash
cd "C:/Users/jonat/CLAW.D.LABS AI AGENCY/CTO (claude code)/MAILFLOW/repo"
uv run pytest packages/core/tests/ -v --tb=short
```

Expected: todos los tests de Fase 1 siguen pasando.

- [ ] **Step 6: Commit final**

```bash
git add apps/api/tests/integration/test_full_cycle.py
git commit -m "test: integration test ciclo completo (Greenmail + Postgres)"
```

- [ ] **Step 7: Crear PR a main**

```bash
git push -u origin feat/fase2a-db-worker
gh pr create \
  --title "feat: Fase 2a — DB Layer + Worker Core" \
  --body "$(cat <<'EOF'
## Qué incluye
- ORM models 8 tablas (Alembic migration incluida)
- Fernet encryption para credenciales IMAP y LLM API keys
- AccountRepository + CycleRepository con tests reales Postgres
- CycleService: loop completo con claim_cycle TOCTOU guard
- Worker ARQ: process_account_cycle + schedule_cycles cron 5 min
- Integration test: Greenmail + Postgres (sin LLM)

## Tests
- Unit tests: crypto, models, repositories, helpers, CycleService, worker
- Integration: ciclo completo classify→move→audit_log

## Cómo probar
\`\`\`bash
docker compose -f infrastructure/docker-compose.dev.yml up -d postgres greenmail
cd apps/api && uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v -m integration
\`\`\`
EOF
)"
```

---

## Self-review checklist

### Spec coverage

| Sección spec | Tarea que la implementa |
|-------------|------------------------|
| §4 packages/core — sin cambios | Verificado: no hay tareas que toquen packages/core |
| §5 DB Schema 8 tablas | Task 2 (models) + Task 3 (migration) |
| §6 Config + Crypto | Task 1 |
| §7 Database setup | Task 3 |
| §8 Alembic | Task 3 |
| §9 ORM Models con relationship | Task 2 |
| §10 AccountRepository (3 métodos) | Task 5 |
| §10 CycleRepository (4 métodos) | Task 6 |
| §11 CycleService + helpers | Task 7 + Task 8 |
| §12 Worker ARQ | Task 9 |
| §13 Tests unit + integration | Task 1-10 |
| §14 mailflow_test DB creation | Task 3 Step 8 |
| §15 Tech debt documentado | En comentarios del código |

### Verificación de consistencia de tipos

- `encrypt(data: dict, key: str) -> str` ✓ — consistente en test y impl
- `decrypt(token: str, key: str) -> dict` ✓
- `AccountRepository.get_full_config → tuple[EmailAccount, AccountConfig, LLMProvider | None]` ✓
- `CycleRepository.insert_processed(account_id, uid, folder, uidvalidity, message_id, from_email, subject, destination_folder, method, confidence, draft_saved, cycle_id)` ✓ — consistente en test y impl
- `CycleResult(cycle_id, emails_processed, drafts_saved, errors)` ✓
- `generate_draft(original_email: ParsedEmail, request: DraftRequest) -> str` ✓
- `save_draft(message_bytes: bytes) -> bool` ✓
- `method` values: `"domain_client"`, `"domain_internal"`, `"thread"`, `"keyword"`, `"llm"`, `"fallback"` ✓ (no "thread_inheritance")
