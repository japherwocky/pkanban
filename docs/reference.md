# CLI Command Reference Cheat Sheet

Complete reference for all Kanban CLI commands. Perfect for quick lookups during agent operations.

> **Detailed Pages:** Each command group has a dedicated page with examples:
> - [All Commands Index](/docs/commands) - Navigable command list
> - [Authentication](/docs/commands/config) - config, login, logout
> - [Boards](/docs/commands/board) - board list, create, get, update, delete; share
> - [Columns](/docs/commands/column) - column management
> - [Cards](/docs/commands/card) - card management
> - [Organizations](/docs/commands/org) - org management
> - [Teams](/docs/commands/team) - team management
> - [API Keys](/docs/commands/apikey) - apikey management

## 🔐 Authentication & Configuration

| Command | Usage | Description |
|---------|-------|-------------|
| `pkanban config` | `pkanban config [--url URL]` | Show or set server URL |
| `pkanban login` | `pkanban login <user> --password <pass>` | Login to server |
| `pkanban logout` | `pkanban logout` | Logout and clear credentials |

## 📋 Board Management

| Command | Usage | Description |
|---------|-------|-------------|
| `pkanban board list` | `pkanban board list` | List all accessible boards |
| `pkanban board create` | `pkanban board create <name>` | Create new board |
| `pkanban board get` | `pkanban board get <board-id>` | Show board details |
| `pkanban board update` | `pkanban board update <board-id> <name>` | Rename board |
| `pkanban board delete` | `pkanban board delete <board-id>` | Delete board |
| `pkanban share` | `pkanban share <board-id> <team-id\|private>` | Share with team or make private |

## 📊 Column Management

| Command | Usage | Description |
|---------|-------|-------------|
| `pkanban column create` | `pkanban column create <board-id> <name> <position>` | Create column |
| `pkanban column delete` | `pkanban column delete <column-id>` | Delete column |

## 🃏 Card Management

| Command | Usage | Description |
|---------|-------|-------------|
| `pkanban card create` | `pkanban card create <column-id> <title> [--description TEXT] [--position NUM]` | Create card |
| `pkanban card update` | `pkanban card update <card-id> <title> [--description TEXT] [--position NUM] [--column NUM]` | Update card |
| `pkanban card delete` | `pkanban card delete <card-id>` | Delete card |

## 🏢 Organization Commands (`pkanban org`)

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `pkanban org list` | `pkanban org list` | List all organizations |
| `pkanban org create` | `pkanban org create <name>` | Create organization |
| `pkanban org get` | `pkanban org get <org-id>` | Show organization details |
| `pkanban org members` | `pkanban org members <org-id>` | List organization members |
| `pkanban org member-add` | `pkanban org member-add <org-id> <username>` | Add member |
| `pkanban org member-remove` | `pkanban org member-remove <org-id> <user-id>` | Remove member |

## 👥 Team Commands (`pkanban team`)

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `pkanban team list` | `pkanban team list --org-id <org-id>` | List teams in org |
| `pkanban team create` | `pkanban team create <org-id> <name>` | Create team |
| `pkanban team get` | `pkanban team get <team-id>` | Show team details |
| `pkanban team members` | `pkanban team members <team-id>` | List team members |
| `pkanban team member-add` | `pkanban team member-add <team-id> <username>` | Add member |
| `pkanban team member-remove` | `pkanban team member-remove <team-id> <user-id>` | Remove member |

## 🔑 API Key Commands (`pkanban apikey`)

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `pkanban apikey list` | `pkanban apikey list` | List all API keys |
| `pkanban apikey create` | `pkanban apikey create <name>` | Create new API key |
| `pkanban apikey revoke` | `pkanban apikey revoke <key-id>` | Revoke/deactivate an API key |
| `pkanban apikey activate` | `pkanban apikey activate <key-id>` | Reactivate a deactivated API key |
| `pkanban apikey use` | `pkanban apikey use <key> <command>` | Run command using an API key |

## 🎯 Common Parameter Patterns

### IDs are always numbers
- Board IDs: `1`, `2`, `3`
- Column IDs: `1`, `2`, `3`  
- Card IDs: `1`, `2`, `3`
- Organization IDs: `1`, `2`, `3`
- Team IDs: `1`, `2`, `3`
- User IDs: `1`, `2`, `3`

### Position is always 0-based
- Position 0 = first position
- Position 1 = second position
- etc.

### Required vs Optional Parameters
```bash
# Required parameters (no brackets)
pkanban board create "Board Name"

# Optional parameters (shown in brackets)
pkanban card create 1 "Title" --description "Optional" --position 0
```

## 🚀 Quick Command Sequences

### New Board Setup
```bash
pkanban board create "Project Name"
pkanban board get <new-board-id>  # Get default columns
pkanban column create <board-id> "To Do" 0
pkanban column create <board-id> "Doing" 1
pkanban column create <board-id> "Done" 2
```

### Team Setup
```bash
pkanban org create "Company"
pkanban team create <org-id> "Dev Team"
pkanban org member-add <org-id> <username>
pkanban team member-add <team-id> <username>
```

### Card Workflow
```bash
pkanban card create <todo-column-id> "New Task" --position 0
pkanban card update <card-id> "Updated Task" --column <doing-column-id> --position 0
pkanban card update <card-id> "Completed Task" --column <done-column-id> --position 0
```

## 🔧 Help System

Get help for any command:
```bash
pkanban --help                    # All commands
pkanban board create --help       # Specific command
pkanban org --help               # Organization sub-commands
pkanban team --help              # Team sub-commands
```

## ⚡ Pro Tips

1. **Always run `pkanban board list` first** to see available board IDs
2. **Use `pkanban board get <id>`** to see column IDs for card operations
3. **Team commands require `--org-id`** flag except for `team get`
4. **Board sharing overwrites** existing sharing settings
5. **Positions are per-column** for cards, per-board for columns