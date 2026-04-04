import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import error, request


WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def _render_alert_line(alert):
    status = alert.get("status", "unknown").upper()
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    name = labels.get("alertname", "UnnamedAlert")
    severity = labels.get("severity", "unknown")
    summary = annotations.get("summary") or name
    description = annotations.get("description", "")
    return f"[{status}] {name} severity={severity} | {summary} | {description}".strip()


class AlertRelayHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/alert":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            print("discord_relay invalid_json", flush=True)
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"invalid json")
            return

        alerts = payload.get("alerts", [])
        timestamp = datetime.now(timezone.utc).isoformat()
        lines = [f"Curtain alert batch at {timestamp}"]
        lines.extend(_render_alert_line(alert) for alert in alerts)
        content = "\n".join(lines)
        print(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "level": "INFO",
                    "component": "discord_relay",
                    "message": "alert.received",
                    "alert_count": len(alerts),
                }
            ),
            flush=True,
        )

        if WEBHOOK_URL:
            body = json.dumps({"content": content}).encode("utf-8")
            outbound = request.Request(
                WEBHOOK_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "CurtainDiscordRelay/1.0",
                },
                method="POST",
            )
            try:
                with request.urlopen(outbound, timeout=10) as response:
                    response_body = response.read().decode("utf-8", errors="replace")
                print(
                    json.dumps(
                        {
                            "timestamp": timestamp,
                            "level": "INFO",
                            "component": "discord_relay",
                            "message": "discord.forwarded",
                            "alert_count": len(alerts),
                            "status_code": getattr(response, "status", None),
                            "response_body": response_body,
                        }
                    ),
                    flush=True,
                )
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                print(
                    json.dumps(
                        {
                            "timestamp": timestamp,
                            "level": "ERROR",
                            "component": "discord_relay",
                            "message": "discord.forward_failed",
                            "status_code": exc.code,
                            "error": str(exc),
                            "response_body": error_body,
                        }
                    ),
                    flush=True,
                )
                self.send_response(502)
                self.end_headers()
                self.wfile.write(
                    f"discord webhook failed: {exc} body={error_body}".encode("utf-8")
                )
                return
            except error.URLError as exc:
                print(
                    json.dumps(
                        {
                            "timestamp": timestamp,
                            "level": "ERROR",
                            "component": "discord_relay",
                            "message": "discord.forward_failed",
                            "error": str(exc),
                        }
                    ),
                    flush=True,
                )
                self.send_response(502)
                self.end_headers()
                self.wfile.write(f"discord webhook failed: {exc}".encode("utf-8"))
                return
        else:
            print(
                json.dumps(
                    {
                        "timestamp": timestamp,
                        "level": "WARNING",
                        "component": "discord_relay",
                        "message": "discord.webhook_missing",
                    }
                ),
                flush=True,
            )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), AlertRelayHandler).serve_forever()
