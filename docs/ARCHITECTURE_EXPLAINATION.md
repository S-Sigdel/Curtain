# Architecture Explanation

This document explains how data moves through Curtain and how the main services work together.

## High-Level Shape

Curtain is a horizontally scaled Flask application running behind Nginx.

At a high level:

- Nginx is the public entry point
- `app` and `app2` are the identical Flask application containers
- PostgreSQL is the durable source of truth
- Redis is split by responsibility instead of using one shared instance for everything
- Prometheus, Grafana, notifier, and Discord relay provide observability and alerting

The system is designed so that reads can be fast, writes stay durable, and monitoring can detect problems quickly.

## Request Entry Flow

Every external request first hits Nginx.

Nginx then forwards the request to one of the two Flask app containers:

- `app`
- `app2`

These two services run the same code and expose the same routes. They are separate instances only for horizontal scaling and redundancy.

## PostgreSQL: Source of Truth

PostgreSQL stores the durable application data:

- `users`
- `urls`
- `events`

If Redis is empty or unavailable for noncritical paths, PostgreSQL still holds the real persisted state. That is why PostgreSQL is the source of truth in this architecture.

## URL Creation Flow

When a client creates a short URL through `POST /urls`:

1. The Flask app validates the JSON payload.
2. The app asks the counter Redis for the next numeric value using the `url:counter` key.
3. That value is converted into a Base62 short code.
4. The URL record is written to PostgreSQL.
5. A `created` event is also written to PostgreSQL.
6. Related cache keys are invalidated so future reads do not return stale data.

If the counter Redis is unavailable, the app falls back to PostgreSQL state to generate the next short code.

## Read and Cache Flow

Some read-heavy endpoints use Redis as a read-through cache:

- `GET /urls`
- `GET /urls/<id>`
- `GET /urls/<id>/analytics`

The flow is:

1. The app receives the request.
2. It builds a deterministic cache key.
3. It checks `redis_cache` first.
4. If the cache contains the value, the app returns it immediately.
5. If the cache misses, the app queries PostgreSQL.
6. The app serializes the result and stores it back in Redis with a TTL.
7. The response is returned to the client.

This means Redis is not the primary database. It is an accelerator for repeated reads.

## Redirect Flow

When a user visits a short URL such as `GET /r/<short_code>`:

1. The app resolves the short code to the original URL.
2. Redirect metadata may come from cache if it was already looked up recently.
3. The app records click activity in the sharded Redis layer.
4. The app writes a `redirect` event to PostgreSQL.
5. The client receives a `302` response pointing to the original destination.

This path is designed to stay fast because redirect traffic is often the hottest path in a URL shortener.

## Sharded Redis Click Tracking

Curtain uses two Redis shards for real-time redirect tracking:

- `redis_shard0`
- `redis_shard1`

The app uses a consistent hash ring to decide which shard owns a given short code.

For each redirect, the app writes several pieces of real-time data to the owning shard:

- total click count
- hourly click bucket
- HyperLogLog unique-visitor sketch
- Redis Stream message

This is useful because it separates fast, high-volume click accounting from the main relational database.

## Stream Consumer Flow

The `stream_consumer` service runs separately from the Flask app.

Its job is to read Redis Stream entries from the click shards and flush them into PostgreSQL in batches.

The flow is:

1. Redirect traffic appends stream messages into the Redis shard.
2. `stream_consumer` reads those messages using consumer groups.
3. It resolves short codes to URL ids.
4. It bulk-inserts redirect events into PostgreSQL.
5. It acknowledges the stream messages only after the database write succeeds.

This creates an at-least-once pipeline from Redis Streams into PostgreSQL.

## Why Redis Is Split by Responsibility

Curtain uses multiple Redis roles because each one solves a different problem:

- `redis`
  Used for monotonic short-code allocation
- `redis_cache`
  Used for cached API responses
- `redis_shard0` and `redis_shard1`
  Used for real-time click counters and streams

This keeps hot traffic patterns isolated from each other. Cache churn cannot interfere with short-code generation, and click-tracking load does not need to share memory behavior with general API caching.

## Monitoring and Alert Flow

Each Flask app exposes `/metrics`.

Prometheus scrapes those metrics from both app containers. Grafana then queries Prometheus to display dashboards such as:

- latency
- traffic
- error rate
- saturation

The notifier service polls Prometheus alerts and sends new firing alerts to the internal Discord relay. The relay then forwards them to the configured Discord webhook.

So the observability flow is:

1. app emits logs and metrics
2. Prometheus collects metrics
3. Grafana visualizes them
4. notifier checks alert state
5. Discord relay sends notifications outward

## Failure Handling Philosophy

The architecture tries to degrade gracefully where possible:

- cache failures behave like cache misses
- counter Redis failures fall back to PostgreSQL-backed short-code generation
- redirect click shard failures are logged and may fail over to another shard
- PostgreSQL remains the durable system of record

This means not every Redis issue becomes a full outage, but PostgreSQL remains critical for correctness and durability.

## Summary

Curtain is a layered architecture:

- Nginx handles entry and traffic distribution
- Flask handles request logic
- PostgreSQL stores durable truth
- Redis accelerates reads and tracks real-time click activity
- the stream consumer moves sharded click events into durable storage
- Prometheus and Grafana provide visibility
- notifier and Discord relay provide operational alerts

The main design idea is simple: keep the app responsive on hot paths, keep durable state in PostgreSQL, and make failures visible quickly.
