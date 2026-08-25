import os
from peewee import SqliteDatabase

DATABASE_PATH = os.environ.get("DATABASE_PATH", "pkanban.db")

# A "file:..." DATABASE_PATH is an SQLite URI and needs uri=True to be parsed
# as one rather than treated as a literal filename. The test suite uses this
# to get a shared in-memory database.
db = SqliteDatabase(DATABASE_PATH, uri=DATABASE_PATH.startswith("file:"))


def init_db():
    # Skip if already connected (e.g., in tests)
    if db.is_connection_usable():
        return

    db.connect()
    from backend.models import ALL_MODELS

    db.create_tables(ALL_MODELS)
    db.close()
