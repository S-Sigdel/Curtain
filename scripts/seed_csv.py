import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Allow `uv run python scripts/...` to import the app package from the repo root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.database import db
from app.models import Event, Url, User

def _read_rows(filename):
    with (ROOT / filename).open(newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize_url_rows(rows):
    for row in rows:
        row["is_active"] = row["is_active"].lower() == "true"
    return rows


def _sync_sequence(model):
    table_name = model._meta.table_name
    sequence_name = f"{table_name}_id_seq"
    # CSV seeding inserts explicit IDs, so PostgreSQL sequences must be advanced manually.
    db.execute_sql(
        f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)",
        (sequence_name,),
    )


def main():
    app = create_app()

    with app.app_context():
        db.connect(reuse_if_open=True)
        db.create_tables([User, Url, Event], safe=True)

        with db.atomic():
            User.insert_many(_read_rows("users.csv")).on_conflict_ignore().execute()
            Url.insert_many(_normalize_url_rows(_read_rows("urls.csv"))).on_conflict_ignore().execute()
            Event.insert_many(_read_rows("events.csv")).on_conflict_ignore().execute()

        _sync_sequence(User)
        _sync_sequence(Url)
        _sync_sequence(Event)

        db.close()
        print("Seeded users.csv, urls.csv, and events.csv")


if __name__ == "__main__":
    main()
