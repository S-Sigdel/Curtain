#   Diagnost Errors

This document shows how to diagnose a fake incident using only the dashboard and logs.

## Scenario

We simulate a real outage by stopping both app containers:

```bash
docker compose stop app app2
```

## What The Dashboard Shows

Open Grafana at `http://localhost:3000` and load `Curtain Command Center`.

Expected signal changes:

- `Traffic` falls toward zero because requests stop being served
- `Error Rate` may spike briefly if Nginx continues receiving requests without healthy upstreams
- `Latency p95` becomes less useful during a total outage because successful request volume collapses
- `Saturation` drops because the app processes are no longer running

## What The Logs Show

Check container state first:

```bash
docker compose ps
```

Then inspect logs:

```bash
docker compose logs --tail=100 nginx prometheus notifier discord_relay
```

What you should see:

- `app` and `app2` are stopped or missing from the running set
- Prometheus reports the `CurtainServiceDown` alert as firing
- notifier forwards the alert batch
- Discord relay logs `alert.received` and `discord.forwarded`

## Root Cause

The outage is caused by the application tier being unavailable, not by the alerting pipeline or Grafana. Prometheus can no longer scrape any `curtain-app` targets, which triggers `CurtainServiceDown`, and the dashboard confirms the same failure pattern through collapsing traffic and saturation.

## Recovery

Bring the app tier back:

```bash
docker compose start app app2
```

Then verify:

```bash
curl -i http://localhost:5000/health
curl -s http://localhost:9090/api/v1/alerts
```

Expected result:

- `/health` returns `200`
- traffic returns in Grafana
- the alert clears after Prometheus sees healthy targets again
