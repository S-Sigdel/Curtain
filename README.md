# Curtain

A Flask + Peewee + PostgreSQL service for URL shortening, management, events, analytics, and load-testing experiments.

**Stack:** Flask · Peewee ORM · PostgreSQL · uv

## Prerequisites

- `git` installed
- Docker + Docker Compose
- Optional for local non-Docker runs: `uv` and PostgreSQL

## uv Basics

`uv` manages your Python version, virtual environment, and dependencies automatically — no manual `python -m venv` needed.

| Command | What it does |
|---------|--------------|
| `uv sync` | Install all dependencies (creates `.venv` automatically) |
| `uv run <script>` | Run a script using the project's virtual environment |
| `uv add <package>` | Add a new dependency |
| `uv remove <package>` | Remove a dependency |

## Build Instructions

```bash
# 1. Clone the repository
git clone git@github.com:S-Sigdel/Curtain.git
cd Curtain

# 2. Configure environment
cp .env.example .env

# 3. Build and start all services
docker compose up --build -d

# 4. Verify
curl http://localhost:5000/health
# → {"status":"ok"}
```

If you want seeded challenge data, run this after the stack is up:

```bash
docker compose exec app uv run python scripts/reset_db.py
docker compose exec app uv run python scripts/seed_csv.py
```

## Docker Quick Start

```bash
docker compose up --build -d
docker compose exec app uv run python scripts/reset_db.py
docker compose exec app uv run python scripts/seed_csv.py
curl http://localhost:5000/health
```

If you change Python code while Docker is already running, restart the app service so Gunicorn reloads the updated routes:

```bash
docker compose restart app app2 nginx
```

## [IMPORTANT] Evidence of Hackathon Quest Logs
All the evidence of each Quests are logged properly in the `evidence/` directory along with the related screenshots as follows:

- Reliability Engineering (up to Gold tier done): [./evidence/RELIABILITY_EVIDENCE.md](./evidence/RELIABILITY_EVIDENCE.md)
- Scalability Engineering (up to Gold tier done): [./evidence/SCALABILITY_EVIDENCE.md](./evidence/SCALABILITY_EVIDENCE.md)
- Incident Response (up to Gold tier done): [./evidence/INCIDENT_RESPONSE_EVIDENCE.md](./evidence/INCIDENT_RESPONSE_EVIDENCE.md)


## Testing

Run the test suite locally with:

```bash
uv sync --dev
uv run pytest --cov=app --cov-report=term-missing
```

If you are using Docker:

```bash
docker compose exec app uv sync --dev
docker compose exec app uv run pytest -q
```

## Observability

If you want to view the structured logs without using SSH and also want to know how to check the matrices, then please refer to the file [./docs/OBSERVABILITY.md](./docs/OBSERVABILITY.md)

## Incident Response

If you want to know how we handle an alert incidence or any other kind of incidence and the tools we are using for them then please refer to the file [./docs/INCIDENT_RESPONSE.md](./docs/INCIDENT_RESPONSE.md)

## Scaling Verification

This project scales with two app containers (`app`, `app2`) behind Nginx.

Quick check:

```bash
docker compose ps
```

Run the baseline 200-user load test:

```bash
docker run --rm \
  --network curtain_default \
  -e BASE_URL=http://nginx \
  -v "$PWD/loadtests:/loadtests" \
  grafana/k6 run /loadtests/loadTest.js
```

For full load-testing procedures, pass criteria, and additional k6 scenarios, see [docs/LOAD_TESTING.md](./docs/LOAD_TESTING.md).

CI runs the same pytest suite on every push and pull request via [.github/workflows/tests.yml](./.github/workflows/tests.yml).

## Documentation

- API request/response examples: [docs/API_EXAMPLES.md](./docs/API_EXAMPLES.md)
- Error-handling behavior: [docs/ERROR_HANDELING.md](./docs/ERROR_HANDELING.md)
- Failure scenarios and mitigations: [docs/FAILURE_MODES.md](./docs/FAILURE_MODES.md)
- Incident response setup and drills: [docs/INCIDENT_RESPONSE.md](./docs/INCIDENT_RESPONSE.md)
- Root-cause diagnosis workflow: [docs/DIAGNOST_ERRORS.md](./docs/DIAGNOST_ERRORS.md)
- Load testing and scaling verification: [docs/LOAD_TESTING.md](./docs/LOAD_TESTING.md)
- Logs, metrics, and observability checks: [docs/OBSERVABILITY.md](./docs/OBSERVABILITY.md)
- Operational runbook : [docs/RUNBOOK.md](./docs/RUNBOOK.md)
- Redis behavior and caching notes: [docs/REDIS_INFO.md](./docs/REDIS_INFO.md)

## API highlights

- `POST /users`, `GET /users`, `GET /users/<id>`, `PUT /users/<id>`
- `POST /urls`, `GET /urls`, `GET /urls/<id>`, `PUT /urls/<id>`
- `GET /events`, `GET /urls/<id>/analytics`

## New User Flow

`POST /urls` only accepts a `user_id` that already exists in the `users` table. If the caller is a brand-new user, create the user first and then use the returned `id` when creating the URL.

```bash
curl -X POST http://localhost:5000/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com"
  }'
```

```bash
curl -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "original_url": "https://example.com/test",
    "title": "Test URL"
  }'
```

If `user_id` is omitted, URL creation is still allowed because `urls.user_id` is nullable.


## Project Structure

```
Curtain/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── database.py          # DatabaseProxy, BaseModel, connection hooks
│   ├── models/
│   │   └── __init__.py      # Registers User, Url, and Event models
│   └── routes/
│       └── __init__.py      # Registers users, urls, and events routes
├── docs/                    # API examples, failure modes, error handling
├── loadtests/               # k6 scripts
├── scripts/
│   ├── init_db.py           # Create tables if they do not exist
│   ├── reset_db.py          # Drop and recreate challenge tables
│   └── seed_csv.py          # Load users.csv, urls.csv, events.csv
├── users.csv                # Seed data
├── urls.csv                 # Seed data
├── events.csv               # Seed data
├── docker-compose.yml       # App, Postgres, and Redis services
├── .env.example             # DB connection template
├── .gitignore               # Python + uv gitignore
├── .python-version          # Pin Python version for uv
├── pyproject.toml           # Project metadata + dependencies
├── run.py                   # Entry point: uv run run.py
└── README.md
```

## Current Schema

The provided CSVs map to these tables:

- `users`: `id`, `username`, `email`, `created_at`
- `urls`: `id`, `user_id`, `short_code`, `original_url`, `title`, `is_active`, `created_at`, `updated_at`
- `events`: `id`, `url_id`, `user_id`, `event_type`, `timestamp`, `details`

Primary keys use auto-incrementing IDs for app-created rows. The seed script inserts the explicit IDs from the CSV files, and PostgreSQL continues from the highest seeded value after that.

## Database Scripts

- `uv run python scripts/init_db.py`
Creates the three challenge tables if they do not exist.

- `uv run python scripts/reset_db.py`
Drops and recreates the three challenge tables. Use this when the schema drifted or tables were created incorrectly.

- `uv run python scripts/seed_csv.py`
Loads `users.csv`, `urls.csv`, and `events.csv` into PostgreSQL. Re-running it is safe for existing IDs because inserts use conflict ignore.


## Tips

- Use `model_to_dict` from `playhouse.shortcuts` to convert model instances to dictionaries for JSON responses.
- Wrap bulk inserts in `db.atomic()` for transactional safety and performance.
- The template uses `teardown_appcontext` for connection cleanup, so connections are closed even when requests fail.
- Check `.env.example` for all available configuration options.
