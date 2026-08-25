# pkanban login

Login to the pkanban server.

```bash
pkanban login <username> --password PASSWORD [--server SERVER]
```

**Arguments**

- `username` (str) — Username

**Options**

- `--password`, `-p` (str) _(required)_ — Password. Omit to be prompted (input hidden, stays out of shell history).
- `--server`, `-s` (str) — Server URL. Defaults to the configured URL (see 'pkanban config'). Passing it also saves it as the configured URL.

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
