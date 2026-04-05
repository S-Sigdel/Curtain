import json
import logging
import os
import socket
import time
from datetime import datetime, timezone

from flask import Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    PlatformCollector,
    generate_latest,
)


INSTANCE_ID = os.environ.get("HOSTNAME", socket.gethostname())


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "instance": INSTANCE_ID,
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
    
    # Use multiprocess collector if configured (standard for Gunicorn)
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        from prometheus_client import multiprocess
        multiprocess.MultiProcessCollector(registry)
    else:
        ProcessCollector(registry=registry)
        PlatformCollector(registry=registry)

    request_counter = Counter(
        "http_requests_total",
        "Total number of HTTP requests served.",
        labelnames=("method", "path", "status_code", "instance"),
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds.",
        labelnames=("method", "path", "instance"),
        registry=registry,
    )

    # Shard ring health counters — visible in Grafana for the fire-drill demo.
    app.shard_failures = Counter(
        "redis_shard_failures_total",
        "Redis shard connection failures.",
        labelnames=("shard_id", "instance"),
        registry=registry,
    )
    app.shard_failovers = Counter(
        "redis_shard_failovers_total",
        "Times traffic was rerouted to a backup shard.",
        labelnames=("from_shard", "to_shard", "instance"),
        registry=registry,
    )

    # Manual process metrics for multiprocess mode
    memory_gauge = Gauge(
        "process_resident_memory_bytes",
        "Resident memory size in bytes.",
        labelnames=("instance",),
        registry=registry,
        multiprocess_mode="livesum",
    )
    cpu_counter = Counter(
        "process_cpu_seconds_total",
        "Total user and system CPU time spent in seconds.",
        labelnames=("instance",),
        registry=registry,
    )

    @app.before_request
    def start_request_timer():
        # Update process metrics on every request to ensure fresh data in shared storage
        try:
            import psutil
            process = psutil.Process()
            memory_gauge.labels(INSTANCE_ID).set(process.memory_info().rss)
            cpu_counter.labels(INSTANCE_ID).inc(process.cpu_times().user + process.cpu_times().system - getattr(g, "last_cpu", 0))
            g.last_cpu = process.cpu_times().user + process.cpu_times().system
        except (ImportError, Exception):
            pass

        g.request_started_at = time.perf_counter()

    @app.after_request
    def record_request_metrics(response):
        # Exclude internal metrics scrapes from traffic stats
        if request.path == "/metrics":
            return response

        duration_seconds = max(
            time.perf_counter() - getattr(g, "request_started_at", time.perf_counter()),
            0.0,
        )
        request_counter.labels(
            request.method,
            request.path,
            response.status_code,
            INSTANCE_ID,
        ).inc()
        request_latency.labels(request.method, request.path, INSTANCE_ID).observe(duration_seconds)

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
        if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
            from prometheus_client import multiprocess
            reg = CollectorRegistry()
            multiprocess.MultiProcessCollector(reg)
            return Response(generate_latest(reg), mimetype=CONTENT_TYPE_LATEST)
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
