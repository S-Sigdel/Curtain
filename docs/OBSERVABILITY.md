# Observability

Curtain exposes structured logs and Prometheus metrics from each Flask app instance.

## What Exists Today

- JSON application logs from Flask request handling
- JSON Gunicorn access and error logs
- `/metrics` on each app container
- Prometheus scraping `app:5000` and `app2:5000`
- Grafana dashboard at `http://localhost:3000`

## Logs

App and Gunicorn logs are emitted as JSON lines. Common fields include:

- `timestamp`
- `level`
- `logger`
- `message`
- `instance`
- `component`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `remote_addr`
- `endpoint`

View logs:

```bash
docker compose logs -f app app2 nginx
docker compose logs -f stream_consumer notifier discord_relay
```

## Metrics

Fetch metrics through Nginx:

```bash
curl http://localhost:5000/metrics
```

Important metrics:

- `http_requests_total`
- `http_request_duration_seconds`
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`
- `redis_shard_failures_total`
- `redis_shard_failovers_total`

The shard metrics are emitted by the Flask app when redirect click writes fail over from one Redis shard to another.

## Quick Verification

```bash
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
curl -i http://localhost:5000/urls
docker compose logs --tail=50 app
```

Expected results:

- `/health` returns `200`
- `/metrics` returns Prometheus text format
- logs show JSON objects rather than plain text lines
