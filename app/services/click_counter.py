"""
Sharded real-time click counter backed by the consistent hash ring.

Per redirect, a single pipelined call to the owning Redis shard:
  - INCR  clicks:{short_code}                     — total counter
  - INCR  clicks:{short_code}:ts:{YYYY-MM-DD:HH}  — hourly time bucket
  - EXPIRE on the hourly bucket (72 h auto-cleanup)
  - PFADD clicks:{short_code}:uv {visitor_ip}     — HyperLogLog unique visitors
  - XADD  stream:clicks:{short_code}              — write-ahead log for PG sync

All operations are O(1) and complete in one network round-trip via pipelining.
If the shard ring is unavailable, errors are swallowed so that the redirect
itself never fails because of the counter.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from redis import RedisError

logger = logging.getLogger(__name__)

# Redis key helpers
_TOTAL_KEY = "clicks:{sc}"
_HOURLY_KEY = "clicks:{sc}:ts:{bucket}"
_UV_KEY = "clicks:{sc}:uv"
_STREAM_KEY = "stream:clicks:{sc}"

HOURLY_TTL = 72 * 3600  # seconds — keep 72 hours of per-hour buckets


def _total_key(short_code: str) -> str:
    return _TOTAL_KEY.format(sc=short_code)


def _hourly_key(short_code: str, bucket: str) -> str:
    return _HOURLY_KEY.format(sc=short_code, bucket=bucket)


def _uv_key(short_code: str) -> str:
    return _UV_KEY.format(sc=short_code)


def _stream_key(short_code: str) -> str:
    return _STREAM_KEY.format(sc=short_code)


def _current_hour_bucket() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d:%H")


def _execute_click_pipeline(client, short_code: str, visitor_ip: str) -> None:
    bucket = _current_hour_bucket()
    hourly = _hourly_key(short_code, bucket)

    pipe = client.pipeline(transaction=False)
    pipe.incr(_total_key(short_code))
    pipe.incr(hourly)
    pipe.expire(hourly, HOURLY_TTL)
    pipe.pfadd(_uv_key(short_code), visitor_ip)
    pipe.xadd(
        _stream_key(short_code),
        {"sc": short_code, "ip": visitor_ip, "ts": str(time.time())},
    )
    pipe.execute()


def record_click(short_code: str, visitor_ip: str, ring) -> bool:
    """
    Record one click against ``short_code`` on the appropriate Redis shard.

    Returns:
        True  — click was written to at least one Redis shard.
        False — all shards failed; caller should persist via the DB fallback.

    Failures are logged at WARNING level and do NOT propagate — the caller
    (the redirect route) must never return a 5xx because the counter failed.
    """
    primary_shard_id = None

    try:
        primary_shard_id, client = ring.get_shard(short_code)
        _execute_click_pipeline(client, short_code, visitor_ip)
        return True
    except Exception as exc:  # RedisError, AllShardsDownError, etc.
        if primary_shard_id is not None and hasattr(ring, "record_failure"):
            ring.record_failure(primary_shard_id)
        primary_error = exc

    try:
        for shard_id, client in ring.get_failover_shards(short_code):
            if shard_id == primary_shard_id:
                continue
            try:
                _execute_click_pipeline(client, short_code, visitor_ip)
                if primary_shard_id is not None and hasattr(ring, "record_failover"):
                    ring.record_failover(primary_shard_id, shard_id)
                return True
            except Exception:
                if hasattr(ring, "record_failure"):
                    ring.record_failure(shard_id)
    except Exception:
        pass

    logger.warning(
        "click_counter.record_failed",
        extra={"short_code": short_code, "error": str(primary_error)},
    )
    return False


def _fetch_stats_from_client(client, short_code: str, bucket_labels: list[str]) -> dict:
    pipe = client.pipeline(transaction=False)
    pipe.get(_total_key(short_code))
    pipe.pfcount(_uv_key(short_code))
    for label in bucket_labels:
        pipe.get(_hourly_key(short_code, label))

    results = pipe.execute()
    return {
        "total_clicks": int(results[0] or 0),
        "unique_visitors": int(results[1] or 0),
        "hourly": {
            bucket_labels[i]: int(results[i + 2] or 0) for i in range(72)
        },
    }


def get_click_stats(short_code: str, ring) -> dict:
    """
    Return real-time click statistics for ``short_code`` from the shard.

    Returns a dict with keys:
      - ``total_clicks``    int
      - ``unique_visitors`` int  (HyperLogLog ±0.81% error)
      - ``hourly``          dict[bucket_str, int] for the last 72 hours

    Returns all zeros on any Redis failure so the analytics endpoint can
    fall back gracefully to PostgreSQL event counts.
    """
    now = datetime.now(UTC)
    bucket_labels = [
        (now - timedelta(hours=i)).strftime("%Y-%m-%d:%H") for i in range(72)
    ]
    totals: dict = {
        "total_clicks": 0,
        "unique_visitors": 0,
        "hourly": {label: 0 for label in bucket_labels},
    }

    try:
        shard_clients = ring.all_clients()
    except Exception as exc:
        logger.warning(
            "click_counter.get_stats_failed",
            extra={"short_code": short_code, "error": str(exc)},
        )
        return {"total_clicks": 0, "unique_visitors": 0, "hourly": {}}

    for shard_id, client in shard_clients:
        try:
            shard_stats = _fetch_stats_from_client(client, short_code, bucket_labels)
            totals["total_clicks"] += shard_stats["total_clicks"]
            totals["unique_visitors"] += shard_stats["unique_visitors"]
            for label, count in shard_stats["hourly"].items():
                totals["hourly"][label] = totals["hourly"].get(label, 0) + count
        except Exception as exc:
            logger.warning(
                "click_counter.get_stats_shard_failed",
                extra={"short_code": short_code, "shard": shard_id, "error": str(exc)},
            )

    return totals
