# Failure Modes

This document describes the current failure behavior of the running architecture.

## Global Behavior

### Source of Truth and Degraded Paths

- PostgreSQL is the durable store for `users`, `urls`, and `events`
- `redis` is the short-code counter store
- `redis_cache` is the read-through cache store
- `redis_shard0` and `redis_shard1` back redirect counters and streams

### Error Envelopes

- most routes use `{"error":"..."}` on failure
- user validation routes use `{"errors":{"field":"..."}}`

### Unknown Routes

Unknown Flask routes return `404` with:

```json
{"error":"Not found"}
```

### Unhandled Exceptions

Unhandled exceptions return `500` with:

```json
{"error":"Internal server error"}
```

## Dependency Failure Behavior

### PostgreSQL Down

- read and write routes usually fail with `500`
- there is no read-only fallback mode

### Counter Redis Down

- `POST /urls` and `POST /shorten-ui` still attempt URL creation
- short-code generation falls back to PostgreSQL max-id state

### Cache Redis Down

- cached endpoints continue to work
- responses behave like cache misses

### Click Shard Redis Down

- redirect requests still try to succeed
- `record_click()` swallows shard errors and logs a warning
- the HTTP redirect should still return `302` unless some later database action fails
- shard failure and failover counters are emitted for observability

## Endpoint Notes

### `GET /health`

- returns `200` with `status` and `instance` when the app is healthy
- if both app containers are down behind Nginx, clients see `502 Bad Gateway`

### `GET /debug/fail`

- returns `404` when `ENABLE_INCIDENT_DEBUG_ROUTES=false`
- raises a runtime error and returns `500` when enabled

### `POST /users`

- validation failures return `422`
- duplicate email returns `422`
- unexpected database errors return `500`

### `POST /urls`

- validation failures return `400`
- duplicate active URLs return the existing mapping with `200`
- new mappings return `201`
- successful responses include `X-Cache: BYPASS`

### `GET /urls`
### `GET /urls/<id>`
### `GET /urls/<id>/analytics`

- these routes use cache read-through behavior
- successful responses include `X-Cache: HIT` or `MISS`
- cache failures degrade to direct PostgreSQL reads

### Redirect Routes

- `GET /r/<short_code>`
- `GET /urls/short/<short_code>`
- `GET /urls/<short_code>/redirect`

Current behavior:

- active short codes return `302`
- inactive or missing short codes return `404`
- redirects append an immediate PostgreSQL `redirect` event
- redirects also attempt sharded Redis click writes and stream writes

## Container-Level Failure Behavior

### One App Container Down

- Nginx can still forward traffic to the remaining app container
- `CurtainInstanceDown` should fire after Prometheus detects fewer than 2 healthy targets

### Both App Containers Down

- users receive `502` from Nginx
- `CurtainServiceDown` should fire

### Stream Consumer Down

- redirect traffic can still succeed
- PostgreSQL stops receiving stream-flushed redirect events from Redis Streams
- immediate redirect events written in the request path still continue
