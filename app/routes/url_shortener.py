from datetime import datetime

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError
from redis import RedisError

from app.models import Url
from app.services.url_shortener import generate_next_short_code

url_shortener_bp = Blueprint("url_shortener", __name__)


@url_shortener_bp.route("/apis/url/shorten", methods=["POST"])
def shorten_url():
    payload = request.get_json(silent=True) or {}
    # Accept a few common client field names to keep the endpoint easy to test.
    long_url = payload.get("long_url") or payload.get("longUrl") or payload.get("url")
    title = payload.get("title")
    user_id = payload.get("user_id")

    if not long_url:
        return jsonify(error="Field 'long_url' is required"), 400

    try:
        short_code = generate_next_short_code()
    except RedisError:
        return jsonify(error="Short URL generation is temporarily unavailable."), 503

    try:
        now = datetime.utcnow()
        Url.create(
            short_code=short_code,
            original_url=long_url,
            title=title,
            user_id=user_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        return jsonify(short_url=short_code), 201
    except IntegrityError as exc:
        return jsonify(error=str(exc)), 400


@url_shortener_bp.route("/apis/url/<shorturl>", methods=["GET"])
def redirect_short_url(shorturl):
    # Only active mappings should resolve to redirects.
    mapping = Url.get_or_none((Url.short_code == shorturl) & (Url.is_active == True))
    if mapping is None:
        return jsonify(error="Short URL not found"), 404

    return redirect(mapping.original_url, code=302)
