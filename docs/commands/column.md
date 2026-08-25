# pkanban column

Column management commands

## Commands

- [`pkanban column create`](#pkanban-column-create) — Create a new column.
- [`pkanban column delete`](#pkanban-column-delete) — Delete a column.

---

## `pkanban column create`

Create a new column.

```bash
pkanban column create <board_id> <name> [position]
```

**Arguments**

- `board_id` (int) — Board ID
- `name` (str) — Column name
- `position` (int) _(optional)_ — Position. Omit to append after the last column.

## `pkanban column delete`

Delete a column.

```bash
pkanban column delete <column_id>
```

**Arguments**

- `column_id` (int) — Column ID

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
