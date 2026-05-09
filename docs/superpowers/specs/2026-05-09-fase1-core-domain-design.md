# Spec: Fase 1 — Core Domain Logic

**Fecha:** 2026-05-09  
**Estado:** Aprobado  
**Scope:** `packages/core/mailflow_core/`  
**Enfoque:** Tipos primero → 4 subagentes paralelos con TDD

---

## 1. Contexto

La Fase 0 entregó el scaffold del monorepo y la interfaz abstracta `EmailProvider` con sus DTOs base (`EmailData`, `DraftRef`). La Fase 1 implementa la lógica de dominio real en `packages/core/`, de forma completamente independiente del API y del worker (que quedan como stubs hasta Fase 2).

**Fuera de scope en Fase 1:**
- `MicrosoftProvider` (OAuth2 MSAL) — Fase posterior
- `GmailProvider` (Google OAuth2) — Fase posterior
- Integración con base de datos — Fase 2
- ARQ worker real (`process_account_cycle`) — Fase 2

---

## 2. Módulos a implementar

| Archivo | Clase principal | Responsabilidad |
|---|---|---|
| `mailflow_core/types.py` | DTOs compartidos | Contratos entre módulos |
| `mailflow_core/exceptions.py` | Jerarquía de errores | Errores de dominio tipados |
| `mailflow_core/providers/imap_generic.py` | `ImapGenericProvider` | IMAP con password auth |
| `mailflow_core/email_parser.py` | `EmailParser` | Parseo + limpieza de emails |
| `mailflow_core/classification/rule_engine.py` | `RuleEngine` | Cascada de clasificación |
| `mailflow_core/classification/llm_client.py` | `LLMClient` | Wrapper LiteLLM |

---

## 3. Paso 1: Contratos compartidos

### 3.1 `types.py`

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class ParsedEmail:
    uid: str
    subject_normalized: str     # sin Re:/Fwd:/RV:/FW:/Ref:/AW:/TR: (bucle, case-insensitive)
    body_text: str              # limpio, sin firma, sin quoted reply
    body_html: str
    signature: str              # firma extraída (vacío si no hay)
    from_email: str
    from_domain: str            # extraído de from_email (parte tras @)
    to_emails: list[str] = field(default_factory=list)
    in_reply_to: str | None = None
    thread_id: str | None = None  # message_id raíz del hilo (de References o In-Reply-To)
    date: str | None = None

@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float           # 0.0–1.0
    method: Literal["domain_internal", "domain_client", "thread", "keyword", "llm", "fallback"]
    rule_id: str | None = None  # ID de regla disparada (para audit trail)

@dataclass(frozen=True)
class DraftRequest:
    in_reply_to_uid: str
    folder: str
    subject: str
    body_text: str
    body_html: str | None
    classification: ClassificationResult
```

### 3.2 `exceptions.py`

```python
class MailFlowError(Exception): ...

class IMAPConnectionError(MailFlowError): ...
class UIDValidityChanged(MailFlowError):
    """Lanzado cuando UIDVALIDITY cambia en una carpeta. Invalida caché."""
    def __init__(self, folder: str, old: int, new: int): ...

class DraftCollisionError(MailFlowError):
    """Lanzado cuando ya existe un borrador MailFlow para el mismo In-Reply-To (ADR-004)."""

class LLMError(MailFlowError): ...
class ClassificationError(MailFlowError): ...
```

---

## 4. ImapGenericProvider

### 4.1 Contrato

Implementa `EmailProvider` (base.py) usando `imapclient>=3.0`.

```python
class ImapGenericProvider(EmailProvider):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
    ) -> None: ...
```

### 4.2 Reglas IMAP no negociables

| Regla | Implementación |
|---|---|
| Siempre UIDs | `use_uid=True` en todas las operaciones |
| Separador dinámico | `LIST "" ""` en `connect()` — no hardcodear `/` ni `.` |
| Carpeta Drafts | Detectar por atributo `\Drafts` con `LIST "" "*"` |
| UIDVALIDITY | Guardar por carpeta en `_uidvalidity: dict[str, int]`; lanzar `UIDValidityChanged` si cambia |
| Move seguro | `COPY` → `STORE \Deleted` → `EXPUNGE`; si `COPY` falla, **no hacer** `EXPUNGE` |
| Anti-colisión borradores | Buscar `DraftRef` existente antes de `APPEND`; lanzar `DraftCollisionError` si ya existe |
| Keepalive | `NOOP` sin efecto si no está conectado |

### 4.3 Métodos

```python
def connect(self) -> None
def disconnect(self) -> None
def fetch_unprocessed(self, folder: str) -> list[EmailData]
    # SEARCH UID NOT KEYWORD MailFlowProcessed
def move_email(self, uid: str, from_folder: str, to_folder: str) -> None
def save_draft(self, request: DraftRequest) -> DraftRef
def find_draft(self, in_reply_to_uid: str, folder: str) -> DraftRef | None
def delete_draft(self, ref: DraftRef) -> None
def create_folder(self, path: str) -> None
def keepalive(self) -> None
```

---

## 5. EmailParser

### 5.1 Contrato

```python
class EmailParser:
    def parse(self, raw_message: bytes) -> ParsedEmail: ...
```

Sin estado. Reusable. No lanza excepciones salvo formato completamente inválido (`MailFlowError`).

### 5.2 Pipeline

1. `email.message_from_bytes()` — extrae headers y partes MIME
2. Extraer `body_text` y `body_html` de las partes `text/plain` y `text/html`
3. `email_reply_parser.EmailReplyParser.parse_reply(body_text)` — extrae solo la respuesta nueva
4. Fallback castellano: si el parser no detecta firma, regex sobre patrones `"Saludos,"`, `"Atentamente,"`, `"Un saludo,"`, `"Gracias,"` seguidos de salto de línea
5. Normalización de asunto: bucle hasta que no haya cambios:
   - Quitar al inicio (case-insensitive, con espacio opcional): `Re:` `RV:` `Fwd:` `FW:` `Ref:` `AW:` `TR:`
6. Extraer `from_domain` desde `from_email.split("@")[-1].lower()`
7. Resolver `thread_id` desde header `References` (primer message-id) → `In-Reply-To` → `None`

### 5.3 Casos de borde

- Email sin body text (solo HTML): `body_text = ""`, `signature = ""`
- Asunto vacío: `subject_normalized = ""`
- `from_email` sin `@`: `from_domain = ""`
- Multipart anidado: extraer recursivamente

---

## 6. RuleEngine

### 6.1 Contrato

```python
@dataclass
class AccountConfig:
    account_id: str
    internal_domains: list[str]           # dominios propios de la organización
    client_domain_rules: list[DomainRule] # {domain, label, rule_id}
    keyword_rules: list[KeywordRule]      # {keywords, label, rule_id, match_all}

class RuleEngine:
    def __init__(self, config: AccountConfig, llm_client: LLMClient | None = None) -> None: ...
    def classify(
        self,
        email: ParsedEmail,
        thread_history: list[ClassificationResult] | None = None,
        available_labels: list[str] | None = None,
    ) -> ClassificationResult: ...
```

### 6.2 Cascada (orden fijo, primer match gana)

| Paso | Condición | Confidence | method |
|---|---|---|---|
| 1 | `from_domain` en `internal_domains` | 1.0 | `domain_internal` |
| 2 | `from_domain` en `client_domain_rules` y no en GENERIC_DOMAINS | 0.95 | `domain_client` |
| 3 | `thread_history` no vacío y el resultado **más reciente** tiene confidence ≥ 0.80 | 0.90 | `thread` |
| 4 | Keywords match en `subject_normalized` o `body_text` | 0.80 | `keyword` |
| 5 | `llm_client` disponible → llamada LLM | variable | `llm` |
| 6 | Fallback | 0.0 | `fallback` |

**GENERIC_DOMAINS** (constante en el módulo):
```python
GENERIC_DOMAINS = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
    "yahoo.es", "icloud.com", "me.com", "protonmail.com",
    "proton.me", "live.com",
})
```

### 6.3 Keyword matching

`KeywordRule` tiene `match_all: bool`:
- `match_all=True`: todas las keywords deben aparecer (AND)
- `match_all=False`: cualquiera vale (OR)

Búsqueda case-insensitive en `subject_normalized + " " + body_text`.

---

## 7. LLMClient

### 7.1 Contrato

```python
@dataclass
class LLMConfig:
    model_id: str           # e.g. "ollama/llama3", "claude-sonnet-4-6", "gpt-4o"
    api_base: str | None    # para Ollama/vLLM; None para APIs cloud
    api_key: str | None     # None para modelos locales
    timeout: float = 30.0
    max_retries: int = 2

class LLMClient:
    def __init__(self, config: LLMConfig) -> None: ...

    def classify(
        self,
        email: ParsedEmail,
        available_labels: list[str],
    ) -> ClassificationResult: ...

    def generate_draft(
        self,
        original_email: ParsedEmail,
        request: DraftRequest,
    ) -> str: ...
```

### 7.2 Clasificación

Prompt de sistema fijo (en inglés, para máxima compatibilidad de modelos). Respuesta forzada a JSON:
```json
{"label": "...", "confidence": 0.85}
```

Si el JSON es inválido o `label` no está en `available_labels` → `ClassificationError`.  
Si la llamada falla tras `max_retries` → `LLMError`.

Confidence mínima aceptable: 0.60. Por debajo → `ClassificationResult` con `method="fallback"`.

### 7.3 Generación de borrador

Prompt incluye: asunto normalizado, body del email original, label de clasificación.  
Devuelve únicamente el body_text del borrador (sin metadata).  
Si falla → `LLMError` (el caller decide el fallback).

### 7.4 Reintentos

`litellm.completion()` con `num_retries=config.max_retries` y `timeout=config.timeout`.  
Backoff gestionado por LiteLLM internamente.

---

## 8. Estrategia de testing

### 8.1 Tests unitarios (`tests/unit/`)

| Módulo | Herramienta | Notas |
|---|---|---|
| `imap_generic` | `pytest-mock` (patch `imapclient.IMAPClient`) | Verificar secuencias IMAP exactas |
| `email_parser` | Fixtures `.eml` reales en `tests/fixtures/` | Casos: reply, forward, solo HTML, firma castellana |
| `rule_engine` | Tabla paramétrica `@pytest.mark.parametrize` | Cubrir los 6 pasos de la cascada |
| `llm_client` | `respx` (mock HTTP) | Respuestas válidas, JSON inválido, timeout |

### 8.2 Tests de integración (`tests/integration/`)

Requieren `pytest -m integration` y Docker corriendo.

**Greenmail** en `docker-compose.dev.yml`:
```yaml
greenmail:
  image: greenmail/standalone:2.1.2
  ports:
    - "3143:3143"   # IMAP
    - "3025:3025"   # SMTP (seed de emails en fixtures)
  environment:
    - GREENMAIL_OPTS=-Dgreenmail.setup.test.all
```

`conftest.py` de integración:
- Fixture `imap_server` de scope `session`: levanta greenmail, crea cuenta de test, yield host/port/creds, teardown.
- Fixture `provider` de scope `function`: instancia `ImapGenericProvider` + connect, yield, disconnect.

Casos cubiertos:
- `connect()` detecta separador y carpeta Drafts
- `fetch_unprocessed()` devuelve solo emails sin `MailFlowProcessed`
- `save_draft()` + `find_draft()` anti-colisión
- `move_email()` safe sequence
- `UIDValidityChanged` detectado correctamente

### 8.3 Coverage

Target: **≥ 80%** en `packages/core/` antes de pasar a Fase 2.  
Comando: `uv run pytest packages/core/tests/ --cov=mailflow_core --cov-fail-under=80`

---

## 9. Dependencias nuevas

`packages/core/pyproject.toml`:
```toml
[project]
dependencies = [
    "imapclient>=3.0",
    "email-reply-parser>=0.5",
    "beautifulsoup4>=4.12",
    "pydantic>=2.10",
    "litellm>=1.40",      # nuevo Fase 1
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-mock>=3.12",
    "respx>=0.21",         # nuevo Fase 1
    "ruff>=0.4",
]
```

`infrastructure/docker-compose.dev.yml`: añadir servicio `greenmail`.

---

## 10. Estructura de archivos final

```
packages/core/
├── mailflow_core/
│   ├── __init__.py
│   ├── types.py              ← nuevo
│   ├── exceptions.py         ← nuevo
│   ├── email_parser.py       ← nuevo
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py           ← sin cambios
│   │   └── imap_generic.py   ← nuevo
│   └── classification/
│       ├── __init__.py       ← nuevo
│       ├── rule_engine.py    ← nuevo
│       └── llm_client.py     ← nuevo
├── pyproject.toml            ← actualizar deps
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   ├── simple_email.eml
    │   ├── reply_with_signature.eml
    │   ├── forward_html_only.eml
    │   └── spanish_signature.eml
    ├── unit/
    │   ├── __init__.py
    │   ├── test_provider_base.py  ← ya existe
    │   ├── test_imap_generic.py   ← nuevo
    │   ├── test_email_parser.py   ← nuevo
    │   ├── test_rule_engine.py    ← nuevo
    │   └── test_llm_client.py    ← nuevo
    └── integration/
        ├── __init__.py           ← nuevo
        ├── conftest.py           ← nuevo
        └── test_imap_integration.py ← nuevo
```

---

## 11. Orden de implementación (Paso 1 → Paso 2)

**Paso 1** (bloqueante, yo): `types.py` + `exceptions.py` + actualizar `pyproject.toml` + añadir greenmail a docker-compose.

**Paso 2** (4 subagentes en paralelo, sobre contratos del Paso 1):
- Agente A: `providers/imap_generic.py` + `tests/unit/test_imap_generic.py` + `tests/integration/`
- Agente B: `email_parser.py` + `tests/unit/test_email_parser.py` + fixtures `.eml`
- Agente C: `classification/rule_engine.py` + `tests/unit/test_rule_engine.py`
- Agente D: `classification/llm_client.py` + `tests/unit/test_llm_client.py`
