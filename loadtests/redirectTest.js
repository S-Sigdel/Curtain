import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    url_read_load: {
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
const URL_ID = __ENV.URL_ID || "1";

export default function () {
  const response = http.get(`${BASE_URL}/urls/${URL_ID}`);

  check(response, {
    "read returns 200": (r) => r.status === 200,
    "read includes short_code": (r) => !!r.json("short_code"),
  });

  sleep(1);
}
