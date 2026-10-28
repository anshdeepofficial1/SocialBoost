"""One-time, non-destructive SQLite-to-PostgreSQL migration.

Use this only if you have a copy of the old SQLite file. The script never deletes
or modifies the source file, refuses to write into a non-empty target database,
preserves primary keys where the current schema still has the same columns, and
prints row counts without printing connection credentials.

Example:
  DATABASE_URL='postgresql://...' python backend/scripts/migrate_sqlite_to_postgres.py /path/to/socialboost.db
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select, func

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy SocialBoost SQLite data into a PostgreSQL database.")
    parser.add_argument("sqlite_file", help="Path to a backup/copy of the old socialboost.db file.")
    parser.add_argument("--dry-run", action="store_true", help="Report source row counts without inserting data.")
    args = parser.parse_args()

    source_path = Path(args.sqlite_file).expanduser().resolve()
    if not source_path.is_file():
        parser.error("The SQLite file does not exist. This script cannot recover a database that Render has already discarded.")

    target_url = (os.getenv("DATABASE_URL") or os.getenv("TARGET_DATABASE_URL") or "").strip()
    if not target_url:
        parser.error("Set DATABASE_URL to the hosted PostgreSQL connection URL before running the migration.")
    if target_url.startswith("sqlite"):
        parser.error("DATABASE_URL must point to PostgreSQL, not SQLite.")

    from app.core.config import normalize_database_url
    from app import models  # noqa: F401 - register all ORM models
    from app.db.session import Base

    target_url = normalize_database_url(target_url)
    source_url = "sqlite:///" + str(source_path)
    source_engine = create_engine(source_url, connect_args={"check_same_thread": False, "timeout": 30})
    target_engine = create_engine(target_url, pool_pre_ping=True, pool_recycle=300)

    try:
        source_tables = set(inspect(source_engine).get_table_names())
        model_tables = [table for table in Base.metadata.sorted_tables if table.name in source_tables]
        if not model_tables:
            raise RuntimeError("No SocialBoost application tables were found in that SQLite file.")

        # Never merge or overwrite a database silently. Configure a fresh
        # Postgres database, or make a deliberate backup and plan separately.
        target_existing = set(inspect(target_engine).get_table_names())
        for table in model_tables:
            if table.name in target_existing:
                count = target_engine.connect().execute(select(func.count()).select_from(table)).scalar_one()
                if count:
                    raise RuntimeError(
                        "The target PostgreSQL database already contains rows in application tables. "
                        "Migration stopped without inserting anything."
                    )

        counts: dict[str, int] = {}
        source_meta = MetaData()
        reflected: dict[str, Table] = {}
        with source_engine.connect() as source_conn:
            for table in model_tables:
                src_table = Table(table.name, source_meta, autoload_with=source_engine)
                reflected[table.name] = src_table
                counts[table.name] = source_conn.execute(
                    select(func.count()).select_from(src_table)
                ).scalar_one()

        print("Source database:", source_path.name)
        print("Tables with rows:", sum(1 for count in counts.values() if count))
        print("Rows to copy:", sum(counts.values()))
        for name, count in counts.items():
            if count:
                print(f"  {name}: {count}")
        if args.dry_run:
            return 0

        Base.metadata.create_all(bind=target_engine)
        with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for target_table in model_tables:
                src_table = reflected[target_table.name]
                common = [column.name for column in target_table.columns if column.name in src_table.c]
                if not common or counts[target_table.name] == 0:
                    continue
                statement = select(*(src_table.c[name] for name in common))
                result = source_conn.execute(statement).mappings()
                batch: list[dict] = []
                for row in result:
                    batch.append({name: row[name] for name in common})
                    if len(batch) >= 250:
                        target_conn.execute(target_table.insert(), batch)
                        batch.clear()
                if batch:
                    target_conn.execute(target_table.insert(), batch)

            for table in model_tables:
                migrated = target_conn.execute(
                    select(func.count()).select_from(table)
                ).scalar_one()
                expected = counts[table.name]
                if migrated != expected:
                    raise RuntimeError(
                        f"Post-migration count mismatch for {table.name}: expected {expected}, got {migrated}."
                    )

        print("Migration completed and row counts verified. The source SQLite file was not changed.")
        print("Keep the existing production SECRET_KEY unchanged so saved login tokens and encrypted OAuth credentials remain readable.")
        return 0
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
