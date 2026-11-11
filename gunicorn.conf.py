"""Gunicorn settings (incl. Prometheus multiprocess cleanup)."""

import sys

bind = "0.0.0.0:8080"
workers = 2
threads = 4
worker_class = "gthread"
accesslog = "-"
errorlog = "-"


def child_exit(server, worker):
    # Best-effort cleanup; never fail worker shutdown on metrics errors.
    try:
        from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

        GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"prometheus child_exit cleanup skipped: {exc}", file=sys.stderr)
