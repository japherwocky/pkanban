# pkanban team

Team management commands

## Commands

- [`pkanban team create`](#pkanban-team-create) — Create a new team.
- [`pkanban team get`](#pkanban-team-get) — Show team details.
- [`pkanban team list`](#pkanban-team-list) — List teams in an organization.
- [`pkanban team member-add`](#pkanban-team-member-add) — Add member to team.
- [`pkanban team member-remove`](#pkanban-team-member-remove) — Remove member from team.
- [`pkanban team members`](#pkanban-team-members) — List team members.

---

## `pkanban team create`

Create a new team.

```bash
pkanban team create <org_id> <name>
```

**Arguments**

- `org_id` (int) — Organization ID
- `name` (str) — Team name

## `pkanban team get`

Show team details.

```bash
pkanban team get <team_id>
```

**Arguments**

- `team_id` (int) — Team ID

## `pkanban team list`

List teams in an organization.

```bash
pkanban team list --org-id ORG_ID
```

**Options**

- `--org-id`, `-o` (int) _(required)_ — Organization ID (required)

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
