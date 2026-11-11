"""Prometheus /metrics endpoint (VictoriaMetrics scrapes the pods)."""

import os


def setup_metrics(app):
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        os.makedirs(multiproc_dir, exist_ok=True)
        from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

        metrics = GunicornPrometheusMetrics.for_app_factory(
            defaults_prefix="backoffice",
            excluded_paths=["/healthz", "/readyz", "/metrics"],
        )
        metrics.init_app(app)
        return

    from prometheus_flask_exporter import PrometheusMetrics

    PrometheusMetrics(
        app,
        defaults_prefix="backoffice",
        excluded_paths=["/healthz", "/readyz", "/metrics"],
    )
