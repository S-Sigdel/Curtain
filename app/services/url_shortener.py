from peewee import fn

from app.models import Url
from app.redis_client import get_redis

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
    redis_client = get_redis()
    # Seed the counter from the current max row ID so new app-generated codes pick up after CSV data.
    redis_client.setnx(URL_COUNTER_KEY, Url.select(fn.MAX(Url.id)).scalar() or 0)
    return base62_encode(redis_client.incr(URL_COUNTER_KEY)).rjust(
        SHORT_CODE_LENGTH, BASE62_ALPHABET[0]
    )
