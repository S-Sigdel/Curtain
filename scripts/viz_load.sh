#!/usr/bin/env bash
# viz_load.sh — fire k6 traffic so you can watch Grafana light up
#
# Usage (from project root):
#   ./scripts/viz_load.sh              # ramp to ~80 req/s, run 3 min
#   PEAK=200 ./scripts/viz_load.sh     # custom peak rate
#   DURATION=5m ./scripts/viz_load.sh  # custom duration
#   SPIKE=1 ./scripts/viz_load.sh      # add a traffic spike mid-run
#
# Requirements: k6 (native) OR docker — script auto-detects which to use.

set -euo pipefail

BOLD=$'\e[1m'; RESET=$'\e[0m'
CYAN=$'\e[36m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'

say()  { echo "${CYAN}${BOLD}▶ $*${RESET}"; }
ok()   { echo "${GREEN}✔  $*${RESET}"; }
warn() { echo "${YELLOW}⚠  $*${RESET}"; }

# ── config ────────────────────────────────────────────────────────────────────

PEAK="${PEAK:-80}"          # peak requests/sec
DURATION="${DURATION:-3m}"  # how long to stay at peak
SPIKE="${SPIKE:-0}"         # set to 1 to add a 10s×300rps spike mid-run
BASE_URL_HOST="http://localhost:5000"
BASE_URL_DOCKER="http://nginx:80"

# ── detect k6 ─────────────────────────────────────────────────────────────────

USE_DOCKER=0
if command -v k6 &>/dev/null; then
  K6_CMD="k6"
  BASE_URL="$BASE_URL_HOST"
  say "Found native k6: $(k6 version 2>&1 | head -1)"
elif docker image inspect grafana/k6:latest &>/dev/null 2>&1 || docker pull grafana/k6:latest -q &>/dev/null; then
  USE_DOCKER=1
  BASE_URL="$BASE_URL_DOCKER"
  say "Using k6 via Docker (grafana/k6:latest)"
else
  echo "ERROR: k6 not found. Install it (https://k6.io/docs/get-started/installation/)"
  echo "       or just make sure Docker is running — this script will pull grafana/k6."
  exit 1
fi

# ── seed a short code if none exist ──────────────────────────────────────────

say "Checking for active short codes..."
SHORT_CODE=$(docker exec curtain-db-1 psql -U postgres -d hackathon_db -t -c \
  "SELECT short_code FROM urls WHERE is_active=true ORDER BY id LIMIT 1;" \
  2>/dev/null | tr -d ' \n') || true

if [[ -z "$SHORT_CODE" ]]; then
  warn "No short codes found — seeding a few..."
  for url in "https://example.com/alpha" "https://example.com/beta" "https://example.com/gamma"; do
    curl -s -o /dev/null -X POST "$BASE_URL_HOST/urls" \
      -H "Content-Type: application/json" \
      -d "{\"original_url\":\"${url}\"}"
  done
  SHORT_CODE=$(docker exec curtain-db-1 psql -U postgres -d hackathon_db -t -c \
    "SELECT short_code FROM urls WHERE is_active=true ORDER BY id LIMIT 1;" \
    2>/dev/null | tr -d ' \n')
fi

ok "Using short code: ${BOLD}${SHORT_CODE}${RESET}"

# ── open grafana hint ─────────────────────────────────────────────────────────

echo ""
echo "  ${BOLD}Open Grafana now:${RESET}"
echo "  ${CYAN}http://localhost:3000/d/curtain-command-center${RESET}  (admin / admin)"
echo ""
echo "  ${BOLD}What to watch:${RESET}"
echo "  • Live Traffic (per Instance)  — two lines climbing, showing load balancing"
echo "  • Traffic by Endpoint Type     — 'redirects' series spikes, others flat"
echo "  • Latency Percentiles          — p50/p95/p99 spread under load"
echo "  • Error Rate stat              — should stay green (0%)"
echo ""
echo "  Dashboard auto-refreshes at 500ms and shows last 3 minutes."
echo "  Press Ctrl+C here to stop the load test early."
echo ""

# ── build the k6 script (inline heredoc) ─────────────────────────────────────

K6_SCRIPT=$(cat <<EOJS
import http from "k6/http";
import { check } from "k6";

// Short codes fetched once at test start via setup()
const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const SEED_CODE = __ENV.SHORT_CODE || "";
const PEAK = parseInt(__ENV.PEAK || "80");
const ADD_SPIKE = (__ENV.SPIKE || "0") === "1";

export const options = {
  scenarios: {
    redirects: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: Math.max(PEAK * 2, 50),
      maxVUs: Math.max(PEAK * 4, 200),
      stages: [
        { duration: "20s", target: PEAK },       // ramp up
        { duration: __ENV.DURATION || "3m", target: PEAK }, // sustain
        ...(ADD_SPIKE ? [
          { duration: "10s", target: PEAK * 4 }, // spike!
          { duration: "10s", target: PEAK },      // recover
        ] : []),
        { duration: "15s", target: 0 },           // ramp down
      ],
    },
  },
  thresholds: {
    http_req_failed:   ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

export function setup() {
  // Collect up to 10 active short codes for variety
  const res = http.get(\`\${BASE_URL}/urls\`);
  let codes = [];
  if (res.status === 200) {
    try {
      const urls = JSON.parse(res.body);
      codes = urls
        .filter(u => u.is_active && u.short_code)
        .map(u => u.short_code)
        .slice(0, 10);
    } catch (_) {}
  }
  if (codes.length === 0 && SEED_CODE) codes = [SEED_CODE];
  return { codes };
}

export default function (data) {
  const codes = (data && data.codes && data.codes.length > 0)
    ? data.codes
    : [SEED_CODE];

  const code = codes[Math.floor(Math.random() * codes.length)];

  const res = http.get(\`\${BASE_URL}/r/\${code}\`, {
    redirects: 0,  // stop at 302 — don't chase to example.com
  });

  check(res, {
    "redirect 302": (r) => r.status === 302,
  });
}
EOJS
)

# ── run k6 ────────────────────────────────────────────────────────────────────

say "Starting k6 — peak ${PEAK} req/s, duration ${DURATION}${SPIKE:+ (+ spike)}"
echo ""

if [[ "$USE_DOCKER" -eq 1 ]]; then
  echo "$K6_SCRIPT" | docker run --rm -i \
    --network curtain_default \
    -e BASE_URL="$BASE_URL" \
    -e SHORT_CODE="$SHORT_CODE" \
    -e PEAK="$PEAK" \
    -e DURATION="$DURATION" \
    -e SPIKE="$SPIKE" \
    grafana/k6:latest run -
else
  echo "$K6_SCRIPT" | BASE_URL="$BASE_URL" SHORT_CODE="$SHORT_CODE" \
    PEAK="$PEAK" DURATION="$DURATION" SPIKE="$SPIKE" \
    k6 run -
fi

echo ""
ok "Load test complete. Check Grafana for the captured traffic shape."
echo "  ${CYAN}http://localhost:3000/d/curtain-command-center${RESET}"
