import json
from datetime import UTC, datetime

from flask import Blueprint, jsonify, redirect, request, render_template
from playhouse.shortcuts import model_to_dict

from app.cache import (
    URL_DETAIL_TTL_SECONDS,
    URL_LIST_TTL_SECONDS,
    URL_REDIRECT_TTL_SECONDS,
    get_cached_json,
    invalidate_url_cache,
    set_cached_json,
    url_detail_cache_key,
    url_redirect_cache_key,
    url_list_cache_key,
)
from app.models import Event, Url
from app.redis_client import get_shard_ring
from app.services.click_counter import record_click
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


def _json_response(payload, status_code=200, cache_status=None):
    response = jsonify(payload)
    response.status_code = status_code
    if cache_status is not None:
        response.headers["X-Cache"] = cache_status
    return response


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

    short_url = f"{request.host_url.rstrip('/')}/r/{mapping.short_code}"
    payload_url = f"{request.host_url.rstrip('/')}/urls/{mapping.id}"
    return (
        f'<div id="message" class="success">'
        f'Short URL ready!<br><br>'
        f'<strong>Redirect:</strong> <a href="{short_url}" target="_blank">{short_url}</a><br>'
        f'<strong>Payload:</strong> <a href="{payload_url}" target="_blank">{payload_url}</a>'
        f'</div>',
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
        invalidate_url_cache(mapping.id, mapping.user_id, mapping.short_code)
    return _json_response(_serialize_url(mapping), status_code=status_code, cache_status="BYPASS")


@url_shortener_bp.route("/urls", methods=["GET"])
def list_urls():
    user_id = request.args.get("user_id", type=int)
    if request.args.get("user_id") is not None and user_id is None:
        return _validation_error("Query parameter 'user_id' must be an integer")

    is_active_raw = request.args.get("is_active")
    is_active = None
    if is_active_raw is not None:
        lowered = is_active_raw.strip().lower()
        if lowered not in {"true", "false"}:
            return _validation_error("Query parameter 'is_active' must be true or false")
        is_active = lowered == "true"

    cache_key = url_list_cache_key(user_id, is_active)
    cached_payload = get_cached_json(cache_key)
    if cached_payload is not None:
        return _json_response(cached_payload, cache_status="HIT")

    query = Url.select().order_by(Url.id)
    if user_id is not None:
        query = query.where(Url.user_id == user_id)
    if is_active is not None:
        query = query.where(Url.is_active == is_active)

    limit = request.args.get("limit", default=100, type=int)
    query = query.limit(max(1, min(limit, 500)))

    payload = [_serialize_url(url) for url in query]
    set_cached_json(cache_key, payload, URL_LIST_TTL_SECONDS)
    return _json_response(payload, cache_status="MISS")


@url_shortener_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    cache_key = url_detail_cache_key(url_id)
    cached_payload = get_cached_json(cache_key)
    if cached_payload is not None:
        return _json_response(cached_payload, cache_status="HIT")

    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    payload = _serialize_url(url)
    set_cached_json(cache_key, payload, URL_DETAIL_TTL_SECONDS)
    return _json_response(payload, cache_status="MISS")


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
        invalidate_url_cache(url.id, url.user_id, url.short_code)

    return _json_response(_serialize_url(url), cache_status="BYPASS")


@url_shortener_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    with url._meta.database.atomic():
        Event.delete().where(Event.url_id == url.id).execute()
        url.delete_instance()
        invalidate_url_cache(url_id, url.user_id, url.short_code)

    return "", 204


@url_shortener_bp.route("/r/<short_code>", methods=["GET"])
@url_shortener_bp.route("/urls/short/<short_code>", methods=["GET"])
@url_shortener_bp.route("/urls/<short_code>/redirect", methods=["GET"])
def redirect_short_code(short_code):
    cache_key = url_redirect_cache_key(short_code)
    cached_payload = get_cached_json(cache_key)
    if cached_payload is not None:
        original_url = cached_payload["original_url"]
        url_id = cached_payload["url_id"]
        cache_status = "HIT"
    else:
        url = Url.get_or_none((Url.short_code == short_code) & (Url.is_active == True))
        if url is None:
            return jsonify(error="URL not found"), 404
        original_url = url.original_url
        url_id = url.id
        set_cached_json(
            cache_key,
            {"original_url": original_url, "url_id": url_id},
            URL_REDIRECT_TTL_SECONDS,
        )
        cache_status = "MISS"

    # Fast path: Redis shard INCR + HyperLogLog + Stream append (1 RTT).
    # Falls back to a direct PostgreSQL Event row when all shards are down so
    # redirects are always counted, even in environments without Redis.
    visitor_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    if not record_click(short_code, visitor_ip, get_shard_ring()):
        Event.create(
            url_id=url_id,
            user_id=None,
            event_type="redirect",
            timestamp=datetime.now(UTC).replace(tzinfo=None),
            details=json.dumps({"short_code": short_code}),
        )

    response = redirect(original_url, code=302)
    response.headers["X-Cache"] = cache_status
    return response
