import bcrypt  # type: ignore
from peewee import (
    CharField,
    IntegerField,
    ForeignKeyField,
    DateTimeField,
    TextField,
    BooleanField,
)
from playhouse.sqlite_ext import Model  # type: ignore
from datetime import datetime, timezone, timedelta

from backend.database import db


class BaseModel(Model):
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
    """Hash an API key for storage (like passwords)."""
    return bcrypt.hashpw(key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_api_key_prefix(key):
    """Get the first 8 characters of an API key for identification."""
    return key[:8]


class ApiKey(BaseModel):
    """One-off API keys for agent authentication."""

    user = ForeignKeyField(User, backref="api_keys")
    name = CharField(max_length=100)  # Friendly name (e.g., "CI Agent")
    key_hash = CharField(max_length=255)  # bcrypt hash of the key
    prefix = CharField(max_length=8)  # First 8 chars for identification
    created_at = DateTimeField(default=datetime.now)
    last_used_at = DateTimeField(null=True)
    expires_at = DateTimeField(null=True)  # Optional expiration
    is_active = BooleanField(default=True)

    @classmethod
    def create_key(cls, user, name, expires_at=None):
        """Create a new API key for a user."""
        key = generate_api_key()
        prefix = get_api_key_prefix(key)
        key_hash = hash_api_key(key)
        return cls.create(
            user=user,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            expires_at=expires_at,
        ), key

    def verify(self, key):
        """Verify an API key against the stored hash."""
        return bcrypt.checkpw(key.encode("utf-8"), self.key_hash.encode("utf-8"))

    def deactivate(self):
        """Deactivate this API key."""
        self.is_active = False
        self.save()

    def update_last_used(self):
        """Update the last used timestamp."""
        self.last_used_at = datetime.now(timezone.utc)
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
    is_public_to_org = BooleanField(default=False)
    created_at = DateTimeField()

    @classmethod
    def create_with_columns(
        cls, owner, name, shared_team=None, is_public_to_org=False, column_names=None
    ):
        if column_names is None:
            column_names = ["To Do", "In Progress", "For Review"]

        board = cls.create(
            owner=owner,
            name=name,
            shared_team=shared_team,
            is_public_to_org=is_public_to_org,
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
    email = CharField(max_length=255, null=True)  # optional - can be anonymous invite
    token = CharField(max_length=64, unique=True)
    status = CharField(
        max_length=20, default="pending"
    )  # pending, accepted, revoked, expired
    created_by = ForeignKeyField(User, backref="created_invites")
    created_at = DateTimeField()
    expires_at = DateTimeField()

    @classmethod
    def create_invite(cls, organization, created_by, email=None, expires_in_days=7):
        """Create a new invite token."""
        token = generate_invite_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return cls.create(
            organization=organization,
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
        """Accept invite - add user to organization."""
        from backend.models import OrganizationMember

        if self.status != "pending":
            raise ValueError("Invite is not pending")
        if self.is_expired():
            self.status = "expired"
            self.save()
            raise ValueError("Invite has expired")
        self.status = "accepted"
        self.save()
        # Add user to organization
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
