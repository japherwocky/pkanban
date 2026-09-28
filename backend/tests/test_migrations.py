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
