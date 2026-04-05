# Current Work Summary

## Monitoring Additions
- Added a PromLens container to `docker-compose.yml` so the stack now exposes a second-level Prometheus query explorer on `http://localhost:8081`.
- Adjusted the PromLens configuration to map container port 8080 → host 8081 and default the datasource to `http://localhost:9090`, ensuring the browser can hit the Prometheus API directly.
- Documented the PromLens workflow (endpoints, quick-start instructions, sample queries, auto-refresh tips) inside `docs/INCIDENT_RESPONSE.md`.

## Observability Fixes
- Updated `app/observability.py` so `/health` requests now emit the JSON `request.complete` log lines (only `/metrics` is skipped). This resolved `tests/test_observability.py::test_request_logs_are_emitted_as_json`.

## Testing
- Ran the full pytest suite inside the `app` container via `docker compose exec app uv run pytest` — 102 tests passed.

## Demo Instructions
- Captured the commands for running fast load spikes (k6 scripts), tailing app logs, and visualizing real-time request rates inside PromLens / Prometheus Graph for the multi-instance load-balancing demo.
