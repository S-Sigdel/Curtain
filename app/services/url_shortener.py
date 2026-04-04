from datetime import datetime, UTC
from urllib.parse import urlparse

from peewee import IntegrityError
from redis import RedisError
from peewee import fn

from app.models import Url
from app.redis_client import get_counter_redis

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
URL_COUNTER_KEY = "url:counter"
SHORT_CODE_LENGTH = 6


def base62_encode(number):
    if number == 0:
        return BASE62_ALPHABET[0]

    encoded = []
    base = len(BASE62_ALPHABET)
    while number > 0:
        number, remainder = divmod(number, base)
        encoded.append(BASE62_ALPHABET[remainder])

    return "".join(reversed(encoded))


def generate_next_short_code():
    redis_client = get_counter_redis()
    # Seed the counter from the current max row ID so new app-generated codes pick up after CSV data.
    redis_client.setnx(URL_COUNTER_KEY, Url.select(fn.MAX(Url.id)).scalar() or 0)
    return base62_encode(redis_client.incr(URL_COUNTER_KEY)).rjust(
        SHORT_CODE_LENGTH, BASE62_ALPHABET[0]
    )


def generate_next_short_code_without_redis():
    next_id = (Url.select(fn.MAX(Url.id)).scalar() or 0) + 1
    return base62_encode(next_id).rjust(SHORT_CODE_LENGTH, BASE62_ALPHABET[0])


def is_valid_long_url(value):
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_or_create_short_url(long_url, title=None, user_id=None):
    if not long_url:
        return None, None, "Field 'original_url' is required", 400
    if not is_valid_long_url(long_url):
        return None, None, "Field 'original_url' must be a valid http or https URL", 400

    existing_mapping = Url.get_or_none(
        (Url.original_url == long_url) & (Url.is_active == True)
    )
    if existing_mapping is not None:
        return existing_mapping.short_code, existing_mapping, None, 200

    try:
        short_code = generate_next_short_code()
    except RedisError:
        short_code = generate_next_short_code_without_redis()

    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        mapping = Url.create(
            short_code=short_code,
            original_url=long_url,
            title=title,
            user_id=user_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        return short_code, mapping, None, 201
    except IntegrityError as exc:
        error_message = str(exc).lower()
        if "user_id" in error_message or "foreign key" in error_message:
            return None, None, "Field 'user_id' must reference an existing user", 400
        return None, None, "Could not create short URL", 400
