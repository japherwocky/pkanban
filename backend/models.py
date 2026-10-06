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
from playhouse.sqlite_ext import (  # type: ignore
    AutoIncrementField,
    FTS5Model,
    Model,
    SearchField,
)
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


# Keep CardSearch in step with card. They live in the database rather than in
# the API, so every write is indexed whichever path made it: the endpoints, a
# board delete, manage.py, a shell. The update trigger watches only title and
# description, and only fires when one actually changed -- card.save() writes
# every column, and a drag that reorders a column saves a dozen cards whose
# text is untouched.
#
# The 'delete' rows must carry the values the index currently holds, which is
# why they read old.*. Handing FTS5 anything else corrupts an external-content
# index without raising.
CARD_SEARCH_TRIGGERS = {
    "card_search_insert": """
        CREATE TRIGGER IF NOT EXISTS card_search_insert AFTER INSERT ON card
        BEGIN
            INSERT INTO cardsearch (rowid, title, description)
            VALUES (new.id, new.title, new.description);
        END
    """,
    "card_search_delete": """
        CREATE TRIGGER IF NOT EXISTS card_search_delete AFTER DELETE ON card
        BEGIN
            INSERT INTO cardsearch (cardsearch, rowid, title, description)
            VALUES ('delete', old.id, old.title, old.description);
        END
    """,
    "card_search_update": """
        CREATE TRIGGER IF NOT EXISTS card_search_update
        AFTER UPDATE OF title, description ON card
        WHEN old.title IS NOT new.title OR old.description IS NOT new.description
        BEGIN
            INSERT INTO cardsearch (cardsearch, rowid, title, description)
            VALUES ('delete', old.id, old.title, old.description);
            INSERT INTO cardsearch (rowid, title, description)
            VALUES (new.id, new.title, new.description);
        END
    """,
}


class CardSearch(FTS5Model):
    """Full-text index over card titles and descriptions.

    External content: the text stays in card, and this holds only the index,
    read back through `content=card`. rowid is the card id.

    porter over unicode61 stems ("archived" finds "archiving") and splits on
    every punctuation character, so "Python/Django" and a sentence-final
    "Postgres." both index as plain words. SQLite does the stemming at index
    and query time alike, so there is no second stemmer that has to agree
    with it.

    create_table() also installs the triggers and rebuilds the index whenever
    it had to create anything. That makes it self-healing: a migration that
    rebuilds the card table drops its triggers with it, and the next startup
    puts them back and reindexes whatever was written in between.
    """

    title = SearchField()
    description = SearchField()

    class Meta:
        database = db
        table_name = "cardsearch"
        options = {
            "content": "card",
            "content_rowid": "id",
            "tokenize": "porter unicode61",
        }
        # The triggers are created on card, so it has to exist first.
        depends_on = [Card]

    @classmethod
    def create_table(cls, safe=True, **options):
        database = cls._meta.database
        existing = {
            row[0]
            for row in database.execute_sql(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'card'"
            )
        }
        stale = not cls.table_exists() or not set(CARD_SEARCH_TRIGGERS) <= existing

        super().create_table(safe=safe, **options)
        for sql in CARD_SEARCH_TRIGGERS.values():
            database.execute_sql(sql)

        if stale:
            cls.rebuild()


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


DEVICE_LOGIN_EXPIRY_MINUTES = 10
DEVICE_LOGIN_POLL_SECONDS = 3
# No vowels and no 0/1, so a code can't spell a word or be misread as O/I/L.
USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"
USER_CODE_LENGTH = 8


def normalize_user_code(code):
    """'wdjb-mjht' and 'WDJBMJHT' are the same code."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def format_user_code(code):
    return f"{code[:4]}-{code[4:]}"


class DeviceLogin(BaseModel):
    """One `pkanban login` waiting for its person to approve it in a browser.

    The device code is the CLI's secret and is kept only as a SHA-256, like an
    API key. The user code is the short thing a person types or follows a link
    with. Approval mints nothing: the API key is made when the CLI next polls,
    so the raw key is never stored and is handed out exactly once.
    """

    device_code_sha256 = CharField(max_length=64, unique=True)
    user_code = CharField(max_length=16, unique=True)
    client_name = CharField(max_length=100)
    requester_ip = CharField(max_length=64, null=True)
    # pending -> approved -> claimed, or pending -> denied.
    status = CharField(max_length=16, default="pending")
    user = ForeignKeyField(User, null=True, backref="device_logins")
    api_key = ForeignKeyField(ApiKey, null=True, backref="device_logins")
    created_at = DateTimeField()
    expires_at = DateTimeField()

    @classmethod
    def start(cls, client_name, requester_ip=None):
        """A new pending login. Returns (record, raw device code)."""
        import secrets

        now = datetime.now(timezone.utc)
        # Anything long past its expiry is only clutter; clearing it here keeps
        # the table bounded without a scheduled job.
        cls.delete().where(cls.expires_at < now - timedelta(days=1)).execute()

        device_code = secrets.token_urlsafe(32)
        while True:
            user_code = "".join(
                secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH)
            )
            if not cls.select().where(cls.user_code == user_code).exists():
                break
        return cls.create(
            device_code_sha256=hash_api_key(device_code),
            user_code=user_code,
            client_name=client_name,
            requester_ip=requester_ip,
            created_at=now,
            expires_at=now + timedelta(minutes=DEVICE_LOGIN_EXPIRY_MINUTES),
        ), device_code

    @classmethod
    def by_device_code(cls, device_code):
        return cls.get_or_none(cls.device_code_sha256 == hash_api_key(device_code))

    @classmethod
    def by_user_code(cls, user_code):
        return cls.get_or_none(cls.user_code == normalize_user_code(user_code))

    def is_expired(self):
        return datetime.now(timezone.utc) > _as_datetime(self.expires_at)


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
    CardSearch,
    Comment,
    Organization,
    OrganizationMember,
    Team,
    TeamMember,
    BetaSignup,
    ApiKey,
    OrganizationInvite,
    EmailVerificationToken,
    DeviceLogin,
]
