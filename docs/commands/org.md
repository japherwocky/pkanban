# pkanban org

Organization management commands

## Commands

- [`pkanban org create`](#pkanban-org-create) — Create a new organization.
- [`pkanban org get`](#pkanban-org-get) — Show organization details.
- [`pkanban org invite-create`](#pkanban-org-invite-create) — Create an invite link for an organization.
- [`pkanban org invite-list`](#pkanban-org-invite-list) — List pending invites for an organization.
- [`pkanban org invite-revoke`](#pkanban-org-invite-revoke) — Revoke a pending invite.
- [`pkanban org list`](#pkanban-org-list) — List all organizations.
- [`pkanban org member-add`](#pkanban-org-member-add) — Add member to organization.
- [`pkanban org member-remove`](#pkanban-org-member-remove) — Remove member from organization.
- [`pkanban org members`](#pkanban-org-members) — List organization members.

---

## `pkanban org create`

Create a new organization.

```bash
pkanban org create <name>
```

**Arguments**

- `name` (str) — Organization name

## `pkanban org get`

Show organization details.

```bash
pkanban org get <org_id>
```

**Arguments**

- `org_id` (int) — Organization ID

## `pkanban org invite-create`

Create an invite link for an organization.

```bash
pkanban org invite-create <org_id> [--email EMAIL]
```

**Arguments**

- `org_id` (int) — Organization ID

**Options**

- `--email`, `-e` (str) — Email of person to invite

## `pkanban org invite-list`

List pending invites for an organization.

```bash
pkanban org invite-list <org_id>
```

**Arguments**

- `org_id` (int) — Organization ID

## `pkanban org invite-revoke`

Revoke a pending invite.

```bash
pkanban org invite-revoke <org_id> <invite_id>
```

**Arguments**

- `org_id` (int) — Organization ID
- `invite_id` (int) — Invite ID to revoke

## `pkanban org list`

List all organizations.

```bash
pkanban org list
```

## `pkanban org member-add`

Add member to organization.

```bash
pkanban org member-add <org_id> <username>
```

**Arguments**

- `org_id` (int) — Organization ID
- `username` (str) — Username to add

## `pkanban org member-remove`

Remove member from organization.

```bash
pkanban org member-remove <org_id> <user_id>
```

**Arguments**

- `org_id` (int) — Organization ID
- `user_id` (int) — User ID to remove

## `pkanban org members`

List organization members.

```bash
pkanban org members <org_id>
```

**Arguments**

- `org_id` (int) — Organization ID

## See Also

- [All Commands](/docs/commands)
- [CLI Reference](/docs/reference)
