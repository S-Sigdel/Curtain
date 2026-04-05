# Deployment Guide

This document explains how to deploy Curtain using Docker Compose on a single host and how to roll back safely if the new version is unhealthy.

## Deployment Platform

The deployment model documented here is:

- one host
- Docker Engine
- Docker Compose
- the services defined in `docker-compose.yml`

This matches the current repository structure and runtime assumptions.

## Services Involved

The main deployable services are:

- `app`
- `app2`
- `nginx`
- `stream_consumer`
- `prometheus`
- `grafana`
- `promlens`
- `notifier`
- `discord_relay`
- `db`
- `redis`
- `redis_cache`
- `redis_shard0`
- `redis_shard1`

In most normal application rollouts, the critical application-tier services are:

- `app`
- `app2`
- `nginx`
- `stream_consumer`

## Prerequisites

Before deploying:

- Docker and Docker Compose must be installed on the target host
- the repository must be present on the target host
- required environment variables must be configured in `.env`
- ports such as `5000`, `3000`, `8080`, `8081`, and `9090` must be available if those services are exposed

## Initial Deployment

To deploy the stack for the first time:

```bash
uv sync
docker compose up --build -d
```

Then verify:

```bash
docker compose ps
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
```

If you need seeded challenge data:

```bash
docker compose exec app uv run python scripts/reset_db.py
docker compose exec app uv run python scripts/seed_csv.py
```

## Normal Application Deployment

When you have a new version of the application code, use this process.

### 1. Update the code on the host

How you do this depends on your workflow, but the common approach is to pull the latest commit:

```bash
git pull
```

### 2. Rebuild and recreate the application tier

```bash
docker compose up --build -d --force-recreate app app2 nginx stream_consumer
```

This rebuilds the containers that depend on the application code and restarts them with the new version.

### 3. Verify the rollout

```bash
docker compose ps
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
docker compose logs --tail=100 app app2 nginx
```

Optional functional checks:

```bash
curl -i http://localhost:5000/urls
curl -i http://localhost:5000/events
```

Optional test verification:

```bash
docker compose exec app uv run pytest -q
```

## Monitoring During Deployment

During and after rollout, check:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- PromLens: `http://localhost:8081`

Signals to watch:

- health endpoint stays available
- error rate does not spike
- latency remains normal
- both app instances are healthy

## Rollback Strategy

Rollback in this deployment model means:

- return the code on the host to the last known-good revision
- rebuild the affected containers
- recreate the application tier

Because this project uses Docker Compose on a single host, rollback is code-and-container based, not a platform-managed blue/green or canary rollback.

## Rollback Steps

### 1. Identify the last known-good commit

Use your git history to locate the previous healthy revision.

Example:

```bash
git log --oneline
```

### 2. Check out the known-good revision

Example:

```bash
git checkout <known-good-commit>
```

If your workflow uses branches instead of detached commits, switch back to the last good branch or tag instead.

### 3. Rebuild and recreate the application tier

```bash
docker compose up --build -d --force-recreate app app2 nginx stream_consumer
```

### 4. Verify recovery

```bash
docker compose ps
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
docker compose logs --tail=100 app app2 nginx
```

## Fast Recovery Commands

If containers are unhealthy and you need a quick recreation of the app tier:

```bash
docker compose start app app2 nginx
docker compose up -d --force-recreate app app2 nginx stream_consumer
```

If the issue is isolated to Redis shards:

```bash
docker compose start redis_shard0 redis_shard1
docker compose up -d --force-recreate redis_shard0 redis_shard1
```

## Database and Seed Data Notes

- PostgreSQL uses a named volume, so normal app rollouts do not wipe persistent data
- Redis services also use named volumes
- do not run `scripts/reset_db.py` during normal production rollback unless you intentionally want to destroy and recreate challenge tables

## Recommended Rollback Trigger

Roll back if any of the following happen after deployment:

- `/health` stops returning `200`
- both app instances do not stay healthy
- error rate rises and stays elevated
- critical API routes fail
- the new version causes repeated incidents visible in Grafana or Prometheus alerts

## Summary

For this repo, deployment is Docker Compose based:

1. update code
2. rebuild and recreate the application tier
3. verify health and telemetry

Rollback is:

1. return to the last known-good code revision
2. rebuild and recreate the application tier
3. verify health again
