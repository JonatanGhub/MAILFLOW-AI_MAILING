# MailFlow

**Open source AI email assistant. Use any LLM. Your inbox, your rules, your privacy.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/JonatanGhub/mailflow/actions/workflows/ci.yml/badge.svg)](https://github.com/JonatanGhub/mailflow/actions/workflows/ci.yml)

MailFlow automatically classifies incoming emails into your IMAP folders and generates draft replies in your writing style — powered by **any LLM you choose** (local Ollama, OpenAI, Anthropic, Gemini, vLLM, LM Studio, or any OpenAI-compatible endpoint).

## Why MailFlow?

| Feature | MailFlow | Superhuman | Shortwave | Spark |
|---|---|---|---|---|
| Open source | ✅ AGPL | ❌ | ❌ | ❌ |
| Self-hostable | ✅ Docker | ❌ | ❌ | ❌ |
| Multi-LLM support | ✅ 100+ | ❌ GPT-only | ❌ Claude-only | ❌ |
| Privacy (local AI) | ✅ Ollama | ❌ | ❌ | ❌ |
| Bilingual EN/ES | ✅ | ❌ | ❌ | ❌ |
| Price | Free / $12/mo | $30-40/mo | $24/mo | $10/mo |

## Quick Start (Self-hosted)

```bash
git clone https://github.com/JonatanGhub/mailflow.git
cd mailflow
cp .env.example .env
docker compose up
```

Open http://localhost:3000 and connect your inbox in under 2 minutes.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + Tailwind + shadcn/ui |
| Backend API | Python 3.13 + FastAPI |
| Workers | ARQ (asyncio jobs) |
| Database | PostgreSQL + pgvector / SQLite (self-host) |
| Auth | Better Auth (multi-tenant, self-hosted) |
| LLM Router | LiteLLM (100+ providers) |
| Email | IMAP + M365 OAuth2 + Gmail OAuth2 |

## Features (v1)

- **Auto-classification** — deterministic cascade (domain → thread → keyword) + LLM fallback
- **Draft generation** — replies in your writing style, saved as IMAP Drafts (never auto-sent)
- **Template library** — reusable templates with auto-detection by keywords
- **Multi-LLM** — choose any engine per workspace: Ollama, OpenAI, Anthropic, Gemini, vLLM…
- **Learning loop** — corrections and edits feed back to improve future suggestions
- **Web dashboard** — view cycles, stats, configure rules and templates

## Development

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for setup instructions.

```bash
# Backend
uv sync
uvicorn apps.api.app.main:app --reload

# Frontend
pnpm install
pnpm dev
```

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).

Commercial SaaS use requires a commercial license. Contact tecnicosestudios@igex.es.
