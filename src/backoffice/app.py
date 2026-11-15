"""Flask app for devops-backoffice."""

import logging
import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

from backoffice.config import LandingConfigStore
from backoffice.logging_setup import configure_logging
from backoffice.metrics import setup_metrics
from backoffice.discovery import resolve_service_versions
from backoffice.icons import list_icons
from backoffice.telemetry import setup_telemetry

APP_VERSION = os.environ.get("APP_VERSION", "0.3.0")
PACKAGE_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("backoffice")


def _lab_force_5xx() -> bool:
    """Lab canary abort switch. Keep /healthz and /readyz green so probes pass."""
    return os.environ.get("LAB_FORCE_5XX", "").strip().lower() in {"1", "true", "yes", "on"}


def _selected_env_name(cfg, team=None):
    requested = (request.args.get("env") or "").strip().lower()
    if requested:
        selected = cfg.resolve_environment(requested)
        return selected.name if selected else cfg.default_environment
    if team and team.default_environment:
        selected = cfg.resolve_environment(team.default_environment)
        if selected is not None:
            return selected.name
    selected = cfg.resolve_environment(None)
    if selected is None:
        return cfg.default_environment
    return selected.name


def _selected_team(cfg):
    requested = (request.args.get("team") or "").strip().lower()
    return cfg.resolve_team(requested or None)


def _cluster_label(environment):
    if environment and environment.cluster:
        return environment.cluster
    return os.environ.get("CLUSTER_NAME", "local")


def _links_payload(cfg, team_id, env_name):
    team, environment, services, products = cfg.resolve_view(team_id, env_name)
    return {
        "title": cfg.title,
        "subtitle": cfg.subtitle,
        "default_environment": cfg.default_environment,
        "default_team": cfg.default_team,
        "team": team.id if team else None,
        "team_label": team.label if team else None,
        "team_description": team.description if team else None,
        "environment": environment.name if environment else env_name,
        "environment_label": environment.label if environment else env_name,
        "metadata": environment.metadata_dict() if environment else {
            "type": "",
            "cloud": "",
            "account": "",
            "region": "",
            "cluster": "",
        },
        # Flat aliases kept for older clients.
        "type": environment.env_type if environment else "",
        "cloud": environment.cloud if environment else "",
        "cluster": environment.cluster if environment else "",
        "region": environment.region if environment else "",
        "account": environment.account if environment else "",
        "environments": [
            {
                "name": env.name,
                "label": env.label,
                "metadata": env.metadata_dict(),
                "type": env.env_type,
                "cloud": env.cloud,
                "cluster": env.cluster,
                "region": env.region,
                "account": env.account,
            }
            for env in cfg.environments
        ],
        "teams": [item.to_dict() for item in cfg.teams],
        "services": [link.to_dict(environment) for link in services],
        "products": [link.to_dict(environment) for link in products],
        # Backward-compatible flat list (services then products).
        "links": (
            [link.to_dict(environment) for link in services]
            + [link.to_dict(environment) for link in products]
        ),
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
    store = LandingConfigStore()
    app.config["LANDING_STORE"] = store

    setup_telemetry(app)
    setup_metrics(app)

    def current_landing():
        return app.config["LANDING_STORE"].get()

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

    @app.get("/api/teams")
    def api_teams():
        cfg = current_landing()
        return jsonify(
            {
                "default_team": cfg.default_team,
                "default_environment": cfg.default_environment,
                "teams": [team.to_dict() for team in cfg.teams],
            }
        )

    @app.get("/api/links")
    def api_links():
        cfg = current_landing()
        team = _selected_team(cfg)
        team_id = team.id if team else cfg.default_team
        env_name = _selected_env_name(cfg, team)
        return jsonify(_links_payload(cfg, team_id, env_name))

    @app.get("/api/service-status")
    def api_service_status():
        cfg = current_landing()
        team = _selected_team(cfg)
        team_id = team.id if team else cfg.default_team
        env_name = _selected_env_name(cfg, team)
        _, _, services, _ = cfg.resolve_view(team_id, env_name)
        return jsonify(
            {
                "team": team_id,
                "environment": env_name,
                "services": resolve_service_versions(services),
            }
        )

    @app.get("/api/config")
    def api_config():
        """Config source fingerprint / reload status (ops debugging)."""
        return jsonify(app.config["LANDING_STORE"].status())

    @app.get("/api/icons")
    def api_icons():
        """Curated icon keys for service/product `icon:` / `logo:` fields."""
        return jsonify({"icons": list_icons()})

    @app.get("/")
    def index():
        if _lab_force_5xx():
            logger.warning("lab_force_5xx", extra={"path": request.path})
            return jsonify({"error": "lab_force_5xx", "service": "devops-backoffice"}), 500
        cfg = current_landing()
        env_name = _selected_env_name(cfg)
        selected = cfg.resolve_environment(env_name)
        return render_template(
            "index.html",
            version=app.config["APP_VERSION"],
            path=request.path,
            title=cfg.title,
            subtitle=cfg.subtitle,
            teams=cfg.teams,
            environments=cfg.environments,
            selected_environment=selected.name if selected else env_name,
            selected_environment_label=selected.label if selected else env_name,
            selected_team=None,
            default_team=cfg.default_team,
            cluster=_cluster_label(selected),
        )

    @app.get("/t/<team_id>")
    def team_landing(team_id):
        if _lab_force_5xx():
            logger.warning("lab_force_5xx", extra={"path": request.path})
            return jsonify({"error": "lab_force_5xx", "service": "devops-backoffice"}), 500
        cfg = current_landing()
        team = cfg.resolve_team(team_id)
        if team is None or team.id != team_id.strip().lower():
            # Unknown team > home
            return redirect(url_for("index"))
        env_name = _selected_env_name(cfg, team)
        team, environment, services, products = cfg.resolve_view(team.id, env_name)
        return render_template(
            "team.html",
            version=app.config["APP_VERSION"],
            path=request.path,
            title=cfg.title,
            subtitle=cfg.subtitle,
            team=team,
            teams=cfg.teams,
            environments=cfg.environments,
            selected_environment=environment.name if environment else env_name,
            selected_environment_label=environment.label if environment else env_name,
            selected_team=team.id if team else None,
            environment=environment,
            env_meta=environment.metadata_dict() if environment else {},
            env_type=environment.env_type if environment else "",
            env_cloud=environment.cloud if environment else "",
            env_cluster=environment.cluster if environment else "",
            env_region=environment.region if environment else "",
            env_account=environment.account if environment else "",
            cluster=_cluster_label(environment),
            services=services,
            products=products,
        )

    @app.get("/dashboard")
    def dashboard():
        """Legacy route: redirect to default team landing (or home)."""
        cfg = current_landing()
        team = cfg.resolve_team(None)
        env = request.args.get("env")
        if team is None:
            return redirect(url_for("index", env=env) if env else url_for("index"))
        return redirect(
            url_for("team_landing", team_id=team.id, env=env) if env else url_for("team_landing", team_id=team.id)
        )

    return app


def main():
    app = create_app()
    host = os.environ.get("BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
