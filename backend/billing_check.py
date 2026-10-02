"""Launch preflight: is billing set up right, and who will it affect?

`python manage.py billing-check`. Run it on the server before flipping
BILLING_ENABLED, and again after. It answers the questions that otherwise get
answered by a customer:

  * are the three Stripe settings present, and is the key live or test?
  * is the Price recurring, and does it charge what the Pricing page advertises?
  * is the dashboard webhook pointed at this server, enabled, and subscribed to
    every event the handler acts on?
  * is a Customer Portal configured? (Live mode has none until someone makes
    one in the dashboard, and then "Manage subscription" fails for everyone.)
  * which existing accounts would be blocked from creating things the moment
    the limits switch on?

It never prints a secret, only whether one is set and what mode it is in. Every
Stripe call is read-only. A call the key is not permitted to make is reported
as a warning (check it by hand), not a failure: a restricted key that can take
payments but cannot list webhook endpoints is a fine key.
"""

import stripe
from peewee import OperationalError, fn

from backend import billing, stripe_billing
from backend.mailer import public_base_url
from backend.models import Board, Card, Column, User

OK, WARN, FAIL = "ok", "warn", "fail"

_SECRET_PREFIXES = {"live": ("sk_live_", "rk_live_"), "test": ("sk_test_", "rk_test_")}


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def key_mode(key):
    """'live', 'test', or None for something that is not a Stripe secret key."""
    for mode, prefixes in _SECRET_PREFIXES.items():
        if key.startswith(prefixes):
            return mode
    return None


def webhook_url():
    return f"{public_base_url()}/api/billing/webhook"


def check_config():
    """(checks, mode): the environment, without calling anything."""
    checks = []
    enabled = billing.billing_enabled()
    checks.append(
        _check(
            "BILLING_ENABLED",
            OK,
            "on: limits are enforced" if enabled else "off: limits are NOT enforced",
        )
    )

    key = stripe_billing._env("STRIPE_SECRET_KEY")
    mode = key_mode(key) if key else None
    if not key:
        checks.append(_check("STRIPE_SECRET_KEY", FAIL, "not set"))
    elif mode is None:
        checks.append(
            _check("STRIPE_SECRET_KEY", FAIL, "set, but does not look like a Stripe secret key")
        )
    else:
        checks.append(_check("STRIPE_SECRET_KEY", OK, f"set ({mode} mode)"))

    price = stripe_billing._env("STRIPE_PRICE_ID")
    checks.append(
        _check("STRIPE_PRICE_ID", OK if price.startswith("price_") else FAIL,
               "set" if price.startswith("price_") else
               "not set" if not price else "set, but does not start with price_")
    )

    secret = stripe_billing._env("STRIPE_WEBHOOK_SECRET")
    if not secret:
        checks.append(_check("STRIPE_WEBHOOK_SECRET", FAIL, "not set: the webhook refuses everything"))
    elif not secret.startswith("whsec_"):
        checks.append(_check("STRIPE_WEBHOOK_SECRET", WARN, "set, but does not start with whsec_"))
    else:
        checks.append(_check("STRIPE_WEBHOOK_SECRET", OK, "set"))

    base = public_base_url()
    if mode == "live" and ("localhost" in base or "127.0.0.1" in base):
        checks.append(_check("PUBLIC_BASE_URL", WARN, f"{base}: a live key with a local address"))
    elif mode == "live" and not base.startswith("https://"):
        checks.append(_check("PUBLIC_BASE_URL", WARN, f"{base}: live checkout returns should be https"))
    else:
        checks.append(_check("PUBLIC_BASE_URL", OK, base))
    return checks, mode


def _describe_error(e):
    if isinstance(e, stripe.AuthenticationError):
        return FAIL, "Stripe rejected the key"
    if isinstance(e, stripe.PermissionError):
        return WARN, "this key is not permitted to do that: check it in the dashboard"
    if isinstance(e, stripe.InvalidRequestError):
        return FAIL, str(getattr(e, "user_message", None) or e)
    return FAIL, f"could not reach Stripe: {e}"


def check_price(client):
    price_id = stripe_billing._env("STRIPE_PRICE_ID")
    try:
        price = stripe_billing._plain(client.v1.prices.retrieve(price_id))
    except stripe.StripeError as e:
        status, detail = _describe_error(e)
        return _check("Stripe Price", status, detail)

    recurring = price.get("recurring") or {}
    interval, count = recurring.get("interval"), recurring.get("interval_count", 1)
    amount, currency = price.get("unit_amount"), (price.get("currency") or "").upper()
    summary = (
        f"{amount / 100:.2f} {currency} / {interval}" if amount is not None else f"no fixed amount / {interval}"
    )
    if not price.get("active"):
        return _check("Stripe Price", FAIL, f"{summary}: the Price is archived")
    if price.get("type") != "recurring":
        return _check("Stripe Price", FAIL, f"{summary}: not a recurring Price")
    if (interval, count, amount) != (billing.PRO_PRICE_INTERVAL, 1, billing.PRO_PRICE_CENTS):
        return _check(
            "Stripe Price",
            FAIL,
            f"{summary}, but the Pricing page advertises "
            f"{billing.PRO_PRICE_CENTS / 100:.2f} / {billing.PRO_PRICE_INTERVAL}",
        )
    return _check("Stripe Price", OK, f"{summary}, active, matches the Pricing page")


def check_webhook(client):
    expected = webhook_url()
    try:
        listing = stripe_billing._plain(client.v1.webhook_endpoints.list(params={"limit": 100}))
    except stripe.StripeError as e:
        status, detail = _describe_error(e)
        if status == WARN:
            detail = f"could not list webhook endpoints ({detail}). Expected {expected}"
        return _check("Stripe webhook", status, detail)

    endpoints = listing.get("data", [])
    found = next((e for e in endpoints if (e.get("url") or "").rstrip("/") == expected), None)
    if found is None:
        others = ", ".join(e.get("url", "?") for e in endpoints) or "none registered"
        return _check("Stripe webhook", FAIL, f"no endpoint for {expected} (found: {others})")
    if found.get("status") != "enabled":
        return _check("Stripe webhook", FAIL, f"{expected} exists but is {found.get('status')}")

    events = set(found.get("enabled_events") or [])
    missing = sorted(stripe_billing.HANDLED_EVENTS - events) if "*" not in events else []
    if missing:
        return _check(
            "Stripe webhook", FAIL, f"{expected} is missing events: {', '.join(missing)}"
        )
    return _check("Stripe webhook", OK, f"{expected}, enabled, all {len(stripe_billing.HANDLED_EVENTS)} events")


def check_portal(client):
    try:
        listing = stripe_billing._plain(
            client.v1.billing_portal.configurations.list(
                params={"is_default": True, "active": True}
            )
        )
    except stripe.StripeError as e:
        status, detail = _describe_error(e)
        return _check("Customer Portal", status, detail)

    configs = listing.get("data", [])
    if not configs:
        return _check(
            "Customer Portal",
            FAIL,
            "no default configuration: Manage subscription would fail for everyone. "
            "Create one in the dashboard under Settings > Billing > Customer portal",
        )
    cancel = ((configs[0].get("features") or {}).get("subscription_cancel") or {}).get("enabled")
    if not cancel:
        return _check("Customer Portal", WARN, "configured, but customers cannot cancel from it")
    return _check("Customer Portal", OK, "default configuration, cancellation enabled")


def affected_users():
    """Free accounts that would be refused a create as soon as limits are on.

    "At the limit" counts: the 5th board is allowed and the 6th is not, so
    an owner of exactly 5 cannot make another, and a board holding exactly 100
    cards cannot take a 101st.
    """
    boards_per_owner = dict(
        Board.select(Board.owner, fn.COUNT(Board.id)).group_by(Board.owner).tuples()
    )
    cards_per_board = dict(
        Card.select(Column.board, fn.COUNT(Card.id)).join(Column).group_by(Column.board).tuples()
    )
    boards_by_owner = {}
    for board in Board.select():
        boards_by_owner.setdefault(board.owner_id, []).append(board)

    affected = []
    for user in User.select().where(User.plan != "pro").order_by(User.id):
        owned = boards_per_owner.get(user.id, 0)
        full = [
            {"id": b.id, "name": b.name, "cards": cards_per_board[b.id]}
            for b in boards_by_owner.get(user.id, [])
            if cards_per_board.get(b.id, 0) >= billing.FREE_MAX_CARDS_PER_BOARD
        ]
        at_board_limit = owned >= billing.FREE_MAX_BOARDS
        if at_board_limit or full:
            affected.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "boards_owned": owned,
                    "at_board_limit": at_board_limit,
                    "full_boards": full,
                }
            )
    return affected


def run(stripe_api=True, client=None):
    """The whole report: {"ok", "mode", "checks", "affected_users"}.

    `client` is for tests; otherwise one is built from the environment. With
    stripe_api=False nothing leaves the machine, for a box with no network or
    a first look before the keys exist.
    """
    checks, mode = check_config()

    if stripe_api and stripe_billing.checkout_configured():
        client = client or stripe_billing._client()
        checks += [check_price(client), check_webhook(client), check_portal(client)]
    elif stripe_api:
        checks.append(_check("Stripe API", WARN, "skipped: no key or price to check with"))

    try:
        affected = affected_users()
    except OperationalError:
        # The schema predates the billing columns: the code was deployed but
        # the migration was not run. Say so, rather than a stack trace.
        affected = []
        checks.append(
            _check(
                "Database",
                FAIL,
                "out of date (no users.plan column). Run: python manage.py migrate",
            )
        )

    return {
        "ok": not any(c["status"] == FAIL for c in checks),
        "mode": mode,
        "checks": checks,
        "affected_users": affected,
    }


_MARK = {OK: "ok  ", WARN: "warn", FAIL: "FAIL"}


def format_report(report):
    lines = ["Billing preflight", ""]
    for c in report["checks"]:
        lines.append(f"  [{_MARK[c['status']]}] {c['name']}: {c['detail']}")

    users = report["affected_users"]
    lines += ["", f"Free accounts that would be blocked from creating things: {len(users)}"]
    for u in users:
        reasons = []
        if u["at_board_limit"]:
            reasons.append(f"owns {u['boards_owned']} boards (limit {billing.FREE_MAX_BOARDS})")
        for b in u["full_boards"]:
            reasons.append(f"board {b['id']} '{b['name']}' has {b['cards']} cards")
        lines.append(f"  {u['username']} (id {u['id']}): " + "; ".join(reasons))
    if users:
        lines.append("  Set a plan for any of these in the admin Users page before switching limits on.")

    fails = sum(c["status"] == FAIL for c in report["checks"])
    lines += ["", "Ready." if report["ok"] else f"Not ready: {fails} check(s) failed."]
    return "\n".join(lines)
