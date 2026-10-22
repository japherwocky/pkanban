# Multi-Tenant Organizations

The application supports multi-tenant organizations with team-based board sharing.

## Organization Model

- **Organizations** group users and teams
- **Organization Members** have roles: `owner`, `admin`, or `member`
- **Teams** are groups of users within an organization
- **Team Members** have roles: `admin` or `member`

## Board Sharing

- Boards are always owned by an individual user
- By default, boards are private (only the owner can access)
- Boards can be shared with any number of teams, each at `read`, `write` or `admin`
- A board shared with an organization gets a level of its own too (`write` by default)
- Someone reachable several ways gets the highest level; the owner is always admin
- `admin` can share the board; only the owner can delete it
- A team needs no organization: membership is the grant

## Organization API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/organizations` | Create organization (auto-creates "Administrators" team) |
| `GET` | `/api/organizations` | List user's organizations |
| `GET` | `/api/organizations/{id}` | Get organization details |
| `PUT` | `/api/organizations/{id}` | Update organization (owner/admin only) |
| `POST` | `/api/organizations/{id}/members` | Add member |
| `GET` | `/api/organizations/{id}/members` | List members |
| `PUT` | `/api/organizations/{id}/members/{user_id}` | Update member role |
| `DELETE` | `/api/organizations/{id}/members/{user_id}` | Remove member |

## Team API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/organizations/{id}/teams` | Create team |
| `GET` | `/api/organizations/{id}/teams` | List teams |
| `PUT` | `/api/teams/{id}` | Update team (team admin only) |
| `DELETE` | `/api/teams/{id}` | Delete team (org admin only) |
| `POST` | `/api/teams/{id}/members` | Add team member |
| `GET` | `/api/teams/{id}/members` | List team members |
| `PUT` | `/api/teams/{id}/members/{user_id}` | Update team member role |
| `DELETE` | `/api/teams/{id}/members/{user_id}` | Remove team member |

## Board Sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/boards/{id}/teams/{team_id}` | Share with a team, or change its level: `{"permission": "read" \| "write" \| "admin"}` (admin) |
| `DELETE` | `/api/boards/{id}/teams/{team_id}` | Take a team's access away (admin) |
| `POST` | `/api/boards/{id}/share` | Organization sharing: `{"is_public_to_org", "organization_id", "org_permission"}` (admin) |
| `POST` | `/api/boards/{id}/invites` | Invite someone by email: `{"email", "permission"}` (admin). Makes a team of you and them, shares the board with it, mails them a link. Answers with the link and `email_sent` |
| `DELETE` | `/api/boards/{id}/invites/{invite_id}` | Revoke a pending invite (admin) |
| `POST` | `/api/teams` | Create a team in no organization, with you on it |
| `GET` | `/api/me/teams` | Teams you can share a board with: yours, and your organizations' |

You can share only with a team you are on, or one in an organization you belong
to. `GET /api/boards/{id}` reports your `permission` and the board's `teams`.

`POST /share` with `{"team_id": null, "is_public_to_org": false}` makes a board
private: every team comes off. Older clients send `{"team_id": <id>}` there to
share with a team; that adds it at `write`.
