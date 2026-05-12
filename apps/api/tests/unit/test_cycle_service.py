"""Tests unitarios de CycleService — todo mockeado (sin DB ni IMAP real)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from mailflow_core.classification.rule_engine import AccountConfig
from mailflow_core.providers.base import EmailData

ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_sf(session=None):
    """Mock session factory que siempre devuelve la misma sesión mock."""
    if session is None:
        session = AsyncMock()

    @asynccontextmanager
    async def sf():
        yield session

    return sf


def make_email(uid: int = 42, in_reply_to: str | None = None) -> EmailData:
    return EmailData(
        uid=uid,
        message_id=f"<msg-{uid}@test>",
        subject="Test subject",
        from_email="sender@external.com",
        to_emails=["worker@company.com"],
        body_text="Hello, need help.",
        body_html="",
        in_reply_to=in_reply_to,
    )


def make_account():
    acc = MagicMock()
    acc.id = ACCOUNT_ID
    acc.imap_host = "localhost"
    acc.imap_port = 1143
    acc.use_ssl = False
    acc.username = "test"
    acc.encrypted_credentials = "tok"
    acc.inbox_folder = "INBOX"
    acc.unclassified_folder = "Sin_Clasificar"
    acc.drafts_folder = "Drafts"
    acc.llm_provider = None
    return acc


# ── claim_cycle → False: abort ───────────────────────────────────────────────


@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
async def test_run_aborts_when_claim_cycle_fails(MockCycleRepo, MockAccountRepo):
    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=False)

    from app.services.cycle import CycleService

    result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 0
    assert result.errors == 0
    MockAccountRepo.return_value.claim_cycle.assert_awaited_once()
    MockCycleRepo.return_value.create_audit_log.assert_not_called()


# ── IMAP connect falla ───────────────────────────────────────────────────────


@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_imap_connect_failure(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService
    from mailflow_core.exceptions import IMAPConnectionError

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    MockCycleRepo.return_value.create_audit_log = AsyncMock()
    MockCycleRepo.return_value.finalize_audit_log = AsyncMock()
    MockProvider.return_value.connect.side_effect = IMAPConnectionError("timeout")

    result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 0
    assert result.errors == 1
    MockCycleRepo.return_value.finalize_audit_log.assert_awaited_once()


# ── mark_as_processed ANTES de move_email ───────────────────────────────────


@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_mark_before_move(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    MockCycleRepo.return_value.create_audit_log = AsyncMock()
    MockCycleRepo.return_value.finalize_audit_log = AsyncMock()
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [
        make_email(uid=42)
    ]
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value=None)
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    call_order: list[str] = []
    MockProvider.return_value.mark_as_processed.side_effect = lambda uid: (
        call_order.append(f"mark:{uid}")
    )
    MockProvider.return_value.move_email.side_effect = lambda uid, dest: (
        call_order.append(f"move:{uid}")
    )

    result = await CycleService(make_sf()).run(ACCOUNT_ID)

    assert result.emails_processed == 1
    assert call_order == ["mark:42", "move:42"]


# ── Thread inheritance → method="thread" ────────────────────────────────────


@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client", return_value=None)
async def test_run_thread_inheritance(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(make_account(), AccountConfig(account_id=str(ACCOUNT_ID)), None)
    )
    MockCycleRepo.return_value.create_audit_log = AsyncMock()
    MockCycleRepo.return_value.finalize_audit_log = AsyncMock()
    # Email es reply → in_reply_to presente
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [
        make_email(uid=99, in_reply_to="<original@test>")
    ]
    # find_thread_folder devuelve carpeta previa
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value="Clients/X")
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    await CycleService(make_sf()).run(ACCOUNT_ID)

    # Verificar que insert_processed recibió method="thread"
    call_kwargs = MockCycleRepo.return_value.insert_processed.call_args.kwargs
    assert call_kwargs["method"] == "thread"
    assert call_kwargs["confidence"] == 0.95
    assert call_kwargs["destination_folder"] == "Clients/X"


# ── Draft generation → save_draft recibe bytes ──────────────────────────────


@patch("app.services.cycle.AccountRepository")
@patch("app.services.cycle.CycleRepository")
@patch("app.services.cycle.ImapGenericProvider")
@patch("app.services.cycle.decrypt", return_value={"password": "pw"})
@patch("app.services.cycle._build_llm_client")
async def test_run_draft_bytes_passed_to_save_draft(
    mock_build, mock_decrypt, MockProvider, MockCycleRepo, MockAccountRepo
):
    from app.services.cycle import CycleService

    account = make_account()
    # account con domain rule para "external.com" → method=domain_client
    from mailflow_core.classification.rule_engine import AccountConfig
    from mailflow_core.classification.rule_engine import DomainRule as CoreDomainRule

    config = AccountConfig(
        account_id=str(ACCOUNT_ID),
        client_domain_rules=[
            CoreDomainRule(domain="external.com", label="Clients/Ext", rule_id="r1")
        ],
    )

    MockAccountRepo.return_value.claim_cycle = AsyncMock(return_value=True)
    MockAccountRepo.return_value.get_full_config = AsyncMock(
        return_value=(account, config, None)
    )
    MockCycleRepo.return_value.create_audit_log = AsyncMock()
    MockCycleRepo.return_value.finalize_audit_log = AsyncMock()
    MockProvider.return_value.fetch_unprocessed_emails.return_value = [
        make_email(uid=55)
    ]
    MockCycleRepo.return_value.find_thread_folder = AsyncMock(return_value=None)
    MockCycleRepo.return_value.insert_processed = AsyncMock()

    mock_generate_client = MagicMock()
    mock_generate_client.generate_draft.return_value = (
        "Estimado cliente, gracias por su consulta."
    )
    mock_build.side_effect = [
        None,
        mock_generate_client,
    ]  # classify=None, generate=mock

    saved_bytes: list = []
    MockProvider.return_value.save_draft.side_effect = lambda b: (
        saved_bytes.append(b) or True
    )

    await CycleService(make_sf()).run(ACCOUNT_ID)

    assert len(saved_bytes) == 1
    assert isinstance(saved_bytes[0], bytes)
    # Verificar que los bytes son un email RFC2822 válido
    import email as email_module

    msg = email_module.message_from_bytes(saved_bytes[0])
    assert "Re:" in msg["Subject"]
