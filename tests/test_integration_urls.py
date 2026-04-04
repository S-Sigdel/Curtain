from datetime import datetime

from app.models import Event, Url, User


class FakeRedis:
    def __init__(self, start=0):
        self.value = start
        self.seeded = None

    def setnx(self, _key, value):
        if self.seeded is None:
            self.seeded = value

    def incr(self, _key):
        self.value += 1
        return self.value


def test_create_url_creates_a_database_row(integration_client, monkeypatch):
    fake_redis = FakeRedis(start=0)
    owner = User.create(
        username="owner",
        email="owner@example.com",
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )
    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: fake_redis)

    response = integration_client.post(
        "/urls",
        json={
            "user_id": owner.id,
            "original_url": "https://www.wikipedia.org/",
            "title": "Wikipedia",
        },
    )

    body = response.get_json()

    assert response.status_code == 201
    assert body == {
        "id": 1,
        "user_id": owner.id,
        "short_code": "000001",
        "original_url": "https://www.wikipedia.org/",
        "title": "Wikipedia",
        "is_active": True,
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }

    created = Url.get(Url.short_code == "000001")
    assert created.original_url == "https://www.wikipedia.org/"
    assert created.title == "Wikipedia"
    assert created.user_id == owner.id
    event = Event.get(Event.url_id == created.id)
    assert event.event_type == "created"
    assert fake_redis.seeded == 0


def test_create_url_returns_400_for_invalid_user_id(integration_client, monkeypatch):
    fake_redis = FakeRedis(start=1)
    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: fake_redis)

    response = integration_client.post(
        "/urls",
        json={"original_url": "https://www.wikipedia.org/", "user_id": 999999},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Field 'user_id' must reference an existing user"
    }


def test_create_url_reuses_existing_active_mapping(integration_client, monkeypatch):
    now = datetime(2026, 1, 1, 0, 0, 0)
    Url.create(
        short_code="reuse01",
        original_url="https://www.wikipedia.org/",
        title="Existing",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    fake_redis = FakeRedis(start=50)
    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: fake_redis)

    response = integration_client.post(
        "/urls",
        json={"original_url": "https://www.wikipedia.org/"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": 1,
        "user_id": None,
        "short_code": "reuse01",
        "original_url": "https://www.wikipedia.org/",
        "title": "Existing",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    assert Url.select().where(Url.original_url == "https://www.wikipedia.org/").count() == 1
    assert fake_redis.seeded is None


def test_list_urls_supports_optional_user_filter(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    first_user = User.create(
        username="first",
        email="first@example.com",
        created_at=now,
    )
    second_user = User.create(
        username="second",
        email="second@example.com",
        created_at=now,
    )
    Url.insert_many(
        [
            {
                "user_id": first_user.id,
                "short_code": "abc123",
                "original_url": "https://example.com/1",
                "title": "First",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "user_id": second_user.id,
                "short_code": "def456",
                "original_url": "https://example.com/2",
                "title": "Second",
                "is_active": False,
                "created_at": now,
                "updated_at": now,
            },
        ]
    ).execute()

    response = integration_client.get(f"/urls?user_id={first_user.id}")

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 1,
            "user_id": first_user.id,
            "short_code": "abc123",
            "original_url": "https://example.com/1",
            "title": "First",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    ]


def test_get_url_by_id_returns_serialized_url(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    owner = User.create(
        username="owner",
        email="owner@example.com",
        created_at=now,
    )
    url = Url.create(
        user_id=owner.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="First",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response = integration_client.get(f"/urls/{url.id}")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": url.id,
        "user_id": owner.id,
        "short_code": "abc123",
        "original_url": "https://example.com/1",
        "title": "First",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }


def test_update_url_updates_requested_fields(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    owner = User.create(
        username="owner",
        email="owner@example.com",
        created_at=now,
    )
    url = Url.create(
        user_id=owner.id,
        short_code="abc123",
        original_url="https://example.com/1",
        title="Before",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response = integration_client.put(
        f"/urls/{url.id}",
        json={"title": "Updated Title", "is_active": False},
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["id"] == url.id
    assert body["user_id"] == owner.id
    assert body["short_code"] == "abc123"
    assert body["original_url"] == "https://example.com/1"
    assert body["title"] == "Updated Title"
    assert body["is_active"] is False
    assert body["created_at"] == "2026-01-01T00:00:00"
    assert body["updated_at"] != "2026-01-01T00:00:00"
    event = Event.get(Event.url_id == url.id)
    assert event.event_type == "updated"
