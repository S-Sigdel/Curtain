from datetime import datetime

from app.models import Event, Url, User


def test_list_events_returns_serialized_events(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    user = User.create(
        username="owner",
        email="owner@example.com",
        created_at=now,
    )
    url = Url.create(
        user_id=user.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    Event.create(
        url_id=url.id,
        user_id=user.id,
        event_type="created",
        timestamp=now,
        details='{"short_code":"abc123","original_url":"https://example.com/1"}',
    )

    response = integration_client.get("/events")

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 1,
            "url_id": url.id,
            "user_id": user.id,
            "event_type": "created",
            "timestamp": "2026-01-01T00:00:00",
            "details": {
                "short_code": "abc123",
                "original_url": "https://example.com/1",
            },
        }
    ]


def test_create_event_creates_row_and_returns_payload(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    user = User.create(
        username="owner",
        email="owner@example.com",
        created_at=now,
    )
    url = Url.create(
        user_id=user.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response = integration_client.post(
        "/events",
        json={
            "url_id": url.id,
            "user_id": user.id,
            "event_type": "click",
            "details": {"referrer": "https://google.com"},
        },
    )

    body = response.get_json()
    assert response.status_code == 201
    assert body["url_id"] == url.id
    assert body["user_id"] == user.id
    assert body["event_type"] == "click"
    assert body["details"] == {"referrer": "https://google.com"}


def test_list_events_supports_filters(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    user = User.create(
        username="owner",
        email="owner@example.com",
        created_at=now,
    )
    url = Url.create(
        user_id=user.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    Event.insert_many(
        [
            {
                "url_id": url.id,
                "user_id": user.id,
                "event_type": "created",
                "timestamp": now,
                "details": '{"short_code":"abc123"}',
            },
            {
                "url_id": url.id,
                "user_id": user.id,
                "event_type": "updated",
                "timestamp": now,
                "details": '{"is_active":false}',
            },
        ]
    ).execute()

    response = integration_client.get(
        f"/events?url_id={url.id}&user_id={user.id}&event_type=updated"
    )

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 2,
            "url_id": url.id,
            "user_id": user.id,
            "event_type": "updated",
            "timestamp": "2026-01-01T00:00:00",
            "details": {"is_active": False},
        }
    ]


def test_url_analytics_returns_event_counts(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    url = Url.create(
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    Event.insert_many(
        [
            {
                "url_id": url.id,
                "event_type": "created",
                "timestamp": now,
                "details": "{}",
            },
            {
                "url_id": url.id,
                "event_type": "updated",
                "timestamp": datetime(2026, 1, 1, 1, 0, 0),
                "details": "{}",
            },
            {
                "url_id": url.id,
                "event_type": "updated",
                "timestamp": datetime(2026, 1, 1, 2, 0, 0),
                "details": "{}",
            },
        ]
    ).execute()

    response = integration_client.get(f"/urls/{url.id}/analytics")

    assert response.status_code == 200
    assert response.get_json() == {
        "url_id": url.id,
        "short_code": "abc123",
        "original_url": "https://example.com/1",
        "total_events": 3,
        "click_count": 0,
        "redirect_count": 0,
        "event_counts": {
            "created": 1,
            "updated": 2,
        },
        "latest_event_at": "2026-01-01T02:00:00",
    }


def test_url_analytics_returns_404_for_missing_url(integration_client):
    response = integration_client.get("/urls/999/analytics")

    assert response.status_code == 404
    assert response.get_json() == {"error": "URL not found"}


def test_list_events_rejects_invalid_query_params(client):
    response = client.get("/events?url_id=abc")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Query parameter 'url_id' must be an integer"}
