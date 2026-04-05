from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Event, Url


def test_create_url_requires_original_url(client):
    response = client.post("/urls", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'original_url' is required"}


def test_create_url_rejects_malformed_json(client):
    response = client.post(
        "/urls",
        data='{"original_url": ',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'original_url' is required"}


def test_create_url_rejects_invalid_url_format(client):
    response = client.post("/urls", json={"original_url": "not-a-real-url"})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Field 'original_url' must be a valid http or https URL"
    }


def test_list_urls_rejects_invalid_user_id_query(client):
    response = client.get("/urls?user_id=abc")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Query parameter 'user_id' must be an integer"
    }


def test_redirect_short_code_does_not_write_redirect_event_directly(integration_client):
    url = Url.create(
        short_code="click1",
        original_url="https://example.com/tracked",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    integration_client.get("/r/click1")

    events = list(Event.select().where(Event.url_id == url.id))
    assert events == []


def test_redirect_calls_record_click_with_short_code(integration_client):
    """record_click is invoked for every redirect, even if Redis is down."""
    Url.create(
        short_code="track1",
        original_url="https://example.com/track",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with patch("app.routes.url_shortener.record_click") as mock_rc:
        integration_client.get("/r/track1")

    mock_rc.assert_called_once()
    call_args = mock_rc.call_args[0]
    assert call_args[0] == "track1"  # short_code


def test_analytics_response_includes_realtime_block(integration_client):
    """Analytics endpoint always returns a realtime key (zeros when Redis is unavailable)."""
    url = Url.create(
        short_code="rt001",
        original_url="https://example.com/rt",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    response = integration_client.get(f"/urls/{url.id}/analytics")

    body = response.get_json()
    assert response.status_code == 200
    assert "realtime" in body
    assert "total_clicks" in body["realtime"]
    assert "unique_visitors" in body["realtime"]
    assert "hourly" in body["realtime"]


def test_analytics_realtime_reflects_mocked_redis_stats(integration_client):
    """When the shard ring returns stats, they appear under analytics.realtime."""
    url = Url.create(
        short_code="rt002",
        original_url="https://example.com/rt2",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    fake_stats = {"total_clicks": 99, "unique_visitors": 42, "hourly": {"2026-04-04:10": 10}}

    # Patch both get_click_stats and get_cached_json (force cache miss) so the
    # test does not pick up a stale cached entry from a prior test run.
    with patch("app.routes.events.get_click_stats", return_value=fake_stats), \
         patch("app.routes.events.get_cached_json", return_value=None):
        response = integration_client.get(f"/urls/{url.id}/analytics")

    assert response.get_json()["realtime"] == fake_stats


def test_update_url_rejects_invalid_boolean_type(integration_client):
    Url.create(
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    response = integration_client.put("/urls/1", json={"is_active": "false"})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'is_active' must be a boolean"}
