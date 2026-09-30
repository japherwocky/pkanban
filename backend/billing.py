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
