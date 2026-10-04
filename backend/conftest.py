import os

# MUST run before anything imports backend.database, which builds its
# SqliteDatabase from DATABASE_PATH at import time.
#
# Rebinding the db afterwards does not work: backend/models.py captures the
# database OBJECT in BaseModel.Meta.database, and backend/api.py captures the
# same object via `from backend.database import db` for its db.atomic() calls.
# Reassigning backend.database.db only moves the module attribute, leaving
# both pointing at the real pkanban.db -- which is how the suite used to wipe
# the developer's local database on every run. Pointing DATABASE_PATH at a
# test database before import means only one db object is ever created, so
# models, transactions, and fixtures all agree on it.
#
# A shared-cache URI rather than plain ":memory:" because the FastAPI
# TestClient serves requests on a different thread, and peewee opens a
# connection per thread. Plain ":memory:" would give each thread its own
# empty database; cache=shared makes them the same one for the process.
os.environ["DATABASE_PATH"] = "file:kanban_test?mode=memory&cache=shared"

# Also set before import: backend.auth resolves its signing key at import time
# and would otherwise generate one and write it to disk. Tests get a fixed key
# so token fixtures are reproducible and the suite leaves no files behind.
os.environ["JWT_SECRET_KEY"] = "test-only-signing-key-not-used-anywhere-real"

import pytest  # noqa: E402
import random  # noqa: E402
import string  # noqa: E402

from backend.database import db as _db  # noqa: E402

TEST_MODELS = None


def _models():
    """Every model, imported lazily so DATABASE_PATH above is set first.

    Reads backend.models.ALL_MODELS rather than repeating the list, so a new
    model cannot be added to the app and silently missed by the test schema.
    """
    global TEST_MODELS
    if TEST_MODELS is None:
        from backend.models import ALL_MODELS

        TEST_MODELS = ALL_MODELS
    return TEST_MODELS


@pytest.fixture(scope="session")
def _setup_test_db():
    """Session-scoped fixture to create tables once."""
    assert _db.database.startswith("file:kanban_test"), (
        f"tests are pointed at {_db.database!r}, not the test database. "
        "Something imported backend.database before conftest set DATABASE_PATH."
    )

    # Held open for the whole session: the shared-cache in-memory database is
    # discarded once the last connection to it closes.
    _db.connect()
    _db.create_tables(_models())
    yield
    _db.close()


@pytest.fixture
def db_session(_setup_test_db):
    """Per-test database fixture that clears all data between tests."""
    from playhouse.sqlite_ext import VirtualModel

    # Reversed, so children go before the parents they reference. ALL_MODELS is
    # ordered parents-first for create_tables; deletion wants the opposite.
    #
    # The search index is skipped, not deleted from: the triggers on card
    # already remove its rows as the cards go. A DELETE here would empty the
    # index first, and every card delete after it would then tell FTS5 to
    # remove words it no longer holds -- which corrupts the index rather than
    # erroring. It is rebuilt afterwards so no test inherits another's state.
    virtual = []
    for table in reversed(_models()):
        if issubclass(table, VirtualModel):
            virtual.append(table)
            continue
        try:
            table.delete().execute()
        except Exception:
            pass
    for table in virtual:
        table.rebuild()
    yield _db


@pytest.fixture
def test_user(db_session):
    """Create a unique test user"""
    from backend.models import User

    random_suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    username = f"testuser_{random_suffix}"
    user = User.create_user(username, "testpassword")
    return user


# Alias for backwards compatibility with tests expecting test_db
@pytest.fixture
def test_db(db_session):
    """Alias for db_session for backwards compatibility."""
    return db_session


@pytest.fixture
def test_cli_user(db_session):
    """Create a unique CLI test user."""
    from backend.models import User

    random_suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    username = f"testuser_{random_suffix}"
    user = User.create_user(username, "testpassword")
    return user
