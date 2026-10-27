"""Additive, idempotent schema maintenance for SQLite development databases.

``Base.metadata.create_all`` creates missing tables but never alters existing
ones. This module brings an existing development database up to the current
models without requiring a manual reset:

* missing columns are added;
* a column that the models allow to be NULL is rebuilt to drop a stale
  ``NOT NULL`` constraint (SQLite cannot ALTER that in place);
* rows created before workspace ownership existed are backfilled.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable

from .session import Base, engine

# Importing the models registers their tables on Base.metadata. ensure_schema is
# often called before any other module has touched them, so do it here too.
from .. import models  # noqa: F401,E402

log = logging.getLogger("socialboost.schema")

# table -> {column_name: SQLite column definition}
_REQUIRED_COLUMNS: dict[str, dict[str, str]] = {
    "predictions": {"workspace_id": "VARCHAR"},
    "drafts": {"workspace_id": "VARCHAR"},
    "model_versions": {"workspace_id": "VARCHAR"},
    "social_accounts": {"credential_ref": "VARCHAR"},
}


def _sqlite_type_sql(column) -> str:
    try:
        return column.type.compile(engine.dialect)
    except Exception:
        return "VARCHAR"


def _rebuild_table(table_name: str) -> None:
    """Recreate a table from the model definition, preserving its rows."""
    table = Base.metadata.tables[table_name]
    tmp = f"{table_name}__rebuild"
    ddl = str(CreateTable(table).compile(engine))
    ddl = ddl.replace(f"CREATE TABLE {table_name} ", f"CREATE TABLE {tmp} ", 1)

    columns = [c.name for c in table.columns]
    column_list = ", ".join(f'"{c}"' for c in columns)

    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{tmp}"'))
        conn.execute(text(ddl))
        conn.execute(
            text(f'INSERT INTO "{tmp}" ({column_list}) SELECT {column_list} FROM "{table_name}"')
        )
        conn.execute(text(f'DROP TABLE "{table_name}"'))
        conn.execute(text(f'ALTER TABLE "{tmp}" RENAME TO "{table_name}"'))


def _has_unknown_columns(table_name: str, inspector) -> bool:
    """True when the database has a column the models do not declare.

    A rebuild only copies model columns, so rebuilding such a table would
    silently drop data. In that case we leave the table alone and log instead.
    """
    table = Base.metadata.tables[table_name]
    model_columns = {c.name for c in table.columns}
    db_columns = {c["name"] for c in inspector.get_columns(table_name)}
    return bool(db_columns - model_columns)


def _stale_not_null(table_name: str, inspector) -> list[str]:
    """Columns that the model allows NULL but the database still forbids."""
    if table_name not in Base.metadata.tables:
        return []
    table = Base.metadata.tables[table_name]
    db_columns = {c["name"]: c for c in inspector.get_columns(table_name)}
    stale = []
    for column in table.columns:
        info = db_columns.get(column.name)
        if info is None:
            continue
        if column.nullable and not info.get("nullable", True):
            stale.append(column.name)
    return stale


def ensure_schema() -> list[str]:
    """Create missing tables, add missing columns, relax stale constraints."""
    changes: list[str] = []
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    existing_tables = set(inspector.get_table_names())

    for table, columns in _REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        for column, ddl in columns.items():
            if column in present:
                continue
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl}'))
            changes.append(f"{table}.{column} added")
            log.info("added column %s.%s", table, column)

    # Any column declared on a model but missing from an existing table.
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        # A fresh inspector per table: SQLAlchemy caches get_columns results.
        present = {c["name"] for c in inspect(engine).get_columns(table_name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = column.name + " " + _sqlite_type_sql(column)
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {ddl}'))
            changes.append(f"{table_name}.{column.name} added")
            log.info("added column %s.%s", table_name, column.name)

    # Relax stale NOT NULL constraints by rebuilding the table.
    for table_name in list(Base.metadata.tables):
        if table_name not in existing_tables:
            continue
        table_inspector = inspect(engine)
        stale = _stale_not_null(table_name, table_inspector)
        if not stale:
            continue
        if _has_unknown_columns(table_name, table_inspector):
            log.warning(
                "skipping rebuild of %s: it has columns the models do not declare", table_name
            )
            continue
        _rebuild_table(table_name)
        changes.append(f"{table_name} rebuilt (nullable: {', '.join(stale)})")
        log.info("rebuilt %s to relax %s", table_name, ", ".join(stale))

    # Backfill workspace ownership for rows created before the column existed.
    for table_name in ("predictions", "drafts"):
        if table_name not in existing_tables:
            continue
        with engine.begin() as conn:
            result = conn.execute(text(
                f'UPDATE "{table_name}" SET workspace_id = ('
                f'  SELECT v.workspace_id FROM videos v WHERE v.id = "{table_name}".video_id'
                f') WHERE workspace_id IS NULL AND video_id IS NOT NULL '
                f'AND EXISTS (SELECT 1 FROM videos v WHERE v.id = "{table_name}".video_id)'
            ))
            if result.rowcount:
                changes.append(f"{table_name}.workspace_id backfilled ({result.rowcount})")

    return changes
