"""Backward-compatible exports for service version discovery."""

from backoffice.discovery.http import extract_version, probe_http
from backoffice.discovery.resolve import resolve_service_versions

# Legacy names used by older imports / docs.
probe_version = probe_http
_extract_version = extract_version


def probe_services(services, timeout=1.5):  # noqa: ARG001 — timeout kept for signature compat
    """Resolve versions for services (config / http / kubernetes)."""
    results = resolve_service_versions(services)
    # Shape expected by older UI consumers.
    for item in results:
        item.setdefault("version_url", item.get("detail"))
    return results
