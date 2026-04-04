"""
Consistent hash ring over Redis shard instances.

Each short code is deterministically mapped to a shard via MD5 hashing with
virtual nodes to smooth load distribution. ResilientShardRing extends the base
ring with automatic failover: if the primary shard is unreachable, traffic is
walked around the ring to the next healthy node.
"""

import bisect
import hashlib
from typing import Tuple

from redis import Redis, ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError


# More virtual nodes → smoother distribution but larger ring structure.
# 150 per shard keeps the ring small while reducing max imbalance to ~5%.
VIRTUAL_NODES = 150


class AllShardsDownError(Exception):
    """Raised when no healthy Redis shard can be found."""


def _md5_int(key: str) -> int:
    return int(hashlib.md5(key.encode(), usedforsecurity=False).hexdigest(), 16)


class ShardRing:
    """
    Consistent hash ring. Thread-safe for reads after construction.

    Usage::

        ring = ShardRing([
            {"id": "shard0", "client": Redis.from_url("redis://shard0:6379/0")},
            {"id": "shard1", "client": Redis.from_url("redis://shard1:6379/0")},
        ])
        shard_id, client = ring.get_shard("abc123")
    """

    def __init__(self, shards: list):
        """
        Args:
            shards: list of dicts with keys ``id`` (str) and ``client`` (Redis).
        """
        self._ring: dict[int, str] = {}          # hash position → shard id
        self._sorted_keys: list[int] = []        # sorted ring positions
        self._clients: dict[str, Redis] = {}     # shard id → Redis client

        for shard in shards:
            self._add_shard(shard["id"], shard["client"])

        self._sorted_keys = sorted(self._ring.keys())

    def _add_shard(self, shard_id: str, client: Redis):
        self._clients[shard_id] = client
        for i in range(VIRTUAL_NODES):
            pos = _md5_int(f"{shard_id}:{i}")
            self._ring[pos] = shard_id

    def get_shard(self, key: str) -> Tuple[str, Redis]:
        """Return (shard_id, Redis client) for the given key."""
        if not self._sorted_keys:
            raise AllShardsDownError("Shard ring is empty")

        h = _md5_int(key)
        idx = bisect.bisect_left(self._sorted_keys, h)
        if idx >= len(self._sorted_keys):
            idx = 0  # wrap around
        shard_id = self._ring[self._sorted_keys[idx]]
        return shard_id, self._clients[shard_id]

    @property
    def shard_ids(self) -> list:
        return list(self._clients.keys())

    def all_clients(self) -> list[Tuple[str, Redis]]:
        """Return all (shard_id, client) pairs — useful for fan-out reads."""
        return list(self._clients.items())


class ResilientShardRing(ShardRing):
    """
    ShardRing with automatic failover.

    If the primary shard for a key is unreachable (ConnectionError or
    TimeoutError), the ring walks clockwise to the next healthy shard.
    Raises AllShardsDownError only when every shard has been tried.
    """

    def get_shard(self, key: str) -> Tuple[str, Redis]:
        if not self._sorted_keys:
            raise AllShardsDownError("Shard ring is empty")

        h = _md5_int(key)
        start_idx = bisect.bisect_left(self._sorted_keys, h)
        if start_idx >= len(self._sorted_keys):
            start_idx = 0

        n = len(self._sorted_keys)
        seen_shards: set[str] = set()

        for step in range(n):
            idx = (start_idx + step) % n
            shard_id = self._ring[self._sorted_keys[idx]]
            if shard_id in seen_shards:
                continue
            seen_shards.add(shard_id)
            client = self._clients[shard_id]
            try:
                client.ping()
                return shard_id, client
            except (RedisConnectionError, RedisTimeoutError):
                continue  # try next shard

        raise AllShardsDownError("No healthy Redis shards available")
