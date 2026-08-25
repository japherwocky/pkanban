# pkanban board

Board management commands

## Commands

- [`pkanban board create`](#pkanban-board-create) — Create a new board.
- [`pkanban board delete`](#pkanban-board-delete) — Delete a board.
- [`pkanban board get`](#pkanban-board-get) — Show board details with column and card IDs.
- [`pkanban board list`](#pkanban-board-list) — List all boards.
- [`pkanban board update`](#pkanban-board-update) — Update board name.

---

## `pkanban board create`

Create a new board.

```bash
pkanban board create <name>
```

**Arguments**

- `name` (str) — Board name

## `pkanban board delete`

Delete a board.

```bash
pkanban board delete <board_id>
```

**Arguments**

- `board_id` (int) — Board ID

## `pkanban board get`

Show board details with column and card IDs.

```bash
pkanban board get <board_id>
```

**Arguments**

- `board_id` (int) — Board ID

## `pkanban board list`

List all boards.

```bash
pkanban board list
```

## `pkanban board update`

Update board name.

```bash
pkanban board update <board_id> <name>
```

**Arguments**

- `board_id` (int) — Board ID
- `name` (str) — New board name

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
