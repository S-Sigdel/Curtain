# Capacity and Limits

This document records the current capacity assumptions, tested load levels, and known limits of the Curtain system.

## Scope

This is not a claim that the system can handle arbitrary internet-scale traffic. It is a summary of:

- what the current architecture was designed to handle
- what load levels were actually tested
- what bottlenecks were reduced
- what limits still exist

## Deployment Assumptions

The current deployment model is:

- one host
- Docker Compose
- two Flask app containers
- one Nginx load balancer
- one PostgreSQL database
- separate Redis roles for counter, cache, and sharded click tracking

This means current capacity claims are based on a single-host horizontally scaled application tier, not a multi-region or autoscaled production platform.

## Tested Load Levels

The system has been tested with the following concurrency levels:

- Bronze baseline: `50` concurrent users
- Silver scale-out: `200` concurrent users
- Gold cached high-read scenario: `500` concurrent users

Observed results from the current evidence:

- `50` users: p95 `38.06 ms` (`0.03806 s`), error rate `0.00%`
- `200` users: p95 `218.17 ms` (`0.21817 s`), error rate `0.00%`
- `500` users: p95 `1.01 s`, error rate `0.00%`

These results come from the current k6 test runs documented in the scalability evidence.

## Capacity Expectations

Based on the current architecture and tests, the practical expectations are:

- the app tier can handle baseline and moderate load by splitting traffic across `app` and `app2`
- cached read paths are significantly more scalable than uncached database-backed reads
- the system remains within the quest threshold of under `5%` error rate during the documented 500-user cached-read scenario
- the Silver-tier latency requirement of under `3s` p95 is comfortably met in the tested 200-user run

## Where Capacity Comes From

The current capacity improvements come from a small set of major design decisions:

- Nginx spreads requests across two app instances instead of one
- hot read endpoints use Redis-backed caching to avoid repeated PostgreSQL work
- redirect click tracking is moved onto sharded Redis instead of doing all hot-path counting directly in PostgreSQL
- the stream consumer batches Redis Stream writes into PostgreSQL asynchronously

These choices reduce pressure on the slowest shared components during heavy traffic.

## Known Limits

The current system still has important limits.

### Single-Host Limit

The deployment is still a single-host Docker Compose stack. If that host fails, the whole deployment fails.

### PostgreSQL Remains Critical

PostgreSQL is still the durable source of truth. Many core flows depend on it:

- user data
- URL records
- event persistence
- analytics recomputation on cache miss

If PostgreSQL is unavailable, many routes fail even if Redis is healthy.

### Redis Shard Memory Limits

The click shards are configured with:

- `--maxmemory 64mb`
- `--maxmemory-policy allkeys-lru`

That means these shards are intentionally bounded and are not sized for unbounded growth.

### Cache Is an Optimization, Not Durability

`redis_cache` improves speed, but it is not a source of truth. A cache miss still depends on PostgreSQL being healthy and responsive.

### Tested Scenarios Are Narrower Than Full Production Traffic

The strongest documented Gold run is a high-read cached scenario. That is useful and valid, but it does not prove that every mixed workload at the same concurrency will behave identically.

### Two App Instances Is Helpful but Not Unlimited

Running two application containers improves concurrency and resilience, but it is still a small fleet. Capacity would need to be revalidated if traffic shape, data volume, or endpoint mix changes significantly.

## Failure and Degradation Expectations

Some components degrade gracefully:

- cache Redis failure behaves like a cache miss
- counter Redis failure falls back to PostgreSQL-backed short-code generation
- click shard failures are logged and may fail over to another shard

But some failures are still hard limits:

- PostgreSQL outage
- full host outage
- both app instances unavailable at once

## How To Revalidate Capacity

If the system changes materially, rerun:

- baseline health load
- 200-user scale-out load
- 500-user cached-read load
- create-path load
- redirect-path load

Also compare:

- p95 latency
- error rate
- traffic distribution across app instances
- shard failure/failover counters
- PostgreSQL behavior under load

## Related Docs

- [LOAD_TESTING.md](LOAD_TESTING.md)
- [ARCHITECTURE_EXPLAINATION.md](ARCHITECTURE_EXPLAINATION.md)
- [REDIS_INFO.md](REDIS_INFO.md)
- [FAILURE_MODES.md](FAILURE_MODES.md)
- [../evidence/SCALABILITY_EVIDENCE.md](../evidence/SCALABILITY_EVIDENCE.md)
