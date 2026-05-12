"""Smoke tests: todos los modelos importan y están registrados en Base.metadata."""


def test_all_tables_registered():
    from app.models import Base

    expected = {
        "organizations",
        "llm_providers",
        "email_accounts",
        "domain_rules",
        "keyword_rules",
        "internal_domains",
        "processed_emails",
        "audit_log",
    }
    assert expected == set(Base.metadata.tables.keys())


def test_email_account_has_llm_provider_relationship():
    from app.models.email_account import EmailAccount

    assert hasattr(EmailAccount, "llm_provider")


def test_keyword_rule_has_array_column():
    from app.models.rules import KeywordRule
    from sqlalchemy.dialects.postgresql import ARRAY

    col = KeywordRule.__table__.c["keywords"]
    assert isinstance(col.type, ARRAY)
