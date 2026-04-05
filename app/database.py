import os
import urllib.parse

from peewee import DatabaseProxy, Model
from playhouse.pool import PooledPostgresqlDatabase

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def _build_database():
    """
    Build a PooledPostgresqlDatabase from environment variables.

    Connection pool keeps up to 20 live connections per process.
    With 4 gthread workers × 4 threads = 16 concurrent DB users per
    container, 20 gives a small buffer without exhausting Postgres's
    default max_connections (100) across both containers.
    """
    pool_kwargs = dict(
        max_connections=20,
        stale_timeout=300,  # recycle connections idle for 5 min
        timeout=10,         # wait up to 10 s for a free slot before raising
    )

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        p = urllib.parse.urlparse(database_url)
        return PooledPostgresqlDatabase(
            p.path.lstrip("/"),
            host=p.hostname,
            port=p.port or 5432,
            user=p.username,
            password=p.password or "",
            **pool_kwargs,
        )

    return PooledPostgresqlDatabase(
        os.environ.get("DATABASE_NAME", "hackathon_db"),
        host=os.environ.get("DATABASE_HOST", "localhost"),
        port=int(os.environ.get("DATABASE_PORT", 5432)),
        user=os.environ.get("DATABASE_USER", "postgres"),
        password=os.environ.get("DATABASE_PASSWORD", "postgres"),
        **pool_kwargs,
    )


def init_db(app):
    database = _build_database()
    db.initialize(database)

    from app.models import MODELS

    db.connect(reuse_if_open=True)
    db.create_tables(MODELS, safe=True)
    db.close()

    @app.before_request
    def _db_connect():
        db.connect(reuse_if_open=True)

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()
