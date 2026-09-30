"""Schema-drift test: fresh install vs. migrated database.

init_db()/create_tables() and the migrations in backend/migrations/ are two
independent code paths that both claim to produce the schema. Nothing checked
that they agree, so a migration could add a column the model never declares
(or name an index differently) and nothing would notice until production.

The migrations are written to be no-ops on a fresh install -- they check for
existing columns before ALTERing. So the convergence property to assert is:
running every migration against a database built from the current models
leaves it byte-for-byte identical (per table_info and index list) to one that
never saw a migration. Any drift between the two paths shows up as a
difference here.
"""

import os
import tempfile

from peewee import SqliteDatabase
from peewee_migrate import Router

from backend.models import ALL_MODELS

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations"
)


def _schema(path):
    """{table: {"columns": [...], "indexes": [...]}} for every real table.

    migratehistory is peewee-migrate's bookkeeping and exists only on the
    migrated side, so it is excluded from the comparison.
    """
    db = SqliteDatabase(path)
    db.connect()
    tables = [
        row[0]
        for row in db.execute_sql(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name != 'migratehistory' ORDER BY name"
        ).fetchall()
    ]
    schema = {}
    for table in tables:
        schema[table] = {
            "columns": db.execute_sql(f"PRAGMA table_info({table})").fetchall(),
            "indexes": db.execute_sql(f"PRAGMA index_list({table})").fetchall(),
        }
    db.close()
    return schema


def test_migrations_leave_a_fresh_install_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = os.path.join(tmp, "fresh.db")
        migrated_path = os.path.join(tmp, "migrated.db")

        # Fresh install: tables built from the models, no migrations.
        fresh = SqliteDatabase(fresh_path)
        with fresh.bind_ctx(ALL_MODELS):
            fresh.connect()
            fresh.create_tables(ALL_MODELS)
            fresh.close()

        # Migrated: same base schema, then every migration in order.
        migrated = SqliteDatabase(migrated_path)
        with migrated.bind_ctx(ALL_MODELS):
            migrated.connect()
            migrated.create_tables(ALL_MODELS)
            Router(migrated, migrate_dir=MIGRATIONS_DIR).run()
            migrated.close()

        fresh_schema = _schema(fresh_path)
        migrated_schema = _schema(migrated_path)

        assert set(fresh_schema) == set(migrated_schema), (
            "Table sets differ between a fresh install and a migrated "
            f"database.\nOnly in fresh: {set(fresh_schema) - set(migrated_schema)}\n"
            f"Only in migrated: {set(migrated_schema) - set(fresh_schema)}"
        )

        for table in fresh_schema:
            assert fresh_schema[table] == migrated_schema[table], (
                f"Schema drift on table '{table}': a fresh install and a "
                "migrated database disagree. If a migration changed this "
                "table, update the model to match -- or vice versa."
            )


def test_006_adds_key_sha256_to_a_pre_006_table():
    """The convergence test above never runs 006's ALTER: a fresh install
    already has the column, so the migration skips. Build the table as it
    stood before 006 and check the migration brings it level with the model.

    `prefix` is compared without its declared type -- the model now says
    VARCHAR(16), an existing table keeps VARCHAR(8), and SQLite enforces
    neither. That difference is deliberate; see the migration's docstring.
    """
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = os.path.join(tmp, "fresh.db")
        old_path = os.path.join(tmp, "old.db")

        fresh = SqliteDatabase(fresh_path)
        with fresh.bind_ctx(ALL_MODELS):
            fresh.connect()
            fresh.create_tables(ALL_MODELS)
            fresh.close()

        old = SqliteDatabase(old_path)
        with old.bind_ctx(ALL_MODELS):
            old.connect()
            old.create_tables(ALL_MODELS)
            old.execute_sql('DROP INDEX "apikey_key_sha256"')
            old.execute_sql("ALTER TABLE apikey DROP COLUMN key_sha256")
            old.execute_sql(
                "INSERT INTO user (username, password_hash, email_verified, admin) "
                "VALUES ('u', 'x', 1, 0)"
            )
            old.execute_sql(
                "INSERT INTO apikey (user_id, name, key_hash, prefix, created_at, "
                "is_active) VALUES (1, 'k', '$2b$04$legacy', 'pkanban_', "
                "'2026-01-01 00:00:00', 1)"
            )
            Router(old, migrate_dir=MIGRATIONS_DIR).run()
            rows = old.execute_sql(
                "SELECT key_hash, key_sha256 FROM apikey"
            ).fetchall()
            old.close()

        def comparable(schema):
            columns = [
                (cid, name, None if name == "prefix" else type_, notnull, dflt, pk)
                for cid, name, type_, notnull, dflt, pk in schema["columns"]
            ]
            return columns, schema["indexes"]

        assert comparable(_schema(old_path)["apikey"]) == comparable(
            _schema(fresh_path)["apikey"]
        )
        # The legacy row survives, still bcrypt-only, for find() to upgrade.
        assert rows == [("$2b$04$legacy", None)]


def _strip_autoincrement(db):
    """Turn a model-built database back into the pre-007 schema."""
    for (table,) in db.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND sql LIKE '%AUTOINCREMENT%'"
    ).fetchall():
        (sql,) = db.execute_sql(
            "SELECT sql FROM sqlite_master WHERE name=?", (table,)
        ).fetchone()
        indexes = [
            r[0]
            for r in db.execute_sql(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            )
        ]
        db.execute_sql(f'ALTER TABLE "{table}" RENAME TO "{table}__old"')
        db.execute_sql(sql.replace(" AUTOINCREMENT", ""))
        db.execute_sql(f'INSERT INTO "{table}" SELECT * FROM "{table}__old"')
        db.execute_sql(f'DROP TABLE "{table}__old"')
        for index_sql in indexes:
            db.execute_sql(index_sql)


def test_007_stops_deleted_ids_being_reused_and_keeps_data():
    """Build the pre-007 schema with real parent/child rows, migrate, and check
    that nothing is lost, every table now autoincrements, the schema matches a
    fresh install, and a deleted highest id is not handed out again.
    """
    with tempfile.TemporaryDirectory() as tmp:
        old_path = os.path.join(tmp, "old.db")
        fresh_path = os.path.join(tmp, "fresh.db")

        fresh = SqliteDatabase(fresh_path)
        with fresh.bind_ctx(ALL_MODELS):
            fresh.connect()
            fresh.create_tables(ALL_MODELS)
            fresh.close()

        old = SqliteDatabase(old_path)
        with old.bind_ctx(ALL_MODELS):
            old.connect()
            old.create_tables(ALL_MODELS)
            _strip_autoincrement(old)
            assert not old.execute_sql(
                "SELECT 1 FROM sqlite_master WHERE sql LIKE '%AUTOINCREMENT%'"
            ).fetchall()

            old.execute_sql(
                "INSERT INTO user (username, password_hash, email_verified, admin) "
                "VALUES ('u', 'x', 1, 0)"
            )
            old.execute_sql(
                "INSERT INTO board (owner_id, name, is_public_to_org, created_at) "
                "VALUES (1, 'b', 0, '2026-01-01')"
            )
            old.execute_sql(
                "INSERT INTO \"column\" (board_id, name, position) VALUES (1, 'c', 0)"
            )
            for n in (1, 2, 3):
                old.execute_sql(
                    "INSERT INTO card (column_id, title, position) "
                    f"VALUES (1, 'card{n}', {n})"
                )
            old.execute_sql(
                "INSERT INTO comment (card_id, user_id, content, created_at) "
                "VALUES (3, 1, 'hi', '2026-01-01')"
            )
            before = {
                t: old.execute_sql(f'SELECT * FROM "{t}" ORDER BY id').fetchall()
                for t in ("user", "board", "column", "card", "comment")
            }

            Router(old, migrate_dir=MIGRATIONS_DIR).run()

            after = {
                t: old.execute_sql(f'SELECT * FROM "{t}" ORDER BY id').fetchall()
                for t in before
            }
            assert after == before, "rows changed or were lost in the rebuild"

            # Every table now autoincrements.
            assert not old.execute_sql(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('sqlite_sequence', 'migratehistory') "
                "AND sql NOT LIKE '%AUTOINCREMENT%'"
            ).fetchall()

            # The core of the bug: delete the newest card, insert another.
            old.execute_sql("DELETE FROM comment")
            old.execute_sql("DELETE FROM card WHERE id = 3")
            old.execute_sql(
                "INSERT INTO card (column_id, title, position) VALUES (1, 'new', 9)"
            )
            assert old.execute_sql("SELECT max(id) FROM card").fetchone()[0] == 4

            # Deleting parents did not cascade: foreign keys stayed off.
            assert old.execute_sql("SELECT count(*) FROM board").fetchone()[0] == 1
            old.close()

        # Same columns and indexes as a fresh install.
        old_schema, fresh_schema = _schema(old_path), _schema(fresh_path)
        assert old_schema == fresh_schema

        # Running again is a no-op.
        again = SqliteDatabase(old_path)
        again.connect()
        Router(again, migrate_dir=MIGRATIONS_DIR).run()
        again.close()


def test_new_models_declare_autoincrement():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fresh.db")
        db = SqliteDatabase(path)
        with db.bind_ctx(ALL_MODELS):
            db.connect()
            db.create_tables(ALL_MODELS)
            missing = db.execute_sql(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('sqlite_sequence') "
                "AND sql NOT LIKE '%AUTOINCREMENT%'"
            ).fetchall()
            db.close()
        assert not missing


def test_008_adds_plan_columns_to_a_pre_008_user_table():
    """A fresh install already has the billing columns, so 008 skips there.
    Build the user table as it stood before 008 and check the migration brings
    it level with the model -- including the DEFAULT 'free' that lands every
    existing account on the free plan."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = os.path.join(tmp, "fresh.db")
        old_path = os.path.join(tmp, "old.db")

        fresh = SqliteDatabase(fresh_path)
        with fresh.bind_ctx(ALL_MODELS):
            fresh.connect()
            fresh.create_tables(ALL_MODELS)
            fresh.close()

        old = SqliteDatabase(old_path)
        with old.bind_ctx(ALL_MODELS):
            old.connect()
            old.create_tables(ALL_MODELS)
            old.execute_sql('DROP INDEX "user_stripe_customer_id"')
            for column in (
                "plan",
                "stripe_customer_id",
                "subscription_status",
                "current_period_end",
            ):
                old.execute_sql(f'ALTER TABLE "user" DROP COLUMN {column}')
            old.execute_sql(
                "INSERT INTO user (username, password_hash, email_verified, admin) "
                "VALUES ('u', 'x', 1, 0)"
            )
            Router(old, migrate_dir=MIGRATIONS_DIR).run()
            rows = old.execute_sql(
                "SELECT username, plan, stripe_customer_id FROM user"
            ).fetchall()
            old.close()

        assert _schema(old_path)["user"] == _schema(fresh_path)["user"]
        # The pre-existing account is on the free plan with no Stripe customer.
        assert rows == [("u", "free", None)]
