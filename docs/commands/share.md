# pkanban share

Share a board with a team (read, write or admin), a person, or an organization.

```bash
pkanban share <board_id> [team_id] [--permission PERMISSION] [--remove] [--email EMAIL] [--revoke-invite REVOKE_INVITE] [--org] [--org-id ORGANIZATION_ID]
```

**Arguments**

- `board_id` (int) — Board ID
- `team_id` (str) _(optional)_ — Team ID, or 'private' to unshare from everyone

**Options**

- `--permission`, `-p` (str) _(default: `write`)_ — read, write or admin (admins can share the board too)
- `--remove` (bool) — Take this team's access away
- `--email`, `-e` (str) — Invite this address to the board (sends them mail)
- `--revoke-invite` (int) — Revoke a pending invite, by its id
- `--org` (bool) — Share with a whole organization instead of a team
- `--org-id` (int) — Which organization, when you belong to more than one

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
