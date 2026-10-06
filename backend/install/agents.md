# pkanban: setup for AI agents

You are an AI agent, and your person wants you to track work on pkanban: a
kanban board you drive from the command line and they watch in a browser at
__PKANBAN_SERVER__. Follow these steps in order. Each one checks before it
acts, so it is safe to start again from the top.

## 1. Install the CLI

Check first:

```bash
pkanban --version
```

You need 0.7.0 or later. If `pkanban` is missing or older, install it.
macOS, Linux or WSL:

```bash
curl -fsSL __PKANBAN_SERVER__/install.sh | sh
```

Windows PowerShell:

```powershell
irm __PKANBAN_SERVER__/install.ps1 | iex
```

The installer needs no Python, and it points the CLI at __PKANBAN_SERVER__.
If `pkanban` still isn't found afterwards, use the full path the installer
printed, or open a new shell.

## 2. Sign in (your person approves in their browser)

Check first:

```bash
pkanban board list --json
```

Exit code 0 means you are signed in; go to step 3. Otherwise start a login
that returns at once:

```bash
pkanban login --no-wait --json
```

It prints `verification_uri_complete` and `user_code`. **Show your person that
link and code**, and ask them to open it, check the code matches, and click
Approve. Anyone without an account can create one from that page. Never ask
for their password; you don't need it.

Once they say they've approved, finish:

```bash
pkanban login --json
```

This picks up the same login and saves an API key to the CLI's config. If it
says the login expired (codes last ten minutes), start this step again.

## 3. Pick or make a board

```bash
pkanban board list --json
```

Ask your person which board to use. If there isn't one, make one with
columns:

```bash
pkanban board create "My project" --json        # note the id
pkanban column create <board-id> "Todo" 0 --json
pkanban column create <board-id> "In Progress" 1 --json
pkanban column create <board-id> "Done" 2 --json
```

## 4. Remember it for next time

So that later sessions (yours or another agent's) know about the board, record
it in the project's agent instructions. With your person's OK, run this in
the project's root:

```bash
pkanban init --board <board-id>
```

It adds a short pkanban section to `AGENTS.md`, or to `CLAUDE.md` if that is
the only one there. Running it again updates the section rather than adding a
second one.

## Working with the board

- Read the board: `pkanban board get <board-id> --json`
- Read one card in full: `pkanban card get <card-id> --json`
- Add a card: `pkanban card create <column-id> "Title" --description-file body.md --json`
- Move a card: `pkanban card move <card-id> --column <column-id> --json`
- Edit a card: `pkanban card update <card-id> --description-file body.md --json`
- Search: `pkanban search "text" --json`

Rules that save trouble:

- **Use `--json`.** stdout then holds only the API response. Errors go to
  stderr as `{"error": ..., "status": ...}` with a non-zero exit code.
- **Put card bodies in a file** with `--description-file` (or `-d -` for
  stdin), never inline with `-d "..."`. Shells split quoted text in ways that
  can rename a card without any error.
- **Move cards as you work:** to In Progress when you start, to Done when you
  finish. The board is how your person sees what you are doing.
- **HTTP 402 with `"code": "plan_limit"`** means the free plan is full. Tell
  your person; the response carries an `upgrade_url`. Nothing was lost.

Every command takes `--help`. Full docs: __PKANBAN_SERVER__/docs
