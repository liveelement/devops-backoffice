"""WSGI entrypoint for Gunicorn (avoids CLI --factory flag compatibility issues)."""

from backoffice.app import create_app

app = create_app()
