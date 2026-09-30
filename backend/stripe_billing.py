"""Stripe: take a payment, and keep User.plan in step with it.

Three pieces, none of which decide anything about what a plan allows (that is
backend/billing.py):

  * a Checkout Session, so the card form is Stripe's, not ours;
  * a Customer Portal session, so changing the card or cancelling is Stripe's
    UI as well -- there is no billing screen of our own to build or secure;
  * a webhook, which is the ONLY thing that moves User.plan. The page Stripe
    redirects to after a payment proves nothing (anyone can type that URL), so
    it is never trusted: it just refreshes the usage and waits for this.

The webhook does not believe its own payload. Events arrive late, twice, and
out of order, so a "subscription deleted" for last year's subscription can land
after the new one went active. Every event is therefore used only to learn
WHICH CUSTOMER to look at; the plan is then derived from that customer's
subscriptions as Stripe reports them right now. That makes a duplicate or
reordered event harmless, because each one recomputes the same answer.

Configured by environment, read per call so tests can set it:
    STRIPE_SECRET_KEY      sk_live_... / sk_test_...
    STRIPE_PRICE_ID        the Pro plan's recurring Price
    STRIPE_WEBHOOK_SECRET  whsec_..., from the webhook endpoint in the dashboard
"""

import logging
import os
from datetime import datetime, timezone

import stripe

from backend.mailer import public_base_url
from backend.models import User

logger = logging.getLogger(__name__)

# past_due stays Pro: Stripe is still retrying the card, and dropping someone
# to the free plan over one failed attempt is how a paying customer loses the
# boards they are using. It moves to unpaid or canceled if retries run out.
PRO_STATUSES = {"active", "trialing", "past_due"}

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


class StripeNotConfigured(Exception):
    """A Stripe setting this call needs is missing from the environment."""


class BadWebhook(Exception):
    """The webhook body or signature is not something Stripe sent."""


def _env(name):
    return os.environ.get(name, "").strip()


def checkout_configured():
    return bool(_env("STRIPE_SECRET_KEY") and _env("STRIPE_PRICE_ID"))


def portal_configured():
    return bool(_env("STRIPE_SECRET_KEY"))


def webhook_configured():
    return bool(_env("STRIPE_SECRET_KEY") and _env("STRIPE_WEBHOOK_SECRET"))


def _client():
    """A Stripe client bound to our key. One seam for tests to replace.

    Built per call rather than setting stripe.api_key, so nothing here leaks a
    process-wide credential into any other code that imports stripe.
    """
    key = _env("STRIPE_SECRET_KEY")
    if not key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    return stripe.StripeClient(key)


def _plain(obj):
    """A Stripe object as a plain dict. They are not dicts themselves."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


# --- checkout and portal -----------------------------------------------------


def create_checkout_url(user):
    if not checkout_configured():
        raise StripeNotConfigured("STRIPE_SECRET_KEY and STRIPE_PRICE_ID are required")

    base = public_base_url()
    params = {
        "mode": "subscription",
        "line_items": [{"price": _env("STRIPE_PRICE_ID"), "quantity": 1}],
        # Both carry our user id, so a webhook can find the account even if it
        # arrives before we have stored the customer id.
        "client_reference_id": str(user.id),
        "subscription_data": {"metadata": {"user_id": str(user.id)}},
        "success_url": f"{base}/settings/plan?checkout=success",
        "cancel_url": f"{base}/settings/plan?checkout=cancelled",
    }
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    elif user.email:
        params["customer_email"] = user.email

    return _plain(_client().v1.checkout.sessions.create(params=params))["url"]


def create_portal_url(user):
    if not portal_configured():
        raise StripeNotConfigured("STRIPE_SECRET_KEY is required")
    params = {
        "customer": user.stripe_customer_id,
        "return_url": f"{public_base_url()}/settings/plan",
    }
    return _plain(_client().v1.billing_portal.sessions.create(params=params))["url"]


# --- webhook -------------------------------------------------------------------


def construct_event(payload, signature):
    """Verify a webhook body against its Stripe-Signature header.

    Raises BadWebhook for a forged, tampered or stale request, and
    StripeNotConfigured if we have no secret to check it with -- which must
    refuse the request, never accept it unchecked.
    """
    if not webhook_configured():
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is required")
    try:
        return _plain(
            _client().construct_event(payload, signature, _env("STRIPE_WEBHOOK_SECRET"))
        )
    except (stripe.SignatureVerificationError, ValueError) as e:
        raise BadWebhook(str(e))


def _customer_and_user_hint(event):
    """(customer id, our user id or None) for an event we act on, else (None, None)."""
    kind = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if kind == "checkout.session.completed":
        if obj.get("mode") != "subscription":
            return None, None
        return obj.get("customer"), obj.get("client_reference_id")

    if kind.startswith("customer.subscription."):
        return obj.get("customer"), (obj.get("metadata") or {}).get("user_id")

    if kind == "invoice.payment_failed":
        # The subscription moves to past_due and fires its own event, but the
        # invoice is enough to name the customer, and recomputing is free.
        return obj.get("customer"), None

    return None, None


def _find_user(customer_id, user_id_hint):
    user = User.get_or_none(User.stripe_customer_id == customer_id)
    if user is None and user_id_hint and str(user_id_hint).isdigit():
        user = User.get_or_none(User.id == int(user_id_hint))
    return user


def _period_end(subscription):
    """When the current paid period ends, as an aware datetime, or None.

    Newer Stripe API versions moved this off the subscription and onto its
    items; older ones have it on the subscription. Either is read.
    """
    stamp = subscription.get("current_period_end")
    if stamp is None:
        ends = [
            item.get("current_period_end")
            for item in (subscription.get("items") or {}).get("data", [])
            if item.get("current_period_end")
        ]
        stamp = max(ends) if ends else None
    return datetime.fromtimestamp(stamp, timezone.utc) if stamp else None


def _best_subscription(subscriptions):
    """The one that decides the plan: a paying one if any, else the latest.

    A customer can hold several over time (subscribe, cancel, subscribe again);
    the old canceled ones must not outvote the live one.
    """
    paying = [s for s in subscriptions if s.get("status") in PRO_STATUSES]
    pool = paying or subscriptions
    if not pool:
        return None
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    return max(pool, key=lambda s: (_period_end(s) or epoch, s.get("created") or 0))


def sync_customer(customer_id, user_id_hint=None):
    """Set the plan of whoever owns `customer_id` from Stripe's current state.

    Returns the updated User, or None when no account matches.
    """
    user = _find_user(customer_id, user_id_hint)
    if user is None:
        logger.warning("Stripe customer %s matches no user; ignoring", customer_id)
        return None

    listing = _plain(
        _client().v1.subscriptions.list(
            params={"customer": customer_id, "status": "all", "limit": 100}
        )
    )
    best = _best_subscription(listing.get("data", []))

    user.stripe_customer_id = customer_id
    if best is None:
        user.plan = "free"
        user.subscription_status = None
        user.current_period_end = None
    else:
        user.plan = "pro" if best.get("status") in PRO_STATUSES else "free"
        user.subscription_status = best.get("status")
        user.current_period_end = _period_end(best)
    user.save()
    return user


def handle_event(event):
    """Act on a verified event. Returns what happened, for the response body."""
    if event.get("type") not in HANDLED_EVENTS:
        return "ignored"
    customer_id, user_hint = _customer_and_user_hint(event)
    if not customer_id:
        return "ignored"
    return "synced" if sync_customer(customer_id, user_hint) else "no matching user"
