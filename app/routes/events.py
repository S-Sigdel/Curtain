import json
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from playhouse.shortcuts import model_to_dict

from app.cache import (
    URL_ANALYTICS_TTL_SECONDS,
    delete_cache_keys,
    get_cached_json,
    set_cached_json,
    url_analytics_cache_key,
)
from app.models import Event, Url, User

events_bp = Blueprint("events", __name__)


def _parse_details(details):
    if details is None:
        return None

    try:
        return json.loads(details)
    except (TypeError, json.JSONDecodeError):
        return details


def _serialize_event(event):
    payload = model_to_dict(event, backrefs=False, recurse=False)
    payload.pop("url", None)
    payload.pop("user", None)
    payload["url_id"] = event.url_id
    payload["user_id"] = event.user_id
    payload["timestamp"] = event.timestamp.isoformat(timespec="seconds")
    payload["details"] = _parse_details(event.details)
    return payload


def _validation_error(message, status_code=400):
    return jsonify(error=message), status_code


def _json_response(payload, status_code=200, cache_status=None):
    response = jsonify(payload)
    response.status_code = status_code
    if cache_status is not None:
        response.headers["X-Cache"] = cache_status
    return response


def _validate_create_payload(payload):
    if not isinstance(payload, dict):
        return "JSON body must be an object"

    if "event_type" not in payload:
        return "Field 'event_type' is required"
    if not isinstance(payload["event_type"], str) or not payload["event_type"].strip():
        return "Field 'event_type' must be a non-empty string"

    if "url_id" not in payload:
        return "Field 'url_id' is required"
    if not isinstance(payload["url_id"], int):
        return "Field 'url_id' must be an integer"

    if "user_id" in payload and payload["user_id"] is not None and not isinstance(payload["user_id"], int):
        return "Field 'user_id' must be an integer"

    if "details" in payload and payload["details"] is not None and not isinstance(payload["details"], (dict, list, str, int, float, bool)):
        return "Field 'details' must be JSON-serializable"

    return None


@events_bp.route("/events", methods=["GET"])
def list_events():
    query = Event.select().order_by(Event.id)

    url_id = request.args.get("url_id", type=int)
    if request.args.get("url_id") is not None and url_id is None:
        return _validation_error("Query parameter 'url_id' must be an integer")

    user_id = request.args.get("user_id", type=int)
    if request.args.get("user_id") is not None and user_id is None:
        return _validation_error("Query parameter 'user_id' must be an integer")

    event_type = request.args.get("event_type")

    if url_id is not None:
        query = query.where(Event.url_id == url_id)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)
    if event_type is not None:
        query = query.where(Event.event_type == event_type)

    return jsonify([_serialize_event(event) for event in query]), 200


@events_bp.route("/events", methods=["POST"])
def create_event():
    payload = request.get_json(silent=True)
    error_message = _validate_create_payload(payload)
    if error_message is not None:
        return _validation_error(error_message)

    url = Url.get_or_none(Url.id == payload["url_id"])
    if url is None:
        return jsonify(error="URL not found"), 404

    user_id = payload.get("user_id")
    if user_id is not None and User.get_or_none(User.id == user_id) is None:
        return jsonify(error="User not found"), 404

    details = payload.get("details")
    event = Event.create(
        url_id=url.id,
        user_id=user_id,
        event_type=payload["event_type"].strip(),
        timestamp=datetime.now(UTC).replace(tzinfo=None),
        details=json.dumps(details if details is not None else {}),
    )
    delete_cache_keys(url_analytics_cache_key(url.id))
    return jsonify(_serialize_event(event)), 201


@events_bp.route("/urls/<int:url_id>/analytics", methods=["GET"])
def get_url_analytics(url_id):
    cache_key = url_analytics_cache_key(url_id)
    cached_payload = get_cached_json(cache_key)
    if cached_payload is not None:
        return _json_response(cached_payload, cache_status="HIT")

    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    events = list(Event.select().where(Event.url_id == url_id).order_by(Event.timestamp, Event.id))
    event_counts = {}
    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    latest_event_at = events[-1].timestamp.isoformat(timespec="seconds") if events else None

    payload = {
        "url_id": url.id,
        "short_code": url.short_code,
        "original_url": url.original_url,
        "total_events": len(events),
        "event_counts": event_counts,
        "latest_event_at": latest_event_at,
    }
    set_cached_json(cache_key, payload, URL_ANALYTICS_TTL_SECONDS)
    return _json_response(payload, cache_status="MISS")
