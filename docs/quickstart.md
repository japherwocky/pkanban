# Quick Start

Get from `pip install` to a working board in a couple of minutes. Every command
below is copy-pasteable; the ones that print something show the output you
should expect.

This guide covers the day-to-day essentials. For the exhaustive list of
commands and flags, see the [Command Reference](reference) and
[All Commands](commands).

## 1. Install

```bash
pip install pkanban
```

This gives you the `pkanban` command. Check it:

```bash
pkanban --version
```

## 2. Connect and log in

Point the CLI at a server, then log in. The hosted service is the usual choice:

```bash
pkanban config --url https://pkanban.pearachute.com
pkanban login <your-username> --password <your-password>
```

```
Server URL set to: https://pkanban.pearachute.com
Logged in as <your-username>
```

`login` uses whatever URL you configured, so you only set the URL once. Your
token is saved to `~/.pkanban.yaml` and reused by every later command — you stay
logged in until you run `pkanban logout`.

Self-hosting instead? Point at your own server:

```bash
pkanban config --url http://localhost:8000
```

> **Heads up:** the password is passed on the command line, so it lands in your
> shell history. For anything unattended (CI, agents, scripts), use an
> [API key](#4-automating-with-api-keys) instead of a password.

Check your connection and identity any time:

```bash
pkanban config          # shows the current server URL
pkanban board list      # first thing to confirm you're authenticated
```

## 3. Your first board

A new board starts **empty** — no columns, no cards. You add the columns you
want, then drop cards into them. IDs are printed as you go; you'll pass them to
the next command.

Create a board:

```bash
pkanban board create "Roadmap"
```

```
Board created with id=7
```

Add a few columns. The last argument is the position (left to right, 0-based):

```bash
pkanban column create 7 "To Do" 0
pkanban column create 7 "In Progress" 1
pkanban column create 7 "Done" 2
```

```
Column created with id=13
Column created with id=14
Column created with id=15
```

Add a card to the "To Do" column (id `13`):

```bash
pkanban card create 13 "Ship v1" --description "Cut the first release" --position 0
```

```
Card created with id=21
```

Now look at the whole board. `board get` is the command you'll reach for most —
it prints every column and card with their IDs:

```bash
pkanban board get 7
```

```
Board: Roadmap
  #13 To Do (1 cards)
    - #21 Ship v1
  #14 In Progress (0 cards)
  #15 Done (0 cards)
```

Move the card to "In Progress" (id `14`) by updating its column:

```bash
pkanban card update 21 "Ship v1" --column 14
```

That's the full loop: create a board, shape it with columns, and move cards
across it.

## 4. Automating with API keys

For CI, scripts, or agents, authenticate with an API key instead of a password.
Create one while logged in:

```bash
pkanban apikey create "CI agent"
```

```
API Key created!

  Name:    CI agent
  Key:     pkanban_a1b2c3d4e5f6...
  Prefix:  pkanban_a....

IMPORTANT: This key is shown only once! Copy it now and store it securely.
```

Save it once, and every later command uses it — no `pkanban login` needed:

```bash
pkanban apikey save pkanban_a1b2c3d4e5f6...
pkanban board list          # now authenticated by the key
```

Manage keys as you'd expect:

```bash
pkanban apikey list                 # see keys, when each was last used
pkanban apikey revoke <key-id>      # deactivate a key
pkanban apikey activate <key-id>    # turn it back on
```

Revoke a key the moment it leaks — that cuts off access without touching your
password or other keys.

## 5. Sharing with a team

Boards are private to you until you share them. Sharing is **team-based**: you
share a board with a team, and everyone on that team gets access. Teams live
inside organizations, so the order is org → team → members → share.

```bash
pkanban org create "Acme"                 # prints an org id
pkanban team create <org-id> "Engineering" # prints a team id
pkanban org member-add <org-id> <username> # add the person to the org
pkanban team member-add <team-id> <username> # then to the team
pkanban share 7 <team-id>                 # share board 7 with the team
```

Make a board private again at any time:

```bash
pkanban share 7 private
```

Inspect what exists:

```bash
pkanban org list
pkanban org members <org-id>
pkanban team list --org-id <org-id>
pkanban team members <team-id>
```

Not everyone you want to share with has an account yet? Invite them:

```bash
pkanban org invite-create <org-id> --email teammate@example.com
pkanban org invite-list <org-id>
```

## How it fits together

```
Organization
  └─ Team ────────────── shared with ──┐
       └─ Members                      │
                                       ▼
User ── owns ──► Board ─► Column ─► Card
```

- **Boards** belong to a user and hold **columns**, which hold **cards**.
- **Organizations** group people; **teams** are subsets of an org.
- **Sharing** connects a board to a team — that's how other people see it.

## Common gotchas

- **New boards have no columns.** Create them yourself (step 3); there's no
  default set.
- **You need to be authenticated first.** Run `pkanban login` (or save an API
  key) before any board command, or you'll get an auth error.
- **Positions are 0-based** for both columns and cards, ordered left-to-right
  and top-to-bottom.
- **Sharing replaces, it doesn't stack.** Sharing a board with a new team
  removes the previous team's access rather than adding to it.
- **IDs come from the command that made the thing.** `board get <id>` reprints
  all of them if you lose track.

## Getting help

Every command and subcommand supports `--help`, which lists its exact arguments
and flags:

```bash
pkanban --help
pkanban board --help
pkanban card create --help
```

From here:

- [Command Reference](reference) — every command, grouped and explained
- [Common Workflows](workflows) — recipes for real tasks
- [Authentication](auth) — tokens, API keys, and how sessions work
- [Organizations & Teams](multi-tenant) — the multi-tenant model in depth
