"""Unit tests for app/stream_consumer.py — no real Redis or PostgreSQL required."""

import json
from datetime import datetime, UTC
from unittest.mock import MagicMock, call, patch

import pytest
from redis.exceptions import ResponseError

from app.stream_consumer import (
    CONSUMER_GROUP,
    _drain_shard,
    _ensure_group,
    _get_stream_keys,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(stream_keys=None, xreadgroup_return=None):
    """Return a mock Redis client pre-configured for stream tests."""
    client = MagicMock()
    raw_keys = [k.encode() for k in (stream_keys or [])]
    client.keys.return_value = raw_keys
    client.xreadgroup.return_value = xreadgroup_return or []
    return client


def _encode_msg(short_code="abc123", ip="1.2.3.4", ts=None):
    """Return a (msg_id, data) pair as Redis would deliver it."""
    ts = ts or "1700000000.0"
    return (
        b"1700000000000-0",
        {b"sc": short_code.encode(), b"ip": ip.encode(), b"ts": ts.encode()},
    )


# ---------------------------------------------------------------------------
# _get_stream_keys
# ---------------------------------------------------------------------------

def test_get_stream_keys_decodes_bytes():
    client = MagicMock()
    client.keys.return_value = [b"stream:clicks:abc", b"stream:clicks:xyz"]
    keys = _get_stream_keys(client)
    assert keys == ["stream:clicks:abc", "stream:clicks:xyz"]


def test_get_stream_keys_returns_empty_for_no_streams():
    client = MagicMock()
    client.keys.return_value = []
    assert _get_stream_keys(client) == []


# ---------------------------------------------------------------------------
# _ensure_group
# ---------------------------------------------------------------------------

def test_ensure_group_creates_group():
    client = MagicMock()
    _ensure_group(client, "stream:clicks:abc")
    client.xgroup_create.assert_called_once_with(
        "stream:clicks:abc", CONSUMER_GROUP, id="0", mkstream=True
    )


def test_ensure_group_ignores_busygroup_error():
    client = MagicMock()
    client.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group already exists")
    # Must not raise
    _ensure_group(client, "stream:clicks:abc")


def test_ensure_group_re_raises_other_redis_errors():
    client = MagicMock()
    client.xgroup_create.side_effect = ResponseError("WRONGTYPE Operation against a key")
    with pytest.raises(ResponseError):
        _ensure_group(client, "stream:clicks:abc")


# ---------------------------------------------------------------------------
# _drain_shard — empty stream
# ---------------------------------------------------------------------------

def test_drain_shard_returns_zero_when_no_streams():
    client = _make_client(stream_keys=[])
    result = _drain_shard("s0", client)
    assert result == 0
    client.xreadgroup.assert_not_called()


def test_drain_shard_returns_zero_when_xreadgroup_empty():
    client = _make_client(stream_keys=["stream:clicks:abc"], xreadgroup_return=[])
    result = _drain_shard("s0", client)
    assert result == 0


# ---------------------------------------------------------------------------
# _drain_shard — happy path with DB mock
# ---------------------------------------------------------------------------

def _make_url_row(short_code, url_id):
    row = MagicMock()
    row.short_code = short_code
    row.id = url_id
    return row


def test_drain_shard_inserts_events_and_acknowledges():
    msg = _encode_msg("abc123", "10.0.0.1")
    client = _make_client(
        stream_keys=["stream:clicks:abc123"],
        xreadgroup_return=[(b"stream:clicks:abc123", [msg])],
    )

    url_row = _make_url_row("abc123", 42)

    with patch("app.stream_consumer.Url") as mock_url, \
         patch("app.stream_consumer.Event") as mock_event, \
         patch("app.stream_consumer.db") as mock_db:

        mock_url.select.return_value.where.return_value = [url_row]
        mock_db.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_db.atomic.return_value.__exit__ = MagicMock(return_value=False)

        result = _drain_shard("s0", client)

    assert result == 1
    mock_event.insert_many.assert_called_once()
    inserted = mock_event.insert_many.call_args[0][0]
    assert len(inserted) == 1
    assert inserted[0]["url_id"] == 42
    assert inserted[0]["event_type"] == "redirect"
    client.xack.assert_called_once_with(
        "stream:clicks:abc123", CONSUMER_GROUP, b"1700000000000-0"
    )


def test_drain_shard_skips_unknown_short_codes():
    """Events for deleted URLs should be dropped, not inserted."""
    msg = _encode_msg("deleted_code", "10.0.0.1")
    client = _make_client(
        stream_keys=["stream:clicks:deleted_code"],
        xreadgroup_return=[(b"stream:clicks:deleted_code", [msg])],
    )

    with patch("app.stream_consumer.Url") as mock_url, \
         patch("app.stream_consumer.Event") as mock_event, \
         patch("app.stream_consumer.db") as mock_db:

        mock_url.select.return_value.where.return_value = []  # no matching URL
        mock_db.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_db.atomic.return_value.__exit__ = MagicMock(return_value=False)

        result = _drain_shard("s0", client)

    assert result == 0
    mock_event.insert_many.assert_not_called()


def test_drain_shard_does_not_ack_before_db_write_succeeds():
    """If DB insert raises, messages must NOT be acknowledged."""
    msg = _encode_msg("abc123", "10.0.0.1")
    client = _make_client(
        stream_keys=["stream:clicks:abc123"],
        xreadgroup_return=[(b"stream:clicks:abc123", [msg])],
    )
    url_row = _make_url_row("abc123", 1)

    with patch("app.stream_consumer.Url") as mock_url, \
         patch("app.stream_consumer.Event") as mock_event, \
         patch("app.stream_consumer.db") as mock_db:

        mock_url.select.return_value.where.return_value = [url_row]
        mock_event.insert_many.return_value.execute.side_effect = Exception("DB down")
        mock_db.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_db.atomic.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(Exception, match="DB down"):
            _drain_shard("s0", client)

    client.xack.assert_not_called()


def test_drain_shard_decodes_string_stream_names():
    """Stream name can arrive as bytes or str — both should work."""
    msg = _encode_msg("xyz999", "2.3.4.5")
    # Stream name as plain string (not bytes)
    client = _make_client(
        stream_keys=["stream:clicks:xyz999"],
        xreadgroup_return=[("stream:clicks:xyz999", [msg])],
    )
    url_row = _make_url_row("xyz999", 7)

    with patch("app.stream_consumer.Url") as mock_url, \
         patch("app.stream_consumer.Event") as mock_event, \
         patch("app.stream_consumer.db") as mock_db:

        mock_url.select.return_value.where.return_value = [url_row]
        mock_db.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_db.atomic.return_value.__exit__ = MagicMock(return_value=False)

        result = _drain_shard("s0", client)

    assert result == 1


def test_drain_shard_handles_bad_timestamp_gracefully():
    """Corrupt ts field in stream message should fall back to now()."""
    bad_msg = (b"1700000000000-0", {b"sc": b"abc123", b"ip": b"1.2.3.4", b"ts": b"not-a-float"})
    client = _make_client(
        stream_keys=["stream:clicks:abc123"],
        xreadgroup_return=[(b"stream:clicks:abc123", [bad_msg])],
    )
    url_row = _make_url_row("abc123", 1)

    with patch("app.stream_consumer.Url") as mock_url, \
         patch("app.stream_consumer.Event") as mock_event, \
         patch("app.stream_consumer.db") as mock_db:

        mock_url.select.return_value.where.return_value = [url_row]
        mock_db.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_db.atomic.return_value.__exit__ = MagicMock(return_value=False)

        result = _drain_shard("s0", client)

    assert result == 1
    inserted = mock_event.insert_many.call_args[0][0]
    assert isinstance(inserted[0]["timestamp"], datetime)
