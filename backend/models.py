import bcrypt  # type: ignore
from peewee import (
    CharField,
    IntegerField,
    ForeignKeyField,
    DateTimeField,
    TextField,
    BooleanField,
    SQL,
)
from playhouse.sqlite_ext import AutoIncrementField, Model  # type: ignore
from datetime import datetime, timezone, timedelta

from backend.database import db


class BaseModel(Model):
    # AUTOINCREMENT, not peewee's default rowid alias: the default hands a deleted
    # row's id to the next insert. Migration 007 rebuilds existing tables to match.
    id = AutoIncrementField()

    class Meta:
        database = db


PASSWORD_MAX_LENGTH = 72


def _as_datetime(value):
    """Normalize a DateTimeField read back into an aware UTC datetime.

    Peewee writes aware datetimes to SQLite as '...+00:00', which matches none
    of the formats it tries when reading them back, so it hands us the raw
    string instead. Naive values are assumed UTC -- everything in this file
    writes UTC, and a naive value would otherwise blow up on comparison with
    an aware one.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


class User(BaseModel):
    username = CharField(unique=True, max_length=100)
    password_hash = CharField(max_length=255)
    # Unique, but still nullable: accounts predating self-serve signup have no
    # email, and SQLite lets a unique index hold any number of NULLs.
    email = CharField(max_length=255, null=True, unique=True)
    # Self-serve signups start False and are gated out of login until they
    # click the emailed link. Accounts made by an admin or the CLI are created
    # verified -- whoever ran that already vouched for the person.
    email_verified = BooleanField(default=False)
    admin = BooleanField(default=False)
    # What the account pays for: "free" or "pro". Billing state, not access
    # control -- see backend/billing.py for what a plan changes. The Stripe
    # webhook is the only thing that should move it. The DEFAULT is spelled out
    # in SQL so a migrated database and a fresh install have the same column
    # (peewee's own default=... lives in Python and never reaches the schema).
    plan = CharField(max_length=20, default="free", constraints=[SQL("DEFAULT 'free'")])
    stripe_customer_id = CharField(max_length=255, null=True, unique=True)
    subscription_status = CharField(max_length=40, null=True)
    current_period_end = DateTimeField(null=True)

    @property
    def is_pro(self):
        return self.plan == "pro"

    @classmethod
    def create_user(
        cls, username, password, email=None, admin=False, email_verified=True
    ):
        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"Password must be {PASSWORD_MAX_LENGTH} characters or fewer"
            )
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        return cls.create(
            username=username,
            password_hash=password_hash,
            email=email,
            admin=admin,
            email_verified=email_verified,
        )

    def verify_password(self, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )  # type: ignore


API_KEY_PREFIX = "pkanban_"
API_KEY_LENGTH = 32  # Length of the random part (32 chars = 192 bits of entropy)


def generate_api_key():
    """Generate a new API key with the pkanban_ prefix."""
    import secrets
    import base64

    random_bytes = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8")
    random_bytes = random_bytes.rstrip("=")[:API_KEY_LENGTH]
    return f"{API_KEY_PREFIX}{random_bytes}"


def hash_api_key(key):
    """SHA-256 of an API key, hex -- what a key is stored and looked up by.

    Not bcrypt, deliberately. A password needs a slow hash because people pick
    guessable ones; a key is 192 random bits, so there is nothing to slow an
    attacker down on, and bcrypt only cost every authenticated request about a
    quarter of a second of CPU. A fast, deterministic hash is also what makes
    the key findable by an indexed equality lookup.
    """
    import hashlib

    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# The literal "pkanban_" plus the first 8 random characters: enough to tell
# one key from another in a list, and far too little to guess the rest.
API_KEY_DISPLAY_LENGTH = len(API_KEY_PREFIX) + 8

# A key's last_used_at is written at most this often, so authenticating is not
# a database write on every request.
LAST_USED_RESOLUTION = timedelta(minutes=1)


def get_api_key_prefix(key):
    """The part of a key that is safe to display, for telling keys apart."""
    return key[:API_KEY_DISPLAY_LENGTH]


class ApiKey(BaseModel):
    """One-off API keys for agent authentication.

    Keys are found by the SHA-256 of the whole key (key_sha256). They used to
    be found by `prefix`, which was the first 8 characters -- the literal
    "pkanban_" on every key -- so the lookup matched the first row in the table
    and every other key failed as "Invalid API key". Keys minted before that
    fix have only a bcrypt `key_hash`; `find()` upgrades each one the first
    time it is used. See migration 006.
    """

    user = ForeignKeyField(User, backref="api_keys")
    name = CharField(max_length=100)  # Friendly name (e.g., "CI Agent")
    # bcrypt hash, for keys minted before migration 006 and not used since.
    # Empty once a key has been upgraded, and for every key minted after.
    key_hash = CharField(max_length=255)
    prefix = CharField(max_length=16)  # Display only, e.g. "pkanban_Ab3xYz12"
    created_at = DateTimeField(default=datetime.now)
    last_used_at = DateTimeField(null=True)
    expires_at = DateTimeField(null=True)  # Optional expiration
    is_active = BooleanField(default=True)
    # Declared last because migration 006 appends it, and a fresh install
    # should build the same column order a migrated database has.
    key_sha256 = CharField(max_length=64, null=True, unique=True)

    @classmethod
    def create_key(cls, user, name, expires_at=None):
        """Create a new API key for a user."""
        key = generate_api_key()
        return cls.create(
            user=user,
            name=name,
            key_hash="",
            key_sha256=hash_api_key(key),
            prefix=get_api_key_prefix(key),
            expires_at=expires_at,
        ), key

    @classmethod
    def find(cls, key):
        """The ApiKey row for a raw key, or None. Active or not.

        One indexed lookup for any key minted or used since migration 006.
        Failing that, the key is checked against the legacy rows -- active
        ones that still have only a bcrypt hash -- and upgraded in place on a
        match, so the slow path runs at most once per legacy key. Inactive
        legacy keys are not scanned: a garbage key costs one bcrypt per active
        legacy row, and that set only shrinks.
        """
        digest = hash_api_key(key)
        row = cls.get_or_none(cls.key_sha256 == digest)
        if row is not None:
            return row

        # Every legacy key has exactly this shape. Checking it also keeps
        # anything over bcrypt's 72-byte input limit away from checkpw.
        if not key.startswith(API_KEY_PREFIX) or len(key) != len(
            API_KEY_PREFIX
        ) + API_KEY_LENGTH:
            return None

        legacy = cls.select().where(
            cls.key_sha256.is_null()
            & (cls.key_hash != "")
            & (cls.is_active == True)  # noqa: E712
        )
        for row in legacy:
            if bcrypt.checkpw(key.encode("utf-8"), row.key_hash.encode("utf-8")):
                row.key_sha256 = digest
                row.key_hash = ""
                row.prefix = get_api_key_prefix(key)
                row.save()
                return row
        return None

    def verify(self, key):
        """Verify a raw key against this row."""
        import hmac

        if self.key_sha256:
            return hmac.compare_digest(self.key_sha256, hash_api_key(key))
        if self.key_hash:
            return bcrypt.checkpw(key.encode("utf-8"), self.key_hash.encode("utf-8"))
        return False

    def deactivate(self):
        """Deactivate this API key."""
        self.is_active = False
        self.save()

    def update_last_used(self):
        """Record that the key was used, at most once per LAST_USED_RESOLUTION."""
        now = datetime.now(timezone.utc)
        last = _as_datetime(self.last_used_at) if self.last_used_at else None
        if last is not None and now - last < LAST_USED_RESOLUTION:
            return
        self.last_used_at = now
        self.save()


class Organization(BaseModel):
    name = CharField(max_length=200)
    slug = CharField(max_length=200, unique=True)
    owner = ForeignKeyField(User, backref="owned_organizations")
    created_at = DateTimeField()

    @classmethod
    def create_with_columns(cls, name, slug, owner):
        return cls.create(
            name=name, slug=slug, owner=owner, created_at=datetime.now(timezone.utc)
        )


class OrganizationMember(BaseModel):
    user = ForeignKeyField(User, backref="organization_memberships")
    organization = ForeignKeyField(Organization, backref="members")
    joined_at = DateTimeField()

    class Meta:  # type: ignore
        indexes = ((("user", "organization"), True),)


class Team(BaseModel):
    name = CharField(max_length=200)
    organization = ForeignKeyField(Organization, backref="teams")
    created_at = DateTimeField()

    @classmethod
    def create_with_columns(cls, name, organization):
        return cls.create(
            name=name, organization=organization, created_at=datetime.now(timezone.utc)
        )


class TeamMember(BaseModel):
    user = ForeignKeyField(User, backref="team_memberships")
    team = ForeignKeyField(Team, backref="members")
    joined_at = DateTimeField()

    class Meta:  # type: ignore
        indexes = ((("user", "team"), True),)


class Board(BaseModel):
    owner = ForeignKeyField(User, backref="boards")
    name = CharField(max_length=200)
    shared_team = ForeignKeyField(Team, null=True, backref="boards")
    # Which organization "public to org" means. Null for a personal board, and
    # set when the board is first shared org-wide -- boards are not owned by an
    # organization, they are shared into one. is_public_to_org was dead for as
    # long as this column did not exist: there was nothing to check membership
    # against, so the flag persisted and was read by nothing.
    organization = ForeignKeyField(Organization, null=True, backref="boards")
    is_public_to_org = BooleanField(default=False)
    created_at = DateTimeField()

    @classmethod
    def create_with_columns(
        cls,
        owner,
        name,
        shared_team=None,
        is_public_to_org=False,
        organization=None,
        column_names=None,
    ):
        if column_names is None:
            column_names = ["To Do", "In Progress", "For Review"]

        board = cls.create(
            owner=owner,
            name=name,
            shared_team=shared_team,
            is_public_to_org=is_public_to_org,
            organization=organization,
            created_at=datetime.now(timezone.utc),
        )
        for i, col_name in enumerate(column_names):
            Column.create(board=board, name=col_name, position=i)
        return board


class Column(BaseModel):
    board = ForeignKeyField(Board, backref="columns")
    name = CharField(max_length=200)
    position = IntegerField()


class Card(BaseModel):
    column = ForeignKeyField(Column, backref="cards")
    title = CharField(max_length=500)
    description = TextField(null=True)
    position = IntegerField()


class Comment(BaseModel):
    card = ForeignKeyField(Card, backref="comments")
    user = ForeignKeyField(User, backref="comments")
    content = TextField()
    created_at = DateTimeField()
    updated_at = DateTimeField(null=True)

    @classmethod
    def create_comment(cls, card, user, content):
        return cls.create(
            card=card, user=user, content=content, created_at=datetime.now(timezone.utc)
        )


class BetaSignup(BaseModel):
    email = CharField(max_length=255, unique=True)
    created_at = DateTimeField()
    status = CharField(max_length=50, default="pending")  # pending, invited, rejected

    @classmethod
    def create_signup(cls, email):
        return cls.create(
            email=email, created_at=datetime.now(timezone.utc), status="pending"
        )


def generate_invite_token():
    """Generate a secure random invite token."""
    import secrets

    return secrets.token_urlsafe(32)


class OrganizationInvite(BaseModel):
    """Invite tokens for joining an organization."""

    organization = ForeignKeyField(Organization, backref="invites")
    # Set when the invite is to a specific team rather than to the org at
    # large. Accepting one of these grants the team and nothing else: teams
    # already span organizations (see add_team_member), so a collaborator can
    # hold a team without appearing in the org's member list. organization is
    # still populated, as the team's owner, for display and scoping.
    team = ForeignKeyField(Team, null=True, backref="invites")
    email = CharField(max_length=255, null=True)  # optional - can be anonymous invite
    token = CharField(max_length=64, unique=True)
    status = CharField(
        max_length=20, default="pending"
    )  # pending, accepted, revoked, expired
    created_by = ForeignKeyField(User, backref="created_invites")
    created_at = DateTimeField()
    expires_at = DateTimeField()

    @classmethod
    def create_invite(
        cls, organization, created_by, email=None, expires_in_days=7, team=None
    ):
        """Create a new invite token."""
        token = generate_invite_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return cls.create(
            organization=organization,
            team=team,
            email=email,
            token=token,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        ), token

    def is_expired(self):
        """Check if invite has expired."""
        return datetime.now(timezone.utc) > _as_datetime(self.expires_at)

    def revoke(self):
        """Revoke this invite."""
        self.status = "revoked"
        self.save()

    def accept(self, user):
        """Accept invite - join the team if it names one, else the org."""
        from backend.models import OrganizationMember, TeamMember

        if self.status != "pending":
            raise ValueError("Invite is not pending")
        if self.is_expired():
            self.status = "expired"
            self.save()
            raise ValueError("Invite has expired")
        self.status = "accepted"
        self.save()

        # A team invite is deliberately the narrower grant: the team carries
        # the boards shared with it, and nothing hands out org membership on
        # the side. Someone who should have both gets two invites.
        if self.team is not None:
            return TeamMember.create(
                user=user, team=self.team, joined_at=datetime.now(timezone.utc)
            )
        return OrganizationMember.create(
            user=user,
            organization=self.organization,
            joined_at=datetime.now(timezone.utc),
        )


VERIFICATION_TOKEN_EXPIRY_HOURS = 24


class EmailVerificationToken(BaseModel):
    """One-shot token proving a self-serve signup owns their email address."""

    user = ForeignKeyField(User, backref="verification_tokens")
    token = CharField(max_length=64, unique=True)
    created_at = DateTimeField()
    expires_at = DateTimeField()
    used_at = DateTimeField(null=True)

    @classmethod
    def create_for(cls, user):
        """Issue a fresh token for a user. Returns (record, token)."""
        token = generate_invite_token()
        now = datetime.now(timezone.utc)
        return cls.create(
            user=user,
            token=token,
            created_at=now,
            expires_at=now + timedelta(hours=VERIFICATION_TOKEN_EXPIRY_HOURS),
        ), token

    def is_expired(self):
        expires_at = _as_datetime(self.expires_at)
        return datetime.now(timezone.utc) > expires_at

    def is_used(self):
        return self.used_at is not None

    def mark_used(self):
        self.used_at = datetime.now(timezone.utc)
        self.save()


# Every model, parents before children.
#
# Single source of truth: database.py, manage.py and the test fixtures all read
# this instead of keeping their own copies. They used to keep four separate
# lists, and manage.py's drifted three tables out of date -- `manage.py init`
# quietly built an incomplete schema and `manage.py status` under-reported.
# Adding a model here is now the only step required.
ALL_MODELS = [
    User,
    Board,
    Column,
    Card,
    Comment,
    Organization,
    OrganizationMember,
    Team,
    TeamMember,
    BetaSignup,
    ApiKey,
    OrganizationInvite,
    EmailVerificationToken,
]
