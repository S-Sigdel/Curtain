# Runbook

This is the incident guide for Curtain.

## Scope

Use this runbook when one of the incident-response alerts fires:

- `CurtainServiceDown`
- `CurtainInstanceDown`
- `CurtainHighErrorRate`

## Quick Links

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Relay health: `http://localhost:8080/health`
- App health: `http://localhost:5000/health`

## First 5 Minutes

1. Confirm the alert in Discord and note the exact alert name and time.
2. Open Grafana and load the `Curtain Command Center` dashboard.
3. Check the four signals:
   - Latency p95
   - Traffic
   - Error Rate
   - Saturation
4. Check container state:

```bash
docker compose ps
```

5. Tail logs for the services involved:

```bash
docker compose logs --tail=100 app app2 nginx prometheus notifier discord_relay
```

## If `CurtainServiceDown` Fires

Likely symptoms:

- `http://localhost:5000/health` fails
- Traffic drops toward zero
- Grafana may still show recent historic data, but live request rate collapses

Immediate checks:

```bash
curl -i http://localhost:5000/health
docker compose ps
curl -s http://localhost:9090/api/v1/alerts
```

Common causes:

- both app containers stopped or crashed
- Nginx is up but upstream app containers are unavailable
- database startup blocked app boot

Recovery actions:

```bash
docker compose start app app2 nginx
docker compose up -d --force-recreate app app2 nginx
```

If startup still fails:

```bash
docker compose logs --tail=200 app app2 nginx db
```

Recovery confirmation:

```bash
curl -i http://localhost:5000/health
curl -s http://localhost:9090/api/v1/alerts
```

Expected result:

- `/health` returns `200`
- request traffic returns in Grafana
- the service-down alert disappears from Prometheus after recovery

## If `CurtainHighErrorRate` Fires

Likely symptoms:

- 5xx error rate rises above 5 percent
- latency may increase
- traffic may remain normal while failures increase

Immediate checks:

```bash
curl -s http://localhost:9090/api/v1/alerts
docker compose logs --tail=200 app app2 nginx
```

Common causes:

- the debug failure route is enabled and being hit by the load test
- database connectivity failures
- unhandled exceptions in one or both app containers

Recovery actions:

1. Confirm whether the incident is synthetic or real.
2. If the debug route is still enabled unintentionally, set `ENABLE_INCIDENT_DEBUG_ROUTES=false` in `.env`.
3. Recreate the app tier:

```bash
docker compose up -d --force-recreate app app2 nginx
```

4. If the issue is database-related, inspect DB health and app logs:

```bash
docker compose ps
docker compose logs --tail=200 db app app2
```

Recovery confirmation:

- Grafana error rate falls back toward zero
- latency normalizes
- Discord stops sending repeated failure notifications

## Escalation

Escalate if any of the following are true:

- service remains down after one restart attempt
- high error rate continues for more than 10 minutes
- PostgreSQL is unhealthy
- you cannot identify the failing tier from Grafana and logs

Escalation package:

- alert name
- incident start time
- screenshots of Grafana panels
- relevant `docker compose ps`
- relevant log excerpts

## Useful Commands

```bash
docker compose ps
docker compose logs -f app app2 nginx
docker compose logs -f prometheus notifier discord_relay
curl -s http://localhost:9090/api/v1/rules
curl -s http://localhost:9090/api/v1/alerts
curl -i http://localhost:5000/health
curl -i http://localhost:8080/health
```
