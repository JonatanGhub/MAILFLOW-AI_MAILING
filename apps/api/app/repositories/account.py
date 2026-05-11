"""AccountRepository stub — full implementation in Task 5 (fase2a-db-worker)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_cycle(self, account_id: UUID, now: datetime) -> bool:
        raise NotImplementedError

    async def get_full_config(self, account_id: UUID) -> tuple:
        raise NotImplementedError

    async def get_accounts_due(self, now: datetime) -> list:
        raise NotImplementedError
