import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    shorten_load: {
      executor: "constant-vus",
      vus: 50,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<3000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://app:5000";

export default function () {
  const payload = JSON.stringify({
    original_url: `https://example.com/load-test/${__VU}-${__ITER}`,
    title: "k6 shorten load test",
  });

  const response = http.post(`${BASE_URL}/urls`, payload, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  check(response, {
    "create returns success": (r) => r.status === 201 || r.status === 200,
    "create returns short_code": (r) => !!r.json("short_code"),
  });

  sleep(1);
}
