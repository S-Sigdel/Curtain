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
    long_url: `https://example.com/load-test/${__VU}-${__ITER}`,
    title: "k6 shorten load test",
  });

  const response = http.post(`${BASE_URL}/apis/url/shorten`, payload, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  check(response, {
    "shorten returns success": (r) => r.status === 201 || r.status === 200,
    "shorten returns short_url": (r) => !!r.json("short_url"),
  });

  sleep(1);
}
