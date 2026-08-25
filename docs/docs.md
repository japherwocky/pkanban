# Kanban CLI Documentation

Welcome to the Kanban CLI documentation. This guide covers everything you need to know to use the Kanban command-line interface.

## Getting Started

New to the Kanban CLI? Start here:

- [Quick Start Guide](/docs/quickstart) - Get up and running in minutes
- [Command Reference](/docs/reference) - Complete list of all commands

## Core Concepts

- [Authentication](/docs/auth) - Login, logout, and API keys
- [Organizations & Teams](/docs/commands/org) - Multi-tenant workspace management

## Command Reference

Browse all available commands:

- [All Commands Index](/docs/commands) - Navigable list of every command
- [Authentication](/docs/commands/config) - config, login, logout
- [Boards](/docs/commands/board) - List, create, view, delete boards
- [Columns](/docs/commands/column) - Manage board columns
- [Cards](/docs/commands/card) - Create and manage cards
- [Organizations](/docs/commands/org) - Organization management
- [Teams](/docs/commands/team) - Team management
- [API Keys](/docs/commands/apikey) - Headless access for agents

## Common Workflows

See [Common Workflows](/docs/workflows) for step-by-step guides:

- Setting up a new board
- Team collaboration patterns
- Card workflow management

## For Agents

Agents can access raw markdown documentation directly:

```bash
# Get specific command docs
curl https://your-domain.com/docs/commands/apikey.md

# Get quickstart
curl https://your-domain.com/docs/quickstart.md

# Get full reference
curl https://your-domain.com/docs/reference.md
```

## Support

- Report issues on [GitHub](https://github.com/japherwocky/pkanban)
- View source code at [github.com/japherwocky/pkanban](https://github.com/japherwocky/pkanban)
