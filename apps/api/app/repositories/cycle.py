"""CycleRepository — audit_log y processed_emails."""
from __future__ import annotations

from datetime import UTC, datetime
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
                finalized_at=datetime.now(tz=UTC),
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
