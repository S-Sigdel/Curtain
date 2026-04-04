from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, request, render_template
from peewee import IntegrityError
from redis import RedisError

from app.models import Url
from app.services.url_shortener import generate_next_short_code

url_shortener_bp = Blueprint("url_shortener", __name__)


def _is_valid_long_url(value):
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@url_shortener_bp.route("/")
def index():
    return render_template("index.html")


@url_shortener_bp.route("/shorten-ui", methods=["POST"])
def shorten_ui():
    long_url = request.form.get("long_url")
    title = request.form.get("title") or None
    user_id_raw = request.form.get("user_id")
    user_id = int(user_id_raw) if user_id_raw and user_id_raw.strip() else None

    if not long_url:
        return '<div id="message" class="error">Field \'long_url\' is required</div>', 400
    if not _is_valid_long_url(long_url):
        return '<div id="message" class="error">Field \'long_url\' must be a valid http or https URL</div>', 400

    try:
        short_code = generate_next_short_code()
    except RedisError:
        return '<div id="message" class="error">Short URL generation is temporarily unavailable.</div>', 503

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
        short_url = f"{request.host_url}{short_code}"
        return f'<div id="message" class="success">Short URL created! <a href="{short_url}" target="_blank">{short_url}</a></div>', 201
    except IntegrityError as exc:
        return f'<div id="message" class="error">{str(exc)}</div>', 400


@url_shortener_bp.route("/apis/url/shorten", methods=["POST"])
def shorten_url():
    payload = request.get_json(silent=True) or {}
    # Accept a few common client field names to keep the endpoint easy to test.
    long_url = payload.get("long_url") or payload.get("longUrl") or payload.get("url")
    title = payload.get("title")
    user_id = payload.get("user_id")

    if not long_url:
        return jsonify(error="Field 'long_url' is required"), 400
    if not _is_valid_long_url(long_url):
        return jsonify(error="Field 'long_url' must be a valid http or https URL"), 400

    existing_mapping = Url.get_or_none(
        (Url.original_url == long_url) & (Url.is_active == True)
    )
    if existing_mapping is not None:
        return jsonify(short_url=existing_mapping.short_code), 200

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
        error_message = str(exc).lower()
        if "user_id" in error_message or "foreign key" in error_message:
            return jsonify(error="Field 'user_id' must reference an existing user"), 400
        return jsonify(error="Could not create short URL"), 400


@url_shortener_bp.route("/apis/url/<shorturl>", methods=["GET"])
@url_shortener_bp.route("/<shorturl>", methods=["GET"])
def redirect_short_url(shorturl):
    # Only active mappings should resolve to redirects.
    mapping = Url.get_or_none((Url.short_code == shorturl) & (Url.is_active == True))
    if mapping is None:
        return jsonify(error="Short URL not found"), 404

    return redirect(mapping.original_url, code=302)
