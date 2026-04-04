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
from datetime import datetime, UTC, timedelta

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


def record_click(short_code: str, visitor_ip: str, ring) -> None:
    """
    Record one click against ``short_code`` on the appropriate Redis shard.

    Args:
        short_code:  The 6-char short code that was accessed.
        visitor_ip:  Remote address of the visitor (used for HyperLogLog).
        ring:        A ShardRing / ResilientShardRing instance.

    Failures are logged at WARNING level and do NOT propagate — the caller
    (the redirect route) must never return a 5xx because the counter failed.
    """
    try:
        _shard_id, client = ring.get_shard(short_code)
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
    except Exception as exc:  # RedisError, AllShardsDownError, etc.
        logger.warning(
            "click_counter.record_failed",
            extra={"short_code": short_code, "error": str(exc)},
        )


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
    empty = {"total_clicks": 0, "unique_visitors": 0, "hourly": {}}
    try:
        _shard_id, client = ring.get_shard(short_code)

        now = datetime.now(UTC)
        bucket_labels = [
            (now - timedelta(hours=i)).strftime("%Y-%m-%d:%H") for i in range(72)
        ]

        pipe = client.pipeline(transaction=False)
        pipe.get(_total_key(short_code))
        pipe.pfcount(_uv_key(short_code))
        for label in bucket_labels:
            pipe.get(_hourly_key(short_code, label))

        results = pipe.execute()

        total = int(results[0] or 0)
        unique = int(results[1] or 0)
        hourly = {
            bucket_labels[i]: int(results[i + 2] or 0) for i in range(72)
        }
        return {"total_clicks": total, "unique_visitors": unique, "hourly": hourly}

    except Exception as exc:
        logger.warning(
            "click_counter.get_stats_failed",
            extra={"short_code": short_code, "error": str(exc)},
        )
        return empty
