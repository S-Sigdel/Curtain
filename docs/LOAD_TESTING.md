# Load Testing

This document describes the scalability baseline setup.

## Baseline Stack

The app container runs with Gunicorn instead of Flask's development server:

- 2 Gunicorn workers
- bound to `0.0.0.0:5000`
- `FLASK_DEBUG=false`

## Bronze Load Test

The baseline `k6` script is:

- [loadtests/loadTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/loadTest.js)

It simulates:

- 50 concurrent virtual users
- 30 seconds of sustained traffic
- requests against `GET /health`

Additional real-flow scripts are also available:

- [loadtests/redirectTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/redirectTest.js)
- [loadtests/shortenTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/shortenTest.js)

## Run With Docker

Start the app stack first:

```bash
docker compose up --build -d
```

Run the baseline:

```bash
docker run --rm --network pe-hackathon-template-2026_default \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

If you want to override the target explicitly, use:

```bash
docker run --rm \
  --network pe-hackathon-template-2026_default \
  -e BASE_URL=http://app:5000 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

## Redirect Load Test

Create a known short URL first:

```bash
curl -s -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url":"https://www.wikipedia.org/"}'
```

Then run:

```bash
docker run --rm \
  --network pe-hackathon-template-2026_default \
  -e BASE_URL=http://app:5000 \
  -e SHORT_CODE=000001 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/redirectTest.js
```

Replace `SHORT_CODE` with the actual short code returned by the API if needed.

## Shorten Load Test

This script generates unique URLs so the create path is exercised instead of hitting the duplicate-reuse path.

```bash
docker run --rm \
  --network pe-hackathon-template-2026_default \
  -e BASE_URL=http://app:5000 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/shortenTest.js
```
