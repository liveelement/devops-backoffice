"""OpenTelemetry tracing for devops-backoffice."""

import logging
import os

logger = logging.getLogger(__name__)


def setup_telemetry(app):
    # Skip when disabled or no collector endpoint (typical for local runs).
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}:
        logger.info("opentelemetry disabled")
        return

    endpoint = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").rstrip("/")
    if not endpoint:
        logger.info("opentelemetry skipped (no OTEL_EXPORTER_OTLP_ENDPOINT)")
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "devops-backoffice"),
            "service.version": os.environ.get("APP_VERSION", "0.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "dev"),
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument_app(
        app,
        excluded_urls="healthz,readyz,metrics",
    )
    logger.info("opentelemetry enabled -> %s", endpoint)
