# Scalability Engineering Quest Evidence

This document maps the current Curtain implementation to the Scalability Engineering quest tiers and links the supporting documentation for each tier.

## Bronze Evidence

Bronze is the baseline: run a load test, simulate 50 concurrent users, and record latency and error-rate behavior.

Below is the screenshot showing the 50-user load-test run.
![Bronze Evidence](../docs/images/scalability/bronze_scale_evidence.png)

This run establishes the baseline before scale-out and caching work. In this baseline run, the measured p95 response time was `38.06 ms` and the error rate was `0.00%`, which gives us the reference point for later 200-user and cache-backed high-concurrency tests.
That is `0.03806 s` at p95.

Relevant docs:

- [../docs/LOAD_TESTING.md](../docs/LOAD_TESTING.md) explains the available k6 scripts and how the baseline load tests are run.
- [../README.md](../README.md) documents how to start the stack before running load tests.

## Silver Evidence

Silver is about horizontal scale-out: 200 concurrent users, multiple app instances, and Nginx load balancing while keeping latency under control.

Below is the screenshot showing the 200-user load-test run.
![Silver 200 User Evidence](../docs/images/scalability/silver_scale_200.png)

Below is the screenshot showing two app containers plus the Nginx load balancer in Docker.
![Silver multiple instances Evidence](../docs/images/scalability/silver_scale_docker_ps.png)

These prove that the service was scaled horizontally with multiple app instances and a dedicated traffic-splitting layer, rather than relying on a single container.
In the 200-user run, the measured p95 response time was `218.17 ms`, which is `0.21817 s`, and the error rate was `0.00%`. This stays well under the Silver requirement of keeping response times below `3 s`.

Relevant docs:

- [../docs/LOAD_TESTING.md](../docs/LOAD_TESTING.md) documents the load-test entrypoints and the scaled runtime topology.
- [../README.md](../README.md) summarizes the current architecture, including the dual app containers and Nginx front door.

## Gold Evidence

Gold is about caching, bottleneck reduction, and surviving high-concurrency traffic with a low error rate.

Below is the screenshot showing the 500-user load-test run.
![Gold 500 User Evidence](../docs/images/scalability/gold_scale_500.png)

In the 500-user run, the measured p95 response time was `1.01 s` and the error rate was `0.00%`. This satisfies the Gold-tier stability requirement of staying under `5%` errors during the high-concurrency run.

Below is the screenshot showing analytics caching behavior. The first request returns `X-Cache: MISS`, and the follow-up request returns `X-Cache: HIT`, proving that the hot read path is being served from Redis-backed cache instead of recomputing from PostgreSQL on every request.
![Gold Redis Cache Evidence](../docs/images/scalability/gold_scale_cache.png)

Bottleneck report:

Before optimization, repeated read-heavy endpoints were limited by unnecessary PostgreSQL work and repeated aggregation on hot paths. The fix was to add Redis-backed caching for URL list/detail and analytics reads, while also keeping two app instances behind Nginx so traffic is split across multiple workers instead of concentrating on one process.

Relevant docs:

- [../docs/REDIS_INFO.md](../docs/REDIS_INFO.md) explains the Redis roles used for caching, counters, and sharded redirect tracking.
- [../docs/LOAD_TESTING.md](../docs/LOAD_TESTING.md) documents the higher-concurrency test scenarios and what to watch during them.
- [../README.md](../README.md) describes the current scaled architecture and the cache-backed read flow.
