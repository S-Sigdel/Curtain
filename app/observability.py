import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    ProcessCollector,
    PlatformCollector,
    generate_latest,
)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in (
            "component",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "remote_addr",
            "endpoint",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_json_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    app.logger.propagate = False

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(handler)
    werkzeug_logger.setLevel(app.logger.level)
    werkzeug_logger.propagate = False


def init_metrics(app):
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    PlatformCollector(registry=registry)

    request_counter = Counter(
        "http_requests_total",
        "Total number of HTTP requests served.",
        labelnames=("method", "path", "status_code"),
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds.",
        labelnames=("method", "path"),
        registry=registry,
    )

    @app.before_request
    def start_request_timer():
        g.request_started_at = time.perf_counter()

    @app.after_request
    def record_request_metrics(response):
        duration_seconds = max(
            time.perf_counter() - getattr(g, "request_started_at", time.perf_counter()),
            0.0,
        )
        request_counter.labels(
            request.method,
            request.path,
            response.status_code,
        ).inc()
        request_latency.labels(request.method, request.path).observe(duration_seconds)

        app.logger.info(
            "request.complete",
            extra={
                "component": "http",
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
                "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
                "endpoint": request.endpoint,
            },
        )
        return response

    @app.route("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

