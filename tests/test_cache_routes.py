from datetime import datetime

from app.models import Event, Url, User


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


def test_get_url_sets_miss_then_hit_cache(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    now = datetime(2026, 1, 1, 0, 0, 0)
    owner = User.create(username="owner", email="owner@example.com", created_at=now)
    url = Url.create(
        user_id=owner.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    first = integration_client.get(f"/urls/{url.id}")
    second = integration_client.get(f"/urls/{url.id}")

    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"


def test_list_urls_sets_miss_then_hit_cache(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    now = datetime(2026, 1, 1, 0, 0, 0)
    user = User.create(username="owner", email="owner@example.com", created_at=now)
    Url.create(
        user_id=user.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    first = integration_client.get(f"/urls?user_id={user.id}")
    second = integration_client.get(f"/urls?user_id={user.id}")

    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"


def test_analytics_sets_miss_then_hit_cache(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    now = datetime(2026, 1, 1, 0, 0, 0)
    url = Url.create(
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    Event.create(url_id=url.id, event_type="created", timestamp=now, details="{}")

    first = integration_client.get(f"/urls/{url.id}/analytics")
    second = integration_client.get(f"/urls/{url.id}/analytics")

    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"


def test_update_url_invalidates_cached_entries(integration_client, monkeypatch):
    fake_cache = FakeCacheRedis()
    monkeypatch.setattr("app.cache.get_cache_redis", lambda: fake_cache)

    now = datetime(2026, 1, 1, 0, 0, 0)
    user = User.create(username="owner", email="owner@example.com", created_at=now)
    url = Url.create(
        user_id=user.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    Event.create(url_id=url.id, user_id=user.id, event_type="created", timestamp=now, details="{}")

    integration_client.get(f"/urls/{url.id}")
    integration_client.get(f"/urls?user_id={user.id}")
    integration_client.get(f"/urls/{url.id}/analytics")

    update = integration_client.put(
        f"/urls/{url.id}",
        json={"title": "Updated Title", "is_active": False},
    )
    detail = integration_client.get(f"/urls/{url.id}")
    listing = integration_client.get(f"/urls?user_id={user.id}")
    analytics = integration_client.get(f"/urls/{url.id}/analytics")

    assert update.status_code == 200
    assert update.headers["X-Cache"] == "BYPASS"
    assert detail.headers["X-Cache"] == "MISS"
    assert listing.headers["X-Cache"] == "MISS"
    assert analytics.headers["X-Cache"] == "MISS"
