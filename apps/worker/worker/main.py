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
