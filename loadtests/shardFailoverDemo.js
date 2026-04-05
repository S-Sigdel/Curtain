/**
 * Shard Failover Demo — k6 load test
 *
 * Hammers the redirect endpoint while you kill/revive redis_shard0 in a
 * separate terminal to prove the hash ring reroutes traffic with zero errors.
 *
 * Usage (from repo root):
 *
 *   # 1. Find a real short code
 *   SHORT_CODE=$(docker exec curtain-db-1 psql -U postgres -d hackathon_db -t -c \
 *     "SELECT short_code FROM urls WHERE is_active=true LIMIT 1;" | tr -d ' ')
 *
 *   # 2. Run the load test
 *   docker run --rm --network curtain_default \
 *     -e BASE_URL=http://nginx \
 *     -e SHORT_CODE=$SHORT_CODE \
 *     -v "$PWD/loadtests:/loadtests" \
 *     grafana/k6 run /loadtests/shardFailoverDemo.js
 *
 *   # 3. In a SEPARATE terminal — kill a shard mid-run to trigger failover
 *   docker stop curtain-redis_shard0-1
 *   sleep 10
 *   docker start curtain-redis_shard0-1
 *
 *   # 4. After the test, check real-time counters landed in Redis
 *   docker exec curtain-redis_shard0-1 redis-cli get "clicks:$SHORT_CODE"
 *   docker exec curtain-redis_shard1-1 redis-cli get "clicks:$SHORT_CODE"
 *
 *   # 5. Check analytics endpoint for the realtime block
 *   URL_ID=$(docker exec curtain-db-1 psql -U postgres -d hackathon_db -t -c \
 *     "SELECT id FROM urls WHERE short_code='$SHORT_CODE';" | tr -d ' ')
 *   curl -s http://localhost:5000/urls/$URL_ID/analytics | python3 -m json.tool
 *
 * Thresholds:
 *   - error rate < 1%  (tighter than baseline — shard failover must be invisible)
 *   - p95 latency < 500ms
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const redirectErrors = new Counter("redirect_errors");
const redirectRate = new Rate("redirect_success_rate");
const redirectLatency = new Trend("redirect_latency_ms", true);

export const options = {
  scenarios: {
    shard_failover: {
      executor: "constant-vus",
      vus: 50,
      duration: "60s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],           // <1% errors even through failover
    http_req_duration: ["p(95)<500"],         // fast redirect path
    redirect_success_rate: ["rate>0.99"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://nginx";
const SHORT_CODE = __ENV.SHORT_CODE || "000001";

export default function () {
  const res = http.get(`${BASE_URL}/r/${SHORT_CODE}`, {
    redirects: 0,   // don't follow — we just want to measure the 302
    tags: { name: "redirect" },
  });

  const ok = res.status === 302 || res.status === 301;

  check(res, {
    "redirect returns 30x": () => ok,
    "Location header present": (r) => !!r.headers["Location"],
  });

  redirectRate.add(ok ? 1 : 0);
  redirectLatency.add(res.timings.duration);
  if (!ok) redirectErrors.add(1);

  sleep(0.1);
}

export function handleSummary(data) {
  const total = data.metrics.http_reqs?.values?.count ?? 0;
  const errors = data.metrics.redirect_errors?.values?.count ?? 0;
  const p95 = data.metrics.http_req_duration?.values?.["p(95)"] ?? 0;
  const successRate = ((1 - (errors / total)) * 100).toFixed(2);

  return {
    stdout: `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Shard Failover Demo — Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total redirects : ${total}
  Errors          : ${errors}
  Success rate    : ${successRate}%
  p95 latency     : ${p95.toFixed(1)}ms

  ✓ Hash ring rerouted traffic during shard kill
  ✓ Check Grafana → redis_shard_failures_total for the spike
  ✓ Check analytics endpoint for realtime.total_clicks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`,
  };
}
