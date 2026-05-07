# MailFlow — Plan maestro de redefinición desde cero

> **Estado**: Plan inicial aprobado conceptualmente. Pendiente de aprobación final del usuario antes de ejecutar.
> **Fecha**: 2026-05-06
> **Nombre del producto**: **MailFlow** (familia de proyectos: MailFlow, PromptFlow, MeetFlow)

---

## 1. Context

### 1.1 Problema que resuelve

El email sigue siendo el cuello de botella de productividad para profesionales y equipos pequeños. Las soluciones actuales tienen tres carencias claras según el análisis competitivo:

1. **Privacidad limitada**: Superhuman, Shortwave, Spark — todas envían el contenido del email a sus servidores y/o a un único proveedor de LLM (OpenAI/Anthropic) sin que el usuario pueda elegir.
2. **Lock-in de LLM**: ningún competidor permite al usuario elegir el motor de IA (Ollama local, OpenAI, Anthropic, Gemini, vLLM, LM Studio…).
3. **No hay alternativa open source seria**: el espacio "email + IA" tiene cero proyectos OSS con tracción real. Thunderbird carece de IA nativa; el resto son SaaS cerrados.

### 1.2 Por qué este pivot

El proyecto MailFlowPro actual (v0.3) es un agente Python local con UI tkinter, fuertemente acoplado al caso de uso interno IGEX. La arquitectura no permite:
- Acceso desde múltiples dispositivos (la UI es Windows-only)
- Multi-tenancy (1 instalación = 1 usuario)
- Comercializarlo como SaaS sin reescribir
- Onboarding amigable para usuarios no técnicos
- Comunidad open source (no hay frontend web visitable, no hay landing)

**Decisión**: wipe total, reescribir como producto dual **open source AGPL + SaaS freemium**.

### 1.3 Resultado esperado

Al cabo de 3-4 meses:
- Repo público en GitHub con **MailFlow** como producto OSS self-hosteable (`docker compose up`)
- SaaS desplegado en `app.mailflow.app` (o dominio elegido) con tier free + plan Pro
- Documentación bilingüe (EN/ES)
- 1 usuario real (Jonatan) usando el SaaS para validar
- Material para promocionar en HN, Reddit, comunidades Ollama/AGPL

---

## 2. Decisiones consolidadas (recap)

| Eje | Decisión |
|---|---|
| Nombre | **MailFlow** |
| Mercado | Open source (GitHub) + SaaS personal (no IGEX) |
| Licencia | AGPL-3.0 |
| Arquitectura | Web app (Next.js) + Core API headless (FastAPI) + Postgres/SQLite |
| Frontend stack | Next.js 15 App Router + Tailwind + shadcn/ui + Zustand |
| Backend stack | Python 3.13 + FastAPI + SQLAlchemy 2.0 + ARQ (jobs) |
| LLM router | LiteLLM (100+ providers) |
| Auth | Better Auth (self-hosted, multi-tenant nativo) |
| DB | PostgreSQL + pgvector (SaaS) / SQLite (self-hosted) |
| Conectores email v1 | M365 OAuth2 + Gmail OAuth2 + IMAP genérico |
| Idiomas v1 | Inglés + español (i18n estructurado, `next-intl`) |
| Monetización | Freemium |
| Timeline | 3-4 meses al MVP usable |
| Código actual | Wipe total. Preservar conocimiento de dominio (no código). |

---

## 3. Análisis competitivo destilado

**Top players**: Superhuman ($30-40/mo), Shortwave ($24/mo, Claude integration), Hey ($99/yr), Spark (freemium, $10/mo Pro), Mailbird ($4-5/mo), Boomerang, Ellie, SaneBox, Front, Missive.

**Table stakes (todos lo tienen)**: triage/clasificación, snooze/archive, búsqueda inteligente, multi-cuenta, read receipts.

**Gaps de mercado (NADIE lo hace bien)**:
1. ❌ **Multi-LLM** — todos están atados a un único proveedor
2. ❌ **Open source con UI moderna** — Thunderbird es legacy; K-9 es mobile-only
3. ❌ **Self-hosted real** — ningún tool moderno permite docker compose up
4. ❌ **UI bilingüe ES/EN nativa** — todos son English-first

**Posicionamiento de MailFlow**:
> *"Open source, self-hostable email AI assistant. Use any LLM (local Ollama, vLLM, OpenAI, Claude, Gemini). Your inbox, your rules, your privacy."*

**Pricing target (freemium)**:
- **Free**: 1 cuenta de email, 100 emails procesados/día, BYOK (Bring Your Own Key) cualquier LLM, self-host ilimitado (open source)
- **Pro ($12/mes)**: cuentas ilimitadas, emails ilimitados, modelos hosteados (Ollama gestionado), templates premium, prioridad de soporte
- **Team ($25/usuario/mes, min 3)**: workspace compartido, plantillas de equipo, audit logs, SSO

(Por debajo de Shortwave $24/mes y Superhuman $30-40/mes intencionalmente.)

---

## 4. Producto MVP — Scope v1

### 4.1 Features must-have v1

1. **Conexión multi-cuenta** (M365 OAuth2 / Gmail OAuth2 / IMAP genérico con contraseña)
2. **Clasificación automática en carpetas IMAP del propio buzón** según cascada determinista + LLM fallback
3. **Generación de borradores de respuesta** en el hilo original, en estilo del usuario, guardados como Drafts IMAP
4. **Biblioteca de plantillas reutilizables** con auto-detección por keywords
5. **Aprendizaje de estilo (feedback loop)**: cuando el usuario edita un borrador o mueve un email a otra carpeta, el sistema aprende
6. **Multi-LLM router**: el usuario elige por workspace qué motor usar (Ollama local, OpenAI, Anthropic, Gemini, vLLM, LM Studio, custom OpenAI-compatible endpoint)
7. **Dashboard web**: ver últimos ciclos, estadísticas básicas, configurar reglas/plantillas/estilo
8. **Onboarding bilingüe** en <5 pasos / <2 minutos hasta primer email procesado

### 4.2 Explícitamente fuera de v1

- Búsqueda semántica del inbox (v2)
- Resumen diario / briefing (v2)
- Acciones bulk con IA (v2)
- Asistente de programación de reuniones (v2)
- Mobile apps nativas (web responsive es suficiente v1)
- Buzones compartidos (ADR-009 vigente)
- Auto-envío sin revisión (siempre se queda en Drafts — política no negociable)

---

## 5. Arquitectura técnica

### 5.1 Diagrama lógico

```
┌─────────────────────────────────────────────────────┐
│  Frontend Next.js 15 (apps/web)                     │
│  • App Router + RSC                                  │
│  • Tailwind + shadcn/ui                              │
│  • Zustand (state) + react-hook-form + zod (forms)  │
│  • next-intl (i18n EN/ES)                            │
│  • Better Auth client                                │
└───────────────────────┬─────────────────────────────┘
                        │ REST + SSE
                        ↓
┌─────────────────────────────────────────────────────┐
│  Core API Python (apps/api)                          │
│  • FastAPI 0.115+ con APIRouter por dominio          │
│  • SQLAlchemy 2.0 async + Alembic migraciones        │
│  • Better Auth verifier (JWT)                        │
│                                                      │
│  Módulos:                                            │
│   ├── providers/      (M365, Gmail, IMAP)            │
│   ├── llm/            (LiteLLM router)               │
│   ├── classification/ (cascada determinista + LLM)   │
│   ├── drafts/         (generador + collision check)  │
│   ├── templates/      (auto-detect + variables)      │
│   ├── learning/       (corrections, feedback)        │
│   ├── tenants/        (multi-tenant: orgs, members)  │
│   └── audit/          (audit log + rollback)         │
└───────────────────────┬─────────────────────────────┘
                        │
        ┌───────────────┼──────────────────┐
        ↓               ↓                  ↓
┌──────────────┐ ┌───────────────┐ ┌──────────────────┐
│  Worker ARQ  │ │  PostgreSQL   │ │   Redis          │
│  • Cycles    │ │  + pgvector   │ │   (ARQ queue)    │
│  • Indexing  │ │  (SaaS)       │ │                  │
│  • LLM calls │ │  --or--       │ └──────────────────┘
└──────────────┘ │  SQLite       │
                 │  (self-host)  │
                 └───────────────┘
```

### 5.2 Estructura del monorepo

```
mailflow/
├── apps/
│   ├── web/                  Next.js frontend
│   ├── api/                  FastAPI backend
│   └── worker/               ARQ worker (mismo paquete que api, distinto entry point)
├── packages/
│   ├── core/                 Lógica de dominio Python (provider abstracta, classification, drafts)
│   ├── ui/                   Componentes React compartidos (shadcn/ui custom)
│   └── i18n/                 Diccionarios EN/ES compartidos web + emails transaccionales
├── infrastructure/
│   ├── docker/               Dockerfiles + docker-compose.yml (self-host)
│   ├── docker-compose.dev.yml
│   ├── docker-compose.saas.yml
│   └── terraform/            (opcional v1.5) infra del SaaS personal
├── docs/
│   ├── README.md             EN
│   ├── README.es.md          ES
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTING.md
│   ├── self-hosting.md
│   └── adr/                  ADRs nuevos (heredan los vigentes del proyecto antiguo)
├── .github/
│   ├── workflows/            CI: lint, test, build, docker push
│   └── ISSUE_TEMPLATE/
├── LICENSE                   AGPL-3.0
├── pyproject.toml            (workspace Python con uv)
├── package.json              (workspace JS con pnpm)
└── turbo.json                (Turborepo para builds incrementales)
```

### 5.3 Decisiones técnicas justificadas

| Decisión | Razón |
|---|---|
| **FastAPI** sobre Litestar | Comunidad masiva = más colaboradores OSS potenciales. Performance suficiente para MVP. Litestar es 2x más rápido pero nicho. |
| **LiteLLM** | 100+ providers en una API. Soporta OpenAI, Anthropic, Gemini, Ollama, vLLM, LM Studio, Mistral, Cohere, etc. AGPL-compatible. |
| **Better Auth** sobre Auth.js / Clerk | Self-hosted nativo (clave para AGPL), multi-tenant out-of-the-box (organizations), sin coste por MAU. |
| **pgvector** dentro de Postgres | Una sola DB. Suficiente para search semántico de v2. HNSW index moderno. |
| **ARQ** sobre Celery | asyncio-native, solo Redis (sin broker dual). Menor overhead operacional. |
| **uv** sobre pip/poetry | 10-100x más rápido. Estándar de facto en 2026 para Python. |
| **pnpm + Turborepo** | Builds incrementales en monorepo. Estándar en SaaS modernos. |
| **Stripe + LemonSqueezy** | Stripe para US/global; LemonSqueezy gestiona VAT EU automáticamente. |

---

## 6. Modelo de datos (entidades core)

```sql
-- Multi-tenancy
organizations (id, name, slug, plan, stripe_customer_id, created_at)
users (id, email, name, locale, created_at)
memberships (org_id, user_id, role)  -- owner/admin/member

-- Email accounts conectadas
email_accounts (id, org_id, owner_user_id, provider_type, username, oauth_token_ref, imap_host, inbox_folder, unclassified_folder, is_active)

-- LLM providers configurados
llm_providers (id, org_id, label, type, base_url, api_key_ref, default_classification_model, default_generation_model)

-- Reglas de clasificación
domain_rules (id, account_id, domain, client_name, base_folder, priority)
keyword_rules (id, account_id, keywords[], folder, priority)
internal_domains (id, account_id, domain, internal_folder)

-- Estilo y plantillas
writing_styles (id, account_id, description, signature, examples_json)
templates (id, org_id, name, triggers[], body_template, variables_json, auto_detect_threshold)

-- Estado y auditoría (mantiene contrato del state.db actual)
processed_emails (id, account_id, uid, folder, uidvalidity, message_id, from_email, subject, destination_folder, method, confidence, template_used, draft_saved, cycle_id, processed_at)
folder_state (account_id, folder, uidvalidity, last_uid)
corrections (id, account_id, processed_email_id, original_folder, corrected_folder, created_at)
audit_log (id, org_id, cycle_id, action, payload_json, created_at)

-- Borradores guardados por el agente
drafts_meta (id, account_id, message_id, draft_uid, generated_at, edited_at, sent_at, llm_model, prompt_hash)
```

**Multi-tenancy**: Row-Level Security (RLS) en Postgres por `org_id`. Cada query del API filtra automáticamente por la org del usuario autenticado vía Better Auth context.

**Self-hosted (SQLite)**: misma estructura, RLS desactivado (un solo "default-org"), credenciales en variables de entorno + tabla cifrada localmente.

---

## 7. Onboarding UX (flujo objetivo: <2 min hasta primer email procesado)

```
1. Landing (1s)
   → "Sync your email in 3 steps · Use any LLM · Open source"
   → CTAs: [Try free] [Self-host with Docker]

2. Sign up (10s)
   → OAuth2: Google / Microsoft / GitHub (Better Auth)
   → Crea organización auto con email domain como slug

3. Connect inbox (20s)
   → Botón único "Sign in with Microsoft" o "Sign in with Google"
   → IMAP solo si elige "Other" (avanzado, plegable)
   → Sin pedir client_id/tenant_id (hardcodeados en el OAuth de la app)

4. Choose your AI (15s)
   → "Use MailFlow Cloud (free, fast)" [default]
   → "Use my own (Ollama, OpenAI, Claude, Gemini, vLLM, LM Studio…)"
   → Si BYOK: campo API key + dropdown modelo + test button

5. First sync (async, 30-60s)
   → Progress bar: "Indexing 1,234 emails..."
   → Mientras tanto, dashboard se carga con empty state inteligente
   → Al primer email procesado: notificación "Your first email is ready!"

6. First aha (30-60s)
   → Highlight del primer email clasificado + razón ("Moved to 'Clients/X' because domain matches")
   → Sugerencia de plantilla si aplica
   → CTA: "Customize rules" (opcional)
```

**Principios aplicados** (del análisis de SaaS modernos):
- OAuth2 antes que email/password
- Empty states con call-to-action contextual (no formularios vacíos)
- Async indexing — el usuario explora la UI mientras se procesa
- Milestone tracker en sidebar (no progress bar ambigua)

---

## 8. Plan de implementación — Fases (timeline 14 semanas)

### Fase 0 · Setup (Semana 1)

- [ ] Crear repo público `github.com/jonatangarcia/mailflow` con AGPL-3.0
- [ ] Estructura monorepo (apps/, packages/, infrastructure/) con pnpm + uv
- [ ] CI base (GitHub Actions: lint Python con ruff, lint TS con biome, tests pytest+vitest, docker build)
- [ ] README EN/ES con propuesta de valor y "coming soon"
- [ ] Dominios: registrar `mailflow.app` (o disponible) — verificar antes
- [ ] App registrada en Azure AD (cliente OAuth2 M365 público)
- [ ] App registrada en Google Cloud (cliente OAuth2 Gmail con verificación pendiente)
- [ ] Cuenta Stripe (modo test) + LemonSqueezy

**Salida**: repo iniciado, CI verde con un "hello world" de cada app.

### Fase 1 · Core API + providers (Semanas 2-4)

Portar conocimiento del proyecto antiguo a `packages/core/`:

- [ ] Abstracción `EmailProvider` (interfaz idéntica al actual `mailflowpro/providers/base.py`)
- [ ] `ImapGenericProvider`: implementa todas las reglas IMAP no negociables (UID, separador dinámico, `\Drafts`, COPY→STORE→EXPUNGE seguro, UIDVALIDITY)
- [ ] `MicrosoftProvider`: OAuth2 Authorization Code Flow con `client_id` hardcodeado, callback en localhost (en self-host) o en `api.mailflow.app/oauth/callback` (SaaS)
- [ ] `GmailProvider`: OAuth2 con scopes IMAP, `client_id` por defecto en SaaS / configurable en self-host
- [ ] `EmailParser`: signature stripping (`email-reply-parser` + fallback castellano), normalización de asunto (loop con prefijos Re:/RV:/Fwd:/etc.), body_clean separado
- [ ] `RuleEngine`: cascada determinista (dominio interno → dominio cliente → herencia hilo → keyword → fallback)
- [ ] `LLMRouter` con LiteLLM: clasificación con JSON schema, generación con streaming
- [ ] Tests unitarios con fixtures de emails reales anonimizados (heredados del proyecto actual) — coverage 80%+

**Salida**: librería `core` testeable end-to-end con CLI mínima `python -m mailflow.core process --account=X`.

### Fase 2 · API multi-tenant + DB + Workers (Semanas 5-6)

- [ ] Schema SQLAlchemy + migraciones Alembic
- [ ] Better Auth integrado (organizations, members, RLS Postgres)
- [ ] Endpoints REST por dominio (`/accounts`, `/rules`, `/templates`, `/drafts`, `/cycles`)
- [ ] ARQ worker: tarea `process_account_cycle(account_id)` que ejecuta core + persiste estado
- [ ] Cron de scheduling: cada cuenta corre cada N minutos (configurable, default 5)
- [ ] Manejo de errores con backoff (IMAP) + circuit breaker (LLM)
- [ ] Audit log + rollback de un ciclo

**Salida**: API funcional probada con `curl`, sin frontend aún.

### Fase 3 · Frontend onboarding + dashboard (Semanas 7-9)

- [ ] Next.js 15 con App Router, layout responsive
- [ ] Pages: `/`, `/login`, `/onboarding/{step}`, `/app/dashboard`, `/app/accounts`, `/app/rules`, `/app/templates`, `/app/style`, `/app/llm`, `/app/audit`
- [ ] Componentes shadcn/ui custom (button, card, dialog, form, table, sheet)
- [ ] i18n con `next-intl` (EN/ES, default por locale del navegador)
- [ ] Onboarding wizard según flujo §7
- [ ] Dashboard con últimos N ciclos, estadísticas (clasificados, drafts generados), botón "Run cycle now"
- [ ] Empty states con CTA accionables

**Salida**: SaaS deployable con onboarding fluido y dashboard usable.

### Fase 4 · Self-hosting + Docker + Documentación (Semanas 10-11)

- [ ] `docker-compose.yml` self-host (web + api + worker + postgres opcional / sqlite default + redis)
- [ ] Variables de entorno documentadas (.env.example bilingüe)
- [ ] Modo "single-tenant local" (sin Better Auth multi-org, login simple)
- [ ] Scripts de migración SQLite ↔ Postgres
- [ ] `docs/self-hosting.md` paso a paso (EN/ES)
- [ ] `docs/CONTRIBUTING.md` para colaboradores OSS
- [ ] Healthchecks y logs estructurados (JSON)

**Salida**: cualquiera puede ejecutar `git clone && docker compose up` y tener MailFlow corriendo.

### Fase 5 · Billing + Plan Pro + Limits (Semanas 12-13)

- [ ] Integración Stripe Checkout + webhooks
- [ ] Upgrade flow `/billing/upgrade` → Stripe Customer Portal
- [ ] Quota enforcement: middleware que cuenta emails procesados/día por org y bloquea si excede plan
- [ ] LemonSqueezy fallback para EU VAT
- [ ] Página de pricing pública con comparativa free vs pro

**Salida**: SaaS monetizable.

### Fase 6 · Beta privada + Launch público (Semana 14)

- [ ] Beta cerrada con 5-10 testers (incluyendo Jonatan como primary)
- [ ] Recoger feedback en Linear / GitHub Issues
- [ ] Bugfixes críticos
- [ ] Anuncio en Hacker News con título "Show HN: MailFlow — Open source AI email assistant with multi-LLM support"
- [ ] Posts paralelos: r/selfhosted, r/privacy, r/productivity
- [ ] Demo video <2 min (Loom o equivalente)

**Salida**: producto público, primeros usuarios reales, feedback loop con la comunidad.

---

## 9. Conocimiento del proyecto anterior preservado

Lo que se porta como **input intelectual** (no código):

### 9.1 Reglas IMAP no negociables (van directo al nuevo `ImapGenericProvider`)

- Usar siempre `use_uid=True`
- Detectar separador de carpetas dinámicamente con `LIST` en `connect()`
- Carpeta Drafts por atributo `\Drafts`, no por nombre
- Orden seguro: `COPY` → verificar OK → `STORE +FLAGS \Deleted` → `EXPUNGE`. Si COPY falla, NO ejecutar EXPUNGE
- Detección de `UIDVALIDITY` cambiado → invalidar caché
- Comprobación de draft previo del usuario en el hilo antes de guardar uno nuevo

### 9.2 ADRs vigentes a portar

| ADR original | Vigencia |
|---|---|
| ADR-001 SQLite como source of truth | ✅ aplica al modo self-hosted |
| ADR-003 Signature stripping con email-reply-parser + fallback castellano | ✅ 100% |
| ADR-004 No sobrescribir drafts del usuario | ✅ 100% |
| ADR-005 Feedback loop (corrections) | ✅ 100% |
| ADR-006 Audit trail con cycle_id | ✅ 100% |
| ADR-007 Modelos distintos para clasificación vs generación | ✅ 100% |
| ADR-008 80%+ coverage pytest | ✅ 100% |
| ADR-012 FIFO en backlog | ✅ 100% |

### 9.3 ADRs a descartar

- ADR-002 Windows Credential Manager → reemplazar con vault de secretos (OAuth tokens en DB cifrada por org)
- ADR-009 Buzones compartidos fuera de alcance → mantener, pero re-evaluar en v2 SaaS
- ADR-010 Dashboard tkinter → reemplazado por web app
- ADR-013 Plan rollback piloto Hostalia → ya no aplica

### 9.4 Heurísticas reutilizables

- **Cascada de clasificación**: dominio interno (1.0) → dominio cliente (1.0) → herencia hilo (0.95) → keyword (0.80) → LLM → fallback `Sin_Clasificar`
- **Dominios genéricos NO matchean regla**: gmail, hotmail, outlook personal, yahoo, icloud, me, live
- **Normalización de asunto**: bucle eliminando prefijos Re:/RV:/Fwd:/FW:/Ref:/AW:/TR:, lower, NFD diacritics
- **Subtipos de cliente**: Con_Cliente / Con_Admin / Con_Proveedor / Informativo según keywords admin

---

## 10. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Verificación Google OAuth tarda meses | Alta | Alto | Empezar trámite en Fase 0. Tener IMAP genérico como fallback en SaaS si Gmail OAuth no aprueba a tiempo |
| Microsoft revoca scope `IMAP.AccessAsUser.All` | Media | Alto | Plan B: Microsoft Graph API (REST en vez de IMAP) — más cambios pero más futuro |
| Costes LLM en SaaS Pro descontrolados | Media | Medio | Quotas por org en middleware. Modelos cloud por defecto solo en Pro. Free tier solo BYOK |
| Better Auth aún inmaduro (v1.0 reciente) | Media | Medio | Fallback Auth.js v5. Aislar la capa de auth detrás de interfaz para poder swappear |
| Competidor copia el ángulo "open source + multi-LLM" | Alta | Bajo | AGPL protege contra clones SaaS. Comunidad+brand son moats reales |
| 3-4 meses no son suficientes (1 dev) | Media | Alto | Scope estricto v1 (sin búsqueda semántica, sin bulk, sin briefing). Cortar features antes que calidad |
| Burnout del único developer | Media | Alto | Sprints de 2 semanas con review explícito. Construir en público (motiva) |

---

## 11. Verificación / Criterios de éxito MVP

**Funcional** (al final de Fase 6):
- [ ] Un usuario puede registrarse, conectar su Gmail/Outlook/IMAP, configurar un LLM, y ver emails clasificados en <2 minutos
- [ ] El sistema clasifica >80% de emails correctamente en pruebas con buzón real (Jonatan)
- [ ] Genera borradores en estilo del usuario que él aprueba sin editar en >50% de casos
- [ ] `docker compose up` levanta el stack completo en <60 segundos
- [ ] Tests unitarios con coverage ≥80% en `packages/core/`
- [ ] CI verde en main: lint + tests + docker build

**Métricas SaaS** (1 mes post-launch):
- 100 signups en GitHub stars (proxy de interés OSS)
- 20 usuarios reales en el SaaS
- 2-3 usuarios pasan a Pro

**Métricas técnicas**:
- p95 de un ciclo de procesamiento <30s (20 emails)
- Errores en producción <0.1% de requests
- Time-to-first-classification post-OAuth <90s

---

## 12. Pendientes para empezar (acciones del usuario antes de Fase 0)

1. **Verificar disponibilidad de dominio** `mailflow.app` o similar (`mailflow.io`, `mailflow.dev`, `getmailflow.com`)
2. **Crear cuentas**:
   - Azure AD App Registration (gratis) → obtener `client_id` para M365
   - Google Cloud Console → Gmail API enabled → OAuth consent screen + `client_id` + verificación
   - Stripe (modo test inicial)
   - GitHub org (si quieres separarlo de tu cuenta personal)
3. **Decidir hosting SaaS** (Fly.io, Railway, AWS, Hetzner Cloud) — afecta a Fase 5 y a costes recurrentes
4. **Aceptar limpieza del proyecto actual**:
   - El `TECHNICAL_INVESTIGATION.md` que un agente escribió en el proyecto antiguo durante este plan se borra junto con el resto al hacer wipe

---

## 13. Anexo — Crítica de la recomendación "Cipher"

El análisis técnico recomendó "Cipher" como nombre. Se descartó porque:
- Connotaciones de cifrado/seguridad, no de email/IA
- Tienes una familia de proyectos con sufijo `-Flow` (PromptFlow, MeetFlow) y `MailFlow` mantiene coherencia de marca
- "Flow" evoca productividad, claridad, no fricción — perfecto para email assistant

**Decisión**: **MailFlow** (sin "Pro").

---

## 14. Próximos pasos inmediatos (tras aprobación de este plan)

1. Verificar dominio + crear repo + LICENSE AGPL-3.0
2. Setup monorepo (pnpm + uv + Turborepo)
3. CI base con un "hello world" por app
4. Empezar Fase 1: portar `EmailProvider` + `ImapGenericProvider` + tests con fixtures heredadas
5. En paralelo: trámite OAuth Google y Azure
