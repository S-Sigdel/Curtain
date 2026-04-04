import os

from playhouse.db_url import connect
from peewee import DatabaseProxy, Model, PostgresqlDatabase

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def init_db(app):
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Container and managed-platform deployments usually provide a single DB URL.
        database = connect(database_url)
    else:
        database = PostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
        )
    db.initialize(database)

    from app.models import MODELS

    db.connect(reuse_if_open=True)
    db.create_tables(MODELS, safe=True)
    db.close()

    @app.before_request
    def _db_connect():
        db.connect(reuse_if_open=True)
        db.create_tables(MODELS, safe=True)

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()
