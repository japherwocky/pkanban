"""Peewee migrations -- 004_board_organization.

Give Board an organization, so is_public_to_org can finally mean something.

can_access_board() had three branches and only two worked:

    if board.is_public_to_org:
        # This requires going through teams to get the org
        # Or we could add a org_id to boards directly
        # For now, skip this - we'll handle it via the shared_team approach
        pass

POST /boards/{id}/share accepted is_public_to_org, returned 200 and persisted
the flag, and nothing ever read it -- an org member saw a 403 and an empty
board list. The blocker was structural: Board had no organization, so there
was nothing to check an OrganizationMember row against.

Nullable, because a board is not owned by an organization -- it is shared into
one. Personal boards keep organization_id NULL forever.

Backfill covers boards already shared with a team, where the org is derivable
as team.organization. A board with is_public_to_org set and no shared_team has
no derivable org and stays NULL; its flag remains inert until someone shares
it again, which is reported below so the count is not silent. Nothing was ever
visible through that flag, so no access is lost either way.
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

    if not _table_exists(database, "board"):
        print("  board table does not exist yet, nothing to migrate")
        return

    if "organization_id" in _columns(database, "board"):
        # Fresh install -- create_tables() already built the column from the
        # model -- or a re-run. Either way the backfill below has either
        # already happened or has nothing to act on.
        print("  board.organization_id already exists, skipping")
        return

    # No REFERENCES clause: SQLite's ALTER TABLE ADD COLUMN cannot add one
    # that peewee's create_tables() would have written inline, and a migrated
    # database that differs from a fresh install is exactly the drift
    # test_migrations.py exists to catch. peewee does not enforce the
    # constraint at the database level here anyway.
    database.execute_sql("ALTER TABLE board ADD COLUMN organization_id INTEGER")
    print("  Added board.organization_id")

    cursor = database.execute_sql("""
        UPDATE board
        SET organization_id = (
            SELECT team.organization_id FROM team WHERE team.id = board.shared_team_id
        )
        WHERE shared_team_id IS NOT NULL
          AND shared_team_id IN (SELECT id FROM team)
    """)
    print(f"  Derived an organization for {cursor.rowcount} shared board(s)")

    stranded = database.execute_sql("""
        SELECT COUNT(*) FROM board
        WHERE is_public_to_org = 1 AND organization_id IS NULL
    """).fetchone()[0]
    if stranded:
        print(
            f"  {stranded} board(s) are flagged public-to-org with no derivable "
            "organization -- the flag stays inert until they are shared again. "
            "It has never granted access, so nothing is lost."
        )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Leave the column in place.

    SQLite cannot drop a column without rebuilding the table, and older code
    never selects it, so leaving it costs nothing.
    """
