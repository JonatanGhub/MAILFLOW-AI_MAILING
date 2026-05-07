"""ARQ worker entry point."""
from __future__ import annotations

import logging
import os

log = logging.getLogger("mailflow.worker")


async def process_account_cycle(ctx: dict, account_id: str) -> dict:
    """Process one classification+draft cycle for a single email account.

    This is the main ARQ job. The full implementation comes in Phase 2.

    Args:
        ctx: ARQ context (contains redis connection, settings, etc.)
        account_id: UUID of the email account to process.

    Returns:
        dict with keys: account_id, emails_processed, drafts_saved, errors
    """
    log.info("Starting cycle for account %s", account_id)
    # TODO Phase 2: load account config, create provider, run classification loop
    return {
        "account_id": account_id,
        "emails_processed": 0,
        "drafts_saved": 0,
        "errors": [],
    }


class WorkerSettings:
    """ARQ worker settings."""

    redis_settings_from_env = True
    functions = [process_account_cycle]
    queue_name = "mailflow:default"

    @classmethod
    def get_redis_url(cls) -> str:
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")
