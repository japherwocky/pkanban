import re
from datetime import datetime, timezone
from typing import Literal, Optional

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from peewee import fn
from pydantic import BaseModel, ConfigDict
import os
import stripe

from backend.auth import (
    Token,
    create_access_token,
    get_current_user,
    get_current_user_or_api_key,
    get_current_user_by_session,
    get_current_admin,
)
from backend.billing import check_can_add_card, check_can_create_board, usage_for
from backend.database import db
from backend import stripe_billing
from backend.mailer import send_invite_email, send_verification_email
from backend.search import search_cards
from backend.models import (
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
    DeviceLogin,
    DEVICE_LOGIN_EXPIRY_MINUTES,
    DEVICE_LOGIN_POLL_SECONDS,
    format_user_code,
    _as_datetime,
)

api = APIRouter()
logger = logging.getLogger(__name__)

EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# Detail string the frontend keys on to offer "resend verification" instead of
# a generic login failure. Changing it means changing Login.svelte too.
UNVERIFIED_EMAIL_DETAIL = "Email not verified"

# Minimum gap between verification emails for one account.
RESEND_COOLDOWN_SECONDS = 60


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def accessible_boards(user):
    """Every board `user` can open, as a query.

    The one definition of board access. can_access_board, the board list and
    search all read it, so none of them can drift from the others: a board
    that lists but answers 403, or one search finds but the list hides. The
    list and the access check used to be separate code, and an org-public
    board was reachable by URL for a while before it ever appeared in the list.

    A board is open to its owner, to members of the team it is shared with,
    and -- when is_public_to_org is set -- to the members and owner of its
    organization. The three are OR'd: a board can carry a shared team and the
    org flag at once (share_board does not clear the team when the flag goes
    on), and either one is enough.

    Nothing here dereferences a foreign key, so dangling ones are harmless. A
    shared_team_id whose team was deleted matches no membership. An
    organization_id whose org is gone matches nothing either, because
    member_orgs joins through Organization. organization_id is null for a
    personal board, and the flag means nothing without it.
    """
    teams = TeamMember.select(TeamMember.team).where(TeamMember.user == user)
    member_orgs = (
        Organization.select(Organization.id)
        .join(OrganizationMember)
        .where(OrganizationMember.user == user)
    )
    owned_orgs = Organization.select(Organization.id).where(Organization.owner == user)
    return Board.select().where(
        (Board.owner == user)
        | Board.shared_team.in_(teams)
        | (
            (Board.is_public_to_org == True)  # noqa: E712 -- peewee needs ==
            & (Board.organization.in_(member_orgs) | Board.organization.in_(owned_orgs))
        )
    )


def can_access_board(user, board):
    return accessible_boards(user).where(Board.id == board.id).exists()


def can_modify_board(user, board):
    return can_access_board(user, board)


def is_org_member(user, organization):
    """Check if user is a member of an organization"""
    return (
        OrganizationMember.get_or_none(
            (OrganizationMember.user == user)
            & (OrganizationMember.organization == organization)
        )
        is not None
    )


def can_delete_board(user, board):
    return board.owner == user


def can_share_board(user, board):
    return board.owner == user


def _resolve_share_organization(user, organization_id):
    """Which organization a board is being shared into.

    Explicit when given, inferred when the user has exactly one organization
    to choose from. Refuses to guess between several -- picking the wrong one
    would expose the board to the wrong set of people, and silently.
    """
    orgs = list(get_user_organizations(user))
    if organization_id is not None:
        org = Organization.get_or_none(Organization.id == organization_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if not is_org_member(user, org) and org.owner_id != user.id:
            raise HTTPException(
                status_code=403, detail="Not a member of this organization"
            )
        return org

    if not orgs:
        raise HTTPException(
            status_code=400,
            detail="You are not a member of any organization to share this board with",
        )
    if len(orgs) > 1:
        names = ", ".join(f"{o.name} (id={o.id})" for o in orgs)
        raise HTTPException(
            status_code=400,
            detail=f"Specify organization_id -- you belong to several: {names}",
        )
    return orgs[0]


def get_user_organizations(user):
    return (
        Organization.select()
        .join(OrganizationMember)
        .where(OrganizationMember.user == user)
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str


class UsernameRequest(BaseModel):
    username: str


class BoardCreate(BaseModel):
    name: str


class BoardUpdate(BaseModel):
    name: str


class BoardShare(BaseModel):
    team_id: Optional[int] = None
    is_public_to_org: Optional[bool] = False
    # Which org "public to org" means. Optional: with exactly one organization
    # to choose from the server infers it, which is the common case and keeps
    # the existing single-checkbox UI working unchanged.
    organization_id: Optional[int] = None


class BoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    columns: list
    shared_team_id: Optional[int] = None
    is_public_to_org: bool = False
    organization_id: Optional[int] = None
    owner_id: int


class ColumnCreate(BaseModel):
    board_id: int
    name: str
    # Omitted means "append after the last column". Callers were otherwise
    # made to track an incrementing counter just to add a column at the end.
    position: Optional[int] = None


class ColumnUpdate(BaseModel):
    name: str
    position: int


class ColumnReorderItem(BaseModel):
    id: int
    position: int


class ColumnReorderRequest(BaseModel):
    columns: list[ColumnReorderItem]


class ColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    position: int
    cards: list


class CardCreate(BaseModel):
    column_id: int
    title: str
    description: Optional[str] = None
    position: int


class CardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None
    column_id: Optional[int] = None


class CardReorderItem(BaseModel):
    id: int
    position: int


class CardReorderRequest(BaseModel):
    cards: list[CardReorderItem]


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    position: int
    comments: Optional[list] = []


class CardDetailResponse(CardResponse):
    """A single card, with the column and board it sits on.

    Fetching one card by id is otherwise context-free: the caller knows the id
    and nothing else, and "which column is this on?" is the question that
    usually comes right after "what does it say?".
    """

    column_id: int
    column_name: str
    board_id: int
    board_name: str


class SearchResult(BaseModel):
    """One card a search found, with where it lives.

    snippet is the part of the description around the match, with matched
    words wrapped in  ...  (see backend/search.py). It is plain text:
    escape it before rendering, then turn the markers into highlights.
    """

    id: int
    title: str
    snippet: Optional[str]
    column_id: int
    column_name: str
    board_id: int
    board_name: str


class CommentCreate(BaseModel):
    card_id: int
    content: str


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    user_id: int
    username: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime]


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    owner_id: int
    created_at: datetime


class OrganizationUpdate(BaseModel):
    name: str


class OrganizationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    joined_at: datetime


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    organization_id: int
    created_at: datetime


class TeamUpdate(BaseModel):
    name: str


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    joined_at: datetime


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    admin: bool = False


class BetaSignupRequest(BaseModel):
    email: str


# API Key models
class ApiKeyCreate(BaseModel):
    name: str
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str  # The actual key (shown only once)
    prefix: str
    created_at: datetime


class UserUpdate(BaseModel):
    username: str
    email: Optional[str] = None
    admin: bool = False
    # Omitted means "leave the plan alone", so callers that predate this field
    # keep working. Anything but free/pro is a 422.
    plan: Optional[Literal["free", "pro"]] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str]
    admin: bool
    plan: str = "free"


class PasswordReset(BaseModel):
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class OrganizationCreateAdmin(BaseModel):
    name: str
    owner_id: int


class OrganizationUpdateAdmin(BaseModel):
    name: str
    owner_id: int


class OrganizationResponseAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    owner_id: int
    owner_username: str
    member_count: int
    team_count: int
    created_at: datetime


class TeamCreateAdmin(BaseModel):
    name: str
    organization_id: int


class TeamUpdateAdmin(BaseModel):
    name: str
    organization_id: int


class TeamResponseAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    organization_id: int
    organization_name: str
    member_count: int
    created_at: datetime


class BoardCreateAdmin(BaseModel):
    name: str
    owner_id: int


class BoardUpdateAdmin(BaseModel):
    name: str


class BoardResponseAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    owner_username: str
    shared_team_id: Optional[int]
    shared_team_name: Optional[str]
    is_public_to_org: bool
    column_count: int
    card_count: int
    created_at: datetime


@api.post("/token", response_model=Token)
async def login(request: LoginRequest):
    user = User.get_or_none(User.username == request.username)
    if not user or not user.verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Checked after the password, not before: answering this for anyone who
    # types a username would leak which accounts exist.
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNVERIFIED_EMAIL_DETAIL,
        )
    access_token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@api.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, background_tasks: BackgroundTasks):
    """Create an account. Public -- this is the self-serve front door.

    Takes no organization of any kind. A new account joins nothing; org
    membership comes only from an owner adding you or from accepting an
    invite token.
    """
    username = request.username.strip()
    email = request.email.strip().lower()

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not re.match(EMAIL_PATTERN, email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    if User.get_or_none(User.username == username):
        raise HTTPException(status_code=400, detail="Username is already taken")
    if User.get_or_none(User.email == email):
        # Deliberately explicit. It does reveal that an address is registered,
        # but the alternative -- silently succeeding and mailing the existing
        # account -- strands people who forgot they signed up. The login page
        # already discloses the same thing for usernames.
        raise HTTPException(
            status_code=400, detail="An account with that email already exists"
        )

    try:
        with db.atomic():
            user = User.create_user(
                username=username,
                password=request.password,
                email=email,
                email_verified=False,
            )
            _, token = EmailVerificationToken.create_for(user)
    except ValueError as exc:
        # Raised by create_user past PASSWORD_MAX_LENGTH.
        raise HTTPException(status_code=400, detail=str(exc))

    background_tasks.add_task(send_verification_email, user, token)

    return {
        "message": "Account created. Check your email for a verification link.",
        "email": user.email,
    }


@api.post("/verify-email", response_model=Token)
async def verify_email(request: VerifyEmailRequest):
    """Consume a verification token and log the user in.

    POST rather than a GET link target on purpose: mail scanners and link
    previewers follow GET URLs, which would silently burn the token before the
    recipient ever clicked it.
    """
    record = EmailVerificationToken.get_or_none(
        EmailVerificationToken.token == request.token
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Invalid verification link")
    if record.is_used():
        raise HTTPException(
            status_code=400, detail="This verification link has already been used"
        )
    if record.is_expired():
        raise HTTPException(
            status_code=400,
            detail="This verification link has expired. Request a new one.",
        )

    user = record.user
    with db.atomic():
        record.mark_used()
        if not user.email_verified:
            user.email_verified = True
            user.save()

    access_token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@api.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest, background_tasks: BackgroundTasks
):
    """Re-send a verification email.

    Always reports the same thing regardless of whether the address is
    registered or already verified, so this cannot be used to enumerate
    accounts.
    """
    generic = {
        "message": "If that address needs verifying, we've sent a new link."
    }

    email = request.email.strip().lower()
    if not re.match(EMAIL_PATTERN, email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    user = User.get_or_none(User.email == email)
    if user is None or user.email_verified:
        return generic

    latest = (
        EmailVerificationToken.select()
        .where(EmailVerificationToken.user == user)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if latest is not None:
        age = datetime.now(timezone.utc) - _as_datetime(latest.created_at)
        if age.total_seconds() < RESEND_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429,
                detail="A verification email was just sent. Try again in a minute.",
            )

    _, token = EmailVerificationToken.create_for(user)
    background_tasks.add_task(send_verification_email, user, token)
    return generic


# Pagination for list routes. Deliberately generous: most collections here are
# small, and a caller (an agent especially) is better served by one big answer
# than by many small ones. The body stays a plain list so existing clients keep
# working; paging state travels in headers.
DEFAULT_PAGE_LIMIT = 1000
MAX_PAGE_LIMIT = 10000


def paginate(query, id_field, response: Response, limit: int, cursor: Optional[int]):
    """One page of `query` in id order, by keyset: ids greater than `cursor`.

    Keyset rather than offset so a row inserted or deleted between two pages
    cannot shift one into the other. Sets X-Total-Count (the whole collection,
    ignoring the cursor, so a caller can size a pull before making it) and,
    when more remains, X-Next-Cursor -- pass it back as ?cursor= for the next
    page. Absent means that was the last page.
    """
    response.headers["X-Total-Count"] = str(query.count())
    page = query.order_by(id_field)
    if cursor is not None:
        page = page.where(id_field > cursor)
    rows = list(page.limit(limit + 1))
    if len(rows) > limit:
        rows = rows[:limit]
        response.headers["X-Next-Cursor"] = str(rows[-1].id)
    return rows


@api.get("/health")
async def health():
    """Liveness check for the deploy pipeline. Public, no auth.

    Deliberately fetches a User row rather than returning a constant. A
    constant would pass while the schema was unmigrated, which is exactly the
    outage this is meant to catch.

    It must be .first() and not .count(): peewee compiles .count() to
    SELECT COUNT(1) FROM (SELECT 1 FROM user LIMIT 1), which names none of the
    model's columns and therefore happily succeeds against a database missing
    one. .first() emits the full column list, so a missing column fails here
    the same way it fails for a real request. Verified against an unmigrated
    copy of production, where .count() reported healthy while /api/token was
    raising "no such column: t1.email_verified".

    An empty table is fine -- the SELECT still names every column, so this
    works on a brand new install with no users.

    The endpoint has to actually exist for the check to mean anything. It did
    not when the deploy started curling it, and back then an undefined
    /api/... path fell through to the SPA catch-all and answered 200 with
    index.html. main.py now 404s unmatched /api/ paths instead, but the deploy
    check accepted "200|404" -- so a missing endpoint still read as healthy,
    just via a different route. Hence matching on the response body.
    """
    try:
        User.select().limit(1).first()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        )
    return {"status": "ok"}


@api.get("/admin/status")
async def admin_status(current_user: User = Depends(get_current_user_or_api_key)):
    """Check if current user has admin access"""
    return {"is_admin": current_user.admin}


# Admin user management endpoints
@api.get("/admin/users", response_model=list)
async def list_admin_users(
    response: Response,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[int] = Query(None, ge=0, description="X-Next-Cursor of the previous page"),
    current_admin_user: User = Depends(get_current_admin),
):
    """List users (admin only), paged -- see paginate()"""
    users = paginate(User.select(), User.id, response, limit, cursor)
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "admin": u.admin,
            "plan": u.plan,
            "subscription_status": u.subscription_status,
            # Whether Stripe knows this account. If so, Stripe stays the source
            # of truth: its next event for the customer recomputes the plan and
            # overwrites a manual change, so the admin UI says so.
            "has_stripe_customer": bool(u.stripe_customer_id),
        }
        for u in users
    ]


@api.post("/admin/users", response_model=UserResponse)
async def create_admin_user(
    user_data: UserCreate,
    current_admin_user: User = Depends(get_current_admin),
):
    """Create a new user (admin only)"""
    try:
        user = User.create_user(
            username=user_data.username,
            password=user_data.password,
            email=user_data.email,
            admin=user_data.admin,
        )
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "admin": user.admin,
            "plan": user.plan,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_admin_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin_user: User = Depends(get_current_admin),
):
    """Update a user (admin only)"""
    user = User.get_or_none(User.id == user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from removing their own admin access
    if user == current_admin_user and not user_data.admin:
        raise HTTPException(
            status_code=400, detail="Cannot remove your own admin access"
        )

    # Check for duplicate username
    existing = User.get_or_none(
        (User.username == user_data.username) & (User.id != user_id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Email is unique now that accounts are created by verifying one, so this
    # would otherwise surface as an IntegrityError 500.
    if user_data.email:
        existing_email = User.get_or_none(
            (User.email == user_data.email) & (User.id != user_id)
        )
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already taken")

    user.username = user_data.username
    user.email = user_data.email
    user.admin = user_data.admin
    if user_data.plan is not None:
        user.plan = user_data.plan
    user.save()

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "admin": user.admin,
        "plan": user.plan,
    }


@api.delete("/admin/users/{user_id}")
async def delete_admin_user(
    user_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """Delete a user (admin only)"""
    user = User.get_or_none(User.id == user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user == current_admin_user:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    with db.atomic():
        # Delete cards, columns, boards, team memberships, org memberships, etc.
        # This is a cascade delete - Peewee should handle foreign key cascades
        user.delete_instance(recursive=True)

    return {"ok": True}


@api.post("/admin/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    reset_data: PasswordReset,
    current_admin_user: User = Depends(get_current_admin),
):
    """Reset a user's password (admin only)"""
    user = User.get_or_none(User.id == user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use the same password validation as create_user
    from bcrypt import hashpw, gensalt

    PASSWORD_MAX_LENGTH = 72
    if len(reset_data.password) > PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be {PASSWORD_MAX_LENGTH} characters or fewer",
        )

    user.password_hash = hashpw(reset_data.password.encode("utf-8"), gensalt()).decode(
        "utf-8"
    )
    user.save()

    return {"ok": True}


# Admin organization management endpoints
@api.get("/admin/organizations", response_model=list)
async def list_admin_organizations(
    current_admin_user: User = Depends(get_current_admin),
):
    """List all organizations (admin only)"""
    organizations = Organization.select().order_by(Organization.id)
    result = []
    for org in organizations:
        member_count = (
            OrganizationMember.select()
            .where(OrganizationMember.organization == org)
            .count()
        )
        team_count = Team.select().where(Team.organization == org).count()
        result.append(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "owner_id": org.owner_id,
                "owner_username": org.owner.username,
                "member_count": member_count,
                "team_count": team_count,
                "created_at": org.created_at,
            }
        )
    return result


@api.post("/admin/organizations", response_model=OrganizationResponseAdmin)
async def create_admin_organization(
    org_data: OrganizationCreateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Create an organization (admin only)"""
    owner = User.get_or_none(User.id == org_data.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")

    base_slug = slugify(org_data.name)
    slug = base_slug
    counter = 1
    while Organization.get_or_none(Organization.slug == slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    with db.atomic():
        org = Organization.create_with_columns(
            name=org_data.name, slug=slug, owner=owner
        )
        # Auto-add owner as member
        OrganizationMember.create(
            user=owner, organization=org, joined_at=datetime.now(timezone.utc)
        )
        # Create default team
        Team.create_with_columns(name="Administrators", organization=org)

    member_count = (
        OrganizationMember.select()
        .where(OrganizationMember.organization == org)
        .count()
    )
    team_count = Team.select().where(Team.organization == org).count()

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "owner_username": org.owner.username,
        "member_count": member_count,
        "team_count": team_count,
        "created_at": org.created_at,
    }


@api.put("/admin/organizations/{org_id}", response_model=OrganizationResponseAdmin)
async def update_admin_organization(
    org_id: int,
    org_data: OrganizationUpdateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Update an organization (admin only)"""
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    new_owner = User.get_or_none(User.id == org_data.owner_id)
    if not new_owner:
        raise HTTPException(status_code=404, detail="New owner user not found")

    org.name = org_data.name
    org.owner = new_owner
    org.save()

    # If owner changed, add new owner as member if not already
    existing_member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == new_owner)
    )
    if not existing_member:
        OrganizationMember.create(
            user=new_owner, organization=org, joined_at=datetime.now(timezone.utc)
        )

    member_count = (
        OrganizationMember.select()
        .where(OrganizationMember.organization == org)
        .count()
    )
    team_count = Team.select().where(Team.organization == org).count()

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "owner_username": org.owner.username,
        "member_count": member_count,
        "team_count": team_count,
        "created_at": org.created_at,
    }


@api.delete("/admin/organizations/{org_id}")
async def delete_admin_organization(
    org_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """Delete an organization (admin only)"""
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    with db.atomic():
        org.delete_instance(recursive=True)

    return {"ok": True}


# Admin team management endpoints
@api.get("/admin/teams", response_model=list)
async def list_admin_teams(current_admin_user: User = Depends(get_current_admin)):
    """List all teams (admin only)"""
    teams = Team.select().order_by(Team.id)
    result = []
    for team in teams:
        member_count = TeamMember.select().where(TeamMember.team == team).count()
        result.append(
            {
                "id": team.id,
                "name": team.name,
                "organization_id": team.organization_id,
                "organization_name": team.organization.name,
                "member_count": member_count,
                "created_at": team.created_at,
            }
        )
    return result


@api.post("/admin/teams", response_model=TeamResponseAdmin)
async def create_admin_team(
    team_data: TeamCreateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Create a team (admin only)"""
    org = Organization.get_or_none(Organization.id == team_data.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    team = Team.create_with_columns(name=team_data.name, organization=org)

    member_count = TeamMember.select().where(TeamMember.team == team).count()

    return {
        "id": team.id,
        "name": team.name,
        "organization_id": team.organization_id,
        "organization_name": team.organization.name,
        "member_count": member_count,
        "created_at": team.created_at,
    }


@api.put("/admin/teams/{team_id}", response_model=TeamResponseAdmin)
async def update_admin_team(
    team_id: int,
    team_data: TeamUpdateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Update a team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    new_org = Organization.get_or_none(Organization.id == team_data.organization_id)
    if not new_org:
        raise HTTPException(status_code=404, detail="New organization not found")

    team.name = team_data.name
    team.organization = new_org
    team.save()

    # When transferring to new organization, keep existing members
    # The membership will persist as it has no org constraint

    member_count = TeamMember.select().where(TeamMember.team == team).count()

    return {
        "id": team.id,
        "name": team.name,
        "organization_id": team.organization_id,
        "organization_name": team.organization.name,
        "member_count": member_count,
        "created_at": team.created_at,
    }


@api.delete("/admin/teams/{team_id}")
async def delete_admin_team(
    team_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """Delete a team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    with db.atomic():
        # Remove team from any boards
        Board.update(shared_team=None).where(Board.shared_team == team).execute()
        # Delete team members
        TeamMember.delete().where(TeamMember.team == team).execute()
        # Delete team
        team.delete_instance()

    return {"ok": True}


# Admin team member management endpoints
@api.get("/admin/teams/{team_id}/members", response_model=list)
async def list_admin_team_members(
    team_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """List all members of a team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = TeamMember.select().where(TeamMember.team == team)
    return [
        {
            "id": m.id,
            "user_id": m.user.id,
            "username": m.user.username,
            "joined_at": m.joined_at,
        }
        for m in members
    ]


@api.get("/admin/teams/{team_id}/available-members", response_model=list)
async def list_available_team_members(
    team_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """List org members who are not yet on this team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get all org members
    org_members = OrganizationMember.select().where(
        OrganizationMember.organization == team.organization
    )

    # Get existing team member user IDs
    team_member_ids = set(
        tm.user.id for tm in TeamMember.select().where(TeamMember.team == team)
    )

    # Filter out users already on the team
    available = []
    for om in org_members:
        if om.user.id not in team_member_ids:
            available.append(
                {
                    "id": om.user.id,
                    "user_id": om.user.id,
                    "username": om.user.username,
                }
            )

    return available


@api.post("/admin/teams/{team_id}/members", response_model=dict)
async def add_admin_team_member(
    team_id: int,
    request: UsernameRequest,
    current_admin_user: User = Depends(get_current_admin),
):
    """Add a member to a team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    user = User.get_or_none(User.username == request.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Deliberately no organization-membership requirement. A team is the unit
    # of authorization -- it is what can_access_board actually checks -- and a
    # team is allowed to span organizations, so that a contractor or a partner
    # can be put on one project's team without being given the run of the org.
    # Organizations group people and carry invites; teams grant access.

    # Check if already a team member
    existing = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == user)
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already in this team")

    team_member = TeamMember.create(
        user=user, team=team, joined_at=datetime.now(timezone.utc)
    )
    return {
        "id": team_member.id,
        "user_id": user.id,
        "username": user.username,
        "joined_at": team_member.joined_at,
    }


@api.delete("/admin/teams/{team_id}/members/{user_id}")
async def remove_admin_team_member(
    team_id: int,
    user_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """Remove a member from a team (admin only)"""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    target = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user_id == user_id)
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    target.delete_instance()
    return {"ok": True}


# Admin board management endpoints
@api.get("/admin/boards", response_model=list)
async def list_admin_boards(
    response: Response,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[int] = Query(None, ge=0, description="X-Next-Cursor of the previous page"),
    current_admin_user: User = Depends(get_current_admin),
):
    """List boards (admin only), paged -- see paginate()"""
    boards = paginate(Board.select(), Board.id, response, limit, cursor)
    result = []
    for board in boards:
        column_count = Column.select().where(Column.board == board).count()
        card_count = Card.select().join(Column).where(Column.board == board).count()
        shared_team_name = board.shared_team.name if board.shared_team else None

        result.append(
            {
                "id": board.id,
                "name": board.name,
                "owner_id": board.owner_id,
                "owner_username": board.owner.username,
                "shared_team_id": board.shared_team_id,
                "shared_team_name": shared_team_name,
                "is_public_to_org": board.is_public_to_org,
                "organization_id": board.organization_id,
                "column_count": column_count,
                "card_count": card_count,
                "created_at": board.created_at,
            }
        )
    return result


@api.post("/admin/boards", response_model=BoardResponseAdmin)
async def create_admin_board(
    board_data: BoardCreateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Create a board (admin only)"""
    owner = User.get_or_none(User.id == board_data.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")

    board = Board.create_with_columns(
        owner=owner, name=board_data.name
    )

    column_count = Column.select().where(Column.board == board).count()
    card_count = Card.select().join(Column).where(Column.board == board).count()

    return {
        "id": board.id,
        "name": board.name,
        "owner_id": board.owner_id,
        "owner_username": board.owner.username,
        "shared_team_id": board.shared_team_id,
        "shared_team_name": None,
        "is_public_to_org": board.is_public_to_org,
        "organization_id": board.organization_id,
        "column_count": column_count,
        "card_count": card_count,
        "created_at": board.created_at,
    }


@api.put("/admin/boards/{board_id}", response_model=BoardResponseAdmin)
async def update_admin_board(
    board_id: int,
    board_data: BoardUpdateAdmin,
    current_admin_user: User = Depends(get_current_admin),
):
    """Update a board (admin only)"""
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    board.name = board_data.name
    board.save()

    column_count = Column.select().where(Column.board == board).count()
    card_count = Card.select().join(Column).where(Column.board == board).count()
    shared_team_name = board.shared_team.name if board.shared_team else None

    return {
        "id": board.id,
        "name": board.name,
        "owner_id": board.owner_id,
        "owner_username": board.owner.username,
        "shared_team_id": board.shared_team_id,
        "shared_team_name": shared_team_name,
        "is_public_to_org": board.is_public_to_org,
        "organization_id": board.organization_id,
        "column_count": column_count,
        "card_count": card_count,
        "created_at": board.created_at,
    }


@api.delete("/admin/boards/{board_id}")
async def delete_admin_board(
    board_id: int,
    current_admin_user: User = Depends(get_current_admin),
):
    """Delete a board (admin only)"""
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    with db.atomic():
        # Delete cards, columns, board
        for column in board.columns:
            Card.delete().where(Card.column == column).execute()
            column.delete_instance()
        board.delete_instance()

    return {"ok": True}


@api.post("/boards", response_model=dict)
async def create_board(
    board_data: BoardCreate, current_user: User = Depends(get_current_user_or_api_key)
):
    check_can_create_board(current_user)
    with db.atomic():
        board = Board.create_with_columns(
            owner=current_user, name=board_data.name
        )
    return {
        "id": board.id,
        "name": board.name,
        "created_at": board.created_at,
        "shared_team_id": board.shared_team_id,
        "owner_id": board.owner_id,
    }


@api.post("/billing/checkout")
async def billing_checkout(current_user: User = Depends(get_current_user)):
    """Start a Pro subscription; returns the Stripe Checkout URL to send the
    user to. Session-only (no API key): this is a payment flow."""
    if current_user.is_pro:
        raise HTTPException(
            status_code=409,
            detail="You are already on Pro. Manage your subscription from Settings > Plan.",
        )
    try:
        url = stripe_billing.create_checkout_url(current_user)
    except stripe_billing.StripeNotConfigured:
        raise HTTPException(status_code=503, detail="Payments are not set up on this server.")
    except stripe.StripeError:
        logger.exception("Stripe checkout failed for user %s", current_user.id)
        raise HTTPException(
            status_code=502, detail="Could not reach the payment provider. Try again shortly."
        )
    return {"url": url}


@api.post("/billing/portal")
async def billing_portal(current_user: User = Depends(get_current_user)):
    """The Stripe Customer Portal, for changing the card or cancelling.
    Session-only: it can end the subscription."""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=409, detail="There is no billing account to manage yet.")
    try:
        url = stripe_billing.create_portal_url(current_user)
    except stripe_billing.StripeNotConfigured:
        raise HTTPException(status_code=503, detail="Payments are not set up on this server.")
    except stripe.StripeError:
        logger.exception("Stripe portal failed for user %s", current_user.id)
        raise HTTPException(
            status_code=502, detail="Could not reach the payment provider. Try again shortly."
        )
    return {"url": url}


@api.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe's event feed -- the only thing that changes User.plan.

    Unauthenticated by design; the signature is the authentication. A request
    without a valid one is refused, and so is every request if we have no
    secret to check it against: failing open here would let anyone POST
    themselves onto the Pro plan.
    """
    payload = await request.body()
    try:
        event = stripe_billing.construct_event(payload, request.headers.get("stripe-signature"))
    except stripe_billing.StripeNotConfigured:
        raise HTTPException(status_code=503, detail="Webhook is not configured.")
    except stripe_billing.BadWebhook:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    try:
        result = stripe_billing.handle_event(event)
    except stripe.StripeError:
        # Non-2xx, so Stripe redelivers once it can be reached again.
        logger.exception("Stripe webhook %s could not be applied", event.get("id"))
        raise HTTPException(status_code=502, detail="Could not reach Stripe.")
    return {"received": True, "result": result}


@api.post("/me/password")
async def change_my_password(
    change: PasswordChange, current_user: User = Depends(get_current_user)
):
    """Change your own password. Session-only: an API key must not be able to
    take over the account it belongs to, so the current password is required."""
    from bcrypt import hashpw, gensalt
    from backend.models import PASSWORD_MAX_LENGTH

    if not current_user.verify_password(change.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if not change.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be empty")
    if len(change.new_password) > PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be {PASSWORD_MAX_LENGTH} characters or fewer",
        )
    current_user.password_hash = hashpw(
        change.new_password.encode("utf-8"), gensalt()
    ).decode("utf-8")
    current_user.save()
    return {"ok": True}


@api.get("/me/usage")
async def get_my_usage(current_user: User = Depends(get_current_user_or_api_key)):
    """The caller's plan, what it allows, and how much of it they are using."""
    return usage_for(current_user)


@api.get("/boards", response_model=list)
async def list_boards(
    response: Response,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[int] = Query(None, ge=0, description="X-Next-Cursor of the previous page"),
    current_user: User = Depends(get_current_user_or_api_key),
):
    boards = paginate(accessible_boards(current_user), Board.id, response, limit, cursor)
    return [
        {
            "id": board.id,
            "name": board.name,
            "created_at": board.created_at,
            "shared_team_id": board.shared_team_id,
            "is_public_to_org": board.is_public_to_org,
            "organization_id": board.organization_id,
            "owner_id": board.owner_id,
        }
        for board in boards
    ]


@api.post("/boards/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int,
    board_data: BoardUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if not can_modify_board(current_user, board):
        raise HTTPException(status_code=403, detail="Not authorized")
    board.name = board_data.name
    board.save()
    columns = [
        {"id": c.id, "name": c.name, "position": c.position} for c in board.columns
    ]
    return {
        "id": board.id,
        "name": board.name,
        "created_at": board.created_at,
        "columns": columns,
        "shared_team_id": board.shared_team_id,
        "is_public_to_org": board.is_public_to_org,
        "organization_id": board.organization_id,
        "owner_id": board.owner_id,
    }


@api.get("/boards/{board_id}", response_model=BoardResponse)
async def get_board(
    board_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if not can_access_board(current_user, board):
        raise HTTPException(status_code=403, detail="Not authorized")
    columns = []
    # Get columns sorted by position
    for column in board.columns.order_by(Column.position):
        cards = []
        # Get cards sorted by position
        for card in column.cards.order_by(Card.position):
            # Get comments for this card
            comments = (
                Comment.select()
                .where(Comment.card == card)
                .order_by(Comment.created_at)
            )
            card_comments = [
                {
                    "id": comment.id,
                    "card_id": comment.card.id,
                    "user_id": comment.user.id,
                    "username": comment.user.username,
                    "content": comment.content,
                    "created_at": comment.created_at,
                    "updated_at": comment.updated_at,
                }
                for comment in comments
            ]
            cards.append(
                {
                    "id": card.id,
                    "title": card.title,
                    "description": card.description,
                    "position": card.position,
                    "comments": card_comments,
                }
            )
        columns.append(
            {
                "id": column.id,
                "name": column.name,
                "position": column.position,
                "cards": cards,
            }
        )
    return {
        "id": board.id,
        "name": board.name,
        "created_at": board.created_at,
        "columns": columns,
        "shared_team_id": board.shared_team_id,
        "is_public_to_org": board.is_public_to_org,
        "organization_id": board.organization_id,
        "owner_id": board.owner_id,
    }


@api.delete("/boards/{board_id}")
async def delete_board(
    board_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if not can_delete_board(current_user, board):
        raise HTTPException(status_code=403, detail="Only the owner can delete a board")
    with db.atomic():
        for column in board.columns:
            for card in column.cards:
                card.delete_instance()
            column.delete_instance()
        board.delete_instance()
    return {"ok": True}


@api.post("/boards/{board_id}/share")
async def share_board(
    board_id: int,
    share_data: BoardShare,
    current_user: User = Depends(get_current_user_or_api_key),
):
    board = Board.get_or_none(Board.id == board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if not can_share_board(current_user, board):
        raise HTTPException(status_code=403, detail="Only the owner can share a board")

    # Set public to org status
    if share_data.is_public_to_org is not None:
        board.is_public_to_org = share_data.is_public_to_org

    # A board is not owned by an organization, it is shared into one, so the
    # org is resolved at the moment it goes public rather than at creation.
    if board.is_public_to_org:
        board.organization = _resolve_share_organization(
            current_user, share_data.organization_id
        )

    # Set shared team (only if not public to org)
    if not board.is_public_to_org and share_data.team_id is not None:
        team = Team.get_or_none(Team.id == share_data.team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        board.shared_team = team
    elif not board.is_public_to_org and share_data.team_id is None:
        board.shared_team = None

    board.save()
    return {
        "ok": True,
        "shared_team_id": board.shared_team_id,
        "is_public_to_org": board.is_public_to_org,
        "organization_id": board.organization_id,
    }


@api.post("/columns", response_model=ColumnResponse)
async def create_column(
    column_data: ColumnCreate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    board = Board.get_or_none(Board.id == column_data.board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if not can_modify_board(current_user, board):
        raise HTTPException(status_code=403, detail="Not authorized")
    position = column_data.position
    if position is None:
        last = (
            Column.select(fn.MAX(Column.position))
            .where(Column.board == board)
            .scalar()
        )
        position = 0 if last is None else last + 1
    column = Column.create(
        board=board,
        name=column_data.name,
        position=position,
    )
    return {
        "id": column.id,
        "name": column.name,
        "position": column.position,
        "cards": [],
    }


@api.put("/columns/{column_id}", response_model=ColumnResponse)
async def update_column(
    column_id: int,
    column_data: ColumnUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    column = Column.get_or_none(Column.id == column_id)
    if not column:
        raise HTTPException(status_code=404, detail="Column not found")
    if not can_modify_board(current_user, column.board):
        raise HTTPException(status_code=403, detail="Not authorized")
    column.name = column_data.name
    column.position = column_data.position
    column.save()
    cards = [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "position": c.position,
        }
        for c in column.cards
    ]
    return {
        "id": column.id,
        "name": column.name,
        "position": column.position,
        "cards": cards,
    }


@api.delete("/columns/{column_id}")
async def delete_column(
    column_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    column = Column.get_or_none(Column.id == column_id)
    if not column:
        raise HTTPException(status_code=404, detail="Column not found")
    if not can_modify_board(current_user, column.board):
        raise HTTPException(status_code=403, detail="Not authorized")
    with db.atomic():
        for card in column.cards:
            card.delete_instance()
        column.delete_instance()
    return {"ok": True}


@api.post("/columns/reorder")
async def reorder_columns(
    reorder_data: ColumnReorderRequest,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Reorder multiple columns by updating their positions."""
    # Verify all columns belong to boards the user can modify
    for item in reorder_data.columns:
        column = Column.get_or_none(Column.id == item.id)
        if not column:
            raise HTTPException(status_code=404, detail=f"Column {item.id} not found")
        if not can_modify_board(current_user, column.board):
            raise HTTPException(status_code=403, detail="Not authorized")

    # Update all column positions in a single transaction
    with db.atomic():
        for item in reorder_data.columns:
            Column.update(position=item.position).where(Column.id == item.id).execute()

    return {"ok": True}


@api.post("/cards", response_model=CardResponse)
async def create_card(
    card_data: CardCreate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    column = Column.get_or_none(Column.id == card_data.column_id)
    if not column:
        raise HTTPException(status_code=404, detail="Column not found")
    if not can_modify_board(current_user, column.board):
        raise HTTPException(status_code=403, detail="Not authorized")
    check_can_add_card(column.board)
    card = Card.create(
        column=column,
        title=card_data.title,
        description=card_data.description,
        position=card_data.position,
    )
    return {
        "id": card.id,
        "title": card.title,
        "description": card.description,
        "position": card.position,
    }


@api.get("/cards/{card_id}", response_model=CardDetailResponse)
async def get_card(
    card_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    """Read one card. Cards were previously only reachable nested inside a
    board, so anything holding a card id had no way to see its body."""
    card = Card.get_or_none(Card.id == card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if not can_access_board(current_user, card.column.board):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this card"
        )

    comments = Comment.select().where(Comment.card == card).order_by(Comment.created_at)
    return {
        "id": card.id,
        "title": card.title,
        "description": card.description,
        "position": card.position,
        "column_id": card.column.id,
        "column_name": card.column.name,
        "board_id": card.column.board.id,
        "board_name": card.column.board.name,
        "comments": [
            {
                "id": comment.id,
                "card_id": comment.card.id,
                "user_id": comment.user.id,
                "username": comment.user.username,
                "content": comment.content,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
            }
            for comment in comments
        ],
    }


@api.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: int,
    card_data: CardUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    card = Card.get_or_none(Card.id == card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if not can_modify_board(current_user, card.column.board):
        raise HTTPException(status_code=403, detail="Not authorized")
    if card_data.column_id is not None and card_data.column_id != card.column.id:
        new_column = Column.get_or_none(Column.id == card_data.column_id)
        if not new_column:
            raise HTTPException(status_code=404, detail="New column not found")
        if not can_modify_board(current_user, new_column.board):
            raise HTTPException(status_code=403, detail="Not authorized")
        # Moving to another board adds a card there, so it counts against that
        # board's cap; a move within one board changes nothing.
        if new_column.board.id != card.column.board.id:
            check_can_add_card(new_column.board)
        card.column = new_column
    if card_data.title is not None:
        card.title = card_data.title
    if card_data.description is not None:
        card.description = card_data.description
    if card_data.position is not None:
        card.position = card_data.position
    card.save()
    return {
        "id": card.id,
        "title": card.title,
        "description": card.description,
        "position": card.position,
    }


@api.delete("/cards/{card_id}")
async def delete_card(
    card_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    card = Card.get_or_none(Card.id == card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if not can_modify_board(current_user, card.column.board):
        raise HTTPException(status_code=403, detail="Not authorized")
    card.delete_instance()
    return {"ok": True}


@api.post("/cards/reorder")
async def reorder_cards(
    reorder_data: CardReorderRequest,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Reorder multiple cards by updating their positions."""
    # Verify all cards belong to boards the user can modify
    for item in reorder_data.cards:
        card = Card.get_or_none(Card.id == item.id)
        if not card:
            raise HTTPException(status_code=404, detail=f"Card {item.id} not found")
        if not can_modify_board(current_user, card.column.board):
            raise HTTPException(status_code=403, detail="Not authorized")

    # Update all card positions in a single transaction
    with db.atomic():
        for item in reorder_data.cards:
            Card.update(position=item.position).where(Card.id == item.id).execute()

    return {"ok": True}


@api.get("/search", response_model=list[SearchResult])
async def search(
    q: str = Query(..., max_length=500, description="What to look for"),
    board_id: Optional[int] = Query(None, description="Search only this board"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Cards whose title or description matches `q`, best first, across every
    board the caller can open.

    Words are stemmed and ANDed, and the last one also matches as a prefix.
    A query that is just a card id ("474" or "#474") puts that card first.
    """
    boards = accessible_boards(current_user)
    if board_id is not None:
        board = Board.get_or_none(Board.id == board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        if not can_access_board(current_user, board):
            raise HTTPException(status_code=403, detail="Not authorized")
        boards = boards.where(Board.id == board_id)
    return search_cards(q, boards, limit)


# Comment endpoints
@api.post("/comments", response_model=CommentResponse)
async def create_comment(
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    # Get the card and verify access
    card = Card.get_or_none(Card.id == comment_data.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if user can access the board containing this card
    if not can_access_board(current_user, card.column.board):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this card"
        )

    # Create the comment
    comment = Comment.create_comment(
        card=card, user=current_user, content=comment_data.content
    )

    # Return comment with username
    return CommentResponse(
        id=comment.id,
        card_id=comment.card.id,
        user_id=comment.user.id,
        username=comment.user.username,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@api.get("/cards/{card_id}/comments", response_model=list[CommentResponse])
async def get_card_comments(
    card_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    # Get the card and verify access
    card = Card.get_or_none(Card.id == card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if user can access the board containing this card
    if not can_access_board(current_user, card.column.board):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this card"
        )

    # Get comments ordered by creation time
    comments = Comment.select().where(Comment.card == card).order_by(Comment.created_at)

    return [
        CommentResponse(
            id=comment.id,
            card_id=comment.card.id,
            user_id=comment.user.id,
            username=comment.user.username,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
        for comment in comments
    ]


@api.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    comment = Comment.get_or_none(Comment.id == comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only the comment author can update their comment
    if comment.user != current_user:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this comment"
        )

    # Update the comment
    comment.content = comment_data.content
    comment.updated_at = datetime.now(timezone.utc)
    comment.save()

    return CommentResponse(
        id=comment.id,
        card_id=comment.card.id,
        user_id=comment.user.id,
        username=comment.user.username,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@api.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    comment = Comment.get_or_none(Comment.id == comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only the comment author can delete their comment
    if comment.user != current_user:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this comment"
        )

    comment.delete_instance()
    return {"ok": True}


@api.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    base_slug = slugify(org_data.name)
    slug = base_slug
    counter = 1
    while Organization.get_or_none(Organization.slug == slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    with db.atomic():
        org = Organization.create_with_columns(
            name=org_data.name, slug=slug, owner=current_user
        )
        OrganizationMember.create(
            user=current_user, organization=org, joined_at=datetime.now(timezone.utc)
        )
        Team.create_with_columns(name="Administrators", organization=org)

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "created_at": org.created_at,
    }


@api.get("/organizations", response_model=list)
async def list_organizations(current_user: User = Depends(get_current_user_or_api_key)):
    orgs = get_user_organizations(current_user)
    return [
        {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "owner_id": org.owner_id,
            "created_at": org.created_at,
        }
        for org in orgs
    ]


@api.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "created_at": org.created_at,
    }


@api.put("/organizations/{org_id}")
async def update_organization(
    org_id: int,
    org_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # Only the owner (root) can update the organization
    if org.owner != current_user:
        raise HTTPException(
            status_code=403, detail="Only the owner can update the organization"
        )
    org.name = org_data.name
    org.save()
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "created_at": org.created_at,
    }


@api.post("/organizations/{org_id}/members", response_model=OrganizationMemberResponse)
async def add_organization_member(
    org_id: int,
    request: UsernameRequest,
    current_user: User = Depends(get_current_user_or_api_key),
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Only the owner (root) can add members
    if org.owner != current_user:
        raise HTTPException(status_code=403, detail="Only the owner can add members")

    user = User.get_or_none(User.username == request.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org) & (OrganizationMember.user == user)
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    org_member = OrganizationMember.create(
        user=user, organization=org, joined_at=datetime.now(timezone.utc)
    )
    return {
        "id": org_member.id,
        "user_id": user.id,
        "username": user.username,
        "joined_at": org_member.joined_at,
    }


@api.get("/organizations/{org_id}/members", response_model=list)
async def list_organization_members(
    org_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    members = OrganizationMember.select().where(OrganizationMember.organization == org)
    return [
        {
            "id": m.id,
            "user_id": m.user.id,
            "username": m.user.username,
            "joined_at": m.joined_at,
        }
        for m in members
    ]


@api.delete("/organizations/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_or_api_key),
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")

    target = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user_id == user_id)
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot remove the owner (root)
    if org.owner_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the owner")

    is_self = user_id == current_user.id
    is_owner = org.owner == current_user

    if not is_self and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized")

    with db.atomic():
        # Only this org's teams. The predicate used to be TeamMember.user alone,
        # which never ran -- and would have dropped the user out of every team
        # in every other organization had it ever been executed.
        #
        # Teams may include people from outside the org, but removing someone
        # from the org still takes them off its teams: otherwise the removal
        # would revoke nothing they could actually reach. Genuine outsiders,
        # who were never org members, are untouched -- there is no
        # OrganizationMember row to remove them by.
        org_team_ids = Team.select(Team.id).where(Team.organization == org)
        TeamMember.delete().where(
            (TeamMember.user_id == user_id) & (TeamMember.team.in_(org_team_ids))
        ).execute()
        target.delete_instance()

    return {"ok": True}


# === Organization Invite Endpoints ===


class InviteCreateRequest(BaseModel):
    email: Optional[str] = None


class TeamInviteCreateRequest(BaseModel):
    # Required, unlike an organization invite's optional email. An anonymous
    # team invite would be a bearer link granting write access to whatever
    # boards the team holds; the org-level anonymous link still exists for
    # people who want that trade.
    email: str


class InviteResponse(BaseModel):
    id: int
    email: Optional[str]
    token: str
    status: str
    created_at: datetime
    expires_at: datetime
    created_by_username: str


@api.post("/organizations/{org_id}/invites", response_model=InviteResponse)
async def create_organization_invite(
    org_id: int,
    request: InviteCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Create an invite token for an organization. Owner only."""
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Only owner can create invites
    if org.owner != current_user:
        raise HTTPException(status_code=403, detail="Only the owner can create invites")

    # One live token per address. Nothing used to stop the same person being
    # invited ten times, and since each invite carries its own token, revoking
    # the one visible in the UI left the other nine working -- revocation did
    # not actually revoke.
    if request.email:
        already = User.get_or_none(fn.LOWER(User.email) == request.email.strip().lower())
        if already is not None and (
            is_org_member(already, org) or org.owner_id == already.id
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{request.email} is already a member of this organization",
            )

        OrganizationInvite.update(status="revoked").where(
            (OrganizationInvite.organization == org)
            & (OrganizationInvite.status == "pending")
            & (fn.LOWER(OrganizationInvite.email) == request.email.strip().lower())
        ).execute()

    invite, token = OrganizationInvite.create_invite(
        organization=org,
        created_by=current_user,
        email=request.email,
    )

    # An anonymous invite has nowhere to go -- the owner passes the token along
    # themselves, which is how this worked before there was a mailer.
    if invite.email:
        background_tasks.add_task(
            send_invite_email, invite.email, token, org.name, current_user.username
        )

    return {
        "id": invite.id,
        "email": invite.email,
        "token": token,
        "status": invite.status,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
        "created_by_username": current_user.username,
    }


@api.get("/organizations/{org_id}/invites", response_model=list)
async def list_organization_invites(
    org_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    """List all pending invites for an organization."""
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Any member OR owner can see invites
    is_owner = org.owner == current_user
    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member and not is_owner:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # Team invites live in this table too but are not org invites: accepting
    # one grants the team alone. Listing them here would show an org invite
    # that never arrives, on a page whose owner cannot revoke it either.
    invites = OrganizationInvite.select().where(
        (OrganizationInvite.organization == org)
        & (OrganizationInvite.team.is_null(True))
        & (OrganizationInvite.status == "pending")
    )
    # Expiry is only ever evaluated when a token is read, so an expired invite
    # sits in the table still marked pending. Filter here rather than listing
    # dead invites as live ones.
    invites = [invite for invite in invites if not invite.is_expired()]

    def format_datetime(dt):
        if isinstance(dt, str):
            return dt
        return dt.isoformat()

    return [
        {
            "id": invite.id,
            "email": invite.email,
            # Owner only. Any member could otherwise lift the token of an
            # invite addressed to someone else and hand it to an outsider,
            # which routes straight around "only the owner can create
            # invites". Members still see that an invite exists and to whom.
            **({"token": invite.token} if is_owner else {}),
            "status": invite.status,
            "created_at": format_datetime(invite.created_at),
            "expires_at": format_datetime(invite.expires_at),
            "created_by_username": invite.created_by.username,
        }
        for invite in invites
    ]


@api.delete("/organizations/{org_id}/invites/{invite_id}")
async def revoke_organization_invite(
    org_id: int,
    invite_id: int,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Revoke a pending invite."""
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Only owner can revoke invites
    if org.owner != current_user:
        raise HTTPException(status_code=403, detail="Only the owner can revoke invites")

    invite = OrganizationInvite.get_or_none(
        (OrganizationInvite.id == invite_id) & (OrganizationInvite.organization == org)
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    invite.revoke()
    return {"ok": True}


@api.get("/invites/{token}")
async def get_invite(token: str):
    """Get invite details (for landing page)."""
    invite = OrganizationInvite.get_or_none(
        (OrganizationInvite.token == token) & (OrganizationInvite.status == "pending")
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")

    if invite.is_expired():
        invite.status = "expired"
        invite.save()
        raise HTTPException(status_code=404, detail="Invite has expired")

    return {
        "id": invite.id,
        "organization_name": invite.organization.name,
        "team_name": invite.team.name if invite.team else None,
        "email": invite.email,
        "status": invite.status,
        "created_by_username": invite.created_by.username,
    }


@api.post("/invites/{token}/accept")
async def accept_invite(
    token: str,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Accept an invite and join the organization."""
    invite = OrganizationInvite.get_or_none(
        (OrganizationInvite.token == token) & (OrganizationInvite.status == "pending")
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")

    if invite.is_expired():
        invite.status = "expired"
        invite.save()
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Which membership already exists depends on which one this invite grants.
    # Checking org membership for a team invite would turn "you are on this
    # org already" into a refusal to join a team the org member is not on.
    if invite.team is not None:
        if TeamMember.get_or_none(
            (TeamMember.team == invite.team) & (TeamMember.user == current_user)
        ):
            raise HTTPException(
                status_code=400, detail="You are already in this team"
            )
    elif OrganizationMember.get_or_none(
        (OrganizationMember.organization == invite.organization)
        & (OrganizationMember.user == current_user)
    ):
        raise HTTPException(
            status_code=400, detail="You are already a member of this organization"
        )

    # An invite sent to a specific address is for that person. Without this it
    # is a bearer token: a forwarded mail, a shared inbox or a mail archive is
    # enough for anyone to take the seat. Anonymous invites (email is null) are
    # deliberately bearer -- that is what they are for, and what the owner
    # should create when they want a link they can pass around.
    if invite.email:
        invited = invite.email.strip().lower()
        held = (current_user.email or "").strip().lower()
        if held != invited:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This invitation was sent to {invite.email}. Sign in with "
                    "that address, or ask for an invitation to the one you use."
                ),
            )

    invite.accept(current_user)
    return {
        "ok": True,
        "organization_id": invite.organization.id,
        "organization_name": invite.organization.name,
        # Null for an org invite. The client needs this to know where to send
        # someone: a team-only member has no access to the organization page.
        "team_id": invite.team_id,
        "team_name": invite.team.name if invite.team else None,
    }


@api.post("/organizations/{org_id}/teams", response_model=TeamResponse)
async def create_team(
    org_id: int,
    team_data: TeamCreate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # The creator joins the team they just made. Without this the team is born
    # empty, and add_team_member's "must already be a member" check then locks
    # everyone out of it permanently -- including the org owner.
    with db.atomic():
        team = Team.create_with_columns(name=team_data.name, organization=org)
        TeamMember.create(
            user=current_user, team=team, joined_at=datetime.now(timezone.utc)
        )
    return {
        "id": team.id,
        "name": team.name,
        "organization_id": org.id,
        "created_at": team.created_at,
    }


@api.get("/organizations/{org_id}/teams", response_model=list)
async def list_organization_teams(
    org_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    org = Organization.get_or_none(Organization.id == org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = OrganizationMember.get_or_none(
        (OrganizationMember.organization == org)
        & (OrganizationMember.user == current_user)
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    teams = Team.select().where(Team.organization == org)
    return [
        {
            "id": team.id,
            "name": team.name,
            "organization_id": org.id,
            "created_at": team.created_at,
        }
        for team in teams
    ]


@api.put("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    team_data: TeamUpdate,
    current_user: User = Depends(get_current_user_or_api_key),
):
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Any team member can update team (Unix group model)
    tm = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == current_user)
    )
    if not tm:
        raise HTTPException(status_code=403, detail="Not authorized to update team")

    team.name = team_data.name
    team.save()
    return {
        "id": team.id,
        "name": team.name,
        "organization_id": team.organization_id,
        "created_at": team.created_at,
    }


@api.delete("/teams/{team_id}")
async def delete_team(
    team_id: int,
    current_user: User = Depends(get_current_user_or_api_key),
):
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Only the organization owner (root) can delete teams
    if team.organization.owner != current_user:
        raise HTTPException(status_code=403, detail="Not authorized")

    with db.atomic():
        Board.update(shared_team=None).where(Board.shared_team == team).execute()
        TeamMember.delete().where(TeamMember.team == team).execute()
        team.delete_instance()

    return {"ok": True}


@api.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: int,
    request: UsernameRequest,
    current_user: User = Depends(get_current_user_or_api_key),
):
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Any team member can add other org members (Unix group model). The org
    # owner is root here whether or not they are in the team -- otherwise a
    # team that lost its last member, or one auto-created with the org, could
    # never be refilled by anyone.
    tm = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == current_user)
    )
    if not tm and team.organization.owner != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to add members")

    user = User.get_or_none(User.username == request.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # No organization-membership requirement on the person being added: teams
    # may span organizations. See the admin endpoint above for why.
    #
    # This does mean any team member can hand board access to any account on
    # the server, which is the Unix group model the rest of this file follows
    # -- being in the group is what lets you add to the group. The org owner is
    # the backstop: they can remove anyone from any team in their org.

    existing = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == user)
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already in this team")

    team_member = TeamMember.create(
        user=user, team=team, joined_at=datetime.now(timezone.utc)
    )
    return {
        "id": team_member.id,
        "user_id": user.id,
        "username": user.username,
        "joined_at": team_member.joined_at,
    }


@api.get("/teams/{team_id}/members", response_model=list)
async def list_team_members(
    team_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Anyone in the org, plus anyone on the team. The second half matters now
    # that teams can span organizations: a member from outside the org could
    # not otherwise see the team they are actually on.
    is_org_member_of_team = (
        OrganizationMember.get_or_none(
            (OrganizationMember.organization == team.organization)
            & (OrganizationMember.user == current_user)
        )
        is not None
    )
    is_team_member = (
        TeamMember.get_or_none(
            (TeamMember.team == team) & (TeamMember.user == current_user)
        )
        is not None
    )
    if not is_org_member_of_team and not is_team_member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    members = TeamMember.select().where(TeamMember.team == team)
    return [
        {
            "id": m.id,
            "user_id": m.user.id,
            "username": m.user.username,
            "joined_at": m.joined_at,
        }
        for m in members
    ]


@api.delete("/teams/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_or_api_key),
):
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    is_owner = team.organization.owner == current_user
    tm = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == current_user)
    )
    if not tm and not is_owner:
        raise HTTPException(status_code=403, detail="Not a team member")

    target = TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user_id == user_id)
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    # Members can only remove themselves; the org owner can remove anyone.
    # Without the owner case, an owner could add someone to a team and then
    # have no way to take them back out again.
    if user_id != current_user.id and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized")

    target.delete_instance()
    return {"ok": True}


def _team_invite_authority(team, user):
    """Whoever may add a member by username may also invite one by email.

    Team membership is the grant here, the Unix group model the rest of this
    file follows -- being in the group is what lets you add to the group. The
    org owner is the backstop, as in add_team_member, so a team that has lost
    its last member can still be refilled.
    """
    if TeamMember.get_or_none((TeamMember.team == team) & (TeamMember.user == user)):
        return True
    return team.organization.owner_id == user.id


@api.post("/teams/{team_id}/invites", response_model=InviteResponse)
async def create_team_invite(
    team_id: int,
    request: TeamInviteCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Invite someone to a team by email, account or no account."""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not _team_invite_authority(team, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to invite")

    email = request.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="An email address is required")

    already = User.get_or_none(fn.LOWER(User.email) == email.lower())
    if already is not None and TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == already)
    ):
        raise HTTPException(
            status_code=400, detail=f"{email} is already in this team"
        )

    # One live token per address per team, for the reason the org endpoint
    # gives: every invite carries its own token, so leaving the older ones
    # pending makes revoking the visible one do nothing.
    OrganizationInvite.update(status="revoked").where(
        (OrganizationInvite.team == team)
        & (OrganizationInvite.status == "pending")
        & (fn.LOWER(OrganizationInvite.email) == email.lower())
    ).execute()

    invite, token = OrganizationInvite.create_invite(
        organization=team.organization,
        created_by=current_user,
        email=email,
        team=team,
    )
    background_tasks.add_task(
        send_invite_email,
        email,
        token,
        team.organization.name,
        current_user.username,
        team.name,
    )

    return {
        "id": invite.id,
        "email": invite.email,
        "token": token,
        "status": invite.status,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
        "created_by_username": current_user.username,
    }


@api.get("/teams/{team_id}/invites", response_model=list)
async def list_team_invites(
    team_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    """Pending invites for a team. Same audience that can create them."""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not _team_invite_authority(team, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    invites = OrganizationInvite.select().where(
        (OrganizationInvite.team == team)
        & (OrganizationInvite.status == "pending")
    )
    # Expiry is only evaluated when a token is read, so an expired invite sits
    # in the table still marked pending -- filter rather than list it as live.
    return [
        {
            "id": invite.id,
            "email": invite.email,
            "status": invite.status,
            "created_at": invite.created_at.isoformat()
            if not isinstance(invite.created_at, str)
            else invite.created_at,
            "expires_at": invite.expires_at.isoformat()
            if not isinstance(invite.expires_at, str)
            else invite.expires_at,
            "created_by_username": invite.created_by.username,
        }
        for invite in invites
        if not invite.is_expired()
    ]


@api.delete("/teams/{team_id}/invites/{invite_id}")
async def revoke_team_invite(
    team_id: int,
    invite_id: int,
    current_user: User = Depends(get_current_user_or_api_key),
):
    """Revoke a pending team invite."""
    team = Team.get_or_none(Team.id == team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not _team_invite_authority(team, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    invite = OrganizationInvite.get_or_none(
        (OrganizationInvite.id == invite_id) & (OrganizationInvite.team == team)
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    invite.revoke()
    return {"ok": True}


# Documentation routes for serving markdown files
@api.get("/docs.md", response_class=PlainTextResponse)
async def docs_markdown():
    """Serve main documentation as raw markdown"""
    docs_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "frontend", "content", "docs.md"
    )
    try:
        with open(docs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return "# Documentation Not Found\n\nThe documentation file could not be found."


@api.get("/docs/{section}.md", response_class=PlainTextResponse)
async def docs_section_markdown(section: str):
    """Serve specific documentation section as raw markdown"""
    # Validate section name to prevent directory traversal
    allowed_sections = ["quickstart", "reference", "workflows"]
    if section not in allowed_sections:
        return (
            "# Section Not Found\n\nThe requested documentation section does not exist."
        )

    docs_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "frontend",
        "content",
        f"{section}.md",
    )
    try:
        with open(docs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return f"# {section.title()} Documentation Not Found\n\nThe documentation section could not be found."


# Beta signup endpoint (public, no auth required)
@api.post("/beta-signup")
async def beta_signup(request: BetaSignupRequest):
    """Register interest for beta access"""
    if not re.match(EMAIL_PATTERN, request.email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Check if already signed up
    existing = BetaSignup.get_or_none(BetaSignup.email == request.email)
    if existing:
        return {"message": "You're already on the list! We'll be in touch."}

    # Create signup
    BetaSignup.create_signup(request.email)
    return {"message": "Thanks for signing up! We'll be in touch soon."}


# API Key management endpoints
@api.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(current_user: User = Depends(get_current_user_or_api_key)):
    """List all API keys for the current user"""
    keys = (
        ApiKey.select()
        .where(ApiKey.user == current_user)
        .order_by(ApiKey.created_at.desc())
    )
    return [
        {
            "id": key.id,
            "name": key.name,
            "prefix": key.prefix,
            "created_at": key.created_at,
            "last_used_at": key.last_used_at,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
        }
        for key in keys
    ]


@api.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    key_data: ApiKeyCreate, current_user: User = Depends(get_current_user_by_session)
):
    """Create a new API key. Returns the key only once - save it securely!"""
    api_key, raw_key = ApiKey.create_key(
        user=current_user, name=key_data.name, expires_at=key_data.expires_at
    )
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key,  # Only returned once!
        "prefix": api_key.prefix,
        "created_at": api_key.created_at,
    }


@api.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int, current_user: User = Depends(get_current_user_or_api_key)
):
    """Deactivate an API key"""
    key = ApiKey.get_or_none((ApiKey.id == key_id) & (ApiKey.user == current_user))
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key.deactivate()
    return {"ok": True, "message": "API key has been deactivated"}


@api.post("/api-keys/{key_id}/activate")
async def activate_api_key(
    key_id: int, current_user: User = Depends(get_current_user_by_session)
):
    """Reactivate a deactivated API key"""
    key = ApiKey.get_or_none((ApiKey.id == key_id) & (ApiKey.user == current_user))
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key.is_active = True
    key.save()
    return {"ok": True, "message": "API key has been activated"}


# Device login: `pkanban login` with no username. The CLI starts a login and
# gets a short code; the person approves it at /device in a browser where they
# are already signed in; the CLI's next poll receives a new API key. Nothing
# secret passes through the terminal, which is the point when the terminal
# belongs to an AI agent. Shaped after RFC 8628 (OAuth device authorization),
# without the OAuth.


class DeviceLoginStart(BaseModel):
    client_name: Optional[str] = None


class DeviceLoginPoll(BaseModel):
    device_code: str


def _device_login_view(login):
    return {
        "user_code": format_user_code(login.user_code),
        "client_name": login.client_name,
        "requester_ip": login.requester_ip,
        "created_at": login.created_at,
        "expires_at": login.expires_at,
        "status": "expired"
        if login.status == "pending" and login.is_expired()
        else login.status,
    }


def _device_poll_error(code, message, status_code=400):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code, content={"error": code, "detail": message}
    )


@api.post("/auth/device")
async def device_login_start(body: DeviceLoginStart, request: Request):
    """Start a device login. Unauthenticated: this is how you get authenticated."""
    client_name = (body.client_name or "").strip()[:60] or "pkanban CLI"
    requester_ip = request.client.host if request.client else None
    login, device_code = DeviceLogin.start(client_name, requester_ip)
    base = str(request.base_url).rstrip("/")
    user_code = format_user_code(login.user_code)
    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": f"{base}/device",
        "verification_uri_complete": f"{base}/device?code={user_code}",
        "expires_in": DEVICE_LOGIN_EXPIRY_MINUTES * 60,
        "interval": DEVICE_LOGIN_POLL_SECONDS,
    }


@api.post("/auth/device/token")
async def device_login_poll(body: DeviceLoginPoll):
    """The CLI's poll. 400 with an `error` code until the person decides.

    Approved logins are claimed exactly once: the API key is minted here, on
    the poll, so the raw key is never stored and a second poll gets nothing.
    """
    login = DeviceLogin.by_device_code(body.device_code)
    if login is None:
        return _device_poll_error("invalid_grant", "Unknown device code.")
    if login.status == "denied":
        return _device_poll_error("access_denied", "The login was denied.")
    if login.status == "claimed":
        return _device_poll_error("invalid_grant", "This login was already used.")
    if login.is_expired():
        return _device_poll_error(
            "expired_token", "The login expired before it was approved."
        )
    if login.status == "pending":
        return _device_poll_error(
            "authorization_pending", "Waiting for approval in the browser."
        )

    with db.atomic():
        # Claim by conditional update, so two polls racing on the same approval
        # cannot both mint a key.
        claimed = (
            DeviceLogin.update(status="claimed")
            .where((DeviceLogin.id == login.id) & (DeviceLogin.status == "approved"))
            .execute()
        )
        if not claimed:
            return _device_poll_error("invalid_grant", "This login was already used.")
        api_key, raw_key = ApiKey.create_key(
            user=login.user, name=f"pkanban login: {login.client_name}"[:100]
        )
        DeviceLogin.update(api_key=api_key).where(DeviceLogin.id == login.id).execute()

    return {
        "api_key": raw_key,
        "api_key_id": api_key.id,
        "api_key_name": api_key.name,
        "username": login.user.username,
    }


def _pending_device_login(user_code):
    login = DeviceLogin.by_user_code(user_code)
    if login is None:
        raise HTTPException(status_code=404, detail="No login with that code.")
    return login


@api.get("/auth/device/{user_code}")
async def device_login_get(
    user_code: str, current_user: User = Depends(get_current_user_by_session)
):
    """What the approval page shows before the person decides."""
    return _device_login_view(_pending_device_login(user_code))


def _decide_device_login(user_code, user, approve):
    login = _pending_device_login(user_code)
    if login.is_expired() and login.status == "pending":
        raise HTTPException(
            status_code=410,
            detail="This code has expired. Run pkanban login again for a new one.",
        )
    if login.status != "pending":
        raise HTTPException(status_code=409, detail="This code was already used.")
    updated = (
        DeviceLogin.update(
            status="approved" if approve else "denied",
            user=user if approve else None,
        )
        .where((DeviceLogin.id == login.id) & (DeviceLogin.status == "pending"))
        .execute()
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This code was already used.")
    return _device_login_view(DeviceLogin.get_by_id(login.id))


@api.post("/auth/device/{user_code}/approve")
async def device_login_approve(
    user_code: str, current_user: User = Depends(get_current_user_by_session)
):
    """Approve a login. Session only: an API key must not be able to make one."""
    return _decide_device_login(user_code, current_user, approve=True)


@api.post("/auth/device/{user_code}/deny")
async def device_login_deny(
    user_code: str, current_user: User = Depends(get_current_user_by_session)
):
    return _decide_device_login(user_code, current_user, approve=False)
