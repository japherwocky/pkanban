# pkanban team

Team management commands

## Commands

- [`pkanban team create`](#pkanban-team-create) — Create a team, with you on it.
- [`pkanban team get`](#pkanban-team-get) — Show team details.
- [`pkanban team list`](#pkanban-team-list) — List the teams you can share a board with, or one organization's.
- [`pkanban team member-add`](#pkanban-team-member-add) — Add member to team.
- [`pkanban team member-remove`](#pkanban-team-member-remove) — Remove member from team.
- [`pkanban team members`](#pkanban-team-members) — List team members.

---

## `pkanban team create`

Create a team, with you on it.

```bash
pkanban team create <first> [name] [--org-id ORG_ID]
```

**Arguments**

- `first` (str) — Team name (or, before a name, an organization ID)
- `name` (str) _(optional)_ — Team name, after an organization ID

**Options**

- `--org-id`, `-o` (int) — Put the team in this organization

## `pkanban team get`

Show team details.

```bash
pkanban team get <team_id>
```

**Arguments**

- `team_id` (int) — Team ID

## `pkanban team list`

List the teams you can share a board with, or one organization's.

```bash
pkanban team list [--org-id ORG_ID]
```

**Options**

- `--org-id`, `-o` (int) — Only this organization's teams

## `pkanban team member-add`

Add member to team.

```bash
pkanban team member-add <team_id> <username>
```

**Arguments**

- `team_id` (int) — Team ID
- `username` (str) — Username to add

## `pkanban team member-remove`

Remove member from team.

```bash
pkanban team member-remove <team_id> <user_id>
```

**Arguments**

- `team_id` (int) — Team ID
- `user_id` (int) — User ID to remove

## `pkanban team members`

List team members.

```bash
pkanban team members <team_id>
```

**Arguments**

- `team_id` (int) — Team ID

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
