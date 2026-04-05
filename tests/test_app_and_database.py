from peewee import SqliteDatabase

from app import create_app
from app.database import db, init_db


def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_unknown_nested_route_returns_json_404(client):
    response = client.get("/missing/path")

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

    sqlite_db = SqliteDatabase(":memory:")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/hackathon_db")
    monkeypatch.setattr("app.database._build_database", lambda: sqlite_db)

    init_db(app)

    assert db.obj is not None
