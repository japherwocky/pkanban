"""Peewee migrations -- 007_autoincrement_ids.

Stop handing out the ids of deleted rows.

Peewee's default primary key is SQLite's `INTEGER PRIMARY KEY` without
AUTOINCREMENT, so an insert takes max(id) + 1. Delete the newest row and the
next insert reuses its id: card ids are cited in commit messages, so an old
citation would silently point at an unrelated card. The models now declare
AutoIncrementField, which makes SQLite keep a high-water mark in
sqlite_sequence; this rebuilds each existing table to match.

SQLite cannot add AUTOINCREMENT in place, so each table goes through the
procedure from https://www.sqlite.org/lang_altertable.html#otheralter: create
the new table, copy the rows, drop the old, rename, recreate its indexes.
The CREATE statement comes from sqlite_master rather than the models, so this
file keeps working after the models move on.

Foreign keys are off on this connection (peewee never turns them on), which is
what makes DROP TABLE safe: with them on it would cascade into child tables.
That is asserted rather than assumed, because PRAGMA foreign_keys cannot be
changed inside the transaction peewee-migrate wraps this in.

Idempotent: a table that already says AUTOINCREMENT is skipped, and a fresh
install (built from the models) has nothing to do. Copying the rows seeds
sqlite_sequence with each table's current max id, so the counter starts at the
right place -- ids freed before this ran are not recoverable.
"""

import re

import peewee as pw
from peewee_migrate import Migrator

TABLES = [
    "user",
    "board",
    "column",
    "card",
    "comment",
    "organization",
    "organizationmember",
    "team",
    "teammember",
    "betasignup",
    "apikey",
    "organizationinvite",
    "emailverificationtoken",
]

_PK = '"id" INTEGER NOT NULL PRIMARY KEY'


def _create_sql(database, table):
    row = database.execute_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    if fake:
        return

    if database.execute_sql("PRAGMA foreign_keys").fetchone()[0]:
        raise RuntimeError(
            "foreign_keys is ON; dropping a table would cascade into its "
            "children. Refusing to rebuild tables."
        )

    for table in TABLES:
        sql = _create_sql(database, table)
        if sql is None:
            print(f"  {table} does not exist yet, skipping")
            continue
        if "AUTOINCREMENT" in sql.upper():
            print(f"  {table} already autoincrements, skipping")
            continue
        if _PK not in sql:
            raise RuntimeError(f"unexpected primary key definition for {table}: {sql}")

        indexes = [
            row[0]
            for row in database.execute_sql(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            )
        ]

        new = f"{table}__new"
        new_sql = sql.replace(_PK, _PK + " AUTOINCREMENT", 1)
        new_sql = re.sub(
            r'^CREATE TABLE ("?)' + re.escape(table) + r'\1',
            f'CREATE TABLE "{new}"',
            new_sql,
            count=1,
        )
        database.execute_sql(f'DROP TABLE IF EXISTS "{new}"')
        database.execute_sql(new_sql)
        database.execute_sql(f'INSERT INTO "{new}" SELECT * FROM "{table}"')
        database.execute_sql(f'DROP TABLE "{table}"')
        database.execute_sql(f'ALTER TABLE "{new}" RENAME TO "{table}"')
        for index_sql in indexes:
            database.execute_sql(index_sql)
        print(f"  Rebuilt {table} with AUTOINCREMENT")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    # Reuse of deleted ids is a defect, not a feature. AUTOINCREMENT tables
    # behave identically to the old ones in every other respect, so there is
    # nothing to undo.
    pass
