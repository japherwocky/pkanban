# Kanban CLI Commands

Complete reference for all Kanban CLI commands.

## Contents

- [Authentication & Configuration](#authentication-configuration)
- [Board Management](#board-management)
- [Column Management](#column-management)
- [Card Management](#card-management)
- [Organization Management](#organization-management)
- [Team Management](#team-management)

---

## Authentication & Configuration

### [`pkanban apikey`](/docs/commands/apikey)

API key management commands

- `pkanban apikey activate` — Reactivate a deactivated API key.
- `pkanban apikey clear` — Remove the saved API key from config, without revoking it server-side.
- `pkanban apikey create` — Create a new API key. The key is shown only once - save it securely!
- `pkanban apikey list` — List all API keys.
- `pkanban apikey revoke` — Revoke (deactivate) an API key.
- `pkanban apikey save` — Save API key to config file for future use.
- `pkanban apikey use` — Check that an API key works, without saving it anywhere.

### [`pkanban config`](/docs/commands/config)

Configure the CLI or show current settings.

### [`pkanban login`](/docs/commands/login)

Login to the pkanban server.

### [`pkanban logout`](/docs/commands/logout)

Logout and clear credentials.

## Board Management

### [`pkanban board`](/docs/commands/board)

Board management commands

- `pkanban board create` — Create a new board.
- `pkanban board delete` — Delete a board.
- `pkanban board get` — Show board details with column and card IDs.
- `pkanban board list` — List all boards.
- `pkanban board update` — Update board name.

### [`pkanban share`](/docs/commands/share)

Share board with a team or a whole organization, or make it private.

## Column Management

### [`pkanban column`](/docs/commands/column)

Column management commands

- `pkanban column create` — Create a new column.
- `pkanban column delete` — Delete a column.

## Card Management

### [`pkanban card`](/docs/commands/card)

Card management commands

- `pkanban card create` — Create a new card.
- `pkanban card delete` — Delete a card.
- `pkanban card get` — Show a card's full contents, including its description.
- `pkanban card move` — Move a card to another column or position, leaving its text alone.
- `pkanban card update` — Update a card. Anything you don't pass is left unchanged.

## Organization Management

### [`pkanban org`](/docs/commands/org)

Organization management commands

- `pkanban org create` — Create a new organization.
- `pkanban org get` — Show organization details.
- `pkanban org invite-create` — Create an invite link for an organization.
- `pkanban org invite-list` — List pending invites for an organization.
- `pkanban org invite-revoke` — Revoke a pending invite.
- `pkanban org list` — List all organizations.
- `pkanban org member-add` — Add member to organization.
- `pkanban org member-remove` — Remove member from organization.
- `pkanban org members` — List organization members.

## Team Management

### [`pkanban team`](/docs/commands/team)

Team management commands

- `pkanban team create` — Create a new team.
- `pkanban team get` — Show team details.
- `pkanban team list` — List teams in an organization.
- `pkanban team member-add` — Add member to team.
- `pkanban team member-remove` — Remove member from team.
- `pkanban team members` — List team members.

---

## Quick Links

- [Quick Start Guide](/docs/quickstart)
- [Common Workflows](/docs/workflows)
- [Full Reference](/docs/reference)
