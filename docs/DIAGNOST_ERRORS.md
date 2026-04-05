# Diagnose Errors

This document describes how to diagnose a service outage using the current dashboard, logs, and container topology.

## Scenario

Simulate a full app-tier outage:

```bash
docker compose stop app app2
```

## What Grafana Should Show

Open `http://localhost:3000` and load `Curtain Command Center`.

Typical signals:

- traffic drops toward zero
- error rate may spike because Nginx loses healthy upstreams
- latency becomes less meaningful once successful traffic collapses
- saturation falls as app processes stop serving requests

## What To Check Next

```bash
docker compose ps
docker compose logs --tail=100 app app2 nginx prometheus notifier discord_relay
curl -s http://localhost:9090/api/v1/alerts
```

Useful conclusions:

- if both app containers are down, the app tier is the fault domain
- if Prometheus is still up and firing alerts, the monitoring path is healthy
- if relay and notifier logs show forwarded alerts, the notification path is healthy

## Root Cause Pattern

When both `app` and `app2` are unavailable, Prometheus loses all `curtain-app` targets and `CurtainServiceDown` fires. Nginx may continue answering with `502`, but the failure is still in the application tier, not in Grafana or the alerting components.

## Recovery

```bash
docker compose start app app2
curl -i http://localhost:5000/health
curl -s http://localhost:9090/api/v1/alerts
```

Expected results:

- `/health` returns `200`
- Grafana traffic recovers
- the active alert clears after healthy scrapes resume
