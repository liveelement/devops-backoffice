# Build from this directory:
#   docker build -t ghcr.io/liveelement/devops-backoffice:0.1.0 .
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_VERSION=0.1.0 \
    OTEL_SERVICE_NAME=devops-backoffice \
    PROMETHEUS_MULTIPROC_DIR=/var/prometheus
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/prometheus \
    && chown 10001:10001 /var/prometheus
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app/src /app/src
COPY gunicorn.conf.py /app/gunicorn.conf.py
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "backoffice.wsgi:app"]
