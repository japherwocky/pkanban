"""Outbound email, via Resend's HTTP API.

Named mailer.py rather than email.py so it cannot be confused with the stdlib
``email`` package that requests and friends import internally.

Sending is best-effort by design. Every caller here is doing something else
that matters more -- creating an account, creating an invite -- and a mail
provider having a bad afternoon should not turn that into a 500. Failures are
logged and reported through the return value; nothing in this module raises.
"""

import os
import sys
from html import escape

import requests

RESEND_API_URL = "https://api.resend.com/emails"

# How long to wait on Resend. Callers run this in a background task, but a
# hung connection would still pin a worker thread indefinitely without this.
SEND_TIMEOUT_SECONDS = 10


def _from_address() -> str:
    # pearachute.com, not pkanban.pearachute.com. In Resend a subdomain is a
    # separate domain with its own DKIM records, and only the apex is
    # verified -- it is also what the pearachute.com site sends from, so both
    # apps share one verified domain. A default pointing at an unverified
    # subdomain would have every send rejected while signup still succeeded,
    # visible only in the service log.
    return os.environ.get("RESEND_FROM", "pkanban <noreply@pearachute.com>")


def public_base_url() -> str:
    """Origin used to build links in outgoing mail.

    Not derived from the incoming request: the links outlive the request, and
    Host is attacker-controlled, so a forged Host would let someone send mail
    from us pointing at their own server.
    """
    return os.environ.get("PUBLIC_BASE_URL", "https://pkanban.pearachute.com").rstrip(
        "/"
    )


def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email. Returns whether it was actually handed to Resend.

    With no RESEND_API_KEY configured this prints the message to stderr and
    returns False, which is what makes local development and the test suite
    work without a key or network access -- verification links show up in the
    server console instead of an inbox.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        print(
            f"pkanban: RESEND_API_KEY not set, not sending mail.\n"
            f"pkanban:   to: {to}\n"
            f"pkanban:   subject: {subject}\n"
            f"pkanban:   body:\n{html}",
            file=sys.stderr,
        )
        return False

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": _from_address(),
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=SEND_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"pkanban: failed to send mail to {to}: {exc}", file=sys.stderr)
        return False

    if not response.ok:
        # Resend puts the reason in the body; the status alone is rarely enough
        # to tell "unverified sending domain" from "malformed address".
        print(
            f"pkanban: Resend rejected mail to {to}: "
            f"{response.status_code} {response.text}",
            file=sys.stderr,
        )
        return False

    return True


# Hardcoded, not tokens: email clients strip <style> blocks and mostly
# don't support CSS custom properties even inline, so these duplicate
# theme.css's values by hand. LIGHT-mode values specifically, not dark --
# mail always renders on a white page regardless of the recipient's
# system theme, so this reuses the same AA-corrected light-mode primary
# theme.css uses for text on white (#63cdf5, the raw brand cyan, is a
# pale tint that fails contrast at roughly 1.8:1 on white).
_BRAND_DARK = "#231f20"  # --color-foreground (light mode) / pear-dark
_BRAND_MUTED = "#6b6560"  # --color-muted-foreground (light mode)
_BRAND_PRIMARY = "#0b6c91"  # --color-primary (light mode)
_BRAND_PRIMARY_FG = "#ffffff"  # --color-primary-foreground (light mode)
_BRAND_BORDER = "#ddd9d4"  # --color-border (light mode)


def _wrap(body: str) -> str:
    """Wraps an email body in the brand container and wordmark header.

    No image logo: many mail clients block remote images by default, so an
    <img> would render as a broken box (or nothing) until the recipient
    opts in -- a text wordmark shows immediately, every time.
    """
    return (
        '<div style="max-width:480px;margin:0 auto;padding:32px 24px;'
        'font-family:Arial,Helvetica,sans-serif">'
        f'<p style="margin:0 0 28px 0;font-size:18px;font-weight:700;'
        f'color:{_BRAND_DARK}">pkanban</p>'
        f"{body}"
        "</div>"
    )


def _button(url: str, label: str) -> str:
    return (
        f'<p><a href="{escape(url)}" '
        f'style="display:inline-block;padding:12px 20px;background:{_BRAND_PRIMARY};'
        f'color:{_BRAND_PRIMARY_FG};border-radius:4px;text-decoration:none;'
        f'font-weight:500">{escape(label)}</a></p>'
        f'<p style="color:{_BRAND_MUTED};font-size:13px">Or paste this into your '
        f'browser:<br>{escape(url)}</p>'
    )


def _signoff() -> str:
    # The one house joke, told once, at the bottom where a signature goes --
    # not explained, not repeated in the subject or body above it.
    return (
        f'<hr style="border:none;border-top:1px solid {_BRAND_BORDER};'
        'margin:28px 0 16px 0">'
        f'<p style="color:{_BRAND_MUTED};font-size:13px;margin:0">'
        "— pkanban (the p is silent)</p>"
    )


def send_verification_email(user, token: str) -> bool:
    """Email a new signup the link that activates their account."""
    url = f"{public_base_url()}/verify?token={token}"
    html = _wrap(
        f'<p style="color:{_BRAND_DARK}">Hi {escape(user.username)},</p>'
        f'<p style="color:{_BRAND_DARK}">Confirm your email address to '
        "finish setting up your pkanban account.</p>"
        f"{_button(url, 'Verify email')}"
        f'<p style="color:{_BRAND_MUTED};font-size:13px">This link expires '
        "in 24 hours. If you didn't sign up, you can ignore this email.</p>"
        f"{_signoff()}"
    )
    return send_email(user.email, "Verify your pkanban email address", html)


def send_invite_email(
    to_email: str, invite_token: str, org_name: str, inviter_username: str
) -> bool:
    """Email someone the link to join an organization."""
    url = f"{public_base_url()}/invite/{invite_token}"
    html = _wrap(
        f'<p style="color:{_BRAND_DARK}"><strong>{escape(inviter_username)}'
        f"</strong> invited you to join <strong>{escape(org_name)}</strong> "
        "on pkanban.</p>"
        f"{_button(url, 'Accept invitation')}"
        f'<p style="color:{_BRAND_MUTED};font-size:13px">This invitation '
        "expires in 7 days.</p>"
        f"{_signoff()}"
    )
    return send_email(to_email, f"{inviter_username} invited you to {org_name}", html)
