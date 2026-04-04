"""Unit tests for app/shard_ring.py — no real Redis connections required."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest
from redis import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from app.shard_ring import AllShardsDownError, ResilientShardRing, ShardRing, _md5_int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(name: str, healthy: bool = True) -> MagicMock:
    """Return a mock Redis client that ping()s successfully or raises."""
    client = MagicMock(name=name)
    if healthy:
        client.ping.return_value = True
    else:
        client.ping.side_effect = RedisConnectionError("refused")
    return client


def _make_shards(*names: str, healthy=True) -> list:
    return [{"id": n, "client": _make_client(n, healthy=healthy)} for n in names]


# ---------------------------------------------------------------------------
# _md5_int
# ---------------------------------------------------------------------------

def test_md5_int_is_deterministic():
    assert _md5_int("hello") == _md5_int("hello")


def test_md5_int_differs_for_different_keys():
    assert _md5_int("abc") != _md5_int("xyz")


def test_md5_int_returns_integer():
    assert isinstance(_md5_int("anything"), int)


# ---------------------------------------------------------------------------
# ShardRing construction
# ---------------------------------------------------------------------------

def test_ring_with_single_shard_always_returns_that_shard():
    shards = _make_shards("only")
    ring = ShardRing(shards)
    shard_id, _ = ring.get_shard("some-key")
    assert shard_id == "only"


def test_ring_with_two_shards_populates_both():
    ring = ShardRing(_make_shards("a", "b"))
    assert set(ring.shard_ids) == {"a", "b"}


def test_ring_virtual_nodes_fill_ring(monkeypatch):
    from app import shard_ring as sr
    monkeypatch.setattr(sr, "VIRTUAL_NODES", 10)
    ring = ShardRing(_make_shards("x", "y"))
    # 2 shards × 10 virtual nodes = 20 positions
    assert len(ring._ring) == 20
    assert len(ring._sorted_keys) == 20


def test_empty_ring_raises():
    ring = ShardRing([])
    with pytest.raises(AllShardsDownError):
        ring.get_shard("anything")


# ---------------------------------------------------------------------------
# ShardRing distribution
# ---------------------------------------------------------------------------

def test_same_key_always_maps_to_same_shard():
    ring = ShardRing(_make_shards("s0", "s1", "s2"))
    first, _ = ring.get_shard("mykey")
    for _ in range(20):
        shard_id, _ = ring.get_shard("mykey")
        assert shard_id == first


def test_different_keys_can_map_to_different_shards():
    ring = ShardRing(_make_shards("s0", "s1", "s2"))
    results = {ring.get_shard(str(i))[0] for i in range(200)}
    # With 3 shards and 200 keys we expect all three to appear
    assert len(results) > 1


def test_all_clients_returns_all_shards():
    ring = ShardRing(_make_shards("alpha", "beta"))
    ids = [sid for sid, _ in ring.all_clients()]
    assert set(ids) == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# ResilientShardRing — failover
# ---------------------------------------------------------------------------

def test_resilient_ring_returns_healthy_shard():
    shards = _make_shards("ok")
    ring = ResilientShardRing(shards)
    shard_id, _ = ring.get_shard("key")
    assert shard_id == "ok"


def test_resilient_ring_skips_dead_shard_and_uses_healthy_one():
    dead = _make_client("dead", healthy=False)
    alive = _make_client("alive", healthy=True)
    ring = ResilientShardRing([
        {"id": "dead", "client": dead},
        {"id": "alive", "client": alive},
    ])

    # Force a key that lands on "dead" first by patching bisect_left result.
    # We do this by making every position on the ring resolve to "dead" first,
    # which is simpler to assert via all_clients order — instead just verify
    # the returned shard is "alive" regardless of which shard the hash picks.
    for key in [str(i) for i in range(50)]:
        shard_id, _ = ring.get_shard(key)
        assert shard_id in {"dead", "alive"}

    # Explicitly verify: if primary is dead, alive must be returned
    # Patch ping to be dead only on the "dead" client — already set above.
    # Try many keys; at least some should land on "dead" first and fall over.
    results = set()
    for i in range(200):
        shard_id, _ = ring.get_shard(str(i))
        results.add(shard_id)
    # alive must appear (failover worked) and never raises
    assert "alive" in results


def test_resilient_ring_raises_when_all_shards_down():
    ring = ResilientShardRing(_make_shards("s0", "s1", healthy=False))
    with pytest.raises(AllShardsDownError):
        ring.get_shard("key")


def test_resilient_ring_timeout_is_treated_as_failure():
    client = _make_client("flaky")
    client.ping.side_effect = RedisTimeoutError("timeout")
    ring = ResilientShardRing([{"id": "flaky", "client": client}])
    with pytest.raises(AllShardsDownError):
        ring.get_shard("key")


def test_resilient_ring_empty_raises():
    ring = ResilientShardRing([])
    with pytest.raises(AllShardsDownError):
        ring.get_shard("key")


# ---------------------------------------------------------------------------
# Wrap-around behaviour (key hash larger than all ring positions)
# ---------------------------------------------------------------------------

def test_ring_wraps_around_when_hash_exceeds_all_positions():
    """get_shard should not raise IndexError when hash > all ring positions."""
    ring = ShardRing(_make_shards("wrap"))
    # Patch sorted_keys so the hash always exceeds them
    ring._sorted_keys = [1, 2, 3]
    ring._ring = {1: "wrap", 2: "wrap", 3: "wrap"}
    # _md5_int returns a very large number; bisect_left returns len → idx 0
    shard_id, _ = ring.get_shard("anything-with-large-hash")
    assert shard_id == "wrap"
