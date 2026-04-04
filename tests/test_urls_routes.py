from datetime import datetime

import app.routes.url_shortener as url_routes
from app.models import Url


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


def test_create_url_returns_503_when_redis_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        url_routes,
        "get_or_create_short_url",
        lambda **kwargs: (None, None, "Short URL generation is temporarily unavailable.", 503),
    )

    response = client.post("/urls", json={"original_url": "https://www.wikipedia.org/"})

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Short URL generation is temporarily unavailable."
    }


def test_list_urls_rejects_invalid_user_id_query(client):
    response = client.get("/urls?user_id=abc")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Query parameter 'user_id' must be an integer"
    }


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
