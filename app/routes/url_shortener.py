import json
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request, render_template
from playhouse.shortcuts import model_to_dict

from app.models import Event, Url
from app.services.url_shortener import get_or_create_short_url

url_shortener_bp = Blueprint("url_shortener", __name__)


def _serialize_url(url):
    payload = model_to_dict(url, backrefs=False, recurse=False)
    payload.pop("user", None)
    payload["user_id"] = url.user_id
    payload["created_at"] = url.created_at.isoformat(timespec="seconds")
    payload["updated_at"] = url.updated_at.isoformat(timespec="seconds")
    return payload


def _validation_error(message, status_code=400):
    return jsonify(error=message), status_code


def _record_event(url, event_type, user_id=None, timestamp=None, details=None):
    Event.create(
        url_id=url.id,
        user_id=user_id,
        event_type=event_type,
        timestamp=timestamp or datetime.now(UTC).replace(tzinfo=None),
        details=json.dumps(details or {}),
    )


def _validate_create_payload(payload):
    if not isinstance(payload, dict):
        return "JSON body must be an object"

    original_url = payload.get("original_url") or payload.get("long_url")
    if original_url is None:
        return "Field 'original_url' is required"
    if not isinstance(original_url, str):
        return "Field 'original_url' must be a string"
    if not original_url.strip():
        return "Field 'original_url' must not be empty"

    if "title" in payload and payload["title"] is not None and not isinstance(payload["title"], str):
        return "Field 'title' must be a string"

    if "user_id" in payload and payload["user_id"] is not None and not isinstance(payload["user_id"], int):
        return "Field 'user_id' must be an integer"

    return None


def _validate_update_payload(payload):
    if not isinstance(payload, dict):
        return "JSON body must be an object"

    allowed_fields = {"title", "is_active"}
    unknown_fields = set(payload) - allowed_fields
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        return f"Field '{field}' cannot be updated"

    if "title" in payload and payload["title"] is not None and not isinstance(payload["title"], str):
        return "Field 'title' must be a string"

    if "is_active" in payload and not isinstance(payload["is_active"], bool):
        return "Field 'is_active' must be a boolean"

    return None


@url_shortener_bp.route("/")
def index():
    return render_template("index.html")


@url_shortener_bp.route("/shorten-ui", methods=["POST"])
def shorten_ui():
    original_url = request.form.get("original_url") or request.form.get("long_url")
    title = request.form.get("title") or None
    user_id_raw = request.form.get("user_id")
    user_id = int(user_id_raw) if user_id_raw and user_id_raw.strip() else None

    short_code, mapping, error_message, status_code = get_or_create_short_url(
        long_url=original_url,
        title=title,
        user_id=user_id,
    )
    if error_message is not None:
        return f'<div id="message" class="error">{error_message}</div>', status_code

    short_url = f"{request.host_url.rstrip('/')}/urls/{mapping.id}"
    return (
        f'<div id="message" class="success">Short URL ready! '
        f'<a href="{short_url}" target="_blank">{short_url}</a></div>',
        status_code,
    )


@url_shortener_bp.route("/urls", methods=["POST"])
def create_url():
    payload = request.get_json(silent=True) or {}
    error_message = _validate_create_payload(payload)
    if error_message is not None:
        return _validation_error(error_message)

    original_url = (payload.get("original_url") or payload.get("long_url")).strip()
    title = payload.get("title")
    title = title.strip() if isinstance(title, str) and title.strip() else None
    user_id = payload.get("user_id")

    _short_code, mapping, error_message, status_code = get_or_create_short_url(
        long_url=original_url,
        title=title,
        user_id=user_id,
    )
    if error_message is not None:
        return jsonify(error=error_message), status_code
    if status_code == 201:
        _record_event(
            mapping,
            "created",
            user_id=mapping.user_id,
            timestamp=mapping.created_at,
            details={
                "short_code": mapping.short_code,
                "original_url": mapping.original_url,
            },
        )
    return jsonify(_serialize_url(mapping)), status_code


@url_shortener_bp.route("/urls", methods=["GET"])
def list_urls():
    query = Url.select().order_by(Url.id)
    user_id = request.args.get("user_id", type=int)
    if request.args.get("user_id") is not None and user_id is None:
        return _validation_error("Query parameter 'user_id' must be an integer")

    if user_id is not None:
        query = query.where(Url.user_id == user_id)

    return jsonify([_serialize_url(url) for url in query]), 200


@url_shortener_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    return jsonify(_serialize_url(url)), 200


@url_shortener_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    payload = request.get_json(silent=True)
    error_message = _validate_update_payload(payload)
    if error_message is not None:
        return _validation_error(error_message)

    updated_fields = []

    if "title" in payload:
        title = payload["title"]
        url.title = title.strip() if isinstance(title, str) and title.strip() else None
        updated_fields.append(Url.title)

    if "is_active" in payload:
        url.is_active = payload["is_active"]
        updated_fields.append(Url.is_active)

    if updated_fields:
        url.updated_at = datetime.now(UTC).replace(tzinfo=None)
        updated_fields.append(Url.updated_at)
        url.save(only=updated_fields)
        _record_event(
            url,
            "updated",
            user_id=url.user_id,
            timestamp=url.updated_at,
            details={
                "title": url.title,
                "is_active": url.is_active,
            },
        )

    return jsonify(_serialize_url(url)), 200
