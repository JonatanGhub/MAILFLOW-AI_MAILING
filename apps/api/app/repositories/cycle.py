"""CycleRepository stub — full implementation in Task 6 (fase2a-db-worker)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class CycleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_audit_log(self, account_id: UUID, cycle_id: UUID) -> None:
        raise NotImplementedError

    async def finalize_audit_log(
        self,
        cycle_id: UUID,
        *,
        emails: int,
        drafts: int,
        errors: int,
        error_detail: str | None,
        duration_ms: int,
    ) -> None:
        raise NotImplementedError

    async def find_thread_folder(self, account_id: UUID, in_reply_to: str) -> str | None:
        raise NotImplementedError

    async def insert_processed(
        self,
        *,
        account_id: UUID,
        uid: int,
        folder: str,
        uidvalidity: int,
        message_id: str,
        from_email: str,
        subject: str,
        destination_folder: str,
        method: str,
        confidence: float,
        draft_saved: bool,
        cycle_id: UUID,
    ) -> None:
        raise NotImplementedError
