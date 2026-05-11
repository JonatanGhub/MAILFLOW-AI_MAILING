"""Fixtures compartidas para tests de apps/api.

Para tests de repositorios se necesita Postgres corriendo (Docker).
Arrancar con:
  docker compose -f infrastructure/docker-compose.dev.yml up -d postgres
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow_test"


@pytest.fixture(scope="session")
async def db_engine():
    """Engine de test: crea todas las tablas al inicio, las borra al final."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def session(db_engine) -> AsyncSession:
    """Sesión de test con rollback automático — cada test arranca con DB limpia."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture()
def session_factory(db_engine):
    """async_sessionmaker real apuntando a mailflow_test."""
    return async_sessionmaker(db_engine, expire_on_commit=False)
