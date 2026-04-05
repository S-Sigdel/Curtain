import http from "k6/http";
import { check, sleep, group } from "k6";
import { SharedArray } from "k6/data";

// Simulate many users hitting different paths
export const options = {
  scenarios: {
    high_traffic: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: '30s', target: 100 }, // Ramp up to 100 requests per second
        { duration: '1m', target: 100 },  // Stay at 100 rps
        { duration: '30s', target: 0 },   // Ramp down
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'], // Less than 1% errors
    http_req_duration: ['p(95)<200'], // 95% of requests should be below 200ms
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

// Try to find some short codes to hit
export default function () {
  group("Health Check", function () {
    const res = http.get(`${BASE_URL}/health`);
    check(res, { "status is 200": (r) => r.status === 200 });
  });

  group("List URLs", function () {
    const res = http.get(`${BASE_URL}/urls`);
    check(res, { "status is 200": (r) => r.status === 200 });
  });

  group("Create and Redirect", function () {
    // 1. Create a URL
    const payload = JSON.stringify({
      original_url: "https://example.com/" + Math.random(),
    });
    const params = { headers: { "Content-Type": "application/json" } };
    const postRes = http.post(`${BASE_URL}/urls`, payload, params);
    
    if (check(postRes, { "URL created": (r) => r.status === 201 })) {
      const shortCode = postRes.json().short_code;
      
      // 2. Hit the redirect multiple times
      for (let i = 0; i < 5; i++) {
        const redirRes = http.get(`${BASE_URL}/r/${shortCode}`, {
          redirects: 0, // Don't follow to example.com
        });
        check(redirRes, { "Redirect is 302": (r) => r.status === 302 });
        sleep(0.1);
      }
    }
  });

  sleep(Math.random() * 2);
}
