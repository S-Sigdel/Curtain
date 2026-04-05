import os
import shutil

bind = "0.0.0.0:5000"

# gthread: real OS threads, no extra deps. Each worker handles `threads`
# concurrent requests without blocking the others on I/O.
# 4 workers × 4 threads = 16 concurrent requests per container,
# 32 total across both instances — enough headroom for 500 VU bursts
# once the URL detail cache warms up after the first few hits.
workers = 4
worker_class = "gthread"
threads = 4

timeout = 30      # kill a worker that hangs longer than this
keepalive = 5     # keep idle client connections alive for 5 s (matches Nginx)

accesslog = "-"
errorlog = "-"
logger_class = "app.gunicorn_logging.GunicornJsonLogger"


def on_starting(server):
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
