from app import create_app


def test_debug_fail_route_is_hidden_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_INCIDENT_DEBUG_ROUTES", "false")
    app = create_app(init_database=False)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    response = app.test_client().get("/debug/fail")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_debug_fail_route_returns_500_when_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_INCIDENT_DEBUG_ROUTES", "true")
    app = create_app(init_database=False)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    response = app.test_client().get("/debug/fail")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}
