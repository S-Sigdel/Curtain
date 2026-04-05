import os
from functools import lru_cache

from redis import Redis

from app.shard_ring import ResilientShardRing

REDIS_SOCKET_TIMEOUT_SECONDS = float(os.environ.get("REDIS_SOCKET_TIMEOUT_SECONDS", "0.05"))
REDIS_CONNECT_TIMEOUT_SECONDS = float(os.environ.get("REDIS_CONNECT_TIMEOUT_SECONDS", "0.05"))


def _redis_client_from_url(url: str) -> Redis:
    return Redis.from_url(
        url,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
    )


def _redis_client(host: str, port: int) -> Redis:
    return Redis(
        host=host,
        port=port,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
    )


@lru_cache(maxsize=1)
def get_counter_redis():
    # Reuse a single client per process so routes do not reconnect on every request.
    return _redis_client_from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@lru_cache(maxsize=1)
def get_cache_redis():
    # Keep the cache client separate from the counter client for operational isolation.
    return _redis_client_from_url(os.environ.get("CACHE_REDIS_URL", "redis://localhost:6380/0"))


@lru_cache(maxsize=1)
def get_shard_ring() -> ResilientShardRing:
    """
    Build and cache the click-counter shard ring for the lifetime of the process.

    Reads REDIS_SHARDS (comma-separated host:port pairs).  Falls back to a
    single shard using REDIS_URL so the app works without any config changes
    until docker-compose is updated in Phase 5.

    Example:
        REDIS_SHARDS=redis_shard0:6379,redis_shard1:6379
    """
    shards_env = os.environ.get("REDIS_SHARDS", "").strip()
    if shards_env:
        addrs = [addr.strip() for addr in shards_env.split(",") if addr.strip()]
    else:
        # Fallback: single shard using the existing counter Redis URL
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        # Parse host:port from URL (redis://host:port/db)
        parts = url.split("//", 1)[-1].split("/")[0]
        addrs = [parts]

    shards = [
        {
            "id": f"shard{i}",
            "client": _redis_client(addr.split(":")[0], int(addr.split(":")[1])),
        }
        for i, addr in enumerate(addrs)
    ]
    return ResilientShardRing(shards)
