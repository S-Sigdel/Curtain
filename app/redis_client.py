import os
from functools import lru_cache

from redis import Redis


@lru_cache(maxsize=1)
def get_counter_redis():
    # Reuse a single client per process so routes do not reconnect on every request.
    return Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@lru_cache(maxsize=1)
def get_cache_redis():
    # Keep the cache client separate from the counter client for operational isolation.
    return Redis.from_url(os.environ.get("CACHE_REDIS_URL", "redis://localhost:6380/0"))
