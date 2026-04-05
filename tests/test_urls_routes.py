from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Event, Url


class FakeCacheRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, _ttl, value):
        self.values[key] = value

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)


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


def test_redirect_short_code_calls_record_click(integration_client):
    # Every redirect always writes a DB Event row (durable audit trail)
    # and also fans out to Redis via record_click.
    url = Url.create(
        short_code="click1",
        original_url="https://example.com/tracked",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with patch("app.routes.url_shortener.record_click", return_value=True) as mock_rc:
        integration_client.get("/r/click1")

    mock_rc.assert_called_once()
    assert mock_rc.call_args[0][0] == "click1"
    assert Event.select().where(Event.url_id == url.id).count() == 1


def test_redirect_short_code_falls_back_to_db_when_redis_down(integration_client):
    # When record_click returns False (all shards unreachable), the route writes
    # an Event row directly so the click is never silently lost.
    url = Url.create(
        short_code="click2",
        original_url="https://example.com/fallback",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with patch("app.routes.url_shortener.record_click", return_value=False):
        integration_client.get("/r/click2")

    events = list(Event.select().where(Event.url_id == url.id))
    assert len(events) == 1
    assert events[0].event_type == "redirect"


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


def test_redirect_short_code_uses_cache_on_subsequent_requests(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    Url.create(
        short_code="cache1",
        original_url="https://example.com/cache",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with patch("app.routes.url_shortener.record_click"), \
         patch("app.routes.url_shortener.Url.get_or_none", wraps=Url.get_or_none) as mock_get:
        first = integration_client.get("/r/cache1")
        second = integration_client.get("/r/cache1")

    assert first.status_code == 302
    assert second.status_code == 302
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert mock_get.call_count == 1


def test_update_url_invalidates_redirect_cache(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    url = Url.create(
        short_code="cache2",
        original_url="https://example.com/old",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with patch("app.routes.url_shortener.record_click"):
        integration_client.get("/r/cache2")

    integration_client.put(f"/urls/{url.id}", json={"is_active": False})

    with patch("app.routes.url_shortener.record_click"), \
         patch("app.routes.url_shortener.Url.get_or_none", wraps=Url.get_or_none) as mock_get:
        response = integration_client.get("/r/cache2")

    assert response.status_code == 404
    assert mock_get.call_count == 1


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
