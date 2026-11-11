"""Flask app for devops-backoffice."""

import logging
import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from backoffice.config import load_landing_config
from backoffice.logging_setup import configure_logging
from backoffice.metrics import setup_metrics
from backoffice.telemetry import setup_telemetry

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")
PACKAGE_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("backoffice")


def _lab_force_5xx() -> bool:
    """Lab canary abort switch. Keep /healthz and /readyz green so probes pass."""
    return os.environ.get("LAB_FORCE_5XX", "").strip().lower() in {"1", "true", "yes", "on"}


def _selected_env_name(cfg):
    requested = (request.args.get("env") or "").strip().lower()
    selected = cfg.resolve_environment(requested or None)
    if selected is None:
        return cfg.default_environment
    return selected.name


def _links_payload(cfg, env_name):
    selected = cfg.resolve_environment(env_name)
    links = selected.links if selected else []
    return {
        "title": cfg.title,
        "subtitle": cfg.subtitle,
        "default_environment": cfg.default_environment,
        "environment": selected.name if selected else env_name,
        "environment_label": selected.label if selected else env_name,
        "environments": [
            {"name": env.name, "label": env.label} for env in cfg.environments
        ],
        "links": [
            {
                "id": link.id,
                "label": link.label,
                "url": link.url,
                "description": link.description,
                "external": link.external,
            }
            for link in links
        ],
    }


def create_app():
    configure_logging()

    app = Flask(
        __name__,
        template_folder=str(PACKAGE_ROOT / "templates"),
        static_folder=str(PACKAGE_ROOT / "static"),
        static_url_path="/static",
    )
    app.config["APP_VERSION"] = APP_VERSION
    app.config["LANDING"] = load_landing_config()

    setup_telemetry(app)
    setup_metrics(app)

    @app.before_request
    def _start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        started = getattr(g, "request_started", None)
        duration_ms = None
        if started is not None:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if request.path not in {"/healthz", "/readyz", "/metrics"}:
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
                },
            )
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    @app.get("/readyz")
    def readyz():
        return {"status": "ready"}, 200

    @app.get("/version")
    def version():
        return jsonify(
            {
                "service": "devops-backoffice",
                "version": app.config["APP_VERSION"],
            }
        )

    @app.get("/api/links")
    def api_links():
        cfg = app.config["LANDING"]
        return jsonify(_links_payload(cfg, _selected_env_name(cfg)))

    @app.get("/")
    def index():
        if _lab_force_5xx():
            logger.warning("lab_force_5xx", extra={"path": request.path})
            return jsonify({"error": "lab_force_5xx", "service": "devops-backoffice"}), 500
        cfg = app.config["LANDING"]
        env_name = _selected_env_name(cfg)
        selected = cfg.resolve_environment(env_name)
        return render_template(
            "index.html",
            version=app.config["APP_VERSION"],
            path=request.path,
            title=cfg.title,
            subtitle=cfg.subtitle,
            links=selected.links if selected else [],
            environments=cfg.environments,
            selected_environment=selected.name if selected else env_name,
            selected_environment_label=selected.label if selected else env_name,
            cluster=os.environ.get("CLUSTER_NAME", "local"),
        )

    @app.get("/dashboard")
    def dashboard():
        if _lab_force_5xx():
            logger.warning("lab_force_5xx", extra={"path": request.path})
            return jsonify({"error": "lab_force_5xx", "service": "devops-backoffice"}), 500
        cfg = app.config["LANDING"]
        env_name = _selected_env_name(cfg)
        selected = cfg.resolve_environment(env_name)
        return render_template(
            "dashboard.html",
            version=app.config["APP_VERSION"],
            cluster=os.environ.get("CLUSTER_NAME", "local"),
            environments=cfg.environments,
            selected_environment=selected.name if selected else env_name,
            selected_environment_label=selected.label if selected else env_name,
            links=selected.links if selected else [],
        )

    return app


def main():
    app = create_app()
    host = os.environ.get("BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
