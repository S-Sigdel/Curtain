# Load Testing

This document describes the Silver-tier horizontal scaling setup.

## Baseline Stack

The stack runs:

- 2 Gunicorn-backed app containers: `app` and `app2`
- 1 Nginx container in front of them
- PostgreSQL as the durable store
- Redis for short-code generation

Each app container runs:

- 2 Gunicorn workers
- bound to `0.0.0.0:5000`
- `FLASK_DEBUG=false`

## Silver Baseline Load Test

The baseline `k6` script is:

- [loadtests/loadTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/loadTest.js)

It simulates:

- 200 concurrent virtual users
- 30 seconds of sustained traffic
- requests against `GET /health` through Nginx

Important:

- `vus: 200` means 200 concurrent users
- it does not mean a fixed rate of 200 requests per second
- actual requests per second depend on response time and script timing

Additional real-flow scripts are also available:

- [loadtests/redirectTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/redirectTest.js)
- [loadtests/shortenTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/shortenTest.js)
- [loadtests/highReadTest.js](/home/pacific/Programming/hackathons/PE-Hackathon-Template-2026/loadtests/highReadTest.js)

## Run With Docker

Start the app stack first:

```bash
docker compose up --build -d
```

For read-based load tests, seed the database first so `URL_ID=1` and related rows exist:

```bash
docker compose exec app uv run python scripts/reset_db.py
docker compose exec app uv run python scripts/seed_csv.py
```

Run the baseline:

```bash
docker run --rm --network curtain_default \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

If you want to override the target explicitly, use:

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

## URL Read Load Test

Create a known URL row first:

```bash
curl -s -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://www.wikipedia.org/"}'
```

Then run:

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -e URL_ID=1 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/redirectTest.js
```

Replace `URL_ID` with an existing row id if needed.

## Create Load Test

This script generates unique URLs so the create path is exercised instead of hitting the duplicate-reuse path.

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/shortenTest.js
```

## Cached URL Read Load Test

This script stresses a hot `GET /urls/<id>` path with 500 concurrent users and checks that the cache evidence header is present.

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -e URL_ID=1 \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/highReadTest.js
```

If `URL_ID=1` does not exist, the test will fail its correctness checks even if the service is otherwise healthy.
