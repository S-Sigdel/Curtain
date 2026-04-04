# Observability

Curtain exposes structured request logs and a Prometheus-compatible metrics page for local debugging and container-based deployments.

## JSON Logs

Application request logs are emitted as JSON lines with:

- `timestamp`
- `level`
- `logger`
- `message`
- `component`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `remote_addr`
- `endpoint`

View logs without SSH:

```bash
docker compose logs -f app
docker compose logs -f app2
docker compose logs -f nginx
```

Example log line:

```json
{"timestamp":"2026-04-04T15:00:00+00:00","level":"INFO","logger":"app","message":"request.complete","component":"http","method":"GET","path":"/urls/1","status_code":200,"duration_ms":12.48,"remote_addr":"172.20.0.1","endpoint":"url_shortener.get_url"}
```

## Metrics

The app exposes Prometheus text-format metrics at:

```bash
curl http://localhost:5000/metrics
```

Key metrics include:

- `http_requests_total`
- `http_request_duration_seconds`
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`

Those process metrics cover CPU and memory usage directly from the running app process.

## Verification

Quick checks:

```bash
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
curl -i http://localhost:5000/urls
docker compose logs --tail=20 app
```

Expected result:

- `/metrics` returns `200 OK`
- the response body contains request and process metrics
- app logs show JSON entries instead of plain `print()` output
