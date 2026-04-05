# Runbook

Use this runbook for the current Prometheus alerts:

- `CurtainServiceDown`
- `CurtainInstanceDown`
- `CurtainHighErrorRate`
- `CurtainRedisShardFailures`

## Quick Links

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- App health: `http://localhost:5000/health`
- Relay health: `http://localhost:8080/health`

## First Checks

```bash
docker compose ps
docker compose logs --tail=100 app app2 nginx prometheus notifier discord_relay stream_consumer
curl -s http://localhost:9090/api/v1/alerts
```

## `CurtainServiceDown`

Meaning:

- Prometheus cannot scrape any app instance

Checks:

```bash
curl -i http://localhost:5000/health
docker compose ps
docker compose logs --tail=200 app app2 nginx db
```

Recovery:

```bash
docker compose start app app2 nginx
docker compose up -d --force-recreate app app2 nginx
```

## `CurtainInstanceDown`

Meaning:

- one of the two app containers is missing or unhealthy

Checks:

```bash
docker compose ps
docker compose logs --tail=200 app app2 nginx
```

Recovery:

```bash
docker compose up -d --force-recreate app app2 nginx
```

## `CurtainHighErrorRate`

Meaning:

- 5xx responses exceed 5 percent for 2 minutes

Checks:

```bash
docker compose logs --tail=200 app app2 nginx
curl -s http://localhost:9090/api/v1/alerts
```

Common causes:

- `/debug/fail` drill traffic with debug route enabled
- application exceptions
- database connectivity issues

## `CurtainRedisShardFailures`

Meaning:

- the redirect click path is encountering repeated shard write failures

Checks:

```bash
docker compose logs --tail=200 app app2
curl -s http://localhost:5000/metrics | grep redis_shard
docker compose ps redis_shard0 redis_shard1
```

Recovery:

```bash
docker compose start redis_shard0 redis_shard1
docker compose up -d --force-recreate redis_shard0 redis_shard1
```

Redirects may continue working during this incident, but real-time click counters and stream durability will be degraded.
