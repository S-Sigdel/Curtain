import sys
from pathlib import Path

import pytest
from peewee import SqliteDatabase

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.database import db
from app.models import MODELS


@pytest.fixture
def app():
    app = create_app(init_database=False)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def integration_app(tmp_path):
    test_db = SqliteDatabase(tmp_path / "test.db", pragmas={"foreign_keys": 1})
    db.initialize(test_db)
    test_db.connect()
    test_db.create_tables(MODELS)

    app = create_app(init_database=False)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    yield app

    test_db.drop_tables(list(reversed(MODELS)))
    test_db.close()


@pytest.fixture
def integration_client(integration_app):
    return integration_app.test_client()
