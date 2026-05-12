"""AccountRepository — consultas de cuentas de email y config completa."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from mailflow_core.classification.rule_engine import (
    AccountConfig,
)
from mailflow_core.classification.rule_engine import (
    DomainRule as CoreDomainRule,
)
from mailflow_core.classification.rule_engine import (
    KeywordRule as CoreKeywordRule,
)
from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.models.rules import DomainRule as DbDomainRule
from app.models.rules import InternalDomain
from app.models.rules import KeywordRule as DbKeywordRule


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _due_condition(self, now: datetime):
        """WHERE clause compartida: cuenta activa cuyo intervalo ya venció."""
        interval_expr = EmailAccount.interval_minutes * text("INTERVAL '1 minute'")
        return or_(
            EmailAccount.last_cycle_at.is_(None),
            EmailAccount.last_cycle_at + interval_expr <= now,
        )

    async def get_accounts_due(self, now: datetime) -> list[EmailAccount]:
        """Retorna cuentas activas cuyo ciclo toca según interval_minutes."""
        stmt = select(EmailAccount).where(
            EmailAccount.is_active.is_(True),
            self._due_condition(now),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def claim_cycle(self, account_id: UUID, now: datetime) -> bool:
        """Atomic UPDATE: marca last_cycle_at=now solo si el ciclo sigue elegible.

        Retorna True si esta instancia ganó la carrera; False si otro worker
        se adelantó (TOCTOU guard).
        """
        interval_expr = EmailAccount.interval_minutes * text("INTERVAL '1 minute'")
        stmt = (
            update(EmailAccount)
            .where(
                EmailAccount.id == account_id,
                EmailAccount.is_active.is_(True),
                or_(
                    EmailAccount.last_cycle_at.is_(None),
                    EmailAccount.last_cycle_at + interval_expr <= now,
                ),
            )
            .values(last_cycle_at=now)
            .returning(EmailAccount.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one_or_none() is not None

    async def get_full_config(
        self, account_id: UUID
    ) -> tuple[EmailAccount, AccountConfig, LLMProvider | None]:
        """Carga account + reglas + llm_provider en queries eficientes.

        COLISIÓN DE NOMBRES: DbDomainRule/DbKeywordRule = modelos SQLAlchemy.
        CoreDomainRule/CoreKeywordRule = dataclasses de packages/core.
        """
        # 1. Account + llm_provider (eager load con selectinload)
        stmt = (
            select(EmailAccount)
            .options(selectinload(EmailAccount.llm_provider))
            .where(EmailAccount.id == account_id)
        )
        account = (await self._session.execute(stmt)).scalar_one()

        # 2. domain_rules ORDER BY priority ASC
        db_domain = list(
            (
                await self._session.execute(
                    select(DbDomainRule)
                    .where(DbDomainRule.account_id == account_id)
                    .order_by(DbDomainRule.priority)
                )
            ).scalars()
        )

        # 3. keyword_rules ORDER BY priority ASC
        db_kw = list(
            (
                await self._session.execute(
                    select(DbKeywordRule)
                    .where(DbKeywordRule.account_id == account_id)
                    .order_by(DbKeywordRule.priority)
                )
            ).scalars()
        )

        # 4. internal_domains
        db_int = list(
            (
                await self._session.execute(
                    select(InternalDomain).where(
                        InternalDomain.account_id == account_id
                    )
                )
            ).scalars()
        )

        # 5. Construir AccountConfig de packages/core
        account_config = AccountConfig(
            account_id=str(account_id),
            internal_domains=[d.domain for d in db_int],
            client_domain_rules=[
                CoreDomainRule(domain=r.domain, label=r.label, rule_id=r.rule_id)
                for r in db_domain
            ],
            keyword_rules=[
                CoreKeywordRule(
                    keywords=tuple(r.keywords),
                    label=r.label,
                    rule_id=r.rule_id,
                    match_all=r.match_all,
                )
                for r in db_kw
            ],
        )

        return account, account_config, account.llm_provider
