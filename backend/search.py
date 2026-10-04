"""Card search: FTS5 over titles and descriptions, scoped to boards.

The keyword half of what jobwolverine calls hybrid search, done server-side.
Wolverine ranks in the browser because its corpus is public and the same for
every visitor. Here every user sees a different set of boards, and the whole
corpus is a few thousand cards, so the server answers in well under a
millisecond and nothing has to be shipped. A semantic half (fastembed) can be
fused in later by rank; nothing here would change except the ordering.

The index itself, and the triggers that keep it current, are CardSearch in
backend/models.py.
"""

import re

from peewee import SQL, fn

from backend.models import Board, Card, CardSearch, Column

# A title hit counts ten times a description hit -- the same 10:1 jobwolverine
# settled on. A card is usually titled for what it is about, and a description
# mentions everything else in passing.
TITLE_WEIGHT = 10.0
DESCRIPTION_WEIGHT = 1.0

# Snippets mark matched words with STX/ETX rather than HTML. The text is user
# written, so a renderer has to escape it anyway; control characters cannot
# collide with markup in it, and the frontend splits on them and builds
# <mark> elements itself.
HIGHLIGHT_START = "\x02"
HIGHLIGHT_END = "\x03"
SNIPPET_TOKENS = 16

# Enough for anything typed. The bound is on query cost, not on usefulness:
# every term is another posting list to intersect.
MAX_TERMS = 16

_WORD = re.compile(r"\w+")
_CARD_ID = re.compile(r"\s*#?(\d+)\s*")


def match_expression(query):
    """Turn typed text into an FTS5 MATCH expression, or None if it has no words.

    Each word becomes a quoted string, so nothing typed is ever read as FTS5
    syntax. Unquoted, a stray `"`, a hyphen, `title:` or a bare NOT is either
    a syntax error (a 500) or an operator nobody meant. Quoted strings are
    ANDed, which is what a search box should do.

    The last word is also a prefix, so results keep up while someone is still
    typing it. Prefixes are matched against stems, which mostly helps ("arch"
    finds "archive") and occasionally does not: half a word can stem to
    something no whole word does. The next keystroke fixes that.

    Words are \\w runs, so "card_search" stays one string. The tokenizer then
    splits it at the underscore, and FTS5 matches the two as a phrase.
    """
    words = _WORD.findall(query)[:MAX_TERMS]
    if not words:
        return None
    phrases = [f'"{word}"' for word in words]
    phrases[-1] += "*"
    return " ".join(phrases)


def _result(card_id, title, snippet, column_id, column_name, board_id, board_name):
    return {
        "id": card_id,
        "title": title,
        "snippet": snippet,
        "column_id": column_id,
        "column_name": column_name,
        "board_id": board_id,
        "board_name": board_name,
    }


def _by_id(query, boards):
    """The card a query like "474" or "#474" names, if the caller can see it.

    Card ids are how cards get cited -- in commits, PRs and other cards -- so
    typing one should find that card, not cards that happen to contain the
    number. It goes first; the full-text hits follow.
    """
    found = _CARD_ID.fullmatch(query)
    if not found:
        return None
    card = (
        Card.select(Card, Column, Board)
        .join(Column)
        .join(Board)
        .where((Card.id == int(found.group(1))) & Board.id.in_(boards.select(Board.id)))
        .first()
    )
    if card is None:
        return None
    description = card.description or ""
    snippet = description[:160] + ("…" if len(description) > 160 else "")
    return _result(
        card.id,
        card.title,
        snippet or None,
        card.column.id,
        card.column.name,
        card.column.board.id,
        card.column.board.name,
    )


def search_cards(query, boards, limit):
    """Cards matching `query` on `boards`, best first.

    Args:
        query: what the user typed.
        boards: a Board query of what they may see -- accessible_boards() in
            backend/api.py, possibly narrowed to one board. Filtering on it here
            rather than after the fact keeps `limit` meaning "this many the
            caller can see", not "this many, minus the ones we then hide".
        limit: the most results to return.

    Returns:
        A list of dicts shaped like SearchResult in backend/api.py.
    """
    results = []
    pinned = _by_id(query, boards)
    if pinned is not None:
        results.append(pinned)

    expression = match_expression(query)
    if expression is None:
        return results

    score = fn.bm25(CardSearch._meta.entity, TITLE_WEIGHT, DESCRIPTION_WEIGHT)
    snippet = fn.snippet(
        CardSearch._meta.entity,
        1,  # the description; the title is returned whole
        HIGHLIGHT_START,
        HIGHLIGHT_END,
        "…",
        SNIPPET_TOKENS,
    )
    rows = (
        CardSearch.select(
            Card.id,
            Card.title,
            snippet.alias("snippet"),
            Column.id.alias("column_id"),
            Column.name.alias("column_name"),
            Board.id.alias("board_id"),
            Board.name.alias("board_name"),
            score.alias("score"),
        )
        .join(Card, on=(CardSearch.rowid == Card.id))
        .join(Column, on=(Card.column == Column.id))
        .join(Board, on=(Column.board == Board.id))
        .where(CardSearch.match(expression) & Board.id.in_(boards.select(Board.id)))
        # bm25() is negative, more so for a better match.
        .order_by(SQL("score"))
        .limit(limit)
        .tuples()
    )

    for card_id, title, text, column_id, column_name, board_id, board_name, _ in rows:
        if pinned is not None and card_id == pinned["id"]:
            continue
        results.append(
            _result(card_id, title, text, column_id, column_name, board_id, board_name)
        )

    return results[:limit]
