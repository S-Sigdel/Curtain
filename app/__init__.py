import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from app.database import init_db
from app.observability import configure_json_logging, init_metrics
from app.routes import register_routes


def create_app(init_database=True):
    load_dotenv()

    app = Flask(__name__)
    configure_json_logging(app)
    init_metrics(app)

    if init_database:
        init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/debug/fail")
    def debug_fail():
        if os.environ.get("ENABLE_INCIDENT_DEBUG_ROUTES", "false").lower() != "true":
            return jsonify(error="Not found"), 404
        raise RuntimeError("Intentional failure for incident-response drill")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.exception(
            "request.failed",
            extra={"component": "http", "path": request.path},
        )
        return jsonify(error="Internal server error"), 500

    return app
