# Redis Usage

Curtain currently uses four Redis roles, not one shared instance for everything.

## Redis Topology

- `redis`
  Used for monotonic short-code allocation via `url:counter`
- `redis_cache`
  Used for cached JSON responses
- `redis_shard0`
  Used for real-time click counters and streams
- `redis_shard1`
  Used for real-time click counters and streams

The clients are built in [app/redis_client.py](/home/pacific/Programming/hackathons/Curtain/app/redis_client.py).

## Counter Redis

Used by [app/services/url_shortener.py](/home/pacific/Programming/hackathons/Curtain/app/services/url_shortener.py).

Key:

- `url:counter`

Flow:

1. Seed `url:counter` from the current PostgreSQL max URL id with `SETNX`.
2. Increment with `INCR`.
3. Base62-encode the number.
4. Left-pad it to the configured short-code width.

If this Redis is unavailable, the app falls back to PostgreSQL max-id generation.

## Cache Redis

Used by [app/cache.py](/home/pacific/Programming/hackathons/Curtain/app/cache.py).

Key families:

- `cache:url:<id>`
- `cache:url:redirect:<short_code>`
- `cache:url:list`
- `cache:url:list:user:<user_id>`
- `cache:url:list:is_active:<bool>`
- `cache:url:list:user:<user_id>:is_active:<bool>`
- `cache:analytics:url:<id>`

Cached routes:

- `GET /urls`
- `GET /urls/<id>`
- `GET /urls/<id>/analytics`
- redirect lookup metadata for short-code redirects

## Sharded Click Redis

Used by [app/services/click_counter.py](/home/pacific/Programming/hackathons/Curtain/app/services/click_counter.py) and [app/stream_consumer.py](/home/pacific/Programming/hackathons/Curtain/app/stream_consumer.py).

Per short code, the owning shard stores:

- `clicks:{short_code}` total counter
- `clicks:{short_code}:ts:{YYYY-MM-DD:HH}` hourly buckets with 72-hour TTL
- `clicks:{short_code}:uv` HyperLogLog unique visitors
- `stream:clicks:{short_code}` Redis Stream entries

Shard ownership is determined by the consistent hash ring in [app/shard_ring.py](/home/pacific/Programming/hackathons/Curtain/app/shard_ring.py).

## Operational Behavior

- click writes are pipelined to keep redirect overhead low
- redirect traffic can fail over to another shard when the primary shard write fails
- shard failures and failovers are exposed as Prometheus counters
- `stream_consumer` reads stream entries and bulk-inserts redirect events into PostgreSQL
