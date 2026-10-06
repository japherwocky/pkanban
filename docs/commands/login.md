# pkanban login

Sign in: in your browser (no username), or with a password.

```bash
pkanban login [username] [--password PASSWORD] [--server SERVER] [--wait] [--browser]
```

**Arguments**

- `username` (str) _(optional)_ — Username, to sign in with a password. Leave it out to approve this login in your browser instead -- nothing secret passes through the terminal, which is the way to sign in an AI agent.

**Options**

- `--password`, `-p` (str) — Password. Omit to be prompted (input hidden, stays out of shell history).
- `--server`, `-s` (str) — Server URL. Defaults to the configured URL (see 'pkanban config'). Passing it also saves it as the configured URL.
- `--wait` (bool) — Browser login only. --no-wait prints the link and returns at once; run 'pkanban login' again after approving to finish.
- `--browser` (bool) — Browser login only. Try to open the approval page.

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
