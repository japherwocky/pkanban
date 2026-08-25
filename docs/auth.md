# Authentication & Authorization

## Authentication Methods

The API accepts two independent credential types. [`get_current_user_or_api_key`](../backend/auth.py) checks for an `X-API-Key` header first and falls back to a `Bearer` JWT — either is sufficient, you don't need both.

### JWT (session login)

Used by `pkanban login` and the web UI.

- `POST /token` (username + password) returns a signed JWT (`create_access_token` in [`backend/auth.py`](../backend/auth.py)), sent back as `Authorization: Bearer <token>`.
- Signed with HS256 using a server-side secret (`JWT_SECRET_KEY`, or an auto-generated key persisted next to the database — see [`_load_secret_key`](../backend/auth.py)).
- **Expiration slides while the session is in use.** `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24` (24 hours) is still baked into the `exp` claim at issuance, but a token presented with less than `TOKEN_RENEWAL_WINDOW_MINUTES` (12 hours) of life left is replaced: the server returns a fresh one on the `X-Renewed-Token` response header, and both clients persist it. A session in continuous use therefore does not hit the 24-hour cliff; one left alone for a full day does.
- **Renewal is capped.** Every token carries `auth_time`, the moment the user actually authenticated, and renewal carries it forward unchanged rather than resetting it. Past `SESSION_ABSOLUTE_MAX_DAYS` (30 days) the server stops renewing and a real login is required. These JWTs are stateless and cannot be revoked, so without the cap a stolen token could be kept alive indefinitely.
- Renewal happens in a single middleware (`renew_session_token` in [`backend/main.py`](../backend/main.py)) rather than in the auth dependencies, so it applies to every authenticated request whichever dependency guarded it. API keys arrive on `X-API-Key`, never as a Bearer token, so they never reach it.
- The CLI persists the token in its config file (see `pkanban config`); there's no refresh-token flow and no server-side session — expiry past the cap just means re-authenticating.

### API Keys (headless / agent access)

Used for CI, bots, and other non-interactive clients — see [`pkanban apikey`](commands/apikey.md).

- Created via `pkanban apikey create <name>` (`POST /api-keys`), sent as `X-API-Key: <key>`.
- The raw key is shown only once at creation; the server stores only a hash plus an 8-character lookup prefix.
- **No expiration by default.** `expires_at` is optional and unset unless explicitly passed at creation — an API key otherwise lives forever until revoked (`pkanban apikey revoke`).
- `last_used_at` is updated on every successful use, but — like the JWT — this is informational only and does not extend `expires_at` if one was set.
- Keys can be deactivated (`pkanban apikey revoke`) and later reactivated (`pkanban apikey activate`) without changing the underlying key value.

## Authorization: Organization Schema

Multi-tenant organization model with team-based board sharing.

## Models

### User

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| username | String(100) | Unique username |
| password_hash | String(255) | bcrypt hash |
| email | String(255), null | User email |
| admin | Boolean | Platform super admin (default: false) |

### Organization

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| name | String(200) | Organization display name |
| slug | String(200) | URL-friendly identifier, unique |
| created_at | DateTime | Creation timestamp |

### OrganizationMember

Many-to-many relationship between User and Organization.

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| user | ForeignKey(User) | Member user |
| organization | ForeignKey(Organization) | Organization |
| role | String | owner \| admin \| member |
| joined_at | DateTime | When joined |

### Team

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| name | String(200) | Team name |
| organization | ForeignKey(Organization) | Parent organization |

Special team: Each org has an "Administrators" team created by default.

### TeamMember

Many-to-many relationship between User and Team.

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| user | ForeignKey(User) | Team member |
| team | ForeignKey(Team) | Team |
| role | String | admin \| member |
| joined_at | DateTime | When joined |

### Board

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| owner | ForeignKey(User) | User who created the board |
| name | String(200) | Board name |
| shared_team | ForeignKey(Team), null | Team with access |
| created_at | DateTime | Creation timestamp |

**Board Access Rules:**
- `shared_team = null`: Private board, only owner can access
- `shared_team = set`: Shared with that team, owner + team members can access

**Permissions:**
- Owner: Full control (edit, share, delete, change shared_team)
- Team members: Full edit access (cards, columns), cannot delete or change sharing

## Access Control Logic

### Board Access Check

```python
def can_access_board(user, board):
    # Owner always has access
    if board.owner == user:
        return True

    # Check team access
    if board.shared_team:
        return TeamMember.exists(
            (TeamMember.user == user) &
            (TeamMember.team == board.shared_team)
        )

    return False
```

### Org Role Mapping

| Org Role | Access Level |
|----------|--------------|
| owner | Full org control, can manage members, teams, delete org |
| admin | Can manage members, teams, billing settings |
| member | Can view org, create teams, create boards |

### Platform Admin

Users with `admin = true` on User model can:
- Access any board (bypasses ownership/team checks)
- Manage any organization
- View system-wide analytics
- No special UI, just elevated API permissions

## API Endpoints

### Organizations

- `POST /organizations` - Create organization
- `GET /organizations` - List user's organizations
- `GET /organizations/{id}` - Get organization details
- `PUT /organizations/{id}` - Update organization (owner only)
- `DELETE /organizations` - Soft delete (owner only)

### Organization Members

- `POST /organizations/{id}/members` - Invite member
- `GET /organizations/{id}/members` - List members
- `PUT /organizations/{id}/members/{user_id}` - Update role
- `DELETE /organizations/{id}/members/{user_id}` - Remove member

### Teams

- `POST /organizations/{id}/teams` - Create team
- `GET /organizations/{id}/teams` - List teams
- `PUT /teams/{id}` - Update team (team admin only)
- `DELETE /teams/{id}` - Delete team (org admin only)

### Team Members

- `POST /teams/{id}/members` - Add member
- `GET /teams/{id}/members` - List members
- `PUT /teams/{id}/members/{user_id}` - Update role
- `DELETE /teams/{id}/members/{user_id}` - Remove member

### Boards (updated)

- `POST /boards` - Create board (personal or org-associated)
- `GET /boards` - List accessible boards (personal + shared)
- `PUT /boards/{id}` - Update board (owner or team member)
- `DELETE /boards/{id}` - Delete board (owner only)
- `POST /boards/{id}/share` - Share with team (owner only)
- `DELETE /boards/{id}/share` - Unshare (owner only)

## Database Schema Diagram

```
User ──┬── OrganizationMember ── Organization ── Team ── TeamMember
       │         (M2M)                  │
       │                              Board
       │                                │
       └────────────────────────────────┘
         (owner FK on Board)
```

## Migration Notes

When upgrading from single-user boards to multi-tenant:

1. Create Organization table
2. Create OrganizationMember table
3. Create Team table
4. Create TeamMember table
5. Add fields to User: email (nullable), admin (default false)
6. Add field to Board: shared_team FK (nullable)
7. Existing boards remain owned by original user, shared_team = null (private)

No automatic org creation for existing users. Users can optionally create organizations and migrate boards if desired.
