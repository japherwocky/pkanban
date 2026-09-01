"""Who may read an invite token, and who may redeem one.

Three weaknesses, all cheap to fix and all much harder to change once invites
are in real use:

  - the list endpoint handed the raw token to every org member, so any member
    could lift an invite addressed to someone else and pass it to an outsider,
    routing around "only the owner can create invites"
  - accept_invite never compared invite.email to the person accepting, so an
    emailed invite was a bearer token
  - nothing deduplicated, so inviting the same address twice minted two live
    tokens and revoking the visible one left the other working
"""

import os
import random
import string
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.auth import create_access_token
from backend.models import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
)


@pytest.fixture
def client():
    return TestClient(app)


def headers(user):
    return {
        "Authorization": "Bearer "
        + create_access_token(data={"sub": user.id, "username": user.username})
    }


def slug(base):
    return f"{base}-" + "".join(random.choices(string.ascii_lowercase, k=8))


def make_org(name, owner):
    return Organization.create_with_columns(name, slug(name.lower()), owner)


class TestAnAddressedInviteIsForThatAddress:
    def test_someone_else_cannot_redeem_it(self, client, db_session):
        owner = User.create_user("ai_owner", "password", email="ai_owner@example.com")
        org = make_org("AI Org", owner)
        interloper = User.create_user("ai_other", "password", email="other@example.com")
        _, token = OrganizationInvite.create_invite(org, owner, "wanted@example.com")

        response = client.post(
            f"/api/invites/{token}/accept", headers=headers(interloper)
        )
        assert response.status_code == 403
        assert "wanted@example.com" in response.json()["detail"]
        assert OrganizationMember.get_or_none(
            (OrganizationMember.organization == org)
            & (OrganizationMember.user == interloper)
        ) is None

    def test_the_addressee_can(self, client, db_session):
        owner = User.create_user("ok_owner", "password", email="ok_owner@example.com")
        org = make_org("OK Org", owner)
        # Case and surrounding space must not decide who gets in.
        invitee = User.create_user("ok_invitee", "password", email="Wanted@Example.com")
        _, token = OrganizationInvite.create_invite(org, owner, "wanted@example.com")

        response = client.post(
            f"/api/invites/{token}/accept", headers=headers(invitee)
        )
        assert response.status_code == 200

    def test_an_account_with_no_email_cannot(self, client, db_session):
        """Accounts predating self-serve signup have no email at all."""
        owner = User.create_user("ne_owner", "password", email="ne_owner@example.com")
        org = make_org("NE Org", owner)
        legacy = User.create_user("ne_legacy", "password")
        _, token = OrganizationInvite.create_invite(org, owner, "someone@example.com")

        response = client.post(f"/api/invites/{token}/accept", headers=headers(legacy))
        assert response.status_code == 403

    def test_an_anonymous_invite_stays_bearer(self, client, db_session):
        """A link with no addressee is meant to be passed around."""
        owner = User.create_user("an_owner", "password", email="an_owner@example.com")
        org = make_org("AN Org", owner)
        anyone = User.create_user("an_anyone", "password", email="anyone@example.com")
        _, token = OrganizationInvite.create_invite(org, owner, email=None)

        response = client.post(f"/api/invites/{token}/accept", headers=headers(anyone))
        assert response.status_code == 200

    def test_an_existing_member_hears_about_that_not_the_address(
        self, client, db_session
    ):
        """The membership check runs first so the message is the useful one."""
        owner = User.create_user("em_owner", "password", email="em_owner@example.com")
        org = make_org("EM Org", owner)
        member = User.create_user("em_member", "password", email="member@example.com")
        OrganizationMember.create(
            user=member, organization=org, joined_at=datetime.now(timezone.utc)
        )
        _, token = OrganizationInvite.create_invite(org, owner, "someone@example.com")

        response = client.post(f"/api/invites/{token}/accept", headers=headers(member))
        assert response.status_code == 400
        assert "already a member" in response.json()["detail"]


class TestTokensAreForTheOwner:
    def test_a_member_sees_the_invite_but_not_its_token(self, client, db_session):
        owner = User.create_user("tk_owner", "password", email="tk_owner@example.com")
        org = make_org("TK Org", owner)
        member = User.create_user("tk_member", "password", email="tk_m@example.com")
        OrganizationMember.create(
            user=member, organization=org, joined_at=datetime.now(timezone.utc)
        )
        OrganizationInvite.create_invite(org, owner, "wanted@example.com")

        as_member = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers(member)
        ).json()
        assert len(as_member) == 1
        assert as_member[0]["email"] == "wanted@example.com"
        assert "token" not in as_member[0]

        as_owner = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers(owner)
        ).json()
        assert as_owner[0]["token"]


class TestOneLiveInvitePerAddress:
    def test_reinviting_supersedes_the_previous_token(self, client, db_session):
        """Revoking the invite shown in the UI used to leave duplicates live."""
        owner = User.create_user("dup_owner", "password", email="dup@example.com")
        org = make_org("DUP Org", owner)
        invitee = User.create_user("dup_to", "password", email="dup_to@example.com")

        first = client.post(
            f"/api/organizations/{org.id}/invites",
            json={"email": "dup_to@example.com"},
            headers=headers(owner),
        ).json()
        second = client.post(
            f"/api/organizations/{org.id}/invites",
            json={"email": "dup_to@example.com"},
            headers=headers(owner),
        ).json()
        assert first["token"] != second["token"]

        listed = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers(owner)
        ).json()
        assert len(listed) == 1, "only the newest invite stays pending"

        assert client.get(f"/api/invites/{first['token']}").status_code == 404
        assert (
            client.post(
                f"/api/invites/{first['token']}/accept", headers=headers(invitee)
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/invites/{second['token']}/accept", headers=headers(invitee)
            ).status_code
            == 200
        )

    def test_inviting_an_existing_member_is_refused(self, client, db_session):
        owner = User.create_user("ex_owner", "password", email="ex_owner@example.com")
        org = make_org("EX Org", owner)
        member = User.create_user("ex_member", "password", email="ex_m@example.com")
        OrganizationMember.create(
            user=member, organization=org, joined_at=datetime.now(timezone.utc)
        )

        response = client.post(
            f"/api/organizations/{org.id}/invites",
            json={"email": "EX_M@example.com"},
            headers=headers(owner),
        )
        assert response.status_code == 400
        assert "already a member" in response.json()["detail"]

    def test_anonymous_invites_do_not_supersede_each_other(self, client, db_session):
        """They have no address to be a duplicate of."""
        owner = User.create_user("aa_owner", "password", email="aa_owner@example.com")
        org = make_org("AA Org", owner)
        for _ in range(2):
            client.post(
                f"/api/organizations/{org.id}/invites",
                json={},
                headers=headers(owner),
            )

        listed = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers(owner)
        ).json()
        assert len(listed) == 2

    def test_superseding_is_scoped_to_one_organization(self, client, db_session):
        """The same person may have a live invite to two different orgs."""
        owner = User.create_user("so_owner", "password", email="so_owner@example.com")
        org_a = make_org("SO Org A", owner)
        org_b = make_org("SO Org B", owner)

        client.post(
            f"/api/organizations/{org_a.id}/invites",
            json={"email": "both@example.com"},
            headers=headers(owner),
        )
        client.post(
            f"/api/organizations/{org_b.id}/invites",
            json={"email": "both@example.com"},
            headers=headers(owner),
        )

        assert len(client.get(
            f"/api/organizations/{org_a.id}/invites", headers=headers(owner)
        ).json()) == 1
        assert len(client.get(
            f"/api/organizations/{org_b.id}/invites", headers=headers(owner)
        ).json()) == 1


class TestExpiredInvitesAreNotListedAsPending:
    def test_an_expired_invite_drops_out_of_the_list(self, client, db_session):
        """Expiry is only evaluated when a token is read, so the row sits in
        the table still marked pending until someone happens to open it."""
        owner = User.create_user("xp_owner", "password", email="xp_owner@example.com")
        org = make_org("XP Org", owner)
        invite, _ = OrganizationInvite.create_invite(org, owner, "xp@example.com")
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        invite.save()

        listed = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers(owner)
        ).json()
        assert listed == []
