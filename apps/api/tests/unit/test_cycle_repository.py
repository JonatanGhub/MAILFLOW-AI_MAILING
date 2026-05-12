"""Tests de CycleRepository con Postgres real."""
from __future__ import annotations

from uuid import uuid4

import pytest
from app.crypto import encrypt
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.repositories.cycle import CycleRepository

TEST_SECRET_KEY = "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs="


@pytest.fixture()
async def org(session):
    o = Organization(name="Org", slug=f"org-{uuid4().hex[:8]}")
    session.add(o)
    await session.commit()
    return o


@pytest.fixture()
async def account(session, org):
    acc = EmailAccount(
        org_id=org.id,
        imap_host="localhost",
        imap_port=1143,
        use_ssl=False,
        username="test",
        encrypted_credentials=encrypt({"password": "pw"}, TEST_SECRET_KEY),
    )
    session.add(acc)
    await session.commit()
    return acc


async def test_create_audit_log(session, account):
    repo = CycleRepository(session)
    cycle_id = uuid4()
    log = await repo.create_audit_log(account.id, cycle_id)
    await session.commit()

    assert log.cycle_id == cycle_id
    assert log.account_id == account.id
    assert log.finalized_at is None
    assert log.emails_processed == 0


async def test_finalize_audit_log(session, account):
    cycle_id = uuid4()
    repo = CycleRepository(session)
    await repo.create_audit_log(account.id, cycle_id)
    await session.commit()

    await repo.finalize_audit_log(
        cycle_id, emails=3, drafts=1, errors=0,
        error_detail=None, duration_ms=1500,
    )
    await session.commit()

    from sqlalchemy import select
    log = (
        await session.execute(select(AuditLog).where(AuditLog.cycle_id == cycle_id))
    ).scalar_one()
    assert log.emails_processed == 3
    assert log.drafts_saved == 1
    assert log.duration_ms == 1500
    assert log.finalized_at is not None


async def test_insert_processed_idempotent(session, account):
    cycle_id = uuid4()
    session.add(AuditLog(account_id=account.id, cycle_id=cycle_id))
    await session.commit()

    repo = CycleRepository(session)
    kwargs = dict(
        account_id=account.id, uid=42, folder="INBOX", uidvalidity=1000,
        message_id="<msg@test>", from_email="a@b.com", subject="Hi",
        destination_folder="Clients/B", method="domain_client", confidence=0.95,
        draft_saved=False, cycle_id=cycle_id,
    )
    await repo.insert_processed(**kwargs)
    await session.commit()
    # Segunda inserción idempotente (ON CONFLICT DO NOTHING)
    await repo.insert_processed(**kwargs)
    await session.commit()

    from app.models.processed_email import ProcessedEmail
    from sqlalchemy import func, select
    count = (
        await session.execute(
            select(func.count()).where(ProcessedEmail.account_id == account.id)
        )
    ).scalar_one()
    assert count == 1


async def test_find_thread_folder_returns_folder(session, account):
    cycle_id = uuid4()
    session.add(AuditLog(account_id=account.id, cycle_id=cycle_id))
    await session.commit()

    repo = CycleRepository(session)
    await repo.insert_processed(
        account_id=account.id, uid=10, folder="INBOX", uidvalidity=999,
        message_id="<original@test>", from_email="x@y.com", subject="Orig",
        destination_folder="Clients/X", method="domain_client", confidence=0.95,
        draft_saved=False, cycle_id=cycle_id,
    )
    await session.commit()

    result = await repo.find_thread_folder(account.id, "<original@test>")
    assert result == "Clients/X"


async def test_find_thread_folder_returns_none_if_not_found(session, account):
    repo = CycleRepository(session)
    result = await repo.find_thread_folder(account.id, "<nonexistent@test>")
    assert result is None
