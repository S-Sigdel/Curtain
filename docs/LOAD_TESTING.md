# Load Testing

This repository includes k6 scripts for baseline service checks, create-path load, redirect load, cached reads, error-rate drills, and shard-failover demos.

## Current Runtime Topology

- `app` and `app2` run Gunicorn with 2 workers each
- `nginx` load-balances both app containers
- PostgreSQL stores durable application data
- `redis_cache` backs cached read endpoints
- `redis_shard0` and `redis_shard1` back redirect counters and streams

## Available Scripts

- [loadtests/loadTest.js](/home/pacific/Programming/hackathons/Curtain/loadtests/loadTest.js): baseline `GET /health`
- [loadtests/shortenTest.js](/home/pacific/Programming/hackathons/Curtain/loadtests/shortenTest.js): create unique URLs
- [loadtests/redirectTest.js](/home/pacific/Programming/hackathons/Curtain/loadtests/redirectTest.js): redirect traffic
- [loadtests/highReadTest.js](/home/pacific/Programming/hackathons/Curtain/loadtests/highReadTest.js): hot cached reads
- [loadtests/errorRateTest.js](/home/pacific/Programming/hackathons/Curtain/loadtests/errorRateTest.js): incident drill against `/debug/fail`
- [loadtests/shardFailoverDemo.js](/home/pacific/Programming/hackathons/Curtain/loadtests/shardFailoverDemo.js): shard-failure demo traffic

## Start the Stack

```bash
docker compose up --build -d
```

For read and redirect tests, seed data first:

```bash
docker compose exec app uv run python scripts/reset_db.py
docker compose exec app uv run python scripts/seed_csv.py
```

## Baseline Health Load

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

## Create Load

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/shortenTest.js
```

## URL Read Load

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -e URL_ID=1 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/redirectTest.js
```

This script reads `GET /urls/<id>`. Use an existing `URL_ID` from your database.

## Cached Read Load

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -e URL_ID=1 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/highReadTest.js
```

This script verifies `X-Cache` headers on the hot `GET /urls/<id>` path.

## What To Watch

- Nginx continues serving traffic while one app instance is down
- cached endpoints flip from `MISS` to `HIT`
- shard failures and failovers appear in Prometheus/Grafana during redirect demos
