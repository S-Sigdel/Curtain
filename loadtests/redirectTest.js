import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    redirect_load: {
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
const SHORT_CODE = __ENV.SHORT_CODE || "000001";

export default function () {
  const response = http.get(`${BASE_URL}/apis/url/${SHORT_CODE}`, {
    redirects: 0,
  });

  check(response, {
    "redirect returns 302": (r) => r.status === 302,
    "redirect includes location header": (r) => !!r.headers.Location,
  });

  sleep(1);
}
