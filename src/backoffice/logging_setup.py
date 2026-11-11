"""JSON logs on stdout for Fluent Bit / Elasticsearch."""

import json
import logging
import os
import sys
from datetime import UTC, datetime


def _trace_fields():
    # Attach OTel ids when a span is active; never break logging on failure.
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return {}
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    except (ImportError, AttributeError, TypeError, ValueError):
        return {}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.environ.get("OTEL_SERVICE_NAME", "devops-backoffice"),
            "environment": os.environ.get("ENVIRONMENT", "dev"),
            "version": os.environ.get("APP_VERSION", "0.0.0"),
        }
        payload.update(_trace_fields())

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key in ("method", "path", "status", "duration_ms", "remote_addr"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level=None):
    log_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("gunicorn.access").setLevel(logging.WARNING)
