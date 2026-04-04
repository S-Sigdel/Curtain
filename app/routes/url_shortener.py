from flask import Blueprint, jsonify, redirect, request, render_template
from peewee import ImproperlyConfigured

from app.models import Url
from app.services.url_shortener import get_or_create_short_url

url_shortener_bp = Blueprint("url_shortener", __name__)


@url_shortener_bp.route("/")
def index():
    return render_template("index.html")


@url_shortener_bp.route("/shorten-ui", methods=["POST"])
def shorten_ui():
    long_url = request.form.get("long_url")
    title = request.form.get("title") or None
    user_id_raw = request.form.get("user_id")
    user_id = int(user_id_raw) if user_id_raw and user_id_raw.strip() else None

    short_code, _mapping, error_message, status_code = get_or_create_short_url(
        long_url=long_url,
        title=title,
        user_id=user_id,
    )
    if error_message is not None:
        return f'<div id="message" class="error">{error_message}</div>', status_code

    short_url = f"{request.host_url}{short_code}"
    return (
        f'<div id="message" class="success">Short URL ready! '
        f'<a href="{short_url}" target="_blank">{short_url}</a></div>',
        status_code,
    )


@url_shortener_bp.route("/apis/url/shorten", methods=["POST"])
def shorten_url():
    payload = request.get_json(silent=True) or {}
    # Accept a few common client field names to keep the endpoint easy to test.
    long_url = payload.get("long_url") or payload.get("longUrl") or payload.get("url")
    title = payload.get("title")
    user_id = payload.get("user_id")

    short_code, _mapping, error_message, status_code = get_or_create_short_url(
        long_url=long_url,
        title=title,
        user_id=user_id,
    )
    if error_message is not None:
        return jsonify(error=error_message), status_code
    return jsonify(short_url=short_code), status_code


@url_shortener_bp.route("/apis/url/<shorturl>", methods=["GET"])
@url_shortener_bp.route("/<shorturl>", methods=["GET"])
def redirect_short_url(shorturl):
    # Only active mappings should resolve to redirects.
    try:
        mapping = Url.get_or_none((Url.short_code == shorturl) & (Url.is_active == True))
    except (AttributeError, ImproperlyConfigured):
        return jsonify(error="Short URL not found"), 404
    if mapping is None:
        return jsonify(error="Short URL not found"), 404

    return redirect(mapping.original_url, code=302)
