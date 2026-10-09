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

### Pointing the CLI at another server or config

`PKANBAN_CONFIG_PATH` moves the config file, which is how to aim the CLI at a
local server without touching your real credentials:

```bash
PKANBAN_CONFIG_PATH=/tmp/scratch.yaml venv/Scripts/pkanban.exe config --url http://localhost:8080
```

`KANBAN_CONFIG_PATH`, the pre-rename name, still works but warns. A wrong
guess at the name falls back to `~/.pkanban.yaml` and the real server.

### Card bodies: use a file, not an argument

Pass anything long or quoted with `--description-file` (or `-d -` to read
stdin), never inline with `-d "..."`. PowerShell 5.1 does not re-quote an
argument for a native executable, so a quoted phrase in a body splits it, and
one stray fragment lands in `card update`'s optional title and renames the
card -- exit 0, no warning (Dev #474). A file never passes through any shell's
parser:

```bash
venv/Scripts/pkanban.exe card update 245 --description-file body.md
```

The file is read as UTF-8; a byte-order mark and the trailing newline are
dropped. Anything after `--` is positional, so a title that looks like a flag
can be passed as `pkanban card create 4 -- --json`.

### Project Board

The **Dev** board (id=1) is the board for this project. Columns:

### Useful Commands
```bash
pkanban board list                    # List all boards
pkanban board get 1                    # Show Dev board details
pkanban board get <id>                 # Show board with columns & cards
pkanban card get <id>                  # Read one card, comments included
pkanban card comment <id> --file note.md  # Comment on a card
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

Human-mode errors go to stderr too, so `pkanban card get 9 > card.txt` never
saves "Card not found" as the card. And a reader that leaves (`| head -1`) is
not a failure: `output.run_quietly()` ends the command with its own status
instead of a traceback and 120.

**Writing a command that prints text** (`pkanban/cli.py`): anything that came
from the server or the user -- a board or card name, a username, an email, a
path -- goes through `esc()` on its way into an f-string passed to `rprint` or
`console.print`. rich reads square brackets as style tags, so `[bug] login
fails` printed as ` login fails` and a title containing `[/x]` aborted the
command. `Text.append()` and `markup=False` are the other safe routes. The
tests for this are in `backend/tests/test_cli_output.py`; a new listing belongs
in its table.

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

### Plan limits (billing switch)

`backend/billing.py` holds the free plan's caps: 5 owned boards, 100 cards per
board (every column counts, Done included). They apply only when
`BILLING_ENABLED=true` is in the environment; unset, nobody is limited -- which
is what tests, local dev and self-hosters get. The board *owner's* plan decides:
a free user on a Pro owner's board is unlimited, and boards shared with you
never count toward your own 5. Past a limit the API answers **402** with
`{"error": "plan_limit", "limit", "max", "current", "detail"}`; only creating
(`POST /boards`, `POST /cards`, or `PUT /cards/{id}` moving a card to another
board) is refused -- nothing is ever locked or deleted.

`GET /api/me/usage` reports the caller's plan, limits (`null` = unlimited) and
per-board card counts; the Settings > Plan page and `pkanban account` both read
it. The CLI turns a plan-limit 402 into a `PlanLimitError` (not an `HTTPError`,
so a command's own `except HTTPError` cannot swallow it); in `--json` mode it
lands on stderr as `{"error", "status": 402, "code": "plan_limit", "limit",
"max", "current", "upgrade_url"}`. The web UI shows it in `PlanLimitModal`.

#### Stripe (taking payment)

`backend/stripe_billing.py`. Set these in the server environment (the deploy
does not manage them -- see `sys/config/production.env`):

- `STRIPE_SECRET_KEY` -- `sk_test_...` or `sk_live_...`
- `STRIPE_PRICE_ID` -- the Pro plan's recurring Price
- `STRIPE_WEBHOOK_SECRET` -- `whsec_...`, from the webhook endpoint

`POST /api/billing/checkout` and `/api/billing/portal` return a Stripe URL to
send the browser to; both refuse API keys (the portal can cancel). Stripe's
webhook goes to `POST /api/billing/webhook` and is **the only thing that sets
`User.plan`** -- the redirect back to `/settings/plan?checkout=success` proves
nothing, so the page polls usage until the webhook lands. Subscribe to
`checkout.session.completed`, `customer.subscription.created|updated|deleted`
and `invoice.payment_failed`. The handler does not trust an event's payload: it
only learns which customer to look at, then derives the plan from that
customer's subscriptions as Stripe reports them now, so a duplicate or
out-of-order event is harmless. `past_due` stays Pro while Stripe retries.
Subscribing works whether or not `BILLING_ENABLED` is on, so a real payment can
be smoke-tested before the limits are switched on. Without a webhook secret the
endpoint answers 503 to everything; it never accepts an unchecked request.

Try it locally with Stripe's test mode and `stripe listen --forward-to
localhost:8080/api/billing/webhook` (it prints the `whsec_...` to use).

`python manage.py billing-check` is the launch preflight (read-only; exits 1 if
anything would break payments or mislead a customer; `--no-stripe` skips the API
calls, `--json` for a machine-readable report). It checks the settings, that
the Price is recurring and equals `PRO_PRICE_CENTS`/`PRO_PRICE_INTERVAL` in
`backend/billing.py` (the same numbers the Pricing page test holds the page to),
that the dashboard webhook points at this server with all five events, that a
Customer Portal exists, and lists the free accounts that would be blocked the
moment limits switch on. The ordered launch runbook is "Billing (Stripe)" in
`sys/DEPLOYMENT.md`. If you change the Pro price, change it in Stripe, in
`billing.py`, and on the Pricing page together.

### Card search

`GET /api/search` (and `pkanban search`) runs SQLite FTS5 over card titles and
descriptions. The index is `CardSearch` in `backend/models.py`, an
external-content table that holds only the index; the text stays in `card`.
Three triggers on `card` keep it current, so nothing in the API has to.

- **Triggers live with the table.** `CardSearch.create_table()` installs them
  and rebuilds the index if anything was missing, and `init_db()` calls it on
  every startup. A migration that rebuilds `card` (as 007 did) drops its
  triggers; the next startup puts them back and reindexes.
- **Never `DELETE FROM cardsearch`.** Deleting cards removes their index rows
  through the trigger. Emptying the index first and then deleting cards hands
  FTS5 'delete' commands for text it no longer holds, which corrupts the index
  without raising an error. `conftest.py` skips it for this reason, and
  `CardSearch.rebuild()` is the safe reset.
- **Board access is `accessible_boards(user)`** in `backend/api.py`. Search,
  the board list and `can_access_board` all use it, so a card search can never
  reach a board the list would hide.

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
