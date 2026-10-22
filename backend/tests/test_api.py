import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import db
from backend.models import (
    User,
    Board,
    Column,
    Card,
    Organization,
    OrganizationMember,
    Team,
    TeamMember,
)


@pytest.fixture
def auth_headers(test_user):
    from backend.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


def test_server_launch():
    from backend.main import app
    from backend.database import db
    from backend.models import User, Board, Column, Card

    assert app is not None
    assert db is not None


def test_root(client):
    response = client.get("/")
    assert response.status_code in [200, 404]


def test_login_success(client, test_user):
    response = client.post(
        "/api/token",
        json={"username": test_user.username, "password": "testpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure(client, test_user):
    response = client.post(
        "/api/token",
        json={"username": test_user.username, "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_create_board(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Test Board"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert isinstance(data["id"], int)
    # Verify all required fields are present for frontend display
    assert "name" in data
    assert data["name"] == "Test Board"
    assert "created_at" in data
    assert data["created_at"] is not None
    assert data["teams"] == []
    assert data["permission"] == "admin"
    assert "owner_id" in data
    assert data["owner_id"] == test_user.id


def test_list_boards(client, auth_headers, test_user):
    response = client.get("/api/boards", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_board_without_auth(client):
    response = client.post(
        "/api/boards",
        json={"name": "Test Board"},
    )
    assert response.status_code == 401


def test_get_board_with_columns(client, auth_headers, test_user):
    """Get a board with its columns"""
    # Create a board
    response = client.post(
        "/api/boards",
        json={"name": "Board with Columns"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    board_id = response.json()["id"]

    response = client.get(f"/api/boards/{board_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Board with Columns"
    assert "columns" in data
    assert len(data["columns"]) == 3
    assert data["columns"][0]["name"] == "To Do"


def test_create_column(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Column Test Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "New Column", "position": 3},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Column"


def test_create_card(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Card Test Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    # Create a column first since API doesn't create default columns
    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "To Do", "position": 0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    column_id = response.json()["id"]

    response = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "Test Card", "position": 0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Card"


def test_move_card(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Move Card Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    # Create columns first since API doesn't create default columns
    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Column 1", "position": 0},
        headers=auth_headers,
    )
    column1_id = response.json()["id"]

    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Column 2", "position": 1},
        headers=auth_headers,
    )
    column2_id = response.json()["id"]

    response = client.post(
        "/api/cards",
        json={"column_id": column1_id, "title": "Card to Move", "position": 0},
        headers=auth_headers,
    )
    card_id = response.json()["id"]

    response = client.put(
        f"/api/cards/{card_id}",
        json={"column_id": column2_id, "title": "Card to Move", "position": 0},
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_delete_card(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Delete Card Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    # Create a column first since API doesn't create default columns
    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "To Delete", "position": 0},
        headers=auth_headers,
    )
    column_id = response.json()["id"]

    response = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "Card to Delete", "position": 0},
        headers=auth_headers,
    )
    card_id = response.json()["id"]

    response = client.delete(f"/api/cards/{card_id}", headers=auth_headers)
    assert response.status_code == 200


def test_update_nonexistent_card_returns_404(client, auth_headers, test_user):
    """Test that updating a non-existent card returns 404, not 422."""
    response = client.put(
        "/api/cards/99999",
        json={"column_id": 1, "title": "Test", "description": "", "position": 0},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_nonexistent_card_returns_404(client, auth_headers, test_user):
    """Test that deleting a non-existent card returns 404."""
    response = client.delete("/api/cards/99999", headers=auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_board(client, auth_headers, test_user):
    response = client.post(
        "/api/boards",
        json={"name": "Board to Delete"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    response = client.delete(f"/api/boards/{board_id}", headers=auth_headers)
    assert response.status_code == 200

    response = client.get(f"/api/boards/{board_id}", headers=auth_headers)
    assert response.status_code == 404


def test_reorder_cards(client, auth_headers, test_user):
    """Test reordering cards within a column"""
    # Create board (gets default columns: To Do, In Progress, For Review)
    response = client.post(
        "/api/boards",
        json={"name": "Reorder Cards Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    # Use the first default column
    response = client.get(
        f"/api/boards/{board_id}",
        headers=auth_headers,
    )
    column_id = response.json()["columns"][0]["id"]

    # Create multiple cards
    card_ids = []
    for i in range(3):
        response = client.post(
            "/api/cards",
            json={"column_id": column_id, "title": f"Card {i}", "position": i},
            headers=auth_headers,
        )
        card_ids.append(response.json()["id"])

    # Reorder cards: reverse their order
    reorder_request = [
        {"id": card_ids[0], "position": 2},
        {"id": card_ids[1], "position": 1},
        {"id": card_ids[2], "position": 0},
    ]

    response = client.post(
        "/api/cards/reorder",
        json={"cards": reorder_request},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Verify the reorder persisted by fetching the board
    response = client.get(f"/api/boards/{board_id}", headers=auth_headers)
    assert response.status_code == 200
    cards = response.json()["columns"][0]["cards"]
    card_titles = [c["title"] for c in cards]
    assert card_titles == ["Card 2", "Card 1", "Card 0"]


def test_reorder_columns(client, auth_headers, test_user):
    """Test reordering columns on a board"""
    # Create board (gets default columns: To Do, In Progress, For Review)
    response = client.post(
        "/api/boards",
        json={"name": "Reorder Columns Board"},
        headers=auth_headers,
    )
    board_id = response.json()["id"]

    # Fetch the default columns
    response = client.get(
        f"/api/boards/{board_id}",
        headers=auth_headers,
    )
    columns = response.json()["columns"]
    column_ids = [c["id"] for c in columns]

    # Reorder columns: reverse their order
    reorder_request = [
        {"id": column_ids[0], "position": 2},
        {"id": column_ids[1], "position": 1},
        {"id": column_ids[2], "position": 0},
    ]

    response = client.post(
        "/api/columns/reorder",
        json={"columns": reorder_request},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Verify the reorder persisted by fetching the board
    response = client.get(f"/api/boards/{board_id}", headers=auth_headers)
    assert response.status_code == 200
    column_names = [c["name"] for c in response.json()["columns"]]
    assert column_names == ["For Review", "In Progress", "To Do"]


def test_reorder_cards_requires_auth(client):
    """Test that reordering cards requires authentication"""
    response = client.post(
        "/api/cards/reorder",
        json={"cards": [{"id": 1, "position": 0}]},
    )
    assert response.status_code == 401


def test_reorder_columns_requires_auth(client):
    """Test that reordering columns requires authentication"""
    response = client.post(
        "/api/columns/reorder",
        json={"columns": [{"id": 1, "position": 0}]},
    )
    assert response.status_code == 401


def test_get_card_returns_description_and_location(client, auth_headers, test_user):
    """A card's body was previously only reachable nested inside a board, so
    anything holding a card id could not read what the card said."""
    board_id = client.post(
        "/api/boards", json={"name": "Read Card Board"}, headers=auth_headers
    ).json()["id"]
    column_id = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Backlog", "position": 0},
        headers=auth_headers,
    ).json()["id"]
    card_id = client.post(
        "/api/cards",
        json={
            "column_id": column_id,
            "title": "Has a body",
            "description": "The part you could not read.",
            "position": 0,
        },
        headers=auth_headers,
    ).json()["id"]

    response = client.get(f"/api/cards/{card_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Has a body"
    assert data["description"] == "The part you could not read."
    # "which column is this on?" is the question right after "what does it say?"
    assert data["column_id"] == column_id
    assert data["column_name"] == "Backlog"
    assert data["board_id"] == board_id
    assert data["board_name"] == "Read Card Board"


def test_get_nonexistent_card_returns_404(client, auth_headers, test_user):
    response = client.get("/api/cards/99999", headers=auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_card_on_another_users_board_is_forbidden(client, auth_headers, test_user):
    """Reading a card must not be a way around board access control."""
    from backend.models import User, Board, Column, Card

    stranger = User.create_user(
        username="card-stranger", password="pw", email="stranger@example.com"
    )
    board = Board.create_with_columns(owner=stranger, name="Private Board")
    column = Column.create(board=board, name="Theirs", position=0)
    card = Card.create(column=column, title="Secret", description="hush", position=0)

    response = client.get(f"/api/cards/{card.id}", headers=auth_headers)
    assert response.status_code == 403


def test_get_card_does_not_shadow_the_comments_route(client, auth_headers, test_user):
    """GET /cards/{id} is declared before /cards/{id}/comments; the extra path
    segment must still route to the comments handler."""
    board_id = client.post(
        "/api/boards", json={"name": "Route Board"}, headers=auth_headers
    ).json()["id"]
    column_id = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Col", "position": 0},
        headers=auth_headers,
    ).json()["id"]
    card_id = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "Card", "position": 0},
        headers=auth_headers,
    ).json()["id"]

    response = client.get(f"/api/cards/{card_id}/comments", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_create_column_without_position_appends(client, auth_headers, test_user):
    """position was required, so callers tracked a counter just to add a
    column at the end."""
    board_id = client.post(
        "/api/boards", json={"name": "Append Board"}, headers=auth_headers
    ).json()["id"]

    # A new board is not empty -- it comes with the default columns. Derived
    # rather than hardcoded so changing that default list does not break this
    # test, which is about appending, not about what the defaults are.
    existing = client.get(f"/api/boards/{board_id}", headers=auth_headers).json()[
        "columns"
    ]
    end = max(c["position"] for c in existing) + 1

    first = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "First"},
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["position"] == end

    second = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Second"},
        headers=auth_headers,
    )
    assert second.json()["position"] == end + 1


def test_create_column_appends_after_the_highest_position(
    client, auth_headers, test_user
):
    """Append means one past the highest position, not one past the count --
    positions need not be contiguous."""
    board_id = client.post(
        "/api/boards", json={"name": "Sparse Board"}, headers=auth_headers
    ).json()["id"]
    client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Far", "position": 9},
        headers=auth_headers,
    )

    appended = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "After"},
        headers=auth_headers,
    )
    assert appended.json()["position"] == 10


def test_create_column_with_explicit_position_is_unchanged(
    client, auth_headers, test_user
):
    board_id = client.post(
        "/api/boards", json={"name": "Explicit Board"}, headers=auth_headers
    ).json()["id"]
    response = client.post(
        "/api/columns",
        json={"board_id": board_id, "name": "Third", "position": 2},
        headers=auth_headers,
    )
    assert response.json()["position"] == 2


def test_unknown_api_path_returns_json_404_not_the_spa(client):
    """The SPA catch-all used to answer 200 text/html for any unmatched path,
    including /api/ ones -- so a missing endpoint looked like a working one,
    and response.json() raised a decode error instead of surfacing a 404."""
    response = client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not found"


def test_bare_api_prefix_returns_404(client):
    response = client.get("/api")
    assert response.status_code == 404


def test_unknown_api_path_404s_without_credentials_too(client):
    """A missing endpoint must not be mistakable for an auth failure -- that
    confusion is what produced the bogus 'boards rejects Bearer, cards accepts
    it' report, where both 200s were really the catch-all."""
    response = client.get("/api/cards/14/not-a-thing")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_real_api_route_still_routes(client, auth_headers, test_user):
    """The 404 guard must not swallow endpoints that do exist."""
    assert client.get("/api/boards", headers=auth_headers).status_code == 200


def test_non_api_path_still_falls_back_to_the_spa(client):
    """Front-end routes must keep working: the guard is scoped to /api/."""
    response = client.get("/some/client/side/route")
    assert response.status_code == 200
