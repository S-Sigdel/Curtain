# Incident Response

This document describes the Silver-tier monitoring and alerting setup.

## Stack

The incident-response stack adds:

- Prometheus for metric scraping and alert evaluation
- a notifier service that polls Prometheus firing alerts every 15 seconds
- a small Discord relay service that converts internal alert webhooks into Discord webhook posts

Services are defined in [docker-compose.yml](/home/pacific/Programming/hackathons/Curtain/docker-compose.yml).

## Endpoints

- Prometheus: `http://localhost:9090`
- Manual relay test: `http://localhost:8080/alert`
- App metrics: `http://localhost:5000/metrics`
- Public health check: `http://localhost:5000/health`

## Alert Rules

Alert rules live in:

- [monitoring/alerts.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/alerts.yml)

Current alerts:

- `CurtainServiceDown`
  Fires when Prometheus cannot scrape any app instance for 1 minute.
- `CurtainHighErrorRate`
  Fires when 5xx responses exceed 5 percent of total requests for 2 minutes.

The 15-second scrape, 15-second evaluation, and 15-second notifier polling keep both alerts within the 5-minute requirement.

## Notification Path

The notifier posts new firing alerts to the internal relay at `http://discord_relay:8080/alert`.
The relay then forwards the alert message to the Discord webhook stored in `DISCORD_WEBHOOK_URL`.

For local verification from the host, the relay is also exposed at `http://localhost:8080/alert`.

Relevant files:

- [monitoring/prometheus_notifier.py](/home/pacific/Programming/hackathons/Curtain/monitoring/prometheus_notifier.py)
- [monitoring/discord_webhook_relay.py](/home/pacific/Programming/hackathons/Curtain/monitoring/discord_webhook_relay.py)

## Fire Drill

Start the full stack:

```bash
docker compose up --build -d
```

### Service Down

Stop both app instances:

```bash
docker compose stop app app2
```

Expected outcome:

- Prometheus loses all `curtain-app` scrape targets
- `CurtainServiceDown` enters firing state after 1 minute
- Discord receives a notification shortly after

Bring the service back:

```bash
docker compose start app app2
```

### High Error Rate

The app exposes a gated drill endpoint at `GET /debug/fail`.
It only returns a `500` when `ENABLE_INCIDENT_DEBUG_ROUTES=true`.

If you change that flag in `.env`, recreate the app containers before running the drill:

```bash
docker compose up -d --force-recreate app app2 nginx
```

Generate sustained failures:

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/errorRateTest.js
```

Expected outcome:

- the app emits `500` responses for at least 2 minutes
- `CurtainHighErrorRate` enters firing state
- Discord receives a notification

## Verification Commands

```bash
docker compose ps
docker compose logs -f prometheus
docker compose logs -f notifier
docker compose logs -f discord_relay
curl -s http://localhost:9090/api/v1/rules
curl -s http://localhost:9090/api/v1/alerts
curl -i http://localhost:8080/health
```
