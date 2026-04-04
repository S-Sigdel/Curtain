import json
import logging
from datetime import datetime, timezone

from gunicorn.glogging import Logger


class GunicornJsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": "gunicorn",
        }

        for field in (
            "client_addr",
            "method",
            "path",
            "query",
            "status_code",
            "response_bytes",
            "user_agent",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class GunicornJsonLogger(Logger):
    def setup(self, cfg):
        super().setup(cfg)
        formatter = GunicornJsonFormatter()

        for logger in (self.error_log, self.access_log):
            for handler in logger.handlers:
                handler.setFormatter(formatter)

    def access(self, resp, req, environ, request_time):
        status = getattr(resp, "status", "").split()[0]
        record = self.access_log.makeRecord(
            name=self.access_log.name,
            level=logging.INFO,
            fn="gunicorn",
            lno=0,
            msg="access",
            args=(),
            exc_info=None,
            extra={
                "client_addr": environ.get("REMOTE_ADDR"),
                "method": environ.get("REQUEST_METHOD"),
                "path": environ.get("PATH_INFO"),
                "query": environ.get("QUERY_STRING") or None,
                "status_code": int(status) if status.isdigit() else status,
                "response_bytes": getattr(resp, "sent", None),
                "user_agent": environ.get("HTTP_USER_AGENT"),
            },
        )
        self.access_log.handle(record)
