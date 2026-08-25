# AGENTS.md

AGENTS.md is the cross-agent standard, CLAUDE.md is a four-line shim that imports it.


## Project Overview

The Kanban project is a full-stack application with:
- **Backend**: FastAPI server (Python) with Peewee ORM and SQLite
- **CLI**: Python CLI client using typer and rich (published as `pkanban` on PyPI)
- **Frontend**: Svelte (served from backend/static)
- **Features**: Multi-tenancy with organizations, teams, API keys, and board sharing

## Remote Configuration

This project uses a remote Kanban server at **pkanban.pearachute.com**.

### Config
The CLI is configured to connect to:
- **Server**: https://pkanban.pearachute.com
- **Auth**: a JWT token or an API key, stored in `~/.pkanban.yaml`


### Running the CLI from this repo

The `pkanban` command is not on the PATH unless the venv is activated. From
this repo root, call the venv binary directly:

```bash
# Windows
venv/Scripts/pkanban.exe --help

# macOS/Linux
venv/bin/pkanban --help
```

The CLI is installed in editable mode (`pip install -e .`), so changes under
`pkanban/` take effect immediately. Activating the venv
(`venv/Scripts/activate` on Windows, `source venv/bin/activate` elsewhere)
puts plain `pkanban` on the PATH.

### Authenticating with an API key

`--api-key <key>` authenticates a single command only. It goes through the
in-memory runtime key and never touches the config file, so it is safe for
per-command use by agents and scripts:

```bash
venv/Scripts/pkanban.exe --api-key pkanban_1-<KEY> board list --json
```

### Project Board

The **Dev** board (id=1) is the board for this project. Columns:

### Useful Commands
```bash
pkanban board list                    # List all boards
pkanban board get 1                    # Show Dev board details
pkanban board get <id>                 # Show board with columns & cards
pkanban card get <id>                  # Read one card's full contents
```

### Scripting the CLI

Pass `--json` (or set `PKANBAN_OUTPUT=json`) and every command prints the raw
API response instead of formatted text. Use it rather than parsing the human
output

```bash
pkanban column create 1 Todo 0 --json | jq -r .id
pkanban board get 1 --json | jq '.columns[].cards[] | {id, title, description}'
```

The flag works before or after the subcommand. In JSON mode stdout holds only
the response; errors go to stderr as `{"error": ..., "status": ...}` alongside
a non-zero exit code, so stdout is always safe to pipe into a parser.

`pkanban card get <id>` reads one card, including its description, the comments
and which board/column it sits on:

```bash
pkanban card get 92 --json | jq -r .description
```

### Setup

The virtualenv probably already exists at `./venv`. Please use it, or create a new one if necessary.

```bash
# Install CLI in editable mode
pip install -e .

# Run it
pkanban --help
```

### Running the Server

manage.py is the main entrypoint, invoke it using the virtualenv's python.


```bash
# Development server with auto-reload (default port 8080)
python manage.py server

# Custom host/port
python manage.py server --host 127.0.0.1 --port 9000

# Disable auto-reload
python manage.py server --no-reload

# Set log level
python manage.py server --log-level debug
```

### Database Management

```bash
# Initialize database
python manage.py init

# Wipe database (destructive)
python manage.py wipe

# Create a user
python manage.py user-create <username> <password> [--email EMAIL] [--admin]

# Check database status
python manage.py status

# Apply pending migrations
python manage.py migrate

# Show what is applied and what is pending, without running anything
python manage.py migrate --list
```

### Database Migrations

Migrations live in `backend/migrations/` and run under **peewee-migrate**.
`sys/scripts/deploy.sh` calls `manage.py migrate` on every deploy, before the
service restarts, and a failure aborts the deploy.  the service keeps serving
the old code rather than starting against a schema it does not match.

Applied migrations are recorded in a `migratehistory` table, so running the
command repeatedly is cheap and safe.

Writing a new one: name it `NNN_description.py` (the three-digit prefix is how
peewee-migrate finds and orders them) and define:

```python
def migrate(migrator, database, *, fake=False):
    ...

def rollback(migrator, database, *, fake=False):
    ...
```


- **Make it idempotent.** Check before you alter. Production applied migration
  001 by hand years before there was a history table, and a fresh install gets
- **Match peewee's index names.** `create_tables()` names the index for
  `email = CharField(unique=True)` as `user_email`. A migration that invents its
  own name leaves fresh installs and migrated databases with different schemas.

`init_db()` still creates *new tables* from the models on startup, so a
migration only needs to handle columns, indexes and data.

### Running Tests

```bash
# Run all backend tests
pytest

# Run all tests in backend/tests/
python -m pytest backend/tests/

# Run a single test file
pytest backend/tests/test_api.py

### Database Patterns

- Use Peewee ORM with proper relationships
- Use `get_or_none()` for lookups that may fail
- Wrap multiple writes in `db.atomic()` transaction
- Use fixtures from `conftest.py` for tests


## PyPI Publishing

The CLI package is published as **pkanban** on PyPI. Publishing is automated via GitHub Actions.

### Publishing a New Version

1. Update version in both files:
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `pkanban/__init__.py`: `__version__ = "X.Y.Z"`

2. Commit and push:
   ```bash
   git add -A && git commit -m "Bump version to X.Y.Z"
   git push
   ```

3. Create and push a tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. GitHub Actions handles the rest:
   - Builds wheel and source distribution
   - Publishes to PyPI (using trusted publishing)
   - Creates a GitHub Release with notes


## GOTCHAS

- **Never load fonts with `@import` from a CSS file.** An `@import` in
  `theme.css` is flattened into `app.css` after Tailwind has emitted its
  `@layer` statements, which makes it invalid -- and postcss drops it from the
  build without failing it. Web fonts never loaded at all until PR #36, and
  every page rendered in the system fallback. Use `<link>` in `index.html`.

- **Run the CLI from the venv: `venv/Scripts/pkanban.exe`.** Plain `pkanban` is
  not on PATH unless the venv is activated
