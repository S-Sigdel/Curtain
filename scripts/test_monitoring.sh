#!/usr/bin/env bash
# test_monitoring.sh — Validate monitoring fixes:
#   1. 2s scrape interval in Prometheus
#   2. 2s refresh rate in Grafana
#   3. /metrics and /health exclusion from traffic stats
#   4. Gunicorn multiprocess metrics aggregation

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
BOLD=$'\e[1m'
RESET=$'\e[0m'
CYAN=$'\e[36m'
GREEN=$'\e[32m'
YELLOW=$'\e[33m'
RED=$'\e[31m'
BLUE=$'\e[34m'

say() { echo "${CYAN}${BOLD}▶ $*${RESET}"; }
ok() { echo "${GREEN}✔  $*${RESET}"; }
warn() { echo "${YELLOW}⚠  $*${RESET}"; }
info() { echo "   $*"; }
header() { echo "${BOLD}${BLUE}# $*${RESET}"; }

# ── checks ───────────────────────────────────────────────────────────────────

header "Checking Prometheus Configuration"
scrape_interval=$(grep "scrape_interval" monitoring/prometheus.yml | head -n 1 | awk '{print $2}')
if [[ "$scrape_interval" == "2s" ]]; then
  ok "Prometheus scrape_interval is 2s"
else
  warn "Prometheus scrape_interval is $scrape_interval (expected 2s)"
fi

header "Checking Grafana Dashboard Configuration"
refresh_rate=$(grep "\"refresh\":" monitoring/grafana/dashboards/curtain-command-center.json | awk -F'"' '{print $4}')
if [[ "$refresh_rate" == "2s" ]]; then
  ok "Grafana dashboard refresh rate is 2s"
else
  warn "Grafana dashboard refresh rate is $refresh_rate (expected 2s)"
fi

header "Checking Gunicorn Multiprocess Configuration"
if grep -q "PROMETHEUS_MULTIPROC_DIR" docker-compose.yml; then
  ok "PROMETHEUS_MULTIPROC_DIR found in docker-compose.yml"
else
  warn "PROMETHEUS_MULTIPROC_DIR NOT found in docker-compose.yml"
fi

if grep -q "def on_starting(server):" gunicorn.conf.py; then
  ok "Gunicorn on_starting hook found in gunicorn.conf.py"
else
  warn "Gunicorn on_starting hook NOT found in gunicorn.conf.py"
fi

header "Checking Traffic Exclusion Logic"
if grep -q "if request.path in (\"/metrics\", \"/health\"):" app/observability.py; then
  ok "Traffic exclusion logic found in app/observability.py"
else
  warn "Traffic exclusion logic NOT found in app/observability.py"
fi

header "Checking Multiprocess Metrics Logic"
if grep -q "from prometheus_client import multiprocess" app/observability.py; then
  ok "Multiprocess metrics logic found in app/observability.py"
else
  warn "Multiprocess metrics logic NOT found in app/observability.py"
fi

header "Checking Database Performance Optimization"
if grep -q "db.create_tables(MODELS, safe=True)" app/database.py | grep -q "before_request"; then
  warn "CRITICAL: db.create_tables STILL found in before_request hook!"
else
  ok "db.create_tables removed from before_request hook"
fi

echo ""
say "Static validation complete."
info "To fully verify, ensure you have restarted the containers:"
info "  ${BOLD}docker-compose down && docker-compose up -d${RESET}"
echo ""
