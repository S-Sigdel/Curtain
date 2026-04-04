from peewee import SqliteDatabase

from app import create_app
from app.database import db, init_db


def test_unknown_routes_return_json_404(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_internal_errors_return_json_500(app):
    @app.route("/boom")
    def boom():
        raise RuntimeError("boom")

    response = app.test_client().get("/boom")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_init_db_uses_database_url(monkeypatch):
    app = create_app(init_database=False)
    captured = {}

    def fake_connect(url):
        captured["url"] = url
        return SqliteDatabase(":memory:")

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr("app.database.connect", fake_connect)

    init_db(app)

    assert captured["url"] == "sqlite:///:memory:"
    assert db.obj is not None
