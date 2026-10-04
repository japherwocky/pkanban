"""Card search: GET /api/search, the FTS5 index behind it, and its triggers.

Cards are written through the API wherever that is the path under test, since
the point of the triggers is that the index follows every write without the
endpoints having to remember it.
"""

import os
import sys
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from peewee import SqliteDatabase

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import create_access_token  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import (  # noqa: E402
    ALL_MODELS,
    Board,
    Card,
    CardSearch,
    Column,
    Organization,
    OrganizationMember,
    Team,
    TeamMember,
    User,
)
from backend.search import HIGHLIGHT_END, HIGHLIGHT_START, match_expression  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def headers(user):
    return {
        "Authorization": "Bearer "
        + create_access_token(data={"sub": user.id, "username": user.username})
    }


def make_board(owner, name="Board"):
    return Board.create_with_columns(owner=owner, name=name)


def first_column(board):
    return board.columns.order_by(Column.position).first()


def add_card(client, user, board, title, description=None):
    response = client.post(
        "/api/cards",
        json={
            "column_id": first_column(board).id,
            "title": title,
            "description": description,
            "position": 0,
        },
        headers=headers(user),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def search(client, user, q, **params):
    response = client.get(
        "/api/search", params={"q": q, **params}, headers=headers(user)
    )
    assert response.status_code == 200, response.json()
    return response.json()


def ids(results):
    return [r["id"] for r in results]


class TestMatching:
    def test_finds_title_and_description_words_by_stem(self, client, db_session):
        user = User.create_user("s_stem", "password")
        board = make_board(user)
        archiving = add_card(client, user, board, "Card archiving")
        limits = add_card(
            client, user, board, "Plan limits", "Archived cards still count."
        )
        add_card(client, user, board, "Unrelated", "Nothing to see")

        assert set(ids(search(client, user, "archived"))) == {
            archiving["id"],
            limits["id"],
        }

    def test_a_title_hit_outranks_a_description_hit(self, client, db_session):
        user = User.create_user("s_rank", "password")
        board = make_board(user)
        in_description = add_card(
            client, user, board, "Plan limits", "Mentions search once, in passing."
        )
        in_title = add_card(client, user, board, "Search the cards", "Body text.")

        assert ids(search(client, user, "search")) == [
            in_title["id"],
            in_description["id"],
        ]

    def test_words_are_anded(self, client, db_session):
        user = User.create_user("s_and", "password")
        board = make_board(user)
        both = add_card(client, user, board, "Deploy", "runs migrations first")
        add_card(client, user, board, "Deploy", "restarts the service")

        assert ids(search(client, user, "deploy migrations")) == [both["id"]]

    def test_the_last_word_matches_as_a_prefix(self, client, db_session):
        user = User.create_user("s_prefix", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Organization invites")

        assert ids(search(client, user, "organization inv")) == [card["id"]]
        # Only the last word: a prefix earlier in the query is a whole word.
        assert search(client, user, "inv organization") == []

    def test_punctuation_splits_words(self, client, db_session):
        user = User.create_user("s_punct", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Stack", "We use Python/Django and Postgres.")

        assert ids(search(client, user, "django")) == [card["id"]]
        assert ids(search(client, user, "postgres")) == [card["id"]]

    def test_snippet_marks_the_matched_words(self, client, db_session):
        user = User.create_user("s_snip", "password")
        board = make_board(user)
        add_card(client, user, board, "Card", "The webhook retries three times.")

        (result,) = search(client, user, "webhook")
        assert f"{HIGHLIGHT_START}webhook{HIGHLIGHT_END}" in result["snippet"]
        assert result["board_id"] == board.id
        assert result["board_name"] == board.name
        assert result["column_name"] == first_column(board).name

    def test_a_card_without_a_description_is_still_found(self, client, db_session):
        user = User.create_user("s_nodesc", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Lonely title")

        (result,) = search(client, user, "lonely")
        assert result["id"] == card["id"]
        assert result["snippet"] is None

    def test_limit(self, client, db_session):
        user = User.create_user("s_limit", "password")
        board = make_board(user)
        for n in range(5):
            add_card(client, user, board, f"Widget {n}")

        assert len(search(client, user, "widget", limit=3)) == 3


class TestQuerySyntaxIsNeverInterpreted:
    @pytest.mark.parametrize(
        "q",
        [
            '"',
            'unbalanced "quote',
            "title:secret",
            "NOT",
            "a AND OR NOT b",
            "-minus",
            "(paren",
            "star*",
            "NEAR(a b)",
            "^caret",
            "日本語",
        ],
    )
    def test_hostile_input_is_a_plain_search(self, client, db_session, q):
        user = User.create_user("s_syntax", "password")
        make_board(user)
        response = client.get("/api/search", params={"q": q}, headers=headers(user))
        assert response.status_code == 200, response.text

    def test_column_filter_syntax_matches_words_not_columns(self, client, db_session):
        user = User.create_user("s_colfilter", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Title", "the title was secret")

        # Read as FTS5 syntax, "title:secret" would search the title column
        # for "secret" and find nothing.
        assert ids(search(client, user, "title:secret")) == [card["id"]]

    @pytest.mark.parametrize("q", ["", "   ", "!!!", '""'])
    def test_no_words_is_no_results(self, client, db_session, q):
        user = User.create_user("s_empty", "password")
        board = make_board(user)
        add_card(client, user, board, "Anything")

        assert search(client, user, q) == []

    def test_match_expression_quotes_every_word(self):
        assert match_expression('fix "the" title:bug') == '"fix" "the" "title" "bug"*'
        assert match_expression("...") is None


class TestCardIds:
    def test_a_card_id_puts_that_card_first(self, client, db_session):
        user = User.create_user("s_id", "password")
        board = make_board(user)
        target = add_card(client, user, board, "The cited card")
        mentions = add_card(client, user, board, "Follow-up", f"See {target['id']}.")

        for q in (str(target["id"]), f"#{target['id']}"):
            results = search(client, user, q)
            assert ids(results)[0] == target["id"]
            # Cards that mention the number still follow, once each.
            assert ids(results).count(target["id"]) == 1
            assert mentions["id"] in ids(results)

    def test_a_card_id_on_someone_elses_board_is_not_found(self, client, db_session):
        owner = User.create_user("s_id_owner", "password")
        stranger = User.create_user("s_id_stranger", "password")
        card = add_card(client, owner, make_board(owner), "Private")

        assert search(client, stranger, str(card["id"])) == []


class TestIndexFollowsWrites:
    def test_a_renamed_card_is_found_by_its_new_title_only(self, client, db_session):
        user = User.create_user("s_rename", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Pteranodon logo")

        client.put(
            f"/api/cards/{card['id']}",
            json={"title": "Pearachute logo"},
            headers=headers(user),
        )

        assert search(client, user, "pteranodon") == []
        assert ids(search(client, user, "pearachute")) == [card["id"]]

    def test_a_new_description_replaces_the_old_one(self, client, db_session):
        user = User.create_user("s_redesc", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Card", "first draft")

        client.put(
            f"/api/cards/{card['id']}",
            json={"description": "second version"},
            headers=headers(user),
        )

        assert search(client, user, "draft") == []
        assert ids(search(client, user, "second")) == [card["id"]]

    def test_moving_a_card_keeps_it_findable(self, client, db_session):
        user = User.create_user("s_move", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Mobile card")
        done = board.columns.order_by(Column.position.desc()).first()

        client.put(
            f"/api/cards/{card['id']}",
            json={"column_id": done.id, "position": 3},
            headers=headers(user),
        )
        client.post(
            "/api/cards/reorder",
            json={"cards": [{"id": card["id"], "position": 0}]},
            headers=headers(user),
        )

        (result,) = search(client, user, "mobile")
        assert result["column_id"] == done.id

    def test_deleted_cards_and_boards_drop_out(self, client, db_session):
        user = User.create_user("s_delete", "password")
        board = make_board(user, "Doomed")
        other = make_board(user, "Kept")
        card = add_card(client, user, board, "Ephemeral one")
        add_card(client, user, board, "Ephemeral two")
        kept = add_card(client, user, other, "Ephemeral three")

        client.delete(f"/api/cards/{card['id']}", headers=headers(user))
        assert len(search(client, user, "ephemeral")) == 2

        client.delete(f"/api/boards/{board.id}", headers=headers(user))
        assert ids(search(client, user, "ephemeral")) == [kept["id"]]

    def test_the_index_stays_consistent(self, client, db_session):
        user = User.create_user("s_integrity", "password")
        board = make_board(user)
        card = add_card(client, user, board, "Alpha", "one")
        add_card(client, user, board, "Beta", "two")
        client.put(f"/api/cards/{card['id']}", json={"title": "Gamma"}, headers=headers(user))
        client.delete(f"/api/cards/{card['id']}", headers=headers(user))

        # Raises "database disk image is malformed" if a trigger ever handed
        # FTS5 a 'delete' for text the index does not hold.
        CardSearch.integrity_check(rank=1)


class TestAccess:
    def test_only_boards_the_caller_can_open_are_searched(self, client, db_session):
        owner = User.create_user("s_acc_owner", "password")
        teammate = User.create_user("s_acc_team", "password")
        org_member = User.create_user("s_acc_org", "password")
        outsider = User.create_user("s_acc_out", "password")

        org = Organization.create_with_columns("Acc Org", "acc-org", owner)
        OrganizationMember.create(
            user=org_member, organization=org, joined_at=datetime.now(timezone.utc)
        )
        team = Team.create_with_columns("Acc Team", org)
        TeamMember.create(user=teammate, team=team, joined_at=datetime.now(timezone.utc))

        private = make_board(owner, "Private")
        team_board = make_board(owner, "Team")
        team_board.shared_team = team
        team_board.save()
        org_board = make_board(owner, "Org")
        org_board.organization = org
        org_board.is_public_to_org = True
        org_board.save()

        on_private = add_card(client, owner, private, "Secret plan")
        on_team = add_card(client, owner, team_board, "Team plan")
        on_org = add_card(client, owner, org_board, "Org plan")

        assert set(ids(search(client, owner, "plan"))) == {
            on_private["id"],
            on_team["id"],
            on_org["id"],
        }
        assert ids(search(client, teammate, "plan")) == [on_team["id"]]
        assert ids(search(client, org_member, "plan")) == [on_org["id"]]
        assert search(client, outsider, "plan") == []

    def test_search_agrees_with_the_board_list(self, client, db_session):
        """Whatever search can reach, the board list shows, and vice versa."""
        owner = User.create_user("s_agree_owner", "password")
        member = User.create_user("s_agree_member", "password")
        org = Organization.create_with_columns("Agree Org", "agree-org", owner)
        OrganizationMember.create(
            user=member, organization=org, joined_at=datetime.now(timezone.utc)
        )
        shared = make_board(owner, "Shared")
        shared.organization = org
        shared.is_public_to_org = True
        shared.save()
        make_board(owner, "Not shared")
        for board in Board.select():
            add_card(client, owner, board, f"Needle on {board.name}")

        listed = {
            b["id"]
            for b in client.get("/api/boards", headers=headers(member)).json()
        }
        searched = {r["board_id"] for r in search(client, member, "needle")}
        assert listed == searched == {shared.id}

    def test_board_filter(self, client, db_session):
        user = User.create_user("s_filter", "password")
        one = make_board(user, "One")
        two = make_board(user, "Two")
        card = add_card(client, user, one, "Shared word")
        add_card(client, user, two, "Shared word")

        assert ids(search(client, user, "shared", board_id=one.id)) == [card["id"]]

    def test_board_filter_on_a_board_you_cannot_open(self, client, db_session):
        owner = User.create_user("s_filter_owner", "password")
        outsider = User.create_user("s_filter_out", "password")
        board = make_board(owner)

        forbidden = client.get(
            "/api/search",
            params={"q": "x", "board_id": board.id},
            headers=headers(outsider),
        )
        missing = client.get(
            "/api/search",
            params={"q": "x", "board_id": board.id + 1000},
            headers=headers(outsider),
        )
        assert forbidden.status_code == 403
        assert missing.status_code == 404

    def test_requires_auth(self, client, db_session):
        assert client.get("/api/search", params={"q": "x"}).status_code == 401


def test_create_table_restores_dropped_triggers_and_reindexes():
    """A migration that rebuilds the card table drops its triggers with it, and
    cards written before the next startup never reach the index. create_table()
    runs on every startup (init_db), puts the triggers back, and rebuilds.
    """
    with tempfile.TemporaryDirectory() as tmp:
        database = SqliteDatabase(os.path.join(tmp, "heal.db"))
        with database.bind_ctx(ALL_MODELS):
            database.connect()
            database.create_tables(ALL_MODELS)

            user = User.create_user("heal", "password")
            board = make_board(user)
            Card.create(column=first_column(board), title="Indexed", position=0)

            for (name,) in database.execute_sql(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall():
                database.execute_sql(f'DROP TRIGGER "{name}"')
            Card.create(column=first_column(board), title="Unindexed", position=1)

            def found(word):
                return (
                    CardSearch.select().where(CardSearch.match(f'"{word}"')).count()
                )

            assert found("unindexed") == 0

            database.create_tables(ALL_MODELS)

            assert found("unindexed") == 1
            assert found("indexed") == 1
            Card.create(column=first_column(board), title="Later", position=2)
            assert found("later") == 1
            CardSearch.integrity_check(rank=1)
            database.close()
