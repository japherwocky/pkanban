# pkanban apikey

API key management commands

## Commands

- [`pkanban apikey activate`](#pkanban-apikey-activate) — Reactivate a deactivated API key.
- [`pkanban apikey clear`](#pkanban-apikey-clear) — Remove the saved API key from config, without revoking it server-side.
- [`pkanban apikey create`](#pkanban-apikey-create) — Create a new API key. The key is shown only once - save it securely!
- [`pkanban apikey list`](#pkanban-apikey-list) — List all API keys.
- [`pkanban apikey revoke`](#pkanban-apikey-revoke) — Revoke (deactivate) an API key.
- [`pkanban apikey save`](#pkanban-apikey-save) — Save API key to config file for future use.
- [`pkanban apikey use`](#pkanban-apikey-use) — Check that an API key works, without saving it anywhere.

---

## `pkanban apikey activate`

Reactivate a deactivated API key.

```bash
pkanban apikey activate <key_id>
```

**Arguments**

- `key_id` (int) — API key ID to activate

## `pkanban apikey clear`

Remove the saved API key from config, without revoking it server-side.

```bash
pkanban apikey clear
```

## `pkanban apikey create`

Create a new API key. The key is shown only once - save it securely!

```bash
pkanban apikey create <name>
```

**Arguments**

- `name` (str) — Name for the API key (e.g., 'CI Agent')

## `pkanban apikey list`

List all API keys.

```bash
pkanban apikey list
```

## `pkanban apikey revoke`

Revoke (deactivate) an API key.

```bash
pkanban apikey revoke <key_id>
```

**Arguments**

- `key_id` (int) — API key ID to revoke

## `pkanban apikey save`

Save API key to config file for future use.

```bash
pkanban apikey save <key>
```

**Arguments**

- `key` (str) — API key to save

## `pkanban apikey use`

Check that an API key works, without saving it anywhere.

```bash
pkanban apikey use <key>
```

**Arguments**

- `key` (str) — API key to check

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
