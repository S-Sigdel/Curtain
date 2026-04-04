from datetime import datetime

from app.models import Url


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


def test_shorten_url_creates_a_database_row(integration_client, monkeypatch):
    fake_redis = FakeRedis(start=0)
    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: fake_redis)

    response = integration_client.post(
        "/apis/url/shorten",
        json={"long_url": "https://www.wikipedia.org/", "title": "Wikipedia"},
    )

    assert response.status_code == 201
    assert response.get_json() == {"short_url": "000001"}

    created = Url.get(Url.short_code == "000001")
    assert created.original_url == "https://www.wikipedia.org/"
    assert created.title == "Wikipedia"
    assert fake_redis.seeded == 0


def test_redirect_short_url_returns_a_redirect_response(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    Url.create(
        short_code="abc123",
        original_url="https://www.wikipedia.org/",
        title="Wikipedia",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response = integration_client.get("/apis/url/abc123")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://www.wikipedia.org/"


def test_shorten_url_returns_400_for_invalid_user_id(integration_client, monkeypatch):
    fake_redis = FakeRedis(start=1)
    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: fake_redis)

    response = integration_client.post(
        "/apis/url/shorten",
        json={"long_url": "https://www.wikipedia.org/", "user_id": 999999},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Field 'user_id' must reference an existing user"
    }


def test_inactive_short_url_returns_json_404(integration_client):
    now = datetime(2026, 1, 1, 0, 0, 0)
    Url.create(
        short_code="dead01",
        original_url="https://www.wikipedia.org/",
        title="Inactive",
        is_active=False,
        created_at=now,
        updated_at=now,
    )

    response = integration_client.get("/apis/url/dead01")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Short URL not found"}


def test_shorten_url_reuses_existing_active_mapping(integration_client, monkeypatch):
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
        "/apis/url/shorten",
        json={"long_url": "https://www.wikipedia.org/"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"short_url": "reuse01"}
    assert Url.select().where(Url.original_url == "https://www.wikipedia.org/").count() == 1
    assert fake_redis.seeded is None
