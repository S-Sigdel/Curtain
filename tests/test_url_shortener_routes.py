from redis import RedisError

import app.routes.url_shortener as url_shortener_routes


def test_shorten_url_requires_long_url(client):
    response = client.post("/apis/url/shorten", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Field 'long_url' is required"}


def test_shorten_url_returns_503_when_redis_is_unavailable(client, monkeypatch):
    def raise_redis_error():
        raise RedisError("redis unavailable")

    monkeypatch.setattr(url_shortener_routes, "generate_next_short_code", raise_redis_error)

    response = client.post("/apis/url/shorten", json={"long_url": "https://www.wikipedia.org/"})

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Short URL generation is temporarily unavailable."
    }
