import json

from redis import RedisError

from app.redis_client import get_cache_redis

URL_DETAIL_TTL_SECONDS = 300
URL_LIST_TTL_SECONDS = 120
URL_ANALYTICS_TTL_SECONDS = 120


def url_detail_cache_key(url_id):
    return f"cache:url:{url_id}"


def url_list_cache_key(user_id=None, is_active=None):
    if user_id is None and is_active is None:
        return "cache:url:list"
    if user_id is None:
        return f"cache:url:list:is_active:{str(is_active).lower()}"
    if is_active is None:
        return f"cache:url:list:user:{user_id}"
    return f"cache:url:list:user:{user_id}:is_active:{str(is_active).lower()}"


def url_analytics_cache_key(url_id):
    return f"cache:analytics:url:{url_id}"


def get_cached_json(cache_key):
    try:
        payload = get_cache_redis().get(cache_key)
    except RedisError:
        return None

    if payload is None:
        return None

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")

    return json.loads(payload)


def set_cached_json(cache_key, payload, ttl_seconds):
    try:
        get_cache_redis().setex(cache_key, ttl_seconds, json.dumps(payload))
    except RedisError:
        return


def delete_cache_keys(*cache_keys):
    keys = [key for key in cache_keys if key]
    if not keys:
        return

    try:
        get_cache_redis().delete(*keys)
    except RedisError:
        return


def invalidate_url_cache(url_id, user_id=None):
    delete_cache_keys(
        url_detail_cache_key(url_id),
        url_analytics_cache_key(url_id),
        url_list_cache_key(),
        url_list_cache_key(is_active=True),
        url_list_cache_key(is_active=False),
        url_list_cache_key(user_id),
        url_list_cache_key(user_id, is_active=True),
        url_list_cache_key(user_id, is_active=False),
    )
