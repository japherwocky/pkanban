"""`manage.py billing-check`: the launch preflight.

Two halves, tested differently. The judgement (what counts as a failure, who is
affected) runs against a fake client so every branch can be hit. The Stripe
calls themselves run against the real SDK talking to a local server, because
method names and request encoding are the SDK's behaviour, not ours.
"""

import importlib
import json
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import stripe

from backend import billing, billing_check, stripe_billing
from backend.models import Board, Card, Column, User

PRICE = "price_launch"
SECRET = "sk_live_supersecretvalue123"
WEBHOOK_SECRET = "whsec_supersecretvalue456"
URL = "https://kanban.example.com/api/billing/webhook"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", SECRET)
    monkeypatch.setenv("STRIPE_PRICE_ID", PRICE)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://kanban.example.com")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)


def good_price(**over):
    p = {"id": PRICE, "active": True, "type": "recurring", "unit_amount": 600,
         "currency": "usd", "recurring": {"interval": "month", "interval_count": 1}}
    p.update(over)
    return p


def good_endpoint(**over):
    e = {"url": URL, "status": "enabled",
         "enabled_events": sorted(stripe_billing.HANDLED_EVENTS)}
    e.update(over)
    return e


GOOD_PORTAL = {"features": {"subscription_cancel": {"enabled": True}}}


class FakeClient:
    """Each attribute is what that call returns, or an exception to raise."""

    def __init__(self, price=None, endpoints=None, portals=None):
        self._price = good_price() if price is None else price
        self._endpoints = [good_endpoint()] if endpoints is None else endpoints
        self._portals = [GOOD_PORTAL] if portals is None else portals
        self.v1 = SimpleNamespace(
            prices=SimpleNamespace(retrieve=lambda price_id: self._give(self._price)),
            webhook_endpoints=SimpleNamespace(
                list=lambda params=None: self._give(self._listing(self._endpoints))
            ),
            billing_portal=SimpleNamespace(
                configurations=SimpleNamespace(
                    list=lambda params=None: self._give(self._listing(self._portals))
                )
            ),
        )

    @staticmethod
    def _listing(items):
        # An exception stands for "this call fails", not for a list of one.
        return items if isinstance(items, Exception) else {"data": items}

    @staticmethod
    def _give(value):
        if isinstance(value, Exception):
            raise value
        return value


def report_for(client):
    return billing_check.run(client=client)


def by_name(report):
    return {c["name"]: c for c in report["checks"]}


def status_of(report, name):
    return by_name(report)[name]["status"]


# --- the happy path ------------------------------------------------------------


def test_a_correct_setup_is_ready(db_session, configured):
    report = report_for(FakeClient())
    assert report["ok"] is True
    assert report["mode"] == "live"
    assert {c["status"] for c in report["checks"]} == {"ok"}


def test_the_report_never_contains_a_secret(db_session, configured):
    report = report_for(FakeClient())
    text = billing_check.format_report(report) + json.dumps(report)
    assert SECRET not in text
    assert WEBHOOK_SECRET not in text
    assert "supersecretvalue" not in text


# --- the environment -----------------------------------------------------------


@pytest.mark.parametrize("missing", ["STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET"])
def test_each_missing_setting_fails_the_check(db_session, configured, monkeypatch, missing):
    monkeypatch.delenv(missing)
    report = billing_check.run(stripe_api=False)
    assert status_of(report, missing) == "fail"
    assert report["ok"] is False


def test_a_key_that_is_not_a_stripe_key_fails(db_session, configured, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "not-a-key")
    report = billing_check.run(stripe_api=False)
    assert status_of(report, "STRIPE_SECRET_KEY") == "fail"


@pytest.mark.parametrize("key,mode", [
    ("sk_live_abc", "live"), ("rk_live_abc", "live"),
    ("sk_test_abc", "test"), ("rk_test_abc", "test"), ("pk_live_abc", None),
])
def test_key_mode(key, mode):
    assert billing_check.key_mode(key) == mode


def test_a_publishable_key_is_not_accepted_as_the_secret(db_session, configured, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "pk_live_abc")
    assert status_of(billing_check.run(stripe_api=False), "STRIPE_SECRET_KEY") == "fail"


def test_a_price_id_that_is_a_product_id_fails(db_session, configured, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID", "prod_123")
    assert status_of(billing_check.run(stripe_api=False), "STRIPE_PRICE_ID") == "fail"


def test_a_live_key_with_a_local_address_warns(db_session, configured, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8080")
    assert status_of(billing_check.run(stripe_api=False), "PUBLIC_BASE_URL") == "warn"


def test_a_test_key_on_a_local_address_is_fine(db_session, configured, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8080")
    assert status_of(billing_check.run(stripe_api=False), "PUBLIC_BASE_URL") == "ok"


def test_the_switch_state_is_reported_but_never_a_failure(db_session, configured, monkeypatch):
    off = by_name(billing_check.run(stripe_api=False))["BILLING_ENABLED"]
    monkeypatch.setenv("BILLING_ENABLED", "true")
    on = by_name(billing_check.run(stripe_api=False))["BILLING_ENABLED"]
    assert off["status"] == on["status"] == "ok"
    assert "NOT enforced" in off["detail"]
    assert "enforced" in on["detail"] and "NOT" not in on["detail"]


def test_no_stripe_flag_makes_no_api_calls(db_session, configured):
    class Boom:
        def __getattr__(self, name):
            raise AssertionError("the Stripe client must not be touched")

    billing_check.run(stripe_api=False, client=Boom())


def test_without_a_key_the_api_checks_are_skipped_with_a_warning(db_session, monkeypatch):
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    report = billing_check.run()
    assert status_of(report, "Stripe API") == "warn"
    assert "Stripe Price" not in by_name(report)


# --- the Price -----------------------------------------------------------------


@pytest.mark.parametrize("over", [
    {"unit_amount": 500},                                   # cheaper than advertised
    {"unit_amount": 700},                                   # dearer than advertised
    {"recurring": {"interval": "year", "interval_count": 1}},
    {"recurring": {"interval": "month", "interval_count": 3}},
    {"active": False},
    {"type": "one_time", "recurring": None},
])
def test_a_price_that_differs_from_the_pricing_page_fails(db_session, configured, over):
    report = report_for(FakeClient(price=good_price(**over)))
    assert status_of(report, "Stripe Price") == "fail"
    assert report["ok"] is False


def test_the_price_failure_says_what_the_page_advertises(db_session, configured):
    detail = by_name(report_for(FakeClient(price=good_price(unit_amount=500))))["Stripe Price"]["detail"]
    assert "5.00" in detail and "6.00" in detail


def test_a_price_that_does_not_exist_fails(db_session, configured):
    err = stripe.InvalidRequestError("No such price: 'price_launch'", param="price")
    assert status_of(report_for(FakeClient(price=err)), "Stripe Price") == "fail"


def test_a_key_stripe_rejects_fails(db_session, configured):
    err = stripe.AuthenticationError("Invalid API Key provided")
    detail = by_name(report_for(FakeClient(price=err)))["Stripe Price"]
    assert detail["status"] == "fail" and "rejected" in detail["detail"]


# --- the webhook ---------------------------------------------------------------


def test_a_missing_webhook_endpoint_fails_and_names_what_exists(db_session, configured):
    other = good_endpoint(url="https://elsewhere.example.com/hook")
    c = by_name(report_for(FakeClient(endpoints=[other])))["Stripe webhook"]
    assert c["status"] == "fail"
    assert URL in c["detail"] and "elsewhere.example.com" in c["detail"]


def test_a_disabled_webhook_endpoint_fails(db_session, configured):
    c = by_name(report_for(FakeClient(endpoints=[good_endpoint(status="disabled")])))["Stripe webhook"]
    assert c["status"] == "fail" and "disabled" in c["detail"]


def test_a_webhook_missing_an_event_fails_and_names_it(db_session, configured):
    events = sorted(stripe_billing.HANDLED_EVENTS - {"invoice.payment_failed"})
    c = by_name(report_for(FakeClient(endpoints=[good_endpoint(enabled_events=events)])))["Stripe webhook"]
    assert c["status"] == "fail"
    assert "invoice.payment_failed" in c["detail"]


def test_a_wildcard_subscription_satisfies_every_event(db_session, configured):
    report = report_for(FakeClient(endpoints=[good_endpoint(enabled_events=["*"])]))
    assert status_of(report, "Stripe webhook") == "ok"


def test_a_trailing_slash_on_the_registered_url_still_matches(db_session, configured):
    report = report_for(FakeClient(endpoints=[good_endpoint(url=URL + "/")]))
    assert status_of(report, "Stripe webhook") == "ok"


def test_a_restricted_key_that_cannot_list_endpoints_is_a_warning_not_a_failure(
    db_session, configured
):
    err = stripe.PermissionError("This API call cannot be made with a restricted key")
    report = report_for(FakeClient(endpoints=err))
    assert status_of(report, "Stripe webhook") == "warn"
    assert URL in by_name(report)["Stripe webhook"]["detail"]  # tells you what to look for
    assert report["ok"] is True


# --- the portal ----------------------------------------------------------------


def test_no_portal_configuration_fails_because_manage_subscription_would_break(
    db_session, configured
):
    c = by_name(report_for(FakeClient(portals=[])))["Customer Portal"]
    assert c["status"] == "fail"
    assert "Customer portal" in c["detail"]


def test_a_portal_that_cannot_cancel_is_a_warning(db_session, configured):
    portal = {"features": {"subscription_cancel": {"enabled": False}}}
    assert status_of(report_for(FakeClient(portals=[portal])), "Customer Portal") == "warn"


# --- who would be affected -------------------------------------------------------


def make_user(plan="free"):
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    u = User.create_user(f"who_{suffix}", "testpassword")
    u.plan = plan
    u.save()
    return u


def give_boards(user, n):
    return [Board.create_with_columns(owner=user, name=f"b{i}") for i in range(n)]


def give_cards(board, n):
    col = board.columns.order_by(Column.position).first()
    Card.insert_many([{"column": col, "title": f"c{i}", "position": i} for i in range(n)]).execute()


def test_a_user_at_the_board_limit_is_affected(db_session):
    user = make_user()
    give_boards(user, billing.FREE_MAX_BOARDS)
    (u,) = billing_check.affected_users()
    assert (u["id"], u["boards_owned"], u["at_board_limit"]) == (user.id, billing.FREE_MAX_BOARDS, True)


def test_a_user_with_a_full_board_is_affected_and_the_board_is_named(db_session):
    user = make_user()
    (board,) = give_boards(user, 1)
    give_cards(board, billing.FREE_MAX_CARDS_PER_BOARD)
    (u,) = billing_check.affected_users()
    assert u["at_board_limit"] is False
    assert u["full_boards"] == [{"id": board.id, "name": "b0", "cards": billing.FREE_MAX_CARDS_PER_BOARD}]


def test_a_user_just_under_both_limits_is_not_affected(db_session):
    user = make_user()
    boards = give_boards(user, billing.FREE_MAX_BOARDS - 1)
    give_cards(boards[0], billing.FREE_MAX_CARDS_PER_BOARD - 1)
    assert billing_check.affected_users() == []


def test_pro_users_are_never_affected(db_session):
    user = make_user(plan="pro")
    boards = give_boards(user, billing.FREE_MAX_BOARDS + 2)
    give_cards(boards[0], billing.FREE_MAX_CARDS_PER_BOARD + 5)
    assert billing_check.affected_users() == []


def test_someone_who_owns_nothing_is_not_affected(db_session):
    make_user()
    assert billing_check.affected_users() == []


def test_the_human_report_lists_affected_users_and_points_at_the_fix(db_session, configured):
    user = make_user()
    (board,) = give_boards(user, 1)
    give_cards(board, billing.FREE_MAX_CARDS_PER_BOARD)
    text = billing_check.format_report(report_for(FakeClient()))
    assert "blocked from creating things: 1" in text
    assert user.username in text and "100 cards" in text
    assert "admin Users page" in text


def test_the_database_being_out_of_date_is_a_plain_failure_not_a_traceback(
    db_session, configured, monkeypatch
):
    from peewee import OperationalError

    def stale():
        raise OperationalError("no such column: t1.plan")

    monkeypatch.setattr(billing_check, "affected_users", stale)
    report = report_for(FakeClient())
    c = by_name(report)["Database"]
    assert c["status"] == "fail" and "manage.py migrate" in c["detail"]
    assert report["ok"] is False


# --- the command -----------------------------------------------------------------


def run_command(capsys, monkeypatch, **flags):
    manage = importlib.import_module("manage")
    # The suite holds one database connection open for the whole session; the
    # command closes its own, which here would destroy the test database.
    monkeypatch.setattr(manage.db, "close", lambda: None)
    args = SimpleNamespace(no_stripe=True, json=False, **flags)
    with pytest.raises(SystemExit) as exit_info:
        manage.cmd_billing_check(args)
    return exit_info.value.code, capsys.readouterr().out


def test_the_command_exits_zero_when_ready_and_one_when_not(db_session, configured, capsys, monkeypatch):
    code, out = run_command(capsys, monkeypatch)
    assert code == 0 and "Ready." in out

    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    code, out = run_command(capsys, monkeypatch)
    assert code == 1 and "Not ready" in out


def test_the_command_can_print_json(db_session, configured, capsys, monkeypatch):
    manage = importlib.import_module("manage")
    monkeypatch.setattr(manage.db, "close", lambda: None)
    with pytest.raises(SystemExit) as exit_info:
        manage.cmd_billing_check(SimpleNamespace(no_stripe=True, json=True))
    assert exit_info.value.code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert {"checks", "affected_users", "mode"} <= set(parsed)


# --- the real SDK ----------------------------------------------------------------


class FakeStripeApi(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        FakeStripeApi.requests.append((parsed.path, parse_qs(parsed.query)))
        if parsed.path == f"/v1/prices/{PRICE}":
            body = {"id": PRICE, "object": "price", "active": True, "type": "recurring",
                    "unit_amount": 600, "currency": "usd", "livemode": True,
                    "recurring": {"interval": "month", "interval_count": 1}}
        elif parsed.path == "/v1/webhook_endpoints":
            body = {"object": "list", "url": "/v1/webhook_endpoints", "has_more": False,
                    "data": [{"id": "we_1", "object": "webhook_endpoint", "url": URL,
                              "status": "enabled",
                              "enabled_events": sorted(stripe_billing.HANDLED_EVENTS)}]}
        elif parsed.path == "/v1/billing_portal/configurations":
            body = {"object": "list", "url": "/v1/billing_portal/configurations",
                    "has_more": False,
                    "data": [{"id": "bpc_1", "object": "billing_portal.configuration",
                              "is_default": True, "active": True,
                              "features": {"subscription_cancel": {"enabled": True}}}]}
        else:
            self.send_error(404)
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_the_real_sdk_passes_every_check_against_a_stripe_shaped_server(db_session, configured):
    FakeStripeApi.requests = []
    server = HTTPServer(("127.0.0.1", 0), FakeStripeApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = stripe.StripeClient(
            "sk_live_wire",
            base_addresses={"api": f"http://127.0.0.1:{server.server_address[1]}"},
            max_network_retries=0,
        )
        report = billing_check.run(client=client)
    finally:
        server.shutdown()

    assert {c["status"] for c in report["checks"]} == {"ok"}, report["checks"]
    paths = [p for p, _ in FakeStripeApi.requests]
    assert paths == [f"/v1/prices/{PRICE}", "/v1/webhook_endpoints", "/v1/billing_portal/configurations"]
    # Every call is a read: nothing here can change anything in Stripe.
    query = dict(FakeStripeApi.requests[2][1])
    assert query["is_default"] == ["true"] and query["active"] == ["true"]
