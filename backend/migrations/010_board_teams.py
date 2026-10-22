"""Peewee migrations -- 010_board_teams.

Boards and teams become many-to-many, each grant carrying a level.

- New table boardteam (board, team, permission: read | write | admin). Every
  board.shared_team_id moves in at write, which is what sharing granted
  before there were levels, so nobody gains or loses access. A shared_team_id
  whose team no longer exists is dropped rather than copied: it granted
  nothing (see 003).
- board.shared_team_id goes. A board held exactly one team, so sharing with a
  second one silently took the first one's access away.
- board.org_permission: what "public to org" grants, write by default.
- team.organization_id and organizationinvite.organization_id may be null. A
  team needs no organization -- membership is the grant -- and an invite to
  such a team has none to name.

SQLite can neither drop a column that has a REFERENCES clause nor relax NOT
NULL in place, so those three tables are rebuilt the way 007 rebuilt every
table: CREATE from the existing sqlite_master text (edited), copy, drop,
rename, recreate indexes and triggers. Starting from the stored text rather
than the models keeps whatever column order and types each database already
has. Foreign keys are off on this connection, as 007 asserts, so dropping the
old table cascades into nothing.

Idempotent: every step checks first, and a fresh install has nothing to do.
"""

import re

import peewee as pw
from peewee_migrate import Migrator

BOARDTEAM_SQL = (
    'CREATE TABLE IF NOT EXISTS "boardteam" ('
    '"id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, '
    '"board_id" INTEGER NOT NULL, "team_id" INTEGER NOT NULL, '
    '"permission" VARCHAR(10) NOT NULL, '
    'FOREIGN KEY ("board_id") REFERENCES "board" ("id"), '
    'FOREIGN KEY ("team_id") REFERENCES "team" ("id"))'
)
# The names create_tables() gives them, so migrated and fresh schemas agree.
BOARDTEAM_INDEXES = [
    'CREATE INDEX IF NOT EXISTS "boardteam_board_id" ON "boardteam" ("board_id")',
    'CREATE INDEX IF NOT EXISTS "boardteam_team_id" ON "boardteam" ("team_id")',
    'CREATE UNIQUE INDEX IF NOT EXISTS "boardteam_board_id_team_id" '
    'ON "boardteam" ("board_id", "team_id")',
]


def _create_sql(database, table):
    row = database.execute_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def _columns(database, table):
    return {
        row[1]: row for row in database.execute_sql(f'PRAGMA table_info("{table}")')
    }


def _rebuild(database, table, new_sql, drop_column=None):
    """Replace `table` with one created by `new_sql`, keeping its rows."""
    if database.execute_sql("PRAGMA foreign_keys").fetchone()[0]:
        raise RuntimeError(
            "foreign_keys is ON; dropping a table would cascade into its "
            "children. Refusing to rebuild tables."
        )
    extras = [
        sql
        for (sql,) in database.execute_sql(
            "SELECT sql FROM sqlite_master "
            "WHERE type IN ('index', 'trigger') AND tbl_name=? AND sql IS NOT NULL",
            (table,),
        )
        if drop_column is None or drop_column not in sql
    ]
    kept = [c for c in _columns(database, table) if c != drop_column]
    cols = ", ".join(f'"{c}"' for c in kept)

    new = f"{table}__new"
    created = re.sub(
        r'^CREATE TABLE ("?)' + re.escape(table) + r"\1",
        f'CREATE TABLE "{new}"',
        new_sql,
        count=1,
    )
    database.execute_sql(f'DROP TABLE IF EXISTS "{new}"')
    database.execute_sql(created)
    database.execute_sql(f'INSERT INTO "{new}" ({cols}) SELECT {cols} FROM "{table}"')
    database.execute_sql(f'DROP TABLE "{table}"')
    database.execute_sql(f'ALTER TABLE "{new}" RENAME TO "{table}"')
    for sql in extras:
        database.execute_sql(sql)


def _drop_shared_team(database):
    sql = _create_sql(database, "board")
    # The column, with an inline REFERENCES if ADD COLUMN put it there, then
    # the table-level FOREIGN KEY clause create_tables() writes instead.
    edited = re.sub(
        r',\s*"?shared_team_id"?\s+INTEGER'
        r'(\s+REFERENCES\s+"?team"?\s*\(\s*"?id"?\s*\))?',
        "",
        sql,
        count=1,
    )
    edited = re.sub(
        r',\s*FOREIGN KEY\s*\("?shared_team_id"?\)\s*REFERENCES\s*"?team"?\s*\("?id"?\)',
        "",
        edited,
        count=1,
    )
    if "shared_team_id" in edited:
        raise RuntimeError(f"could not remove shared_team_id from board: {sql}")
    _rebuild(database, "board", edited, drop_column="shared_team_id")


def _allow_null_organization(database, table):
    sql = _create_sql(database, table)
    edited, n = re.subn(
        r'("?organization_id"?\s+INTEGER)\s+NOT NULL', r"\1", sql, count=1
    )
    if n != 1:
        raise RuntimeError(f"unexpected organization_id definition in {table}: {sql}")
    _rebuild(database, table, edited)


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    if fake:
        return
    if _create_sql(database, "board") is None:
        print("  board table does not exist yet, nothing to migrate")
        return

    database.execute_sql(BOARDTEAM_SQL)
    for sql in BOARDTEAM_INDEXES:
        database.execute_sql(sql)

    if "shared_team_id" in _columns(database, "board"):
        moved = database.execute_sql(
            'INSERT OR IGNORE INTO "boardteam" (board_id, team_id, permission) '
            "SELECT id, shared_team_id, 'write' FROM board "
            "WHERE shared_team_id IN (SELECT id FROM team)"
        ).rowcount
        print(f"  Moved {moved} shared team(s) into boardteam")
        _drop_shared_team(database)
        print("  Dropped board.shared_team_id")

    if "org_permission" not in _columns(database, "board"):
        database.execute_sql(
            'ALTER TABLE "board" ADD COLUMN "org_permission" '
            "VARCHAR(10) NOT NULL DEFAULT 'write'"
        )
        print("  Added board.org_permission")

    for table in ("team", "organizationinvite"):
        column = _columns(database, table).get("organization_id")
        if column is not None and column[3]:  # notnull
            _allow_null_organization(database, table)
            print(f"  {table}.organization_id may now be null")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Give each board back one shared_team_id, the highest-granted team.

    A board shared with several teams keeps only one under the old code; the
    rest lose access until this migration runs again. The boardteam table and
    the nullable columns stay: older code ignores the one and never writes
    nulls into the others.
    """
    if fake or "shared_team_id" in _columns(database, "board"):
        return
    database.execute_sql('ALTER TABLE "board" ADD COLUMN "shared_team_id" INTEGER')
    database.execute_sql(
        "UPDATE board SET shared_team_id = ("
        "  SELECT team_id FROM boardteam WHERE boardteam.board_id = board.id"
        "  ORDER BY CASE permission WHEN 'admin' THEN 0 WHEN 'write' THEN 1 ELSE 2 END,"
        "  id LIMIT 1)"
    )
