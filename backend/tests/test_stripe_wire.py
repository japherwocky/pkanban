"""The real Stripe SDK, talking to a local server that speaks Stripe's wire format.

test_stripe_billing.py replaces the client with a fake, which leaves two things
unproven: that our calls serialise into the form-encoded request Stripe expects
(nested params like line_items[0][price] are easy to get subtly wrong), and that
a real StripeObject survives `.to_dict()` into the shapes sync_customer reads.
Both are the SDK's behaviour, not ours, and only the real SDK can show them.
Nothing leaves the machine: the client's API base address is this test's server.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
import stripe
from fastapi.testclient import TestClient

from backend import stripe_billing
from backend.auth import create_access_token
from backend.main import app
from backend.models import User, _as_datetime


class FakeStripeApi(BaseHTTPRequestHandler):
    requests = []  # (method, path, query, form)

    def log_message(self, *args):
        pass

    def _reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self, form=None):
        parsed = urlparse(self.path)
        FakeStripeApi.requests.append(
            (self.command, parsed.path, parse_qs(parsed.query), form or {})
        )
        return parsed.path

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode())
        path = self._record(form)
        if path == "/v1/checkout/sessions":
            self._reply({"id": "cs_test_1", "object": "checkout.session",
                         "url": "https://checkout.stripe.test/c/pay/cs_test_1"})
        elif path == "/v1/billing_portal/sessions":
            self._reply({"id": "bps_1", "object": "billing_portal.session",
                         "url": "https://billing.stripe.test/p/session/bps_1"})
        else:
            self.send_error(404)

    def do_GET(self):
        path = self._record()
        if path == "/v1/subscriptions":
            # The shape of the pinned API version: the period end is on the
            # items, not on the subscription.
            self._reply({
                "object": "list", "url": "/v1/subscriptions", "has_more": False,
                "data": [{
                    "id": "sub_1", "object": "subscription", "customer": "cus_wire",
                    "status": "active", "created": 1_700_000_000,
                    "metadata": {"user_id": "1"},
                    "items": {"object": "list", "has_more": False, "data": [{
                        "id": "si_1", "object": "subscription_item",
                        "current_period_end": 1_850_000_000,
                    }]},
                }],
            })
        else:
            self.send_error(404)


@pytest.fixture
def stripe_api(monkeypatch):
    FakeStripeApi.requests = []
    server = HTTPServer(("127.0.0.1", 0), FakeStripeApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_wire")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_wire")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_wire")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://kanban.example.com")
    monkeypatch.setattr(
        stripe_billing,
        "_client",
        lambda: stripe.StripeClient(
            "sk_test_wire", base_addresses={"api": base}, max_network_retries=0
        ),
    )
    yield FakeStripeApi.requests
    server.shutdown()


@pytest.fixture
def user(db_session):
    u = User.create_user("wire_user", "testpassword", email="wire@example.com")
    return u


def auth(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def test_checkout_is_serialised_the_way_stripe_expects(stripe_api, user):
    client = TestClient(app)
    r = client.post("/api/billing/checkout", headers=auth(user))

    assert r.status_code == 200
    assert r.json()["url"] == "https://checkout.stripe.test/c/pay/cs_test_1"

    method, path, _, form = stripe_api[-1]
    assert (method, path) == ("POST", "/v1/checkout/sessions")
    assert form["mode"] == ["subscription"]
    assert form["line_items[0][price]"] == ["price_wire"]
    assert form["line_items[0][quantity]"] == ["1"]
    assert form["client_reference_id"] == [str(user.id)]
    assert form["subscription_data[metadata][user_id]"] == [str(user.id)]
    assert form["customer_email"] == ["wire@example.com"]
    assert form["success_url"] == ["https://kanban.example.com/settings/plan?checkout=success"]


def test_portal_is_serialised_the_way_stripe_expects(stripe_api, user):
    user.stripe_customer_id = "cus_wire"
    user.save()
    r = TestClient(app).post("/api/billing/portal", headers=auth(user))

    assert r.status_code == 200
    assert r.json()["url"] == "https://billing.stripe.test/p/session/bps_1"
    _, path, _, form = stripe_api[-1]
    assert path == "/v1/billing_portal/sessions"
    assert form["customer"] == ["cus_wire"]
    assert form["return_url"] == ["https://kanban.example.com/settings/plan"]


def test_a_real_subscription_object_becomes_a_plan(stripe_api, user):
    """The real SDK parses the JSON into StripeObjects; sync_customer must read
    status, customer and the period end (on the items) out of them."""
    user.stripe_customer_id = "cus_wire"
    user.save()

    stripe_billing.sync_customer("cus_wire")

    _, path, query, _ = stripe_api[-1]
    assert path == "/v1/subscriptions"
    assert query["customer"] == ["cus_wire"]
    assert query["status"] == ["all"]
    user = User.get_by_id(user.id)
    assert user.plan == "pro"
    assert user.subscription_status == "active"
    assert int(_as_datetime(user.current_period_end).timestamp()) == 1_850_000_000
