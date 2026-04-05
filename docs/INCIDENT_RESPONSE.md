# Incident Response

Curtain includes a local incident-response stack built around Prometheus, Grafana, an alert notifier, and a Discord relay.

## Stack

- Prometheus scrapes `/metrics` from `app` and `app2`
- Grafana displays the `Curtain Command Center` dashboard
- `notifier` polls Prometheus alert state every 15 seconds
- `discord_relay` receives internal alert payloads and forwards them to Discord

Relevant files:

- [docker-compose.yml](/home/pacific/Programming/hackathons/Curtain/docker-compose.yml)
- [monitoring/prometheus.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/prometheus.yml)
- [monitoring/alerts.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/alerts.yml)
- [monitoring/prometheus_notifier.py](/home/pacific/Programming/hackathons/Curtain/monitoring/prometheus_notifier.py)
- [monitoring/discord_webhook_relay.py](/home/pacific/Programming/hackathons/Curtain/monitoring/discord_webhook_relay.py)
- [docs/RUNBOOK.md](/home/pacific/Programming/hackathons/Curtain/docs/RUNBOOK.md)

## Endpoints

- App health: `http://localhost:5000/health`
- App metrics: `http://localhost:5000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Relay health: `http://localhost:8080/health`
- Manual relay post target: `http://localhost:8080/alert`

## Current Alert Rules

- `CurtainServiceDown`: fewer than 1 healthy app targets for 1 minute
- `CurtainInstanceDown`: fewer than 2 healthy app targets for 1 minute
- `CurtainHighErrorRate`: 5xx rate above 5 percent for 2 minutes
- `CurtainRedisShardFailures`: more than 5 shard failures in 1 minute

## Notification Flow

1. Prometheus evaluates alert rules.
2. `notifier` fetches `/api/v1/alerts`.
3. New firing alerts are posted to `http://discord_relay:8080/alert`.
4. `discord_relay` forwards the alert batch to the configured Discord webhook.

## Fire Drills

### Full Service Down

```bash
docker compose stop app app2
```

Expected result:

- `CurtainServiceDown` fires
- Grafana traffic collapses
- Discord receives an alert after Prometheus and notifier polling windows elapse

Recover:

```bash
docker compose start app app2
```

### High Error Rate

Enable the drill route by setting `ENABLE_INCIDENT_DEBUG_ROUTES=true` in `.env`, then recreate the app tier:

```bash
docker compose up -d --force-recreate app app2 nginx
```

Then drive sustained failures:

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/errorRateTest.js
```

### Redis Shard Failure Demo

Drive redirect traffic, then interrupt a shard:

```bash
docker compose stop redis_shard0
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/shardFailoverDemo.js
```

Expected result:

- redirect traffic may continue through failover
- `redis_shard_failures_total` and `redis_shard_failovers_total` increase
- `CurtainRedisShardFailures` can fire if failures cross the rule threshold
