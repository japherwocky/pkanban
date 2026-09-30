"""Plan limits: what the free plan may own, and the 402 raised past it.

Everything here is behind BILLING_ENABLED, and the default is off. The repo is
MIT and public and people run their own copy; a self-hoster, the test suite and
local dev all see no limits at all until the switch is on. Nobody is charged by
this module -- it only refuses to create more.

The billing unit is the board OWNER. A user is limited in how many boards they
own, and a board's card cap follows the plan of the user who owns it, not the
plan of whoever is adding the card. Teams grant access (see can_access_board),
so a free user working on a Pro owner's board is unlimited there, and a Pro
user sharing a board never makes their collaborators pay.

Being over a limit never locks anything. Only creating a new board or card is
refused; reading, editing, moving within a board and deleting all keep working,
which is also what makes a downgrade safe.
"""

import os

from peewee import fn

from backend.models import Board, Card, Column

FREE_MAX_BOARDS = 5
# Counts every card on the board, Done included. Not an oversight: archiving is
# deliberately not a way around the cap, so heavy use is what Pro is for.
FREE_MAX_CARDS_PER_BOARD = 100


def billing_enabled():
    """Read per call, not at import, so the switch can be flipped in tests."""
    return os.environ.get("BILLING_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class PlanLimitExceeded(Exception):
    """A create was refused because the owner's plan has no room for it.

    main.py turns this into a 402 whose body a program can read:
    {"error": "plan_limit", "limit": ..., "max": ..., "current": ..., "detail": ...}
    """

    def __init__(self, limit, maximum, current, detail):
        super().__init__(detail)
        self.limit = limit
        self.maximum = maximum
        self.current = current
        self.detail = detail

    def body(self):
        return {
            "error": "plan_limit",
            "limit": self.limit,
            "max": self.maximum,
            "current": self.current,
            # The key existing clients already print, so an old CLI or web UI
            # says something useful instead of a bare "Request failed (402)".
            "detail": self.detail,
        }


def count_owned_boards(user):
    return Board.select().where(Board.owner == user).count()


def count_cards(board):
    return Card.select().join(Column).where(Column.board == board).count()


def check_can_create_board(user):
    """Raise PlanLimitExceeded if `user` may not own another board."""
    if not billing_enabled() or user.is_pro:
        return
    current = count_owned_boards(user)
    if current >= FREE_MAX_BOARDS:
        raise PlanLimitExceeded(
            "boards",
            FREE_MAX_BOARDS,
            current,
            f"The free plan allows {FREE_MAX_BOARDS} boards and you own {current}. "
            "Upgrade to Pro for unlimited boards.",
        )


def check_can_add_card(board):
    """Raise PlanLimitExceeded if `board` has no room for another card.

    Follows the board owner's plan. Callers moving a card within one board must
    not call this: the board's count does not change.
    """
    if not billing_enabled() or board.owner.is_pro:
        return
    current = count_cards(board)
    if current >= FREE_MAX_CARDS_PER_BOARD:
        raise PlanLimitExceeded(
            "cards_per_board",
            FREE_MAX_CARDS_PER_BOARD,
            current,
            f"This board is on the free plan, which allows "
            f"{FREE_MAX_CARDS_PER_BOARD} cards per board, and it has {current}. "
            "The board's owner can upgrade to Pro for unlimited cards.",
        )


def usage_for(user):
    """What `user` has and what their plan allows, for the web UI and the CLI.

    A `max` of None means unlimited: a Pro user, or any user while billing is
    off (the server is not enforcing limits, so there is no number to show).
    `boards` lists only boards the user OWNS -- those are the ones whose card
    cap follows their plan -- busiest first, so a client can warn about the
    ones nearing the cap without a request per board.
    """
    limited = billing_enabled() and not user.is_pro
    max_boards = FREE_MAX_BOARDS if limited else None
    max_cards = FREE_MAX_CARDS_PER_BOARD if limited else None

    owned = list(Board.select().where(Board.owner == user))
    counts = {
        board_id: n
        for board_id, n in Card.select(Column.board, fn.COUNT(Card.id))
        .join(Column)
        .where(Column.board.in_([b.id for b in owned]))
        .group_by(Column.board)
        .tuples()
    }
    boards = sorted(
        (
            {"id": b.id, "name": b.name, "cards": counts.get(b.id, 0)}
            for b in owned
        ),
        key=lambda b: (-b["cards"], b["id"]),
    )

    return {
        "plan": user.plan,
        "billing_enabled": billing_enabled(),
        "subscription_status": user.subscription_status,
        "current_period_end": user.current_period_end,
        "max_boards": max_boards,
        "max_cards_per_board": max_cards,
        "boards_owned": len(owned),
        "boards": boards,
    }
