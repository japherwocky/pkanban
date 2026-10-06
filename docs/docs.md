# pkanban Documentation

Welcome to the pkanban documentation. This guide covers everything you need to know to use pkanban.

## Getting Started

New to pkanban? Start here:

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

Setting up pkanban for someone? Start at
[/agents.md](https://pkanban.pearachute.com/agents.md): install, sign-in (your
person approves it in their browser), picking a board, and recording it in the
project's `AGENTS.md` with `pkanban init`. Telling an agent "Read
pkanban.pearachute.com/agents.md and set up pkanban for me" is the whole setup.

The rest of the docs are raw markdown too:

```bash
# Get specific command docs
curl https://pkanban.pearachute.com/docs/commands/apikey.md

# Get quickstart
curl https://pkanban.pearachute.com/docs/quickstart.md

# Get full reference
curl https://pkanban.pearachute.com/docs/reference.md
```

## Support

- Report issues on [GitHub](https://github.com/japherwocky/pkanban)
- View source code at [github.com/japherwocky/pkanban](https://github.com/japherwocky/pkanban)
