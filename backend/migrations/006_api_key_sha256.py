"""Peewee migrations -- 006_api_key_sha256.

Find API keys by a hash of the whole key, so more than one key can work.

Keys were looked up by `prefix`, the first 8 characters of the key -- and every
key begins with the 8-character literal "pkanban_". The lookup therefore
matched every row and returned the first. That one key authenticated; any
other key was checked against the wrong row's bcrypt hash and refused as
"Invalid API key", or as "API key is inactive" once the first key had been
revoked. A test asserted prefix == "pkanban_", so the suite encoded the bug.

This adds key_sha256, unique and indexed. New keys are stored by it and found
with one equality lookup. Existing rows are left NULL: their raw keys were
never stored, so there is nothing to backfill from. ApiKey.find() checks an
unknown key against the remaining bcrypt rows and fills in key_sha256 on the
first match, so each legacy key upgrades itself the first time it is used and
nobody has to re-mint anything.

`prefix` also changes meaning, from the useless "pkanban_" to the first 16
characters, so a key list can tell keys apart. The model now declares it
VARCHAR(16); an existing table keeps VARCHAR(8), which SQLite does not enforce,
so no rebuild is done for it.
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

    if not _table_exists(database, "apikey"):
        print("  apikey table does not exist yet, nothing to migrate")
        return

    if "key_sha256" in _columns(database, "apikey"):
        print("  apikey.key_sha256 already exists, skipping")
        return

    database.execute_sql("ALTER TABLE apikey ADD COLUMN key_sha256 VARCHAR(64)")
    print("  Added apikey.key_sha256")

    # The name create_tables() gives the index for a unique=True field, so a
    # migrated database and a fresh install end up with the same schema.
    database.execute_sql(
        'CREATE UNIQUE INDEX IF NOT EXISTS "apikey_key_sha256" '
        'ON "apikey" ("key_sha256")'
    )
    print("  Added unique index apikey_key_sha256")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Leave the column in place.

    SQLite cannot drop a column without rebuilding the table. Older code never
    selects it, but it also cannot authenticate a key minted after this
    migration: those rows carry an empty key_hash for its bcrypt check.
    """
    database.execute_sql('DROP INDEX IF EXISTS "apikey_key_sha256"')
