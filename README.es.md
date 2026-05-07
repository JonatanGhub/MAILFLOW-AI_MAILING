# MailFlow

**Asistente de email con IA de código abierto. Usa cualquier LLM. Tu bandeja de entrada, tus reglas, tu privacidad.**

MailFlow clasifica automáticamente los emails entrantes en tus carpetas IMAP y genera borradores de respuesta en tu estilo de escritura — impulsado por **cualquier LLM que elijas** (Ollama local, OpenAI, Anthropic, Gemini, vLLM, LM Studio o cualquier endpoint compatible con OpenAI).

## Inicio rápido (Self-hosted)

```bash
git clone https://github.com/JonatanGhub/mailflow.git
cd mailflow
cp .env.example .env
docker compose up
```

Abre http://localhost:3000 y conecta tu bandeja en menos de 2 minutos.

## Funcionalidades (v1)

- **Clasificación automática** — cascada determinista (dominio → hilo → palabra clave) + LLM como fallback
- **Generación de borradores** — respuestas en tu estilo, guardadas como Borradores IMAP (nunca se envían automáticamente)
- **Biblioteca de plantillas** — plantillas reutilizables con detección automática por palabras clave
- **Multi-LLM** — elige cualquier motor por espacio de trabajo: Ollama, OpenAI, Anthropic, Gemini, vLLM…
- **Aprendizaje continuo** — las correcciones y ediciones retroalimentan el sistema para mejorar sugerencias futuras
- **Dashboard web** — visualiza ciclos, estadísticas, configura reglas y plantillas

## Desarrollo

Consulta [CONTRIBUTING.md](docs/CONTRIBUTING.md) para instrucciones de configuración.

## Licencia

GNU Affero General Public License v3.0 — ver [LICENSE](LICENSE).
