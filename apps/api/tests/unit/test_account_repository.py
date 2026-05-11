"""Tests de AccountRepository con Postgres real.

Requiere: docker compose up -d postgres
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.organization import Organization
from app.models.email_account import EmailAccount
from app.models.rules import DomainRule as DbDomainRule, KeywordRule as DbKeywordRule, InternalDomain
from app.repositories.account import AccountRepository
from mailflow_core.classification.rule_engine import AccountConfig

# Fernet key válida (44 chars base64)
TEST_SECRET_KEY = "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs="


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
async def org(session):
    o = Organization(name="Test Org", slug=f"test-{uuid4().hex[:8]}")
    session.add(o)
    await session.commit()
    return o


@pytest.fixture()
async def account(session, org):
    from app.crypto import encrypt
    acc = EmailAccount(
        org_id=org.id,
        imap_host="localhost",
        imap_port=1143,
        use_ssl=False,
        username="test",
        encrypted_credentials=encrypt({"password": "pw"}, TEST_SECRET_KEY),
        interval_minutes=5,
    )
    session.add(acc)
    await session.commit()
    return acc


# ── Tests get_accounts_due ───────────────────────────────────────────────────

async def test_get_accounts_due_includes_never_run(session, account):
    repo = AccountRepository(session)
    now = datetime.now(tz=timezone.utc)
    result = await repo.get_accounts_due(now)
    ids = [a.id for a in result]
    assert account.id in ids


async def test_get_accounts_due_includes_overdue(session, account):
    # last_cycle_at hace 10 min, interval=5 → debe estar en la lista
    account.last_cycle_at = datetime.now(tz=timezone.utc) - timedelta(minutes=10)
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id in [a.id for a in result]


async def test_get_accounts_due_excludes_recent(session, account):
    # last_cycle_at hace 2 min, interval=5 → NO debe estar
    account.last_cycle_at = datetime.now(tz=timezone.utc) - timedelta(minutes=2)
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id not in [a.id for a in result]


async def test_get_accounts_due_excludes_inactive(session, account):
    account.is_active = False
    await session.commit()

    repo = AccountRepository(session)
    result = await repo.get_accounts_due(datetime.now(tz=timezone.utc))
    assert account.id not in [a.id for a in result]


# ── Tests claim_cycle ────────────────────────────────────────────────────────

async def test_claim_cycle_returns_true_first_call(session, account):
    repo = AccountRepository(session)
    now = datetime.now(tz=timezone.utc)
    won = await repo.claim_cycle(account.id, now)
    assert won is True


async def test_claim_cycle_returns_false_second_call(session_factory, account):
    """Dos workers intentan claim al mismo tiempo → solo uno gana."""
    now = datetime.now(tz=timezone.utc)
    async with session_factory() as s1:
        won1 = await AccountRepository(s1).claim_cycle(account.id, now)
        await s1.commit()
    async with session_factory() as s2:
        # last_cycle_at ya fue marcado por s1 → s2 no gana
        won2 = await AccountRepository(s2).claim_cycle(account.id, now)
    assert won1 is True
    assert won2 is False


# ── Tests get_full_config ────────────────────────────────────────────────────

async def test_get_full_config_builds_account_config(session, account):
    # Insertar reglas
    session.add(DbDomainRule(
        account_id=account.id,
        domain="client.com", label="Clients/Client", rule_id="r1", priority=0,
    ))
    session.add(DbKeywordRule(
        account_id=account.id,
        keywords=["urgent", "ASAP"], label="Urgent", rule_id="r2", match_all=False, priority=1,
    ))
    session.add(InternalDomain(account_id=account.id, domain="company.com"))
    await session.commit()

    repo = AccountRepository(session)
    acc_model, config, llm_prov = await repo.get_full_config(account.id)

    assert isinstance(config, AccountConfig)
    assert config.account_id == str(account.id)
    assert "company.com" in config.internal_domains
    assert len(config.client_domain_rules) == 1
    assert config.client_domain_rules[0].domain == "client.com"
    assert len(config.keyword_rules) == 1
    assert config.keyword_rules[0].keywords == ("urgent", "ASAP")
    assert llm_prov is None  # no llm_provider configurado
