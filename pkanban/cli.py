import sys
from typing import Optional

import typer
from rich import print as rprint
import requests

from pkanban.client import PkanbanClient, PkanbanError
from pkanban.config import (
    get_server_url,
    set_server_url,
    get_token,
    set_token,
    clear_token,
    get_api_key,
    set_api_key,
    clear_api_key,
    get_runtime_api_key,
    set_runtime_api_key,
)
from pkanban.output import emit, emit_error, set_json_output

app = typer.Typer(
    help="pkanban board CLI", no_args_is_help=True, invoke_without_command=True
)


def _version_callback(value: bool):
    if value:
        from pkanban import __version__

        def _print_version():
            rprint(f"pkanban {__version__}")
            # The joke goes here once, dry, and nowhere near the JSON payload
            # above -- scripts parse {"version": ...} and shouldn't have to
            # skip a punchline to get it.
            rprint('[dim]The "p" is silent, like in "pneumonia".[/dim]')

        emit({"version": __version__}, _print_version)
        raise typer.Exit()


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the installed version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Print the raw API response as JSON instead of formatted text. "
        "Can also be set with PKANBAN_OUTPUT=json.",
    ),
):
    """pkanban board CLI"""
    # main() usually strips --json before typer sees it, so this only fires
    # when app() is invoked directly. Declaring it here is what puts it in
    # `pkanban --help`.
    if json_out:
        set_json_output(True)


def describe_http_error(e):
    """Turn an HTTP failure into something a user can act on.

    Commands that can say something more specific catch HTTPError themselves;
    this is the fallback so nothing reaches the user as a traceback.
    """
    response = e.response
    if response is None:
        return f"Request failed: {e}"

    detail = None
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail")
    except ValueError:
        pass

    status = response.status_code
    if status == 401:
        # Naming expiry first: with sliding renewal, a token only reaches its
        # expiry after a real absence, so that is the likely cause -- and "not
        # authenticated" alone reads like the credentials were never there.
        return (
            "Not authenticated -- your session may have expired. Run "
            "'pkanban login', or check that your API key is still active "
            "(pkanban apikey list)."
        )
    if status == 403:
        return detail or "You don't have permission to do that."
    if status == 404:
        return detail or "Not found. Check the ID and try again."
    if status == 422:
        return f"Invalid request: {detail or response.text}"
    if status >= 500:
        return f"The server returned an error ({status}). Try again shortly."
    return detail or f"Request failed ({status}): {response.text}"


def make_client():
    runtime_api_key = get_runtime_api_key()
    if runtime_api_key:
        return PkanbanClient(api_key=runtime_api_key)
    token = get_token()
    api_key = get_api_key()
    if not token and not api_key:
        emit_error("Not authenticated. Run 'pkanban login' first or use --api-key.")
        raise typer.Exit(1)
    return PkanbanClient(token=token, api_key=api_key)


# === Auth Commands ===


@app.command("config")
def cmd_config(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Set the server URL"),
):
    """Configure the CLI or show current settings."""
    if url:
        set_server_url(url)
        emit(
            {"server_url": url},
            lambda: rprint(f"Server URL set to: [green]{url}[/green]"),
        )
    else:
        current = get_server_url()
        emit(
            {"server_url": current},
            lambda: rprint(f"Server URL: [cyan]{current}[/cyan]"),
        )


@app.command("login")
def cmd_login(
    username: str = typer.Argument(..., help="Username"),
    password: str = typer.Option(
        ...,
        "--password",
        "-p",
        help="Password. Omit to be prompted (input hidden, stays out of shell history).",
        hide_input=True,
        prompt=True,
    ),
    server: Optional[str] = typer.Option(
        None,
        "--server",
        "-s",
        help="Server URL. Defaults to the configured URL (see 'pkanban config'). "
        "Passing it also saves it as the configured URL.",
    ),
):
    """Login to the pkanban server."""
    # Default to the configured URL so `pkanban config --url ...` then `pkanban
    # login` works. Before this fell back to a hardcoded localhost, so login
    # ignored config and quietly hit the wrong server.
    server_url = server or get_server_url()
    client = PkanbanClient(server_url=server_url)
    try:
        token = client.login(username, password)
    except Exception as e:
        emit_error(f"Login failed: {e}")
        raise typer.Exit(1)
    # Only after a successful login: the token was issued by server_url, so
    # every later command has to talk to that same server. Persist an explicit
    # --server so the token and the stored URL can't drift apart.
    set_token(token)
    if server is not None:
        set_server_url(server_url)
    # PkanbanClient prefers api_key over token (see config.get_api_key), so a
    # saved API key silently outranks the login that just happened -- the new
    # token is on disk but every command keeps acting as the API key's
    # identity until that key is cleared.
    api_key_warning = None
    if get_api_key():
        api_key_warning = (
            "A saved API key is still active and takes precedence over this "
            "login. Run 'pkanban apikey clear' to use this session instead."
        )
    # The access token is deliberately left out of the JSON: it is already
    # saved to the config file, and stdout is exactly what CI logs capture.
    def render():
        rprint(f"Logged in as [green]{username}[/green]")
        if api_key_warning:
            rprint(f"[yellow]Warning: {api_key_warning}[/yellow]")

    emit(
        {
            "ok": True,
            "username": username,
            "server_url": server_url,
            **({"warning": api_key_warning} if api_key_warning else {}),
        },
        render,
    )


@app.command("logout")
def cmd_logout():
    """Logout and clear credentials."""
    clear_token()
    emit({"ok": True}, lambda: rprint("Logged out"))


# === Board Commands ===

board_app = typer.Typer(help="Board management commands", no_args_is_help=True)
app.add_typer(board_app, name="board")


@board_app.command("list")
def cmd_boards():
    """List all boards."""
    client = make_client()
    boards = client.boards()

    def render():
        if not boards:
            rprint("No boards found")
            return
        for b in boards:
            shared_info = ""
            if b.get("shared_team_id"):
                shared_info = f" (shared with team {b['shared_team_id']})"
            elif b.get("is_public_to_org"):
                shared_info = " (public to organization)"
            rprint(f"{b['id']:4}  [bold]{b['name']}[/bold]{shared_info}")

    emit(boards, render)


@board_app.command("create")
def cmd_board_create(name: str = typer.Argument(..., help="Board name")):
    """Create a new board."""
    client = make_client()
    result = client.board_create(name)
    emit(result, lambda: rprint(f"Board created with [green]id={result['id']}[/green]"))


@board_app.command("get")
def cmd_board_get(board_id: int = typer.Argument(..., help="Board ID")):
    """Show board details with column and card IDs."""
    from rich.text import Text
    from rich.console import Console

    client = make_client()
    board = client.board_get(board_id)

    def render():
        console = Console()
        console.print(f"Board: [bold]{board['name']}[/bold]")
        for col in board.get("columns", []):
            line = Text("  ")
            line.append(f"#{col['id']}", style="yellow")
            line.append(f" {col['name']}")
            line.append(f" ({len(col['cards'])} cards)")
            console.print(line)
            for card in col.get("cards", []):
                card_line = Text("    - ")
                card_line.append(f"#{card['id']}", style="yellow")
                card_line.append(f" {card['title']}")
                console.print(card_line)

    emit(board, render)


@board_app.command("delete")
def cmd_board_delete(board_id: int = typer.Argument(..., help="Board ID")):
    """Delete a board."""
    client = make_client()
    result = client.board_delete(board_id)
    emit(result, lambda: rprint("[green]Board deleted[/green]"))


@board_app.command("update")
def cmd_board_update(
    board_id: int = typer.Argument(..., help="Board ID"),
    name: str = typer.Argument(..., help="New board name"),
):
    """Update board name."""
    client = make_client()
    result = client.board_update(board_id, name)
    emit(result, lambda: rprint("[green]Board updated[/green]"))


# === Column Commands ===

column_app = typer.Typer(help="Column management commands", no_args_is_help=True)
app.add_typer(column_app, name="column")


@column_app.command("create")
def cmd_column_create(
    board_id: int = typer.Argument(..., help="Board ID"),
    name: str = typer.Argument(..., help="Column name"),
    # Optional rather than an -p option, so the old positional form still
    # works for anything already calling `column create <board> <name> <pos>`.
    position: Optional[int] = typer.Argument(
        None, help="Position. Omit to append after the last column."
    ),
):
    """Create a new column."""
    client = make_client()
    result = client.column_create(board_id, name, position)
    emit(
        result, lambda: rprint(f"Column created with [green]id={result['id']}[/green]")
    )


@column_app.command("delete")
def cmd_column_delete(column_id: int = typer.Argument(..., help="Column ID")):
    """Delete a column."""
    client = make_client()
    result = client.column_delete(column_id)
    emit(result, lambda: rprint("[green]Column deleted[/green]"))


# === Card Commands ===

card_app = typer.Typer(help="Card management commands", no_args_is_help=True)
app.add_typer(card_app, name="card")


@card_app.command("get")
def cmd_card_get(card_id: int = typer.Argument(..., help="Card ID")):
    """Show a card's full contents, including its description."""
    from rich.console import Console

    client = make_client()
    card = client.card_get(card_id)

    def render():
        console = Console()
        console.print(f"[yellow]#{card['id']}[/yellow] [bold]{card['title']}[/bold]")
        console.print(
            f"  on {card['board_name']} / {card['column_name']} "
            f"(column {card['column_id']})"
        )
        # The description is user-written text, so hand it to rich as plain
        # data -- printing it as markup would let a stray [b] eat characters.
        if card.get("description"):
            console.print("")
            console.print(card["description"], markup=False, highlight=False)
        else:
            console.print("  [dim](no description)[/dim]")
        for comment in card.get("comments", []):
            console.print("")
            console.print(f"  [cyan]{comment['username']}[/cyan]:")
            console.print(comment["content"], markup=False, highlight=False)

    emit(card, render)


@card_app.command("create")
def cmd_card_create(
    column_id: int = typer.Argument(..., help="Column ID"),
    title: str = typer.Argument(..., help="Card title"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Card description"
    ),
    position: int = typer.Option(0, "--position", "-p", help="Position"),
):
    """Create a new card."""
    client = make_client()
    result = client.card_create(column_id, title, description, position)
    emit(result, lambda: rprint(f"Card created with [green]id={result['id']}[/green]"))


def _apply_card_update(card_id, title, description, position, column):
    """Send a partial card update and report the outcome.

    Shared by `card update` and `card move`, which differ only in which
    fields they let you name.
    """
    if title is None and description is None and position is None and column is None:
        emit_error("Nothing to change. Pass a title, --description, --position or --column.")
        raise typer.Exit(1)

    client = make_client()
    try:
        result = client.card_update(card_id, title, description, position, column)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 404:
            message = f"Card {card_id} not found. It may have been deleted."
        elif status == 403:
            message = "You don't have permission to update this card."
        elif status == 422:
            message = "Invalid data. Check that the card ID and column ID are correct."
        else:
            message = f"Error: {e.response.text}"
        emit_error(message, status=status)
        raise typer.Exit(1)
    emit(result, lambda: rprint("[green]Card updated[/green]"))


@card_app.command("update")
def cmd_card_update(
    card_id: int = typer.Argument(..., help="Card ID"),
    # Optional: it used to be required, so moving a card meant retyping its
    # exact title and one wrong character silently renamed it. Omitted fields
    # are left alone, which is how --description already behaved.
    title: Optional[str] = typer.Argument(
        None, help="New card title. Omit to leave the title alone."
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Card description"
    ),
    position: Optional[int] = typer.Option(None, "--position", "-p", help="Position"),
    column: Optional[int] = typer.Option(None, "--column", "-c", help="New column ID"),
):
    """Update a card. Anything you don't pass is left unchanged."""
    _apply_card_update(card_id, title, description, position, column)


@card_app.command("move")
def cmd_card_move(
    card_id: int = typer.Argument(..., help="Card ID"),
    column: Optional[int] = typer.Option(
        None, "--column", "-c", help="Destination column ID"
    ),
    position: Optional[int] = typer.Option(
        None, "--position", "-p", help="Position within the column"
    ),
):
    """Move a card to another column or position, leaving its text alone."""
    if column is None and position is None:
        emit_error("Nothing to move. Pass --column and/or --position.")
        raise typer.Exit(1)
    _apply_card_update(card_id, None, None, position, column)


@card_app.command("delete")
def cmd_card_delete(card_id: int = typer.Argument(..., help="Card ID")):
    """Delete a card."""
    client = make_client()
    try:
        result = client.card_delete(card_id)
        emit(result, lambda: rprint("[green]Card deleted[/green]"))
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 404:
            message = f"Card {card_id} not found. It may have already been deleted."
        elif status == 403:
            message = "You don't have permission to delete this card."
        else:
            message = f"Error: {e.response.text}"
        emit_error(message, status=status)
        raise typer.Exit(1)


# === Organization Commands ===

org_app = typer.Typer(help="Organization management commands", no_args_is_help=True)
app.add_typer(org_app, name="org")


@org_app.command("list")
def cmd_organizations():
    """List all organizations."""
    client = make_client()
    orgs = client.organizations()

    def render():
        if not orgs:
            rprint("No organizations found")
            return
        for org in orgs:
            rprint(
                f"{org['id']:4}  [bold]{org['name']}[/bold] (owner: {org.get('owner_username', 'Unknown')})"
            )

    emit(orgs, render)


@org_app.command("create")
def cmd_organization_create(name: str = typer.Argument(..., help="Organization name")):
    """Create a new organization."""
    client = make_client()
    result = client.organization_create(name)
    emit(
        result,
        lambda: rprint(f"Organization created with [green]id={result['id']}[/green]"),
    )


@org_app.command("get")
def cmd_organization_get(org_id: int = typer.Argument(..., help="Organization ID")):
    """Show organization details."""
    client = make_client()
    org = client.organization_get(org_id)

    def render():
        rprint(f"Organization: [bold]{org['name']}[/bold]")
        rprint(f"Owner: {org.get('owner_username', 'Unknown')}")
        rprint("Members:")
        for member in org.get("members", []):
            role = member.get("role")
            role_info = f" ({role or 'member'})" if role else ""
            rprint(f"  - {member['username']}{role_info}")

    emit(org, render)


@org_app.command("members")
def cmd_organization_members(org_id: int = typer.Argument(..., help="Organization ID")):
    """List organization members."""
    client = make_client()
    members = client.organization_members(org_id)

    def render():
        for member in members:
            role = member.get("role")
            role_info = f" ({role or 'member'})" if role else ""
            rprint(f"{member['id']:4}  {member['username']}{role_info}")

    emit(members, render)


@org_app.command("member-add")
def cmd_organization_member_add(
    org_id: int = typer.Argument(..., help="Organization ID"),
    username: str = typer.Argument(..., help="Username to add"),
):
    """Add member to organization."""
    client = make_client()
    result = client.organization_member_add(org_id, username)
    emit(result, lambda: rprint(f"Added [green]{username}[/green] to organization"))


@org_app.command("member-remove")
def cmd_organization_member_remove(
    org_id: int = typer.Argument(..., help="Organization ID"),
    user_id: int = typer.Argument(..., help="User ID to remove"),
):
    """Remove member from organization."""
    client = make_client()
    result = client.organization_member_remove(org_id, user_id)
    emit(
        result,
        lambda: rprint(f"Removed user [green]{user_id}[/green] from organization"),
    )


# === Organization Invite Commands ===


@org_app.command("invite-create")
def cmd_organization_invite_create(
    org_id: int = typer.Argument(..., help="Organization ID"),
    email: str = typer.Option(None, "--email", "-e", help="Email of person to invite"),
):
    """Create an invite link for an organization."""
    client = make_client()
    result = client.organization_invite_create(org_id, email)
    server_url = get_server_url()
    invite_link = f"{server_url.rstrip('/')}/invite/{result['token']}"

    def render():
        rprint("[bold]Invite created![/bold]")
        rprint(f"  ID:       {result['id']}")
        rprint(f"  Email:    {email or '(anonymous)'}")
        rprint(f"  Link:    [cyan]{invite_link}[/cyan]")
        rprint("")
        rprint("Share this link with the person you want to invite.")

    # The link is assembled here, not by the server, so a script would have to
    # rebuild it from the token -- hand it over alongside the raw response.
    emit({**result, "invite_url": invite_link}, render)


@org_app.command("invite-list")
def cmd_organization_invites(org_id: int = typer.Argument(..., help="Organization ID")):
    """List pending invites for an organization."""
    client = make_client()
    invites = client.organization_invites(org_id)
    base = get_server_url().rstrip("/")

    # The server returns the token to the org owner only, so a member listing
    # invites sees who is pending without getting a link they could pass on.
    def invite_url(invite):
        token = invite.get("token")
        return f"{base}/invite/{token}" if token else None

    def render():
        if not invites:
            rprint("No pending invites")
            return
        rprint("[bold]Pending Invites:[/bold]")
        for invite in invites:
            rprint(f"  {invite['id']:4}  {invite['email'] or '(anonymous)'}")
            url = invite_url(invite)
            if url:
                rprint(f"       Link: {url}")

    emit([{**i, "invite_url": invite_url(i)} for i in invites], render)


@org_app.command("invite-revoke")
def cmd_organization_invite_revoke(
    org_id: int = typer.Argument(..., help="Organization ID"),
    invite_id: int = typer.Argument(..., help="Invite ID to revoke"),
):
    """Revoke a pending invite."""
    client = make_client()
    result = client.organization_invite_revoke(org_id, invite_id)
    emit(
        result, lambda: rprint(f"Invite [green]{invite_id}[/green] has been revoked")
    )


# === Team Commands ===

team_app = typer.Typer(help="Team management commands", no_args_is_help=True)
app.add_typer(team_app, name="team")


@team_app.command("list")
def cmd_teams(
    org_id: int = typer.Option(
        ..., "--org-id", "-o", help="Organization ID (required)"
    ),
):
    """List teams in an organization."""
    client = make_client()
    teams = client.organization_teams(org_id)

    def render():
        if not teams:
            rprint("No teams found")
            return
        for team in teams:
            rprint(
                f"{team['id']:4}  [bold]{team['name']}[/bold] (org: {team.get('organization_name', 'Unknown')})"
            )

    emit(teams, render)


@team_app.command("create")
def cmd_team_create(
    org_id: int = typer.Argument(..., help="Organization ID"),
    name: str = typer.Argument(..., help="Team name"),
):
    """Create a new team."""
    client = make_client()
    result = client.team_create(org_id, name)
    emit(result, lambda: rprint(f"Team created with [green]id={result['id']}[/green]"))


@team_app.command("get")
def cmd_team_get(team_id: int = typer.Argument(..., help="Team ID")):
    """Show team details."""
    client = make_client()
    team = client.team_get(team_id)

    def render():
        rprint(f"Team: [bold]{team['name']}[/bold]")
        rprint(f"Organization: {team.get('organization_name', 'Unknown')}")
        rprint("Members:")
        for member in team.get("members", []):
            rprint(f"  - {member['username']}")

    emit(team, render)


@team_app.command("members")
def cmd_team_members(team_id: int = typer.Argument(..., help="Team ID")):
    """List team members."""
    client = make_client()
    members = client.team_members(team_id)

    def render():
        for member in members:
            rprint(f"{member['id']:4}  {member['username']}")

    emit(members, render)


@team_app.command("member-add")
def cmd_team_member_add(
    team_id: int = typer.Argument(..., help="Team ID"),
    username: str = typer.Argument(..., help="Username to add"),
):
    """Add member to team."""
    client = make_client()
    result = client.team_member_add(team_id, username)
    emit(result, lambda: rprint(f"Added [green]{username}[/green] to team"))


@team_app.command("member-remove")
def cmd_team_member_remove(
    team_id: int = typer.Argument(..., help="Team ID"),
    user_id: int = typer.Argument(..., help="User ID to remove"),
):
    """Remove member from team."""
    client = make_client()
    result = client.team_member_remove(team_id, user_id)
    emit(result, lambda: rprint(f"Removed user [green]{user_id}[/green] from team"))


# === Board Sharing ===


@app.command("share")
def cmd_board_share(
    board_id: int = typer.Argument(..., help="Board ID"),
    team_id: str = typer.Argument(
        None, help="Team ID or 'private' to make board private"
    ),
    org: bool = typer.Option(
        False, "--org", help="Share with a whole organization instead of a team"
    ),
    organization_id: int = typer.Option(
        None,
        "--org-id",
        help="Which organization, when you belong to more than one",
    ),
):
    """Share board with a team or a whole organization, or make it private."""
    # --org-id on its own means --org: naming the organization is a clear
    # enough statement of intent that making people pass both is just friction.
    share_with_org = org or organization_id is not None

    if share_with_org and team_id and team_id != "private":
        rprint("[red]Pass a team id or --org, not both.[/red]", file=sys.stderr)
        raise typer.Exit(code=1)
    if not share_with_org and team_id is None:
        rprint(
            "[red]Pass a team id, 'private', or --org.[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    client = make_client()
    team_id_value = None if (team_id == "private" or share_with_org) else team_id
    result = client.board_share(
        board_id,
        team_id_value,
        is_public_to_org=share_with_org,
        organization_id=organization_id,
    )

    def render():
        if share_with_org:
            rprint(
                f"Board [green]{board_id}[/green] shared with organization "
                f"{result.get('organization_id')}"
            )
        elif team_id_value:
            rprint(f"Board [green]{board_id}[/green] shared with team {team_id_value}")
        else:
            rprint(f"Board [green]{board_id}[/green] made private")

    emit(result, render)


# === API Key Commands ===

apikey_app = typer.Typer(help="API key management commands", no_args_is_help=True)
app.add_typer(apikey_app, name="apikey")


@apikey_app.command("list")
def cmd_apikey_list():
    """List all API keys."""
    client = make_client()
    keys = client.api_keys()

    def render():
        if not keys:
            rprint("No API keys found")
            return
        rprint("[bold]Your API Keys:[/bold]")
        for key in keys:
            status = (
                "[green]active[/green]" if key["is_active"] else "[red]inactive[/red]"
            )
            last_used = key["last_used_at"][:10] if key["last_used_at"] else "never"
            expires = key["expires_at"][:10] if key["expires_at"] else "never"
            rprint(
                f"  {key['prefix']}....  {key['name']}  {status}  last used: {last_used}  expires: {expires}"
            )

    emit(keys, render)


@apikey_app.command("create")
def cmd_apikey_create(
    name: str = typer.Argument(..., help="Name for the API key (e.g., 'CI Agent')"),
):
    """Create a new API key. The key is shown only once - save it securely!"""
    client = make_client()
    result = client.api_key_create(name)

    def render():
        rprint("[bold]API Key created![/bold]")
        rprint("")
        rprint(f"  Name:    {result['name']}")
        rprint(f"  Key:     [yellow]{result['key']}[/yellow]")
        rprint(f"  Prefix:  {result['prefix']}....")
        rprint("")
        rprint(
            "[yellow]IMPORTANT: This key is shown only once! Copy it now and store it securely.[/yellow]"
        )

    emit(result, render)


@apikey_app.command("revoke")
def cmd_apikey_revoke(key_id: int = typer.Argument(..., help="API key ID to revoke")):
    """Revoke (deactivate) an API key."""
    client = make_client()
    try:
        result = client.api_key_revoke(key_id)
        emit(
            result, lambda: rprint(f"API key [green]{key_id}[/green] has been revoked")
        )
    except Exception as e:
        emit_error(f"Failed to revoke key: {e}")
        raise typer.Exit(1)


@apikey_app.command("activate")
def cmd_apikey_activate(
    key_id: int = typer.Argument(..., help="API key ID to activate"),
):
    """Reactivate a deactivated API key."""
    client = make_client()
    try:
        result = client.api_key_activate(key_id)
        emit(
            result, lambda: rprint(f"API key [green]{key_id}[/green] has been activated")
        )
    except Exception as e:
        emit_error(f"Failed to activate key: {e}")
        raise typer.Exit(1)


@apikey_app.command("use")
def cmd_apikey_use(
    key: str = typer.Argument(..., help="API key to check"),
):
    """Check that an API key works, without saving it anywhere.

    Use 'pkanban --api-key <key> <command>' to run a single command with it,
    or 'pkanban apikey save <key>' to store it.
    """
    # Nothing here touches the config file. This used to call clear_token()
    # and set_api_key(), so merely testing a key logged the user out and
    # overwrote their stored credentials -- the same bug that was fixed for
    # --api-key, which authenticates through the runtime key instead.
    client = PkanbanClient(api_key=key)

    try:
        boards = client.boards()
    except Exception as e:
        emit_error(f"API key verification failed: {e}")
        raise typer.Exit(1)

    def render():
        rprint(f"[green]API key verified[/green] - found {len(boards)} board(s)")
        rprint(
            "Run a single command with it: "
            "[cyan]pkanban --api-key <key> <command>[/cyan]"
        )
        rprint("Or save it for future use: [cyan]pkanban apikey save <key>[/cyan]")

    emit({"ok": True, "board_count": len(boards)}, render)


@apikey_app.command("save")
def cmd_apikey_save(key: str = typer.Argument(..., help="API key to save")):
    """Save API key to config file for future use."""
    from pkanban.config import set_api_key

    set_api_key(key)

    def render():
        rprint("[green]API key saved to ~/.pkanban.yaml[/green]")
        rprint("Run commands without --api-key from now on.")

    emit({"ok": True}, render)


@apikey_app.command("clear")
def cmd_apikey_clear():
    """Remove the saved API key from config, without revoking it server-side.

    An API key takes precedence over a logged-in session (see 'pkanban
    login'), so a stale saved key silently outranks any later login. This
    only forgets it locally -- use 'pkanban apikey revoke' to invalidate it.
    """
    clear_api_key()

    def render():
        rprint("[green]API key cleared from ~/.pkanban.yaml[/green]")

    emit({"ok": True}, render)


# Options that consume no value, so a `--json` following one belongs to us
# rather than to them.
VALUELESS_FLAGS = frozenset(
    {
        "--json",
        "--version",
        "-V",
        "--help",
        "--install-completion",
        "--show-completion",
    }
)


def _extract_json_flag(argv):
    """Pull `--json` off the command line wherever it appears.

    Click only accepts an option on the command that declares it, so
    `pkanban --json board list` would work while `pkanban board list --json`
    failed -- and the second form is the one people type. Strip it here
    instead, the same trick `--api-key` already uses.

    A `--json` sitting right after a value-taking option is left alone: there
    it is that option's value (`--description --json`), not a flag of ours.
    Following a flag that takes no value it is ours, which is why
    `pkanban --version --json` needs VALUELESS_FLAGS below rather than a blanket
    "preceded by a dash" test.
    """
    found = False
    for i in range(len(argv) - 1, 0, -1):
        if argv[i] != "--json":
            continue
        previous = argv[i - 1]
        if previous.startswith("-") and previous not in VALUELESS_FLAGS:
            continue
        argv.pop(i)
        found = True
    return found


def main():
    """Main entry point for the CLI."""
    if _extract_json_flag(sys.argv):
        set_json_output(True)

    # Check for --api-key option
    if "--api-key" in sys.argv or "-k" in sys.argv:
        idx = None
        if "--api-key" in sys.argv:
            idx = sys.argv.index("--api-key")
        elif "-k" in sys.argv:
            idx = sys.argv.index("-k")

        if idx is not None and idx + 1 < len(sys.argv):
            api_key = sys.argv[idx + 1]
            # Remove --api-key and the key from sys.argv
            sys.argv.pop(idx)
            sys.argv.pop(idx)
            # Use this key for this invocation only -- do not touch the
            # stored token/API key in ~/.pkanban.yaml.
            set_runtime_api_key(api_key)

    try:
        app()
    except PkanbanError as e:
        emit_error(str(e))
        raise SystemExit(1)
    except requests.exceptions.HTTPError as e:
        extra = {} if e.response is None else {"status": e.response.status_code}
        emit_error(describe_http_error(e), **extra)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
