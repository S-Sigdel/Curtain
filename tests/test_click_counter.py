"""Unit tests for app/services/click_counter.py — no real Redis required."""

from datetime import datetime, UTC
from unittest.mock import MagicMock, call, patch

import pytest
from redis import ConnectionError as RedisConnectionError

from app.shard_ring import AllShardsDownError
from app.services.click_counter import (
    HOURLY_TTL,
    _current_hour_bucket,
    _hourly_key,
    _stream_key,
    _total_key,
    _uv_key,
    get_click_stats,
    record_click,
)


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def test_total_key():
    assert _total_key("abc123") == "clicks:abc123"


def test_hourly_key():
    assert _hourly_key("abc123", "2026-04-04:14") == "clicks:abc123:ts:2026-04-04:14"


def test_uv_key():
    assert _uv_key("abc123") == "clicks:abc123:uv"


def test_stream_key():
    assert _stream_key("abc123") == "stream:clicks:abc123"


def test_current_hour_bucket_format():
    bucket = _current_hour_bucket()
    # Must match YYYY-MM-DD:HH
    parts = bucket.split(":")
    assert len(parts) == 2
    assert len(parts[0]) == 10  # YYYY-MM-DD
    assert len(parts[1]) == 2   # HH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ring(client):
    """Return a mock ring that always gives (shard_id, client)."""
    ring = MagicMock()
    ring.get_shard.return_value = ("shard0", client)
    ring.get_failover_shards.return_value = [("shard0", client)]
    ring.all_clients.return_value = [("shard0", client)]
    return ring


def _make_pipeline():
    pipe = MagicMock()
    pipe.execute.return_value = []
    return pipe


# ---------------------------------------------------------------------------
# record_click — happy path
# ---------------------------------------------------------------------------

def test_record_click_issues_five_pipeline_commands():
    pipe = _make_pipeline()
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("abc123", "1.2.3.4", ring)

    client.pipeline.assert_called_once_with(transaction=False)
    pipe.incr.assert_called()          # total key
    pipe.pfadd.assert_called_once()    # unique visitors
    pipe.xadd.assert_called_once()     # stream
    pipe.execute.assert_called_once()


def test_record_click_increments_correct_total_key():
    pipe = _make_pipeline()
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("xyz999", "10.0.0.1", ring)

    # First incr call must target the total key
    first_incr_key = pipe.incr.call_args_list[0][0][0]
    assert first_incr_key == "clicks:xyz999"


def test_record_click_sets_expire_on_hourly_bucket():
    pipe = _make_pipeline()
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("abc123", "1.2.3.4", ring)

    pipe.expire.assert_called_once()
    _key, ttl = pipe.expire.call_args[0]
    assert ttl == HOURLY_TTL


def test_record_click_uses_correct_visitor_ip_in_pfadd():
    pipe = _make_pipeline()
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("sc0001", "192.168.1.1", ring)

    pfadd_args = pipe.pfadd.call_args[0]
    assert pfadd_args[0] == "clicks:sc0001:uv"
    assert "192.168.1.1" in pfadd_args


def test_record_click_adds_short_code_to_stream():
    pipe = _make_pipeline()
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("sc0001", "10.0.0.1", ring)

    xadd_args = pipe.xadd.call_args[0]
    assert xadd_args[0] == "stream:clicks:sc0001"
    payload = xadd_args[1]
    assert payload["sc"] == "sc0001"
    assert payload["ip"] == "10.0.0.1"
    assert "ts" in payload


# ---------------------------------------------------------------------------
# record_click — failure handling
# ---------------------------------------------------------------------------

def test_record_click_does_not_raise_on_redis_error():
    ring = MagicMock()
    ring.get_shard.side_effect = RedisConnectionError("down")
    ring.get_failover_shards.side_effect = AllShardsDownError("no shards")
    # Must not raise — redirect should still succeed
    record_click("sc0001", "1.2.3.4", ring)


def test_record_click_does_not_raise_when_all_shards_down():
    ring = MagicMock()
    ring.get_shard.side_effect = AllShardsDownError("no shards")
    ring.get_failover_shards.side_effect = AllShardsDownError("no shards")
    record_click("sc0001", "1.2.3.4", ring)


def test_record_click_does_not_raise_on_pipeline_execute_failure():
    pipe = _make_pipeline()
    pipe.execute.side_effect = RedisConnectionError("pipe broke")
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    record_click("sc0001", "1.2.3.4", ring)  # must not raise


def test_record_click_fails_over_to_next_shard_on_primary_write_error():
    primary_pipe = _make_pipeline()
    primary_pipe.execute.side_effect = RedisConnectionError("primary down")
    primary_client = MagicMock()
    primary_client.pipeline.return_value = primary_pipe

    failover_pipe = _make_pipeline()
    failover_client = MagicMock()
    failover_client.pipeline.return_value = failover_pipe

    ring = MagicMock()
    ring.get_shard.return_value = ("shard0", primary_client)
    ring.get_failover_shards.return_value = [
        ("shard0", primary_client),
        ("shard1", failover_client),
    ]

    record_click("sc0001", "1.2.3.4", ring)

    ring.record_failure.assert_called_with("shard0")
    ring.record_failover.assert_called_with("shard0", "shard1")
    failover_pipe.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_click_stats — happy path
# ---------------------------------------------------------------------------

def test_get_click_stats_returns_total_and_unique():
    # pipeline execute: [total, unique, *72 hourly buckets]
    results = [42, 17] + [0] * 72
    pipe = MagicMock()
    pipe.execute.return_value = results
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    stats = get_click_stats("abc123", ring)

    assert stats["total_clicks"] == 42
    assert stats["unique_visitors"] == 17


def test_get_click_stats_returns_72_hourly_buckets():
    results = [10, 5] + [i for i in range(72)]
    pipe = MagicMock()
    pipe.execute.return_value = results
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    stats = get_click_stats("abc123", ring)

    assert len(stats["hourly"]) == 72


def test_get_click_stats_handles_none_redis_values():
    # Redis returns None for keys that don't exist
    results = [None, None] + [None] * 72
    pipe = MagicMock()
    pipe.execute.return_value = results
    client = MagicMock()
    client.pipeline.return_value = pipe
    ring = _make_ring(client)

    stats = get_click_stats("abc123", ring)

    assert stats["total_clicks"] == 0
    assert stats["unique_visitors"] == 0
    assert all(v == 0 for v in stats["hourly"].values())


# ---------------------------------------------------------------------------
# get_click_stats — failure handling
# ---------------------------------------------------------------------------

def test_get_click_stats_returns_zeros_on_redis_error():
    ring = MagicMock()
    ring.all_clients.side_effect = RedisConnectionError("down")

    stats = get_click_stats("sc0001", ring)

    assert stats == {"total_clicks": 0, "unique_visitors": 0, "hourly": {}}


def test_get_click_stats_returns_zeros_when_all_shards_down():
    ring = MagicMock()
    ring.all_clients.side_effect = AllShardsDownError("no shards")

    stats = get_click_stats("sc0001", ring)

    assert stats["total_clicks"] == 0
    assert stats["unique_visitors"] == 0


def test_get_click_stats_sums_results_across_shards():
    first_pipe = MagicMock()
    first_pipe.execute.return_value = [5, 2] + [1] * 72
    first_client = MagicMock()
    first_client.pipeline.return_value = first_pipe

    second_pipe = MagicMock()
    second_pipe.execute.return_value = [7, 3] + [2] * 72
    second_client = MagicMock()
    second_client.pipeline.return_value = second_pipe

    ring = MagicMock()
    ring.all_clients.return_value = [("shard0", first_client), ("shard1", second_client)]

    stats = get_click_stats("abc123", ring)

    assert stats["total_clicks"] == 12
    assert stats["unique_visitors"] == 5
    assert all(v == 3 for v in stats["hourly"].values())
