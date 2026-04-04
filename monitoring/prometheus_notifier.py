import json
import os
import time
from datetime import datetime, timezone
from urllib import error, request


PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
WEBHOOK_URL = os.environ.get("NOTIFIER_WEBHOOK_URL", "http://discord_relay:8080/alert")
POLL_SECONDS = int(os.environ.get("NOTIFIER_POLL_SECONDS", "15"))


def log(level, message, **fields):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": "prometheus_notifier",
        "message": message,
    }
    payload.update(fields)
    print(json.dumps(payload), flush=True)


def fetch_alerts():
    with request.urlopen(f"{PROMETHEUS_URL}/api/v1/alerts", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("data", {}).get("alerts", [])


def post_alert_batch(alerts):
    body = json.dumps({"alerts": alerts}).encode("utf-8")
    outbound = request.Request(
        WEBHOOK_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CurtainPrometheusNotifier/1.0",
        },
        method="POST",
    )
    with request.urlopen(outbound, timeout=10) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def fingerprint(alert):
    labels = alert.get("labels", {})
    return "|".join(
        [
            alert.get("state", ""),
            labels.get("alertname", ""),
            labels.get("severity", ""),
            labels.get("instance", ""),
            labels.get("job", ""),
        ]
    )


def to_relay_alert(alert):
    relay_alert = dict(alert)
    relay_alert["status"] = alert.get("state", "unknown")
    return relay_alert


if __name__ == "__main__":
    sent_fingerprints = set()

    while True:
        try:
            alerts = fetch_alerts()
            firing_alerts = [alert for alert in alerts if alert.get("state") == "firing"]
            current_fingerprints = {fingerprint(alert) for alert in firing_alerts}
            new_alerts = [
                to_relay_alert(alert)
                for alert in firing_alerts
                if fingerprint(alert) not in sent_fingerprints
            ]

            if new_alerts:
                status_code, response_body = post_alert_batch(new_alerts)
                log(
                    "INFO",
                    "alerts.forwarded",
                    alert_count=len(new_alerts),
                    status_code=status_code,
                    response_body=response_body,
                )

            resolved = sent_fingerprints - current_fingerprints
            sent_fingerprints = (sent_fingerprints | {fingerprint(a) for a in new_alerts}) - resolved

            if resolved:
                log("INFO", "alerts.resolved", resolved_count=len(resolved))
        except error.URLError as exc:
            log("ERROR", "poll.failed", error=str(exc))
        except Exception as exc:
            log("ERROR", "notifier.failed", error=str(exc))

        time.sleep(POLL_SECONDS)
