"""Stripe: checkout, the customer portal, and the webhook that sets User.plan.

The webhook tests sign their payloads for real and let the real SDK verify
them; only the calls that would leave the machine (create a session, list a
customer's subscriptions) go to a fake.

The property worth the most here: the plan is derived from the customer's
subscriptions as Stripe reports them, not from the event that arrived. So a
duplicated or reordered event cannot leave the wrong plan behind.
"""

import hashlib
import hmac
import json
import random
import string
import time
from types import SimpleNamespace

import pytest
import stripe
from fastapi.testclient import TestClient

from backend import stripe_billing
from backend.auth import create_access_token
from backend.main import app
from backend.models import ApiKey, User, _as_datetime

WEBHOOK_SECRET = "whsec_test_secret"
PRICE = "price_pro_monthly"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID", PRICE)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://kanban.example.com")


class FakeStripe:
    """Stands in for stripe.StripeClient. Records what was asked of it."""

    def __init__(self, subscriptions=(), error=None):
        self.subscriptions = list(subscriptions)
        self.error = error
        self.checkout_params = None
        self.portal_params = None
        self.list_calls = []
        self._real = stripe.StripeClient("sk_test_x")
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=SimpleNamespace(create=self._checkout)),
            billing_portal=SimpleNamespace(sessions=SimpleNamespace(create=self._portal)),
            subscriptions=SimpleNamespace(list=self._list),
        )

    def _maybe_fail(self):
        if self.error:
            raise self.error

    def _checkout(self, params):
        self._maybe_fail()
        self.checkout_params = params
        return {"url": "https://checkout.stripe.test/c/pay"}

    def _portal(self, params):
        self._maybe_fail()
        self.portal_params = params
        return {"url": "https://billing.stripe.test/p/session"}

    def _list(self, params):
        self._maybe_fail()
        self.list_calls.append(params)
        mine = [s for s in self.subscriptions if s["customer"] == params["customer"]]
        return {"data": mine}

    def construct_event(self, payload, signature, secret):
        # The real thing: signature checking is what is under test.
        return self._real.construct_event(payload, signature, secret)


@pytest.fixture
def fake(monkeypatch, configured):
    f = FakeStripe()
    monkeypatch.setattr(stripe_billing, "_client", lambda: f)
    return f


def make_user(email=True, plan="free", customer=None):
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    user = User.create_user(
        f"pay_{suffix}", "testpassword", email=f"{suffix}@example.com" if email else None
    )
    user.plan = plan
    user.stripe_customer_id = customer
    user.save()
    return user


def auth(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def sub(customer, status="active", created=1_700_000_000, end=None, items_end=None, sid=None):
    s = {
        "id": sid or f"sub_{random.randint(1, 10**9)}",
        "customer": customer,
        "status": status,
        "created": created,
        "metadata": {},
    }
    if end is not None:
        s["current_period_end"] = end
    if items_end is not None:
        s["items"] = {"data": [{"current_period_end": items_end}]}
    return s


# --- webhook plumbing --------------------------------------------------------


def signed(payload, secret=WEBHOOK_SECRET, ts=None):
    ts = int(time.time()) if ts is None else ts
    digest = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={digest}", "Content-Type": "application/json"}


def event(kind, obj, event_id="evt_1"):
    return {"id": event_id, "object": "event", "type": kind, "data": {"object": obj}}


def post_event(client, ev, headers=None, secret=WEBHOOK_SECRET):
    body = json.dumps(ev).encode()
    return client.post(
        "/api/billing/webhook", content=body, headers=headers or signed(body, secret)
    )


def refresh(user):
    return User.get_by_id(user.id)


def period_end(user):
    """current_period_end as epoch seconds. SQLite hands an aware datetime back
    as a string, which is what _as_datetime in models.py exists to undo."""
    return int(_as_datetime(refresh(user).current_period_end).timestamp())


# --- checkout ----------------------------------------------------------------


def test_checkout_returns_the_stripe_url(client, db_session, fake):
    user = make_user()
    r = client.post("/api/billing/checkout", headers=auth(user))
    assert r.status_code == 200
    assert r.json() == {"url": "https://checkout.stripe.test/c/pay"}


def test_checkout_asks_for_a_subscription_to_the_configured_price(
    client, db_session, fake
):
    user = make_user()
    client.post("/api/billing/checkout", headers=auth(user))
    p = fake.checkout_params
    assert p["mode"] == "subscription"
    assert p["line_items"] == [{"price": PRICE, "quantity": 1}]
    # Both carry our user id, so a webhook can find the account even if it
    # lands before the customer id has been stored.
    assert p["client_reference_id"] == str(user.id)
    assert p["subscription_data"]["metadata"] == {"user_id": str(user.id)}
    assert p["success_url"] == "https://kanban.example.com/settings/plan?checkout=success"
    assert p["cancel_url"].startswith("https://kanban.example.com/settings/plan")
    assert p["customer_email"] == user.email
    assert "customer" not in p


def test_checkout_reuses_an_existing_stripe_customer(client, db_session, fake):
    user = make_user(customer="cus_existing")
    client.post("/api/billing/checkout", headers=auth(user))
    assert fake.checkout_params["customer"] == "cus_existing"
    assert "customer_email" not in fake.checkout_params


def test_checkout_works_for_a_user_with_no_email(client, db_session, fake):
    user = make_user(email=False)
    assert client.post("/api/billing/checkout", headers=auth(user)).status_code == 200
    assert "customer_email" not in fake.checkout_params


def test_checkout_refuses_someone_already_on_pro(client, db_session, fake):
    user = make_user(plan="pro")
    r = client.post("/api/billing/checkout", headers=auth(user))
    assert r.status_code == 409
    assert fake.checkout_params is None


def test_checkout_without_stripe_configured_is_a_503(client, db_session, monkeypatch):
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    r = client.post("/api/billing/checkout", headers=auth(make_user()))
    assert r.status_code == 503


def test_checkout_reports_stripe_being_down_as_a_502(client, db_session, configured, monkeypatch):
    monkeypatch.setattr(
        stripe_billing, "_client", lambda: FakeStripe(error=stripe.APIConnectionError("down"))
    )
    r = client.post("/api/billing/checkout", headers=auth(make_user()))
    assert r.status_code == 502


def test_an_api_key_cannot_start_checkout_or_open_the_portal(client, db_session, fake):
    user = make_user(customer="cus_1")
    _, key = ApiKey.create_key(user, "agent")
    for path in ("/api/billing/checkout", "/api/billing/portal"):
        r = client.post(path, headers={"X-API-Key": key})
        assert r.status_code in (401, 403), path
    assert fake.checkout_params is None and fake.portal_params is None


def test_checkout_needs_login(client, db_session, fake):
    assert client.post("/api/billing/checkout").status_code in (401, 403)


# --- portal ------------------------------------------------------------------


def test_portal_returns_the_stripe_url_for_the_customer(client, db_session, fake):
    user = make_user(customer="cus_1")
    r = client.post("/api/billing/portal", headers=auth(user))
    assert r.status_code == 200
    assert r.json() == {"url": "https://billing.stripe.test/p/session"}
    assert fake.portal_params["customer"] == "cus_1"
    assert fake.portal_params["return_url"] == "https://kanban.example.com/settings/plan"


def test_portal_without_a_billing_account_is_a_409(client, db_session, fake):
    r = client.post("/api/billing/portal", headers=auth(make_user()))
    assert r.status_code == 409
    assert fake.portal_params is None


# --- the webhook refuses what Stripe did not send ------------------------------


def test_webhook_rejects_a_bad_signature(client, db_session, fake):
    user = make_user(customer="cus_1")
    fake.subscriptions = [sub("cus_1")]
    ev = event("customer.subscription.updated", sub("cus_1"))
    r = post_event(client, ev, secret="whsec_someone_elses")
    assert r.status_code == 400
    assert refresh(user).plan == "free"


def test_webhook_rejects_a_missing_signature(client, db_session, fake):
    body = json.dumps(event("customer.subscription.updated", sub("cus_1"))).encode()
    r = client.post("/api/billing/webhook", content=body)
    assert r.status_code == 400


def test_webhook_rejects_a_body_changed_after_signing(client, db_session, fake):
    user = make_user(customer="cus_1")
    fake.subscriptions = [sub("cus_1")]
    original = json.dumps(event("customer.subscription.updated", sub("cus_1"))).encode()
    headers = signed(original)
    tampered = original.replace(b"cus_1", b"cus_2")
    r = client.post("/api/billing/webhook", content=tampered, headers=headers)
    assert r.status_code == 400
    assert refresh(user).plan == "free"


def test_webhook_rejects_a_replayed_old_signature(client, db_session, fake):
    body = json.dumps(event("customer.subscription.updated", sub("cus_1"))).encode()
    r = client.post(
        "/api/billing/webhook",
        content=body,
        headers=signed(body, ts=int(time.time()) - 3600),
    )
    assert r.status_code == 400


def test_webhook_without_a_secret_refuses_everything(client, db_session, monkeypatch):
    """Failing open here would let anyone POST themselves onto Pro."""
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    user = make_user(customer="cus_1")
    ev = event("customer.subscription.updated", sub("cus_1"))
    r = post_event(client, ev)
    assert r.status_code == 503
    assert refresh(user).plan == "free"


# --- the webhook sets the plan ---------------------------------------------------


def test_checkout_completed_links_the_customer_and_makes_the_user_pro(
    client, db_session, fake
):
    user = make_user()
    fake.subscriptions = [sub("cus_new", "active", items_end=1_800_000_000)]
    ev = event(
        "checkout.session.completed",
        {
            "mode": "subscription",
            "customer": "cus_new",
            "client_reference_id": str(user.id),
            "subscription": "sub_x",
        },
    )
    r = post_event(client, ev)
    assert r.status_code == 200
    user = refresh(user)
    assert user.plan == "pro"
    assert user.stripe_customer_id == "cus_new"
    assert user.subscription_status == "active"
    assert period_end(user) == 1_800_000_000


def test_a_cancelled_subscription_drops_the_user_to_free(client, db_session, fake):
    user = make_user(plan="pro", customer="cus_1")
    fake.subscriptions = [sub("cus_1", "canceled")]
    post_event(client, event("customer.subscription.deleted", sub("cus_1", "canceled")))
    user = refresh(user)
    assert user.plan == "free"
    assert user.subscription_status == "canceled"


@pytest.mark.parametrize(
    "status,plan",
    [
        ("active", "pro"),
        ("trialing", "pro"),
        ("past_due", "pro"),  # Stripe is still retrying the card
        ("unpaid", "free"),
        ("canceled", "free"),
        ("incomplete", "free"),
        ("incomplete_expired", "free"),
        ("paused", "free"),
    ],
)
def test_each_subscription_status_maps_to_a_plan(client, db_session, fake, status, plan):
    user = make_user(customer="cus_1")
    fake.subscriptions = [sub("cus_1", status)]
    post_event(client, event("customer.subscription.updated", sub("cus_1", status)))
    user = refresh(user)
    assert user.plan == plan
    assert user.subscription_status == status


def test_a_failed_payment_is_recorded_without_dropping_the_plan(client, db_session, fake):
    user = make_user(plan="pro", customer="cus_1")
    fake.subscriptions = [sub("cus_1", "past_due")]
    post_event(client, event("invoice.payment_failed", {"customer": "cus_1"}))
    user = refresh(user)
    assert user.subscription_status == "past_due"
    assert user.plan == "pro"


def test_a_duplicate_delivery_changes_nothing(client, db_session, fake):
    user = make_user(customer="cus_1")
    fake.subscriptions = [sub("cus_1", "active", end=1_800_000_000)]
    ev = event("customer.subscription.updated", sub("cus_1"))
    post_event(client, ev)
    once = refresh(user)
    post_event(client, ev)
    twice = refresh(user)
    assert (once.plan, once.subscription_status, once.current_period_end) == (
        twice.plan,
        twice.subscription_status,
        twice.current_period_end,
    )
    assert twice.plan == "pro"


def test_a_late_event_for_an_old_subscription_does_not_undo_a_new_one(
    client, db_session, fake
):
    """Subscribe, cancel, subscribe again. The old subscription's 'deleted'
    event is delivered last. Believing it would drop a paying customer to free;
    deriving the plan from the customer's current subscriptions cannot."""
    user = make_user(plan="pro", customer="cus_1")
    old = sub("cus_1", "canceled", created=1_600_000_000, end=1_650_000_000, sid="sub_old")
    new = sub("cus_1", "active", created=1_700_000_000, end=1_900_000_000, sid="sub_new")
    fake.subscriptions = [old, new]
    post_event(client, event("customer.subscription.deleted", old))
    user = refresh(user)
    assert user.plan == "pro"
    assert user.subscription_status == "active"
    assert period_end(user) == 1_900_000_000


def test_period_end_is_read_from_the_subscription_when_not_on_its_items(
    client, db_session, fake
):
    user = make_user(customer="cus_1")
    fake.subscriptions = [sub("cus_1", "active", end=1_800_000_123)]
    post_event(client, event("customer.subscription.updated", sub("cus_1")))
    assert period_end(user) == 1_800_000_123


def test_a_customer_with_no_subscriptions_is_free(client, db_session, fake):
    user = make_user(plan="pro", customer="cus_1")
    fake.subscriptions = []
    post_event(client, event("customer.subscription.deleted", {"customer": "cus_1"}))
    user = refresh(user)
    assert user.plan == "free"
    assert user.subscription_status is None
    assert user.current_period_end is None


def test_a_subscription_event_arriving_before_checkout_completed_finds_the_user(
    client, db_session, fake
):
    """The customer id is not stored yet, so the user comes from the metadata
    we put on the subscription at checkout."""
    user = make_user()
    fake.subscriptions = [sub("cus_new", "active")]
    obj = sub("cus_new", "active")
    obj["metadata"] = {"user_id": str(user.id)}
    post_event(client, event("customer.subscription.created", obj))
    user = refresh(user)
    assert user.plan == "pro"
    assert user.stripe_customer_id == "cus_new"


def test_an_unknown_customer_is_acknowledged_and_changes_nothing(client, db_session, fake):
    bystander = make_user()
    r = post_event(client, event("customer.subscription.updated", sub("cus_nobody")))
    assert r.status_code == 200
    assert r.json()["result"] == "no matching user"
    assert refresh(bystander).plan == "free"


def test_events_we_do_not_handle_are_acknowledged_without_calling_stripe(
    client, db_session, fake
):
    r = post_event(client, event("charge.refunded", {"customer": "cus_1"}))
    assert r.status_code == 200
    assert r.json()["result"] == "ignored"
    assert fake.list_calls == []


def test_a_one_off_payment_checkout_is_ignored(client, db_session, fake):
    r = post_event(
        client,
        event("checkout.session.completed", {"mode": "payment", "customer": "cus_1"}),
    )
    assert r.json()["result"] == "ignored"
    assert fake.list_calls == []


def test_a_stripe_outage_while_applying_an_event_is_retryable(
    client, db_session, configured, monkeypatch
):
    user = make_user(customer="cus_1")
    monkeypatch.setattr(
        stripe_billing, "_client", lambda: FakeStripe(error=stripe.APIConnectionError("down"))
    )
    r = post_event(client, event("customer.subscription.updated", sub("cus_1")))
    # Non-2xx, so Stripe redelivers instead of treating the event as done.
    assert r.status_code == 502
    assert refresh(user).plan == "free"


# --- what the Plan page is told it may offer -------------------------------------


def usage(client, user):
    return client.get("/api/me/usage", headers=auth(user)).json()


def test_usage_offers_an_upgrade_when_stripe_is_configured(client, db_session, fake):
    body = usage(client, make_user())
    assert body["upgrade_available"] is True
    assert body["manage_available"] is False


def test_usage_offers_the_portal_to_a_customer_and_no_upgrade_to_a_pro_user(
    client, db_session, fake
):
    body = usage(client, make_user(plan="pro", customer="cus_1"))
    assert body["upgrade_available"] is False
    assert body["manage_available"] is True


def test_usage_offers_nothing_when_stripe_is_not_configured(client, db_session, monkeypatch):
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    body = usage(client, make_user(customer="cus_1"))
    assert body["upgrade_available"] is False
    assert body["manage_available"] is False
