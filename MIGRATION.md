# pkanban Rename Migration

A clean break: every surface that says `kanban` becomes `pkanban`. No deprecation
shims, no read-both periods, no accept-both. Existing users reinstall and re-login.

## Status (code work complete; external handoff below)

All Python, frontend, docs, deploy, and CI changes are done and committed-ready.
Pytest is green (290/291, 1 skip, identical to pre-rename). `pkanban --version`
reports `pkanban 0.3.0`. `pip install pkanban` from the new tree installs the
new binary as `pkanban` (not `kanban`). `scripts/generate_cli_docs.py --check`
is clean.

The only remaining work is outside the repo.

## Decisions (locked)

| Surface | Old | New | Compatibility |
|---|---|---|---|
| PyPI package | `pkanban` | `pkanban` | already aligned |
| Python module | `kanban/` | `pkanban/` | clean break |
| CLI command | `kanban` | `pkanban` | clean break |
| Config file | `~/.kanban.yaml` | `~/.pkanban.yaml` | clean break |
| API key prefix | `kanban_` | `pkanban_` | clean break (existing keys invalid) |
| Env var | `KANBAN_OUTPUT` | `PKANBAN_OUTPUT` | clean break |
| Domain | `kanban.pearachute.com` | `pkanban.pearachute.com` | clean break |
| systemd unit | `kanban.service` | `pkanban.service` | clean break |
| Deploy path | `/opt/kanban/` | `/opt/pkanban/` | clean break |
| System user | `kanban` | `pkanban` | clean break |
| DB filename | `kanban.db` | `pkanban.db` | clean break |
| Localstorage theme key | `kanban-theme` | `pkanban-theme` | clean break (theme resets to default once) |
| GitHub repo | `japherwocky/kanban` | `japherwocky/pkanban` | user does this on GitHub |

## What was changed in this tree

### Code
- `kanban/` -> `pkanban/` (git mv preserves history)
- `pyproject.toml`: package name stays `pkanban`; console_scripts entry updated;
  packages.find include updated; GitHub URLs updated
- `pkanban/config.py`: `DEFAULT_CONFIG_FILE` and `DEFAULT_SERVER_URL` updated
- `pkanban/cli.py`: all `kanban` user-facing strings (help, errors, examples)
- `pkanban/output.py`: `KANBAN_OUTPUT` -> `PKANBAN_OUTPUT`
- `pkanban/client.py`: error messages
- `pkanban/__init__.py`: docstring + version bump
- `scripts/generate_cli_docs.py`: hardcoded `kanban` -> `pkanban` in usage lines
- `backend/models.py`: `API_KEY_PREFIX = "pkanban_"`
- `backend/database.py`: `DATABASE_PATH` default `"pkanban.db"`
- `backend/main.py`: CORS default updated
- `backend/auth.py`, `backend/mailer.py`: log prefixes updated
- `manage.py`: argparse description updated
- All `from kanban.X import` -> `from pkanban.X import` (CLI + tests + generator)
- Backend tests updated for new prefix + argv + config path

### Frontend
- `FeaturesSection.svelte`, `TerminalSimulator.svelte`, `demoApi.js`,
  `ApiKeyCreated.svelte`: CLI invocations and API key examples
- `Footer.svelte`, `Contact.svelte`: GitHub repo URL
- `theme.js`, `theme.test.js`: localStorage key
- Left alone (correctly):
  - `About.svelte` "kanban tool" / "kanban boards" -- generic noun usage
  - `Footer.svelte` tagline "A kanban tool..."
  - `KanbanDemo.svelte` `.kanban-board` CSS class
  - `kanban_throughput` test data string and `kanban_test` in-memory DB URI

### Docs (hand-edited)
- `README.md`, `AGENTS.md`, `MARKETING.md`
- `docs/quickstart.md`, `docs/workflows.md`, `docs/reference.md`
- `docs/multi-tenant.md`, `docs/auth.md`, `docs/docs.md`, `docs/theme-system.md`
- `MARKETING.md` line 11 fixed: `pkanban move` (wrong) -> `pkanban card move` (right)
- `pyproject.toml` keywords list left as `["kanban", ...]` -- people searching for
  "kanban" should still find this package; the keyword is a search hint, not a brand

### Docs (auto-generated)
- `docs/commands.md` + `docs/commands/*.md` regenerated via
  `scripts/generate_cli_docs.py` after the script and CLI were renamed
- `generate_cli_docs.py --check` is clean

### Deploy / ops
- `sys/systemd/kanban.service` -> `sys/systemd/pkanban.service`
- `sys/nginx/kanban.pearachute.com.conf` -> `sys/nginx/pkanban.pearachute.com.conf`
- `sys/scripts/deploy.sh`: paths, user, service, sudoers filenames, env defaults
- `sys/scripts/install.sh`: same
- `sys/DEPLOYMENT.md`: full sweep
- The old `kanban.pearachute.com.conf` is NOT kept -- new cert for the new domain

### CI
- `.github/workflows/deploy-production.yml`: env vars + URL
- `.github/workflows/publish-pypi.yml`: `kanban/__init__.py` -> `pkanban/__init__.py`

### Version
- Bumped `0.2.0` -> `0.3.0` in `pyproject.toml` and `pkanban/__init__.py`
- The publish workflow's tag/version check now validates against `pkanban/__init__.py`

## External (you do these, not in repo)

Run them in this order -- the code already points at the new names, but the
running service and the public hostname need to follow.

1. **GitHub: rename the repo.**
   Settings -> General -> "Repository name" -> `japherwocky/kanban` ->
   `japherwocky/pkanban`. GitHub 301-redirects the old URL for a year, so
   existing links keep working while people migrate.

2. **PyPI: update the trusted publisher binding for `pkanban`.**
   The publish workflow uses OIDC-based trusted publishing (no API token).
   The binding on PyPI is keyed by owner + repo name, so renaming the repo
   silently breaks publish until the binding is updated. Do this **before**
   pushing the v0.3.0 tag.
   - Go to https://pypi.org/manage/project/pkanban/publishing/
   - Either edit the existing entry's Repository field from `kanban` to
     `pkanban`, or delete and recreate it. Owner stays `japherwocky`,
     workflow filename stays `publish-pypi.yml`.
   - Without this, `pypa/gh-action-pypi-publish` fails with a clear
     "trusted publisher not found" error and the workflow exits non-zero.

3. **DNS: add the new A record.**
   In your DNS provider (Gandi): create `pkanban.pearachute.com` A record
   pointing at the same IP as `kanban.pearachute.com`. Until this resolves
   nothing in step 3-4 will work.

4. **TLS: request a new cert for the new hostname.**
   ```
   sudo certbot certonly --nginx -d pkanban.pearachute.com
   ```
   New lineage at `/etc/letsencrypt/live/pkanban.pearachute.com/`. The repo's
   nginx config already references that path.

5. **Decide the fate of the old domain.** Two options:
   - **Cut over.** Let `kanban.pearachute.com` expire. Anyone hitting the old
     URL sees a cert error. The CLI's baked-in default `pkanban.pearachute.com`
     is what new installs get.
   - **Redirect.** Add two nginx server blocks for `kanban.pearachute.com`
     (`:80` keep ACME, `:443` 301 to `pkanban.pearachute.com`). Preserves any
     links. `sys/nginx/` doesn't carry this -- add it by hand.

6. **Prod box: rename the deploy artefacts.**
   - `sudo systemctl stop pkanban` (yes, the new name -- the new unit is
     staged but not yet enabled)
   - `sudo mv /opt/kanban /opt/pkanban` (and fix the systemd EnvironmentFile
     line in the new unit if it hardcodes the path -- it does, via
     `Environment=DATABASE_PATH=/opt/pkanban/...`)
   - `sudo useradd --system --home /opt/pkanban --shell /bin/bash pkanban`
     then `sudo chown -R pkanban:pkanban /opt/pkanban`. If the old `kanban`
     user owns files that need to survive, chown them to `pkanban:pkanban`
     before deleting the old user. The repo's `install.sh` already names
     `pkanban` for a fresh install.
   - `sudo mv /opt/pkanban/kanban.db /opt/pkanban/pkanban.db` (the
     `DATABASE_PATH` env var overrides the default; using the default path
     makes the rename visible)

7. **Update systemd symlink and nginx site symlink.**
   The deploy script does this automatically when `sys/systemd/pkanban.service`
   and `sys/nginx/pkanban.pearachute.com.conf` differ from what's installed.
   Just run:
   ```
   sudo -u pkanban /opt/pkanban/sys/scripts/deploy.sh
   ```
   It will cp the unit, daemon-reload, install the nginx config, and restart
   -- after which the service is `pkanban.service` and the site is the new
   conf.

8. **Notify users.** Anyone with stored credentials loses them -- the token
   file is at the old `~/.kanban.yaml` path, and existing API keys were
   minted with the `kanban_` prefix (now invalid). The cleanest message:
   "v0.3.0 is a clean-break rename. Reinstall (`pip install --upgrade
   pkanban`), re-login (`pkanban login`), and regenerate API keys."

9. **Tag and publish v0.3.0.** This will trigger the publish-pypi workflow:
   ```
   git tag v0.3.0
   git push origin v0.3.0
   ```
   The workflow already validates the tag against `pkanban/__init__.py`,
   and the trusted publisher binding (updated in step 2) accepts the OIDC
   token from the renamed repo.

## On the Dev board

The "pkanban rename" column on the Dev board (id=1) tracks the phases. Phase
cards 1-6 (ids 214-219) are still in that column -- the CLI session lost auth
mid-rename (a clean-break side effect: the stored JWT was at the old config
path) so they didn't get moved to Done. Move them by hand, or re-login and
run `pkanban card update <id> --column 6` for each.

"External: user does these" (card 220) and the overview (card 213) stay in
the column for visibility until the release ships.

Card 109 ("Redirect pkanban.pearachute.com to kanban.pearachute.com") is now
obsolete -- we flipped the direction. Close it when the cutover ships.
