"""Base declarativa + helper uuid_pk para todos los modelos SQLAlchemy."""
from __future__ import annotations

import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> MappedColumn:
    """Primary key UUID generado en Python (no en DB) para consistencia."""
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
