# Redis Usage

This project uses two Redis services alongside PostgreSQL.

## Current Usage

The project separates Redis responsibilities:

Relevant files:

- [app/redis_client.py](/home/pacific/Programming/hackathons/Curtain/app/redis_client.py)
- [app/services/url_shortener.py](/home/pacific/Programming/hackathons/Curtain/app/services/url_shortener.py)
- [app/cache.py](/home/pacific/Programming/hackathons/Curtain/app/cache.py)

Current service split:

- `redis`
  Used for the short-code counter.
- `redis_cache`
  Used for cached API responses.

Current key usage:

- `url:counter`
  Used as the monotonic counter for generating new short codes.
- `cache:url:<id>`
  Cached `GET /urls/<id>` payloads.
- `cache:url:list`
  Cached `GET /urls` payloads without filters.
- `cache:url:list:user:<user_id>`
  Cached `GET /urls?user_id=<id>` payloads.
- `cache:analytics:url:<id>`
  Cached `GET /urls/<id>/analytics` payloads.

Flow:

1. Read the current maximum URL id from PostgreSQL if the counter is not initialized.
2. Seed `url:counter` with that value using `SETNX`.
3. Increment the Redis counter with `INCR`.
4. Convert the incremented value into a base62 short code.

The counter and cache are intentionally separated to make their operational roles clearer.

Benefits of this split:

- cache eviction policies cannot interfere with the short-code counter
- cache traffic and counter traffic are isolated
- it is easier to reason about memory use and failure impact
- the design reads more clearly for contributors and reviewers

## Recommended Cache Targets

The most useful cache targets in this repo are:

### `GET /urls/<id>`

This is a strong cache candidate because:

- it is read-heavy
- the response is small
- the row changes infrequently

Suggested key:

- `cache:url:<id>`

Suggested invalidation:

- delete the key on `PUT /urls/<id>`

Suggested TTL:

- 60 to 300 seconds

### `GET /urls`

This should also be cached when the request shape is simple, because listing URLs is core product behavior here.

Suggested keys:

- `cache:url:list`
- `cache:url:list:user:<user_id>`

Suggested invalidation:

- delete affected list keys when a URL is created or updated

Suggested TTL:

- 30 to 120 seconds

Notes:

- cache key design matters more here because query params change the result set
- keep the first version limited to supported filters such as `user_id`

### `GET /urls/<id>/analytics`

This is also a good cache target because it may aggregate events repeatedly for the same URL.

Suggested key:

- `cache:analytics:url:<id>`

Suggested invalidation:

- delete the analytics key when a new event is written for that URL
- delete it when the URL itself is updated

Suggested TTL:

- 30 to 120 seconds

## What Should Not Be Cached First

Do not start by caching every possible `/events` query shape.

Reasons:

- query combinations multiply key count quickly
- invalidation becomes harder
- the payoff is usually lower than caching the hot URL and analytics reads

## Recommended Read-Through Pattern

For cacheable reads:

1. Build a deterministic cache key.
2. Check Redis first.
3. If present, return the cached payload.
4. If missing, read from PostgreSQL.
5. Serialize the response.
6. Store it in Redis with TTL.
7. Return the response.

For writes:

1. Update PostgreSQL first.
2. Delete affected cache keys.
3. Let the next read repopulate the cache.

## Helpful Response Evidence

If caching is added, expose cache behavior in responses with a header such as:

- `X-Cache: HIT`
- `X-Cache: MISS`

That makes verification easier during load testing and local debugging.
