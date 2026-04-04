import os
from functools import lru_cache

from redis import Redis

from app.shard_ring import ResilientShardRing


@lru_cache(maxsize=1)
def get_counter_redis():
    # Reuse a single client per process so routes do not reconnect on every request.
    return Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@lru_cache(maxsize=1)
def get_cache_redis():
    # Keep the cache client separate from the counter client for operational isolation.
    return Redis.from_url(os.environ.get("CACHE_REDIS_URL", "redis://localhost:6380/0"))


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
        {"id": f"shard{i}", "client": Redis(host=addr.split(":")[0], port=int(addr.split(":")[1]))}
        for i, addr in enumerate(addrs)
    ]
    return ResilientShardRing(shards)
