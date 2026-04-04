import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    cached_url_read: {
      executor: "constant-vus",
      vus: 1000,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<3000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://nginx";
const URL_ID = __ENV.URL_ID || "1";

export default function () {
  const response = http.get(`${BASE_URL}/urls/${URL_ID}`);

  check(response, {
    "read returns 200": (r) => r.status === 200,
    "read includes short_code": (r) => !!r.json("short_code"),
    "cache header exists": (r) => !!r.headers["X-Cache"],
  });

  sleep(1);
}
