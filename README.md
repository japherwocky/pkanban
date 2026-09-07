# pkanban

A CLI-first Kanban board for humans and AI agents. (The "p" is silent, like in "pneumonia".)

Most users will connect to our hosted service at [pkanban.pearachute.com](https://pkanban.pearachute.com). If you want to run your own server, see the Self-Hosting section below.

## Quick Start

```bash
pip install pkanban
```

The CLI connects to the hosted service at https://pkanban.pearachute.com by
default, so you can log in right away:

```bash
pkanban login <username>
```

You'll be prompted for your password (it stays out of your shell history).
That's it! You can now manage your boards from the command line.

> Self-hosting? Point the CLI at your own server first with
> `pkanban config --url http://localhost:8000` — see [Self-Hosting](#self-hosting).

## Common Commands

```bash
# List your boards
pkanban board list

# Create a new board
pkanban board create "My Project"

# View a board with its columns and cards
pkanban board get 1

# Add a column
pkanban column create 1 "To Do" 0

# Add a card
pkanban card create 1 "First task" --description "Getting started"

# Share a board with a team
pkanban share 1 <team-id>
```

## API Keys

For automation, CI/CD, or giving access to agents, use API keys instead of passwords:

```bash
# Create a key (shown only once!)
pkanban apikey create "CI Agent"

# Save it once; subsequent commands use it automatically
pkanban apikey save pkanban_abc123...
pkanban board list

# Or pass it per command
pkanban --api-key pkanban_abc123... board list
```

API keys can be revoked and reactivated at any time. They're stored securely (bcrypt-hashed) and track their last usage.

## Scripting: JSON output

`--json` makes any command print the raw API response instead of formatted
text, so scripts never have to scrape prose for values like IDs:

```bash
pkanban board create "Roadmap" --json
pkanban board get 1 --json | jq '.columns[] | {id, name}'
```

`PKANBAN_OUTPUT=json` does the same for a whole run:

```bash
export PKANBAN_OUTPUT=json
```

The flag works in either position (`pkanban --json board list` and
`pkanban board list --json` are equivalent). In JSON mode stdout carries only
the response, and errors go to stderr as `{"error": ..., "status": ...}` with a
non-zero exit code — so stdout is always safe to pipe into a parser.

`pkanban login --json` deliberately omits the access token: it is already saved
to `~/.pkanban.yaml`, and stdout is what CI logs capture.

## Command Reference

| Command | Description |
|---------|-------------|
| `pkanban config [--url URL]` | Show or set server URL |
| `pkanban login <user> --password <pass>` | Login to the server |
| `pkanban logout` | Logout and clear credentials |
| `pkanban --api-key <key>` | Use API key for authentication |
| `pkanban --json <command>` | Print the raw API response as JSON |
| `pkanban apikey create <name>` | Generate a new API key |
| `pkanban apikey list` | List your API keys |
| `pkanban apikey revoke <id>` | Revoke an API key |
| `pkanban apikey activate <id>` | Reactivate a revoked key |
| `pkanban board list` | List all boards |
| `pkanban board create <name>` | Create a new board |
| `pkanban board get <id>` | Show board details |
| `pkanban board delete <id>` | Delete a board |
| `pkanban board update <id> <name>` | Update board name |
| `pkanban share <board_id> <team_id\|private>` | Share board or make private |
| `pkanban column create <board_id> <name> [position]` | Create a column (appends by default) |
| `pkanban column delete <id>` | Delete a column |
| `pkanban card get <id>` | Show a card's description and comments |
| `pkanban card create <column_id> <title> [options]` | Create a card |
| `pkanban card update <id> [title] [options]` | Update a card; omitted fields are unchanged |
| `pkanban card move <id> --column <n> [-p <pos>]` | Move a card without touching its text |
| `pkanban card delete <id>` | Delete a card |
| `pkanban org list` | List all organizations |
| `pkanban org create <name>` | Create an organization |
| `pkanban org get <org-id>` | Show organization details |
| `pkanban org members <org-id>` | List organization members |
| `pkanban org member-add <org-id> <username>` | Add member to organization |
| `pkanban org member-remove <org-id> <user-id>` | Remove member |
| `pkanban team list --org-id <org-id>` | List teams in organization |
| `pkanban team create <org-id> <name>` | Create a new team |
| `pkanban team get <team-id>` | Show team details |
| `pkanban team members <team-id>` | List team members |
| `pkanban team member-add <team-id> <username>` | Add member to team |
| `pkanban team member-remove <team-id> <user-id>` | Remove member from team |

## Self-Hosting

Want to run your own server? Here's how:

### 1. Clone and setup

```bash
git clone https://github.com/japherwocky/pkanban.git
cd pkanban
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### 2. Initialize and run

```bash
python manage.py init
python manage.py user-create admin mypassword --admin
python manage.py server
```

The server runs at http://localhost:8000 by default.

### 3. Connect the CLI

The CLI defaults to the hosted service, so point it at your local server first,
then log in (you'll be prompted for the password):

```bash
pkanban config --url http://localhost:8000
pkanban login admin
```

## Development

```bash
# Run the server with auto-reload
python manage.py server

# Run frontend dev server (hot reload)
cd frontend && npm run dev

# Run tests
python -m pytest backend/tests/
```

### Database commands

```bash
python manage.py init          # Create tables
python manage.py wipe          # Drop and recreate tables
python manage.py status        # Check database status
python manage.py user-create <user> <pass> [--admin]
```

## API Reference

The backend exposes a REST API at `/api/`:

**Authentication**
- `POST /api/token` - Login (returns JWT)
- `X-API-Key` header - Alternative auth via API key

**API Keys**
- `GET /api/api-keys` - List your keys
- `POST /api/api-keys` - Create a key
- `DELETE /api/api-keys/{id}` - Revoke a key
- `POST /api/api-keys/{id}/activate` - Reactivate a key

**Boards**
- `GET /api/boards` - List accessible boards
- `POST /api/boards` - Create a board
- `GET /api/boards/{id}` - Get board details
- `POST /api/boards/{id}` - Update board
- `DELETE /api/boards/{id}` - Delete board

**Columns**
- `POST /api/columns` - Create column
- `PUT /api/columns/{id}` - Update column
- `DELETE /api/columns/{id}` - Delete column

**Cards**
- `GET /api/cards/{id}` - Get one card with its description and comments
- `POST /api/cards` - Create card
- `PUT /api/cards/{id}` - Update card
- `DELETE /api/cards/{id}` - Delete card

For multi-tenant organization details, see [docs/multi-tenant.md](docs/multi-tenant.md).