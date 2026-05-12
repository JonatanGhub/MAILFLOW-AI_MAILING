"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    # 2. llm_providers (referencia organizations)
    op.create_table(
        "llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("encrypted_api_key", sa.String, nullable=True),
        sa.Column("default_classification_model", sa.String(200), nullable=False),
        sa.Column("default_generation_model", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3. email_accounts (referencia organizations + llm_providers)
    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_type", sa.String(20), nullable=False, server_default="imap"),
        sa.Column("imap_host", sa.String(255), nullable=False),
        sa.Column("imap_port", sa.Integer, nullable=False, server_default="993"),
        sa.Column("use_ssl", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("encrypted_credentials", sa.String, nullable=False),
        sa.Column("inbox_folder", sa.String(255), nullable=False, server_default="INBOX"),
        sa.Column(
            "unclassified_folder",
            sa.String(255),
            nullable=False,
            server_default="Sin_Clasificar",
        ),
        sa.Column("drafts_folder", sa.String(255), nullable=False, server_default="Drafts"),
        sa.Column("interval_minutes", sa.Integer, nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_cycle_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "llm_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_providers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 4. domain_rules
    op.create_table(
        "domain_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
    )

    # 5. keyword_rules
    op.create_table(
        "keyword_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keywords", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("match_all", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
    )

    # 6. internal_domains
    op.create_table(
        "internal_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(255), nullable=False),
    )

    # 7. audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("emails_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("drafts_saved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_detail", sa.String, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 8. processed_emails (referencia email_accounts + audit_log.cycle_id)
    op.create_table(
        "processed_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uid", sa.BigInteger, nullable=False),
        sa.Column("folder", sa.String(255), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.String(500), nullable=True),
        sa.Column("from_email", sa.String(500), nullable=False),
        sa.Column("subject", sa.String, nullable=False, server_default=""),
        sa.Column("destination_folder", sa.String(255), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("draft_saved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_log.cycle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "account_id", "uid", "uidvalidity", name="uq_processed_email"
        ),
    )
    op.create_index(
        "ix_processed_email_msg_id",
        "processed_emails",
        ["account_id", "message_id"],
    )


def downgrade() -> None:
    op.drop_table("processed_emails")
    op.drop_table("audit_log")
    op.drop_table("internal_domains")
    op.drop_table("keyword_rules")
    op.drop_table("domain_rules")
    op.drop_table("email_accounts")
    op.drop_table("llm_providers")
    op.drop_table("organizations")
