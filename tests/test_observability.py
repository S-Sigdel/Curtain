import io
import json
import logging
import sys

from app.observability import JsonFormatter


def test_metrics_endpoint_exposes_request_and_process_metrics(client):
    response = client.get("/metrics")

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "process_cpu_seconds_total" in body
    assert "process_resident_memory_bytes" in body


def test_request_logs_are_emitted_as_json(app):
    stream = io.StringIO()
    handler = app.logger.handlers[0]
    original_stream = handler.setStream(stream)

    try:
        app.test_client().get("/health")
    finally:
        handler.setStream(original_stream)

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    payload = json.loads(lines[-1])

    assert payload["message"] == "request.complete"
    assert payload["level"] == "INFO"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert "timestamp" in payload
    assert "duration_ms" in payload


def test_json_formatter_includes_exception_data():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="request.failed",
        args=(),
        exc_info=None,
    )

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record.exc_info = sys.exc_info()

    record.component = "http"

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "request.failed"
    assert payload["level"] == "ERROR"
    assert payload["component"] == "http"
    assert "exception" in payload
