import io
from datetime import datetime

from app.models import User


def test_bulk_import_users_accepts_csv_upload(integration_client):
    csv_payload = io.BytesIO(
        (
            "username,email,created_at\n"
            "silvertrail15,silvertrail15@hackstack.io,2025-09-19 22:25:05\n"
            "urbancanyon36,urbancanyon36@opswise.net,2024-04-09 02:51:03\n"
        ).encode("utf-8")
    )

    response = integration_client.post(
        "/users/bulk",
        data={"file": (csv_payload, "users.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json() == {"count": 2}
    assert User.select().count() == 2


def test_list_users_supports_optional_pagination(integration_client):
    User.insert_many(
        [
            {
                "username": "alpha",
                "email": "alpha@example.com",
                "created_at": datetime(2026, 1, 1, 12, 0, 0),
            },
            {
                "username": "beta",
                "email": "beta@example.com",
                "created_at": datetime(2026, 1, 2, 12, 0, 0),
            },
        ]
    ).execute()

    response = integration_client.get("/users?page=1&per_page=1")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["username"] == "alpha"


def test_get_user_by_id_returns_serialized_user(integration_client):
    user = User.create(
        username="lookup",
        email="lookup@example.com",
        created_at=datetime(2026, 1, 3, 8, 30, 0),
    )

    response = integration_client.get(f"/users/{user.id}")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": user.id,
        "username": "lookup",
        "email": "lookup@example.com",
        "created_at": "2026-01-03T08:30:00",
    }


def test_create_user_rejects_invalid_schema(integration_client):
    response = integration_client.post(
        "/users",
        json={"username": 123, "email": "testuser@example.com"},
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "errors": {"username": "Field 'username' must be a string"}
    }


def test_create_user_creates_row_and_returns_payload(integration_client):
    response = integration_client.post(
        "/users",
        json={"username": "testuser", "email": "testuser@example.com"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] >= 1
    assert body["username"] == "testuser"
    assert body["email"] == "testuser@example.com"
    assert "T" in body["created_at"]


def test_update_user_updates_requested_fields(integration_client):
    user = User.create(
        username="before",
        email="before@example.com",
        created_at=datetime(2026, 1, 4, 9, 0, 0),
    )

    response = integration_client.put(
        f"/users/{user.id}",
        json={"username": "updated_username"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": user.id,
        "username": "updated_username",
        "email": "before@example.com",
        "created_at": "2026-01-04T09:00:00",
    }


def test_delete_user_removes_user_and_returns_204(integration_client):
    user = User.create(
        username="delete_me",
        email="delete_me@example.com",
        created_at=datetime(2026, 1, 5, 9, 0, 0),
    )

    response = integration_client.delete(f"/users/{user.id}")

    assert response.status_code == 204
    assert User.get_or_none(User.id == user.id) is None
