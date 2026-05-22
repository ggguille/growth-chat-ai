"""
Apply:    uv run --package database python -m database.migrate
Dry run:  uv run --package database python -m database.migrate --dry-run
Rollback: uv run --package database python -m database.migrate --rollback 1
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

_PACKAGE_DIR = Path(__file__).parent.parent.parent  # data/database/
MIGRATIONS_DIR = _PACKAGE_DIR / "migrations"

load_dotenv(_PACKAGE_DIR / ".env", override=False)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_url() -> str:
    url = os.environ.get("CHECKPOINT_DB_URL", "")
    if not url:
        sys.exit("CHECKPOINT_DB_URL is not set")
    return url.replace("postgresql+asyncpg://", "postgresql://")


def ensure_table(conn: psycopg.Connection) -> None:
    conn.execute(CREATE_TABLE)
    conn.commit()


def get_applied(conn: psycopg.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()]


def apply(dry_run: bool = False) -> None:
    all_files = {
        f.stem: f
        for f in MIGRATIONS_DIR.glob("*.sql")
        if not f.stem.endswith(".down")
    }

    with psycopg.connect(get_url(), autocommit=False) as conn:
        ensure_table(conn)
        applied = set(get_applied(conn))
        pending = [s for s in sorted(all_files) if s not in applied]

        if not pending:
            print("All migrations already applied.")
            return

        for stem in pending:
            if dry_run:
                print(f"[dry-run] would apply: {stem}")
                continue
            print(f"Applying {stem} ...", end=" ", flush=True)
            try:
                conn.execute(all_files[stem].read_text())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (stem,))
                conn.commit()
                print("OK")
            except Exception as exc:
                conn.rollback()
                print(f"FAILED\n{exc}")
                sys.exit(1)


def rollback(count: int = 1, dry_run: bool = False) -> None:
    with psycopg.connect(get_url(), autocommit=False) as conn:
        ensure_table(conn)
        applied = list(reversed(get_applied(conn)))
        to_roll = applied[:count]

        if not to_roll:
            print("Nothing to roll back.")
            return

        for stem in to_roll:
            down_file = MIGRATIONS_DIR / f"{stem}.down.sql"
            if not down_file.exists():
                sys.exit(f"No rollback file found: {down_file.name}")
            if dry_run:
                print(f"[dry-run] would roll back: {stem}")
                continue
            print(f"Rolling back {stem} ...", end=" ", flush=True)
            try:
                conn.execute(down_file.read_text())
                conn.execute("DELETE FROM schema_migrations WHERE version = %s", (stem,))
                conn.commit()
                print("OK")
            except Exception as exc:
                conn.rollback()
                print(f"FAILED\n{exc}")
                sys.exit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Database migration runner")
    p.add_argument("--dry-run", action="store_true", help="Print pending migrations without applying them")
    p.add_argument("--rollback", type=int, metavar="N", help="Roll back the last N migrations")
    args = p.parse_args()
    if args.rollback:
        rollback(count=args.rollback, dry_run=args.dry_run)
    else:
        apply(dry_run=args.dry_run)
