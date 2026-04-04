import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    forced_errors: {
      executor: "constant-vus",
      vus: 25,
      duration: "2m30s",
    },
  },
};

const BASE_URL = __ENV.BASE_URL || "http://nginx";

export default function () {
  const response = http.get(`${BASE_URL}/debug/fail`);

  check(response, {
    "failure endpoint returns 500": (r) => r.status === 500,
  });

  sleep(1);
}
