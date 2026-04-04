import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    baseline_health: {
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
  const response = http.get(`${BASE_URL}/health`);

  check(response, {
    "health returns 200": (r) => r.status === 200,
    "health body includes ok": (r) => !!r.body && r.body.includes('"status"'),
  });

  sleep(1);
}
