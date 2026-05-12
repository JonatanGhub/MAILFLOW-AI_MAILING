"""Test de integración: ciclo completo con Greenmail (IMAP real) + Postgres real.

El test NO usa LLM — la cuenta no tiene llm_provider configurado,
por lo que no se generan borradores. Se verifica:
  - Email clasificado por domain_client rule
  - processed_emails: 1 registro con method="domain_client"
  - audit_log: finalized_at NOT NULL
  - Greenmail: email movido a la carpeta destino
"""
from __future__ import annotations

import imaplib
import smtplib
import time
from email.mime.text import MIMEText
from uuid import uuid4

import pytest
from app.crypto import encrypt
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.models.processed_email import ProcessedEmail
from app.models.rules import DomainRule as DbDomainRule
from app.services.cycle import CycleService
from sqlalchemy import select

# Credenciales Greenmail de docker-compose.dev.yml
GREENMAIL_HOST = "localhost"
GREENMAIL_IMAP_PORT = 3143
GREENMAIL_SMTP_PORT = 3025
GREENMAIL_USER = "test"
GREENMAIL_PASS = "password"
GREENMAIL_EMAIL = "test@localhost"

# Fernet key válida de 44 chars (igual al .env de dev)
_TEST_SECRET_KEY = "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs="


@pytest.fixture()
async def full_account(session):
    """Crea Organization + EmailAccount con DomainRule para external.com."""
    org = Organization(name="IntegrationOrg", slug=f"int-{uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    acc = EmailAccount(
        org_id=org.id,
        imap_host=GREENMAIL_HOST,
        imap_port=GREENMAIL_IMAP_PORT,
        use_ssl=False,
        username=GREENMAIL_USER,
        encrypted_credentials=encrypt({"password": GREENMAIL_PASS}, _TEST_SECRET_KEY),
        inbox_folder="INBOX",
        unclassified_folder="Sin_Clasificar",
        is_active=True,
        interval_minutes=5,
    )
    session.add(acc)
    await session.flush()

    rule = DbDomainRule(
        account_id=acc.id,
        domain="external.com",
        label="Clients/External",
        rule_id="r-ext",
        priority=0,
    )
    session.add(rule)
    await session.commit()
    return acc


def _send_test_email(subject: str = "Integration test") -> None:
    """Envía un email a test@localhost vía SMTP Greenmail."""
    msg = MIMEText("This is a test email from external.com")
    msg["Subject"] = subject
    msg["From"] = "sender@external.com"
    msg["To"] = GREENMAIL_EMAIL
    with smtplib.SMTP(GREENMAIL_HOST, GREENMAIL_SMTP_PORT) as smtp:
        smtp.sendmail("sender@external.com", [GREENMAIL_EMAIL], msg.as_bytes())
    # Greenmail necesita un momento para entregar el mensaje
    time.sleep(0.5)


def _get_imap_folder_uids(folder: str) -> list[str]:
    """Devuelve los UIDs de mensajes en la carpeta IMAP especificada."""
    client = imaplib.IMAP4(GREENMAIL_HOST, GREENMAIL_IMAP_PORT)
    client.login(GREENMAIL_USER, GREENMAIL_PASS)
    status, _ = client.select(folder)
    if status != "OK":
        client.logout()
        return []
    _, data = client.uid("SEARCH", "ALL")
    client.logout()
    raw = data[0].decode() if data[0] else ""
    return raw.split() if raw.strip() else []


@pytest.mark.integration
async def test_full_cycle_classifies_and_moves_email(session, session_factory, full_account):
    """Ciclo completo: email → classify → move → audit_log finalizado."""
    # 1. Enviar email desde external.com
    _send_test_email("Invoice inquiry")

    # 2. Parchear settings para que CycleService use la clave de test
    import app.services.cycle as cycle_module

    original_settings = cycle_module.settings

    class _FakeSettings:
        SECRET_KEY = _TEST_SECRET_KEY
        DATABASE_URL = original_settings.DATABASE_URL
        REDIS_URL = original_settings.REDIS_URL

    cycle_module.settings = _FakeSettings()
    try:
        service = CycleService(session_factory)
        result = await service.run(full_account.id)
    finally:
        cycle_module.settings = original_settings

    # 3. Resultado básico
    assert result.emails_processed >= 1
    assert result.errors == 0

    # 4. processed_emails en DB
    records = list(
        (
            await session.execute(
                select(ProcessedEmail).where(ProcessedEmail.account_id == full_account.id)
            )
        ).scalars()
    )
    assert len(records) >= 1
    rec = records[0]
    assert rec.destination_folder == "Clients/External"
    assert rec.method == "domain_client"

    # 5. audit_log finalizado
    log_row = (
        await session.execute(
            select(AuditLog).where(AuditLog.cycle_id == result.cycle_id)
        )
    ).scalar_one()
    assert log_row.finalized_at is not None
    assert log_row.emails_processed >= 1

    # 6. Email movido en Greenmail (Greenmail tarda un poco)
    time.sleep(0.5)
    uids_in_dest = _get_imap_folder_uids("Clients/External")
    assert len(uids_in_dest) >= 1
