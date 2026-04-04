import csv
from datetime import UTC, datetime
from io import StringIO

from flask import Blueprint, jsonify, request
from peewee import IntegrityError
from peewee import chunked
from playhouse.shortcuts import model_to_dict

from app.database import db
from app.models import Event, Url, User

users_bp = Blueprint("users", __name__)


def _serialize_user(user):
    payload = model_to_dict(user, backrefs=False, recurse=False)
    payload["created_at"] = user.created_at.isoformat(timespec="seconds")
    return payload


def _validation_error(field, message, status_code=422):
    return jsonify(errors={field: message}), status_code


def _validate_user_payload(payload, partial=False):
    if not isinstance(payload, dict):
        return "request", "JSON body must be an object"

    required_fields = ("username", "email")
    for field in required_fields:
        if not partial and field not in payload:
            return field, f"Field '{field}' is required"

    for field in required_fields:
        if field not in payload:
            continue
        value = payload[field]
        if not isinstance(value, str):
            return field, f"Field '{field}' must be a string"
        if not value.strip():
            return field, f"Field '{field}' must not be empty"

    return None, None


def _parse_created_at(value):
    if not value:
        return datetime.now(UTC).replace(tzinfo=None)

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid created_at value")


def _sync_user_sequence():
    if db.obj is None or "postgres" not in db.obj.__class__.__name__.lower():
        return

    db.execute_sql(
        "SELECT setval(%s, COALESCE((SELECT MAX(id) FROM users), 1), true)",
        ("users_id_seq",),
    )


@users_bp.route("/users/bulk", methods=["POST"])
def bulk_import_users():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify(error="Field 'file' is required"), 400

    content = upload.stream.read().decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(content)))
    now = datetime.now(UTC).replace(tzinfo=None)
    prepared_rows = []

    for row in rows:
        username = (row.get("username") or "").strip()
        email = (row.get("email") or "").strip()
        if not username or not email:
            return jsonify(error="CSV rows must include username and email"), 400

        prepared = {
            "username": username,
            "email": email,
            "created_at": _parse_created_at(row.get("created_at")) if "created_at" in row else now,
        }
        if row.get("id"):
            prepared["id"] = int(row["id"])
        prepared_rows.append(prepared)

    if not prepared_rows:
        return jsonify(count=0), 200

    with db.atomic():
        inserted = 0
        for batch in chunked(prepared_rows, 100):
            inserted += (
                User.insert_many(batch)
                .on_conflict_ignore()
                .as_rowcount()
                .execute()
            )
        _sync_user_sequence()

    status_code = 201 if inserted else 200
    return jsonify(count=inserted), status_code


@users_bp.route("/users", methods=["GET"])
def list_users():
    query = User.select().order_by(User.id)
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    if page is not None or per_page is not None:
        page = page or 1
        per_page = per_page or 20
        if page < 1 or per_page < 1:
            return jsonify(error="Pagination parameters must be positive integers"), 400

        users = [_serialize_user(user) for user in query.paginate(page, per_page)]
        return jsonify(users), 200

    return jsonify([_serialize_user(user) for user in query]), 200


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404
    return jsonify(_serialize_user(user)), 200


@users_bp.route("/users", methods=["POST"])
def create_user():
    payload = request.get_json(silent=True)
    field, message = _validate_user_payload(payload, partial=False)
    if message is not None:
        return _validation_error(field, message)

    try:
        user = User.create(
            username=payload["username"].strip(),
            email=payload["email"].strip(),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    except IntegrityError as exc:
        if "email" in str(exc).lower() or "unique" in str(exc).lower():
            return _validation_error("email", "Field 'email' must be unique")
        _sync_user_sequence()
        try:
            user = User.create(
                username=payload["username"].strip(),
                email=payload["email"].strip(),
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        except IntegrityError:
            return _validation_error("email", "Field 'email' must be unique")
    return jsonify(_serialize_user(user)), 201


@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404

    payload = request.get_json(silent=True)
    field, message = _validate_user_payload(payload, partial=True)
    if message is not None:
        return _validation_error(field, message)

    updated_fields = []
    if "username" in payload:
        user.username = payload["username"].strip()
        updated_fields.append(User.username)
    if "email" in payload:
        user.email = payload["email"].strip()
        updated_fields.append(User.email)

    if updated_fields:
        user.save(only=updated_fields)

    return jsonify(_serialize_user(user)), 200


@users_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404

    with db.atomic():
        Url.update(user=None).where(Url.user_id == user_id).execute()
        Event.update(user=None).where(Event.user_id == user_id).execute()
        user.delete_instance()

    return "", 204
