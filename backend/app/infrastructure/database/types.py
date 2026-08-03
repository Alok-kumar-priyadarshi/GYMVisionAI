# file_name: types.py

"""Portable column types.

``docs/07_database/38_IDENTIFIER_STRATEGY.md`` section 5 requires identifiers to
use PostgreSQL's native ``UUID`` type and never plain text. PostgreSQL is the
production database, but the test suite runs on SQLite, which has neither native
UUID nor JSONB.

These decorators use the native PostgreSQL type when the dialect supports it and
fall back to a portable representation otherwise. Production still gets a real
``UUID`` column; tests still exercise the real mapping code.
"""

import uuid
from typing import Any

from sqlalchemy import CHAR, JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID


class GUID(TypeDecorator):
    """A UUID column, native on PostgreSQL and 36-character text elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgresUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class JSONColumn(TypeDecorator):
    """A JSON column, ``JSONB`` on PostgreSQL and ``JSON`` elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class StringList(TypeDecorator):
    """A list of short strings, stored as JSON.

    Used for muscle lists, instructions and feedback, which are read as a whole
    and never queried element by element.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return [str(item) for item in value]

    def process_result_value(self, value: Any, dialect: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(value)
