"""Peewee migrations -- 005_team_invites.

Let an invite name a team, so someone can be invited to a board's team by
email instead of having to already exist as a username.

Sharing a board means pointing Board.shared_team at a team, and the only way
to put a person on a team was POST /teams/{id}/members, which takes a
username and 404s on anyone without an account. The invite table -- which
does have an email column and a mailer behind it -- could only grant
organization membership. So inviting an outside collaborator to one board was
two disjoint steps with a signup wedged between them.

Nullable: an invite with team_id NULL is an organization invite and behaves
exactly as before. Nothing is backfilled, because no existing invite was ever
about a team.
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

    if not _table_exists(database, "organizationinvite"):
        print("  organizationinvite table does not exist yet, nothing to migrate")
        return

    if "team_id" in _columns(database, "organizationinvite"):
        # Fresh install -- create_tables() built it from the model -- or a
        # re-run of this migration.
        print("  organizationinvite.team_id already exists, skipping")
        return

    # No REFERENCES clause: SQLite's ALTER TABLE ADD COLUMN cannot add one.
    # See 004 for the same trade-off; peewee does not enforce it here anyway.
    database.execute_sql("ALTER TABLE organizationinvite ADD COLUMN team_id INTEGER")
    print("  Added organizationinvite.team_id")

    # peewee's create_tables() indexes every ForeignKeyField and names the
    # index "<table>_<column>". Inventing a different name here would leave
    # fresh installs and migrated databases with schemas that differ, which is
    # what test_migrations.py exists to catch.
    database.execute_sql(
        'CREATE INDEX IF NOT EXISTS "organizationinvite_team_id" '
        'ON "organizationinvite" ("team_id")'
    )
    print("  Added index organizationinvite_team_id")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Leave the column in place.

    SQLite cannot drop a column without rebuilding the table, and older code
    never selects it. An invite created against a team would fall back to
    granting organization membership on accept, which is the pre-005
    behaviour.
    """
    database.execute_sql('DROP INDEX IF EXISTS "organizationinvite_team_id"')
