from redis import RedisError

import app.routes.url_shortener as url_shortener_routes


def test_shorten_url_requires_long_url(client):
    response = client.post("/apis/url/shorten", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'long_url' is required"}


def test_shorten_url_rejects_malformed_json(client):
    response = client.post(
        "/apis/url/shorten",
        data='{"long_url": ',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'long_url' is required"}


def test_shorten_url_rejects_invalid_url_format(client):
    response = client.post("/apis/url/shorten", json={"long_url": "not-a-real-url"})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Field 'long_url' must be a valid http or https URL"
    }


def test_shorten_url_returns_503_when_redis_is_unavailable(client, monkeypatch):
    def raise_redis_error():
        raise RedisError("redis unavailable")

    monkeypatch.setattr(
        url_shortener_routes,
        "get_or_create_short_url",
        lambda **kwargs: (None, None, "Short URL generation is temporarily unavailable.", 503),
    )

    response = client.post("/apis/url/shorten", json={"long_url": "https://www.wikipedia.org/"})

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Short URL generation is temporarily unavailable."
    }


def test_shorten_ui_reuses_shared_creation_logic(client, monkeypatch):
    monkeypatch.setattr(
        url_shortener_routes,
        "get_or_create_short_url",
        lambda **kwargs: ("0000ab", object(), None, 200),
    )

    response = client.post(
        "/shorten-ui",
        data={"long_url": "https://www.wikipedia.org/"},
    )

    assert response.status_code == 200
    assert "0000ab" in response.get_data(as_text=True)
