# MLH PE Hackathon — Flask + Peewee + PostgreSQL Template

A minimal hackathon starter template. You get the scaffolding and database wiring — you build the models, routes, and CSV loading logic.

**Stack:** Flask · Peewee ORM · PostgreSQL · uv

## **Important**

You need to work with around the seed files that you can find in [MLH PE Hackathon](https://mlh-pe-hackathon.com) platform. This will help you build the schema for the database and have some data to do some testing and submit your project for judging. If you need help with this, reach out on Discord or on the Q&A tab on the platform.

## Prerequisites

- **uv** — a fast Python package manager that handles Python versions, virtual environments, and dependencies automatically.
  Install it with:
  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  For other methods see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).
- PostgreSQL running locally (you can use Docker or a local instance)

## uv Basics

`uv` manages your Python version, virtual environment, and dependencies automatically — no manual `python -m venv` needed.

| Command | What it does |
|---------|--------------|
| `uv sync` | Install all dependencies (creates `.venv` automatically) |
| `uv run <script>` | Run a script using the project's virtual environment |
| `uv add <package>` | Add a new dependency |
| `uv remove <package>` | Remove a dependency |

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd PE-Hackathon-Template-2026

# 2. Install dependencies
uv sync

# 3. Create the database
createdb hackathon_db

# 4. Configure environment
cp .env.example .env   # edit if your DB credentials differ

# 5. Reset the schema to match the challenge CSVs
uv run python scripts/reset_db.py

# 6. Seed the database
uv run python scripts/seed_csv.py

# 7. Run the server
uv run run.py

# 8. Verify
curl http://localhost:5000/health
# → {"status":"ok"}
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
docker compose restart app
```

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

CI runs the same pytest suite on every push and pull request via [.github/workflows/tests.yml](./.github/workflows/tests.yml).

Detailed behavior docs:

- [docs/API_EXAMPLES.md](./docs/API_EXAMPLES.md)
- [docs/ERROR_HANDELING.md](./docs/ERROR_HANDELING.md)
- [docs/FAILURE_MODES.md](./docs/FAILURE_MODES.md)
- [docs/LOAD_TESTING.md](./docs/LOAD_TESTING.md)

Current API highlights:

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
mlh-pe-hackathon/
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

## How to Add a Model

1. Create a file in `app/models/`, e.g. `app/models/product.py`:

```python
from peewee import CharField, DecimalField, IntegerField

from app.database import BaseModel


class Product(BaseModel):
    name = CharField()
    category = CharField()
    price = DecimalField(decimal_places=2)
    stock = IntegerField()
```

2. Import it in `app/models/__init__.py`:

```python
from app.models.product import Product
```

3. Create the table (run once in a Python shell or a setup script):

```python
from app.database import db
from app.models.product import Product

db.create_tables([Product])
```

## How to Add Routes

1. Create a blueprint in `app/routes/`, e.g. `app/routes/products.py`:

```python
from flask import Blueprint, jsonify
from playhouse.shortcuts import model_to_dict

from app.models.product import Product

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
def list_products():
    products = Product.select()
    return jsonify([model_to_dict(p) for p in products])
```

2. Register it in `app/routes/__init__.py`:

```python
def register_routes(app):
    from app.routes.products import products_bp
    app.register_blueprint(products_bp)
```

## How to Load CSV Data

```python
import csv
from peewee import chunked
from app.database import db
from app.models.product import Product

def load_csv(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with db.atomic():
        for batch in chunked(rows, 100):
            Product.insert_many(batch).execute()
```

## Useful Peewee Patterns

```python
from peewee import fn
from playhouse.shortcuts import model_to_dict

# Select all
products = Product.select()

# Filter
cheap = Product.select().where(Product.price < 10)

# Get by ID
p = Product.get_by_id(1)

# Create
Product.create(name="Widget", category="Tools", price=9.99, stock=50)

# Convert to dict (great for JSON responses)
model_to_dict(p)

# Aggregations
avg_price = Product.select(fn.AVG(Product.price)).scalar()
total = Product.select(fn.SUM(Product.stock)).scalar()

# Group by
from peewee import fn
query = (Product
         .select(Product.category, fn.COUNT(Product.id).alias("count"))
         .group_by(Product.category))
```

## Tips

- Use `model_to_dict` from `playhouse.shortcuts` to convert model instances to dictionaries for JSON responses.
- Wrap bulk inserts in `db.atomic()` for transactional safety and performance.
- The template uses `teardown_appcontext` for connection cleanup, so connections are closed even when requests fail.
- Check `.env.example` for all available configuration options.
