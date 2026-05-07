# MailFlow — Instrucciones para Claude Code

> Producto: **MailFlow** — Asistente de email con IA, open source AGPL + SaaS freemium.
> Stack: Next.js 15 + FastAPI + PostgreSQL + LiteLLM + Better Auth + ARQ
> Plan maestro: `docs/PLAN.md`

---

## Estructura del monorepo

```
mailflow/
├── apps/
│   ├── web/          Next.js 15 frontend (pnpm)
│   ├── api/          FastAPI backend (uv)
│   └── worker/       ARQ worker (mismo paquete que api)
├── packages/
│   ├── core/         Lógica de dominio Python (providers, classification, drafts)
│   ├── ui/           Componentes React compartidos
│   └── i18n/         Diccionarios EN/ES
├── infrastructure/   Docker, docker-compose
├── docs/             PLAN.md, ARCHITECTURE.md, CONTRIBUTING.md, adr/
└── .github/          CI/CD workflows
```

## Reglas

- Código en inglés, docstrings y strings de usuario en español
- Funciones < 50 líneas, archivos < 400 líneas
- TDD obligatorio para lógica de dominio en `packages/core/`
- Coverage ≥ 80% antes de merge
- NUNCA hardcodear credenciales ni API keys
- NUNCA enviar emails — solo guardar borradores IMAP
- Ver docs/adr/ para decisiones de diseño vigentes

## Comandos frecuentes

```bash
# Backend
uv sync
uvicorn apps.api.app.main:app --reload

# Tests Python
pytest packages/core/tests/
pytest --cov=mailflow_core --cov-fail-under=80

# Frontend
pnpm install
pnpm dev

# Lint
ruff check .
ruff format .
pnpm biome check .
```

## ADRs vigentes (heredados de MailFlowPro)

- ADR-003 Signature stripping con email-reply-parser + fallback castellano
- ADR-004 No sobrescribir drafts del usuario
- ADR-005 Feedback loop (corrections)
- ADR-006 Audit trail con cycle_id
- ADR-007 Modelos distintos para clasificación vs generación
- ADR-008 Coverage ≥ 80% pytest
- ADR-012 FIFO en backlog
