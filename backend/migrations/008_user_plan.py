"""Peewee migrations -- 008_user_plan.

Billing state on the user: which plan they are on, and the Stripe identifiers
the webhook will need to find them again.

`plan` is NOT NULL DEFAULT 'free', so every existing account lands on the free
plan without a backfill. The other three columns are nullable: nobody has a
Stripe customer yet. stripe_customer_id is unique -- the webhook looks users up
by it -- and the index carries the name create_tables() gives a unique field
(user_stripe_customer_id), so a migrated database and a fresh install match.

Idempotent: each column is added only if it is missing, and the index is
IF NOT EXISTS. A fresh install built from the models has all of it already.
"""

import peewee as pw
from peewee_migrate import Migrator

COLUMNS = [
    ("plan", "VARCHAR(20) NOT NULL DEFAULT 'free'"),
    ("stripe_customer_id", "VARCHAR(255)"),
    ("subscription_status", "VARCHAR(40)"),
    ("current_period_end", "DATETIME"),
]


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

    if not _table_exists(database, "user"):
        print("  user table does not exist yet, nothing to migrate")
        return

    existing = _columns(database, "user")
    for name, definition in COLUMNS:
        if name in existing:
            print(f"  user.{name} already exists, skipping")
            continue
        database.execute_sql(f'ALTER TABLE "user" ADD COLUMN {name} {definition}')
        print(f"  Added user.{name}")

    database.execute_sql(
        'CREATE UNIQUE INDEX IF NOT EXISTS "user_stripe_customer_id" '
        'ON "user" ("stripe_customer_id")'
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Leave the columns in place.

    SQLite cannot drop a column without rebuilding the table, and older code
    never selects these. Dropping the index is enough to make the rollback
    reversible by re-running migrate().
    """
    database.execute_sql('DROP INDEX IF EXISTS "user_stripe_customer_id"')
