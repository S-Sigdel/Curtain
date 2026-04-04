import json

from flask import Blueprint, jsonify, request
from playhouse.shortcuts import model_to_dict

from app.models import Event, Url

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


@events_bp.route("/urls/<int:url_id>/analytics", methods=["GET"])
def get_url_analytics(url_id):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    events = list(Event.select().where(Event.url_id == url_id).order_by(Event.timestamp, Event.id))
    event_counts = {}
    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    latest_event_at = events[-1].timestamp.isoformat(timespec="seconds") if events else None

    return jsonify(
        url_id=url.id,
        short_code=url.short_code,
        original_url=url.original_url,
        total_events=len(events),
        event_counts=event_counts,
        latest_event_at=latest_event_at,
    ), 200
