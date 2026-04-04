from app.services.url_shortener import base62_encode, generate_next_short_code


class DummyScalarQuery:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class DummyRedis:
    def __init__(self, incr_value):
        self.incr_value = incr_value
        self.setnx_calls = []
        self.incr_calls = []

    def setnx(self, key, value):
        self.setnx_calls.append((key, value))

    def incr(self, key):
        self.incr_calls.append(key)
        return self.incr_value


def test_base62_encode_encodes_expected_values():
    assert base62_encode(0) == "0"
    assert base62_encode(1) == "1"
    assert base62_encode(61) == "Z"
    assert base62_encode(62) == "10"
    assert base62_encode(2001) == "wh"


def test_generate_next_short_code_seeds_counter_from_max_url_id(monkeypatch):
    redis_client = DummyRedis(incr_value=2001)

    monkeypatch.setattr("app.services.url_shortener.get_redis", lambda: redis_client)
    monkeypatch.setattr(
        "app.services.url_shortener.Url.select",
        lambda *args, **kwargs: DummyScalarQuery(2000),
    )

    short_code = generate_next_short_code()

    assert short_code == "wh"
    assert redis_client.setnx_calls == [("url:counter", 2000)]
    assert redis_client.incr_calls == ["url:counter"]
