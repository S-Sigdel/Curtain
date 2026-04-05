"""
Redis Streams → PostgreSQL batch writer.

Run as a standalone service (not part of the Flask app):

    uv run python -m app.stream_consumer

For every Redis shard in the ring, this worker:
  1. Creates a consumer group ``pg_writers`` on every ``stream:clicks:*`` key.
  2. Reads up to BATCH_SIZE messages from each stream.
  3. Bulk-inserts the messages into the PostgreSQL ``events`` table as
     ``event_type="redirect"``.
  4. Acknowledges the messages so they are not re-delivered.

If the PostgreSQL insert fails the messages are NOT acknowledged, so they
will be retried on the next iteration.  This gives us at-least-once delivery
to Postgres.

Environment variables:
    DATABASE_URL          – PostgreSQL DSN (required in container)
    REDIS_SHARDS          – comma-separated host:port pairs (or falls back to REDIS_URL)
    STREAM_BATCH_SIZE     – messages per read call (default: 100)
    STREAM_BLOCK_MS       – ms to block waiting for new messages (default: 5000)
    STREAM_POLL_INTERVAL  – seconds between full scan cycles (default: 1)
"""

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, UTC

from redis.exceptions import ResponseError

from app.database import db
from app.models import MODELS
from app.models.event import Event
from app.models.url import Url
from app.redis_client import get_shard_ring

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = int(os.environ.get("STREAM_BATCH_SIZE", "100"))
BLOCK_MS = int(os.environ.get("STREAM_BLOCK_MS", "5000"))
POLL_INTERVAL = float(os.environ.get("STREAM_POLL_INTERVAL", "1"))
CONSUMER_GROUP = "pg_writers"

# ---------------------------------------------------------------------------
# Logging (same JSON format as the rest of the app)
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stream_consumer")


def _log(level: str, message: str, **fields):
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "component": "stream_consumer",
        "message": message,
    }
    payload.update(fields)
    print(json.dumps(payload, default=str), flush=True)


# ---------------------------------------------------------------------------
# Consumer group bootstrap
# ---------------------------------------------------------------------------

def _ensure_group(client, stream_key: str) -> None:
    """Create the consumer group starting from the beginning of the stream."""
    try:
        client.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
        _log("INFO", "consumer_group.created", stream=stream_key, group=CONSUMER_GROUP)
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            pass  # group already exists — normal on restart
        else:
            raise


# ---------------------------------------------------------------------------
# Per-shard drain loop
# ---------------------------------------------------------------------------

def _get_stream_keys(client) -> list:
    """Return all click-stream keys on this shard."""
    raw = client.keys("stream:clicks:*")
    return [k.decode() if isinstance(k, bytes) else k for k in raw]


def _drain_shard(shard_id: str, client) -> int:
    """
    Read one batch from every stream on this shard and write to Postgres.

    Returns the number of events written.
    """
    stream_keys = _get_stream_keys(client)
    if not stream_keys:
        return 0

    # Bootstrap consumer groups for any newly seen streams
    for key in stream_keys:
        _ensure_group(client, key)

    worker_name = f"worker-{shard_id}-{os.getpid()}"

    entries = client.xreadgroup(
        CONSUMER_GROUP,
        worker_name,
        {k: ">" for k in stream_keys},
        count=BATCH_SIZE,
        block=BLOCK_MS,
    )

    if not entries:
        return 0

    events_to_insert = []
    ack_map: dict[str, list] = defaultdict(list)

    for stream_name, messages in entries:
        stream_name = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
        for msg_id, data in messages:
            # Decode bytes keys/values from Redis
            decoded = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in data.items()
            }
            short_code = decoded.get("sc", "")
            visitor_ip = decoded.get("ip", "")
            ts_raw = decoded.get("ts")

            try:
                ts = datetime.fromtimestamp(float(ts_raw), UTC).replace(tzinfo=None)
            except (TypeError, ValueError):
                ts = datetime.now(UTC).replace(tzinfo=None)

            events_to_insert.append({
                "url_id": None,          # avoid FK join on hot path; url resolved by short_code below
                "short_code": short_code,
                "event_type": "redirect",
                "timestamp": ts,
                "details": json.dumps({"ip": visitor_ip, "shard": shard_id, "source": "stream"}),
            })
            ack_map[stream_name].append(msg_id)

    if not events_to_insert:
        return 0

    # Resolve short_codes → url_ids in one query
    short_codes = list({e["short_code"] for e in events_to_insert})
    url_map = {
        row.short_code: row.id
        for row in Url.select(Url.id, Url.short_code).where(Url.short_code.in_(short_codes))
    }

    # Build final insert rows, skipping unknown short codes
    insert_rows = []
    for e in events_to_insert:
        url_id = url_map.get(e["short_code"])
        if url_id is None:
            continue  # URL was deleted — drop the event
        insert_rows.append({
            "url_id": url_id,
            "user_id": None,
            "event_type": e["event_type"],
            "timestamp": e["timestamp"],
            "details": e["details"],
        })

    if insert_rows:
        with db.atomic():
            Event.insert_many(insert_rows).execute()

    # Only acknowledge after successful DB write
    for stream_name, msg_ids in ack_map.items():
        client.xack(stream_name, CONSUMER_GROUP, *msg_ids)

    written = len(insert_rows)
    if written:
        _log("INFO", "stream.flushed", shard=shard_id, events_written=written)
    return written


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _connect_db():
    """Open a direct DB connection (no Flask app context needed)."""
    from playhouse.db_url import connect
    from peewee import PostgresqlDatabase

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        from playhouse.db_url import connect as db_connect
        database = db_connect(database_url)
    else:
        database = PostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
        )
    db.initialize(database)
    db.connect(reuse_if_open=True)
    db.create_tables(MODELS, safe=True)


def run():
    _log("INFO", "stream_consumer.starting", batch_size=BATCH_SIZE, block_ms=BLOCK_MS)
    _connect_db()

    ring = get_shard_ring()
    _log("INFO", "stream_consumer.shards_loaded", shards=ring.shard_ids)

    while True:
        total = 0
        for shard_id, client in ring.all_clients():
            try:
                total += _drain_shard(shard_id, client)
            except Exception as exc:
                _log("ERROR", "stream_consumer.shard_error", shard=shard_id, error=str(exc))
        if total == 0:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
