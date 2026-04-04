import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Allow `uv run python scripts/...` to import the app package from the repo root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.database import db
from app.models import MODELS


def main():
    app = create_app()

    with app.app_context():
        db.connect(reuse_if_open=True)
        # Drop children before parents to satisfy foreign-key dependencies.
        db.drop_tables(list(reversed(MODELS)), safe=True, cascade=True)
        db.create_tables(MODELS, safe=True)
        db.close()
        print("Reset tables: users, urls, events")


if __name__ == "__main__":
    main()
