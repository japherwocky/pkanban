"""Peewee migrations -- 009_card_archived_at.

Card archiving (#781): a nullable `archived_at` on card. Null means the card is
live, so every existing card stays exactly as it was, with no backfill.

ADD COLUMN, not a table rebuild, so the search triggers on card (CardSearch in
backend/models.py) are untouched. A rebuild would drop them until the next
startup.

Idempotent: the column is added only if it is missing. A fresh install built
from the models already has it.
"""

import peewee as pw
from peewee_migrate import Migrator


def _table_exists(database, table):
    rows = database.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchall()
    return bool(rows)


def _columns(database, table):
    return [row[1] for row in database.execute_sql(f"PRAGMA table_info({table})")]


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    if fake:
        return

    if not _table_exists(database, "card"):
        print("  card table does not exist yet, nothing to migrate")
        return

    if "archived_at" in _columns(database, "card"):
        print("  card.archived_at already exists, skipping")
        return

    database.execute_sql('ALTER TABLE "card" ADD COLUMN archived_at DATETIME')
    print("  Added card.archived_at")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Leave the column in place.

    Code from before this migration never selects it, and dropping a column
    would throw away which cards were archived.
    """
