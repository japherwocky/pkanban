# pkanban card

Card management commands

## Commands

- [`pkanban card comment`](#pkanban-card-comment) — Comment on a card. `card get` shows a card's comments.
- [`pkanban card create`](#pkanban-card-create) — Create a new card.
- [`pkanban card delete`](#pkanban-card-delete) — Delete a card.
- [`pkanban card get`](#pkanban-card-get) — Show a card's full contents: its description and comments.
- [`pkanban card move`](#pkanban-card-move) — Move a card to another column or position, leaving its text alone.
- [`pkanban card update`](#pkanban-card-update) — Update a card. Anything you don't pass is left unchanged.

---

## `pkanban card comment`

Comment on a card. `card get` shows a card's comments.

```bash
pkanban card comment <card_id> [text] [--file FILE]
```

**Arguments**

- `card_id` (int) — Card ID
- `text` (str) _(optional)_ — The comment. '-' reads it from stdin.

**Options**

- `--file`, `-f` (str) — Read the comment from a file. Safer than passing it inline for anything long or quoted: no shell ever parses it.

## `pkanban card create`

Create a new card.

```bash
pkanban card create <column_id> <title> [--description DESCRIPTION] [--description-file DESCRIPTION_FILE] [--position POSITION]
```

**Arguments**

- `column_id` (int) — Column ID
- `title` (str) — Card title

**Options**

- `--description`, `-d` (str) — Card description. '-' reads it from stdin.
- `--description-file`, `-D` (str) — Read the description from a file. Safer than -d for anything long or quoted: no shell ever parses it.
- `--position`, `-p` (int) _(default: `0`)_ — Position

## `pkanban card delete`

Delete a card.

```bash
pkanban card delete <card_id>
```

**Arguments**

- `card_id` (int) — Card ID

## `pkanban card get`

Show a card's full contents: its description and comments.

```bash
pkanban card get <card_id>
```

**Arguments**

- `card_id` (int) — Card ID

## `pkanban card move`

Move a card to another column or position, leaving its text alone.

```bash
pkanban card move <card_id> [--column COLUMN] [--position POSITION]
```

**Arguments**

- `card_id` (int) — Card ID

**Options**

- `--column`, `-c` (int) — Destination column ID
- `--position`, `-p` (int) — Position within the column

## `pkanban card update`

Update a card. Anything you don't pass is left unchanged.

```bash
pkanban card update <card_id> [title] [--description DESCRIPTION] [--description-file DESCRIPTION_FILE] [--position POSITION] [--column COLUMN]
```

**Arguments**

- `card_id` (int) — Card ID
- `title` (str) _(optional)_ — New card title. Omit to leave the title alone.

**Options**

- `--description`, `-d` (str) — Card description. '-' reads it from stdin.
- `--description-file`, `-D` (str) — Read the description from a file. Safer than -d for anything long or quoted: no shell ever parses it.
- `--position`, `-p` (int) — Position
- `--column`, `-c` (int) — New column ID

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
