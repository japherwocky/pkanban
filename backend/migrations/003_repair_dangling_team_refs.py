"""Peewee migrations -- 003_repair_dangling_team_refs.

Clean up after four peewee queries that were built and never executed.

DELETE /teams/{id} and its admin twin both did this:

    Board.update(shared_team=None).where(Board.shared_team == team)
    TeamMember.delete().where(TeamMember.team == team)
    team.delete_instance()

Model.update()/delete() only build a query; without .execute() nothing runs.
So the team row went away while boards kept pointing at it and its membership
rows survived. can_access_board() then resolved board.shared_team, got
Team.DoesNotExist, and returned a 500 to every non-owner asking for that board
-- unrepairable from the UI, because the team it names no longer exists.

The code is fixed. This clears whatever the broken version already left behind.
Idempotent: on a database that never hit the bug both statements match nothing.

Not handled here: orphaned Card rows from the admin board-delete path, which
had the same missing .execute(). Those are unreachable rather than harmful --
their column and board are gone, so nothing queries them -- and deleting rows
whose parent is already gone is not worth the risk of a wrong predicate. They
cost a few KB.
"""

import peewee as pw
from peewee_migrate import Migrator


def _table_exists(database, table):
    rows = database.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchall()
    return bool(rows)


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    if fake:
        return

    if not _table_exists(database, "team"):
        print("  team table does not exist yet, nothing to repair")
        return

    # Boards pointing at a team that is gone. NOT NULL guard matters: an
    # unshared board has shared_team_id NULL, and NULL NOT IN (...) is NULL
    # rather than true, so those rows would never match anyway -- but being
    # explicit keeps the intent readable.
    cursor = database.execute_sql("""
        UPDATE board SET shared_team_id = NULL
        WHERE shared_team_id IS NOT NULL
          AND shared_team_id NOT IN (SELECT id FROM team)
    """)
    print(f"  Unshared {cursor.rowcount} board(s) referencing a deleted team")

    if _table_exists(database, "teammember"):
        cursor = database.execute_sql("""
            DELETE FROM teammember
            WHERE team_id NOT IN (SELECT id FROM team)
        """)
        print(f"  Removed {cursor.rowcount} membership row(s) for deleted teams")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Nothing to undo.

    This deletes rows that reference something already gone. Restoring them
    would mean recreating the teams they pointed at, which no longer exist in
    any form -- and the state it repairs is corruption, not a schema choice.
    """
