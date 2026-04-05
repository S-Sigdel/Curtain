# Incident Response

Curtain includes a local incident-response stack built around Prometheus, Grafana, an alert notifier, and a Discord relay.

## Stack

- Prometheus scrapes `/metrics` from `app` and `app2` for metric scraping and alert evaluation
- Grafana displays the `Curtain Command Center` dashboard for the visual command-center dashboard
- `notifier` polls Prometheus alert state every 15 seconds
- `discord_relay` receives internal alert payloads and forwards them to Discord
- PromLens for sub-second Prometheus query exploration and spike demos

Relevant files:

- [docker-compose.yml](/home/pacific/Programming/hackathons/Curtain/docker-compose.yml)
- [monitoring/prometheus.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/prometheus.yml)
- [monitoring/alerts.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/alerts.yml)

## Endpoints

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- PromLens: `http://localhost:8081`
- Manual relay test: `http://localhost:8080/alert`
- App metrics: `http://localhost:5000/metrics`
- Public health check: `http://localhost:5000/health`

## PromLens Quick Start

PromLens is bundled next to Prometheus so you can showcase second-level spikes without waiting for Grafana refresh windows.

1. `docker compose up --build -d` (PromLens depends on the main stack).
2. Visit `http://localhost:8081` from the host.
3. The default data source is pre-set to `http://localhost:9090` (so your browser can reach the Prometheus port directly). If you run the stack on a remote host, type the reachable URL manually (for example `http://host.docker.internal:9090`).
4. Execute queries such as:
   - `rate(http_requests_total{job="curtain-app"}[5s])`
   - `sum by (instance) (rate(nginx_http_requests_total[5s]))`
5. Use the 1-second auto-refresh toggle for live spikes while your load test runs.

Because PromLens pulls directly from Prometheus, any reduced `scrape_interval` you configure will be reflected instantly when demoing traffic bursts.

## Alert Rules

Alert rules live in:

- [monitoring/alerts.yml](/home/pacific/Programming/hackathons/Curtain/monitoring/alerts.yml)

Current alerts:

- `CurtainServiceDown`
  Fires when Prometheus cannot scrape any app instance for 1 minute.
- `CurtainInstanceDown`
  Fires when fewer than 2 app instances are reachable for 1 minute (partial outage, load balancer degraded).
- `CurtainHighErrorRate`
  Fires when 5xx responses exceed 5 percent of total requests for 2 minutes.

Prometheus is currently configured with a `500ms` scrape interval and `500ms` evaluation interval, while the notifier polls every `15s`. That keeps the alerting path comfortably within the quest's 5-minute requirement while also making Prometheus and PromLens much more responsive during demos.

## Notification Path

The notifier posts new firing alerts to the internal relay at `http://discord_relay:8080/alert`.
The relay then forwards the alert message to the Discord webhook stored in `DISCORD_WEBHOOK_URL`.

For local verification from the host, the relay is also exposed at `http://localhost:8080/alert`.
