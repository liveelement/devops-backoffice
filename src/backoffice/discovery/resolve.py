"""Resolve service versions from configured discovery sources."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from backoffice.discovery.http import probe_http
from backoffice.discovery.k8s import probe_kubernetes

logger = logging.getLogger(__name__)

_MAX_WORKERS = 6
_TIMEOUT_S = 1.5


def _resolve_one(service) -> dict:
    declared = getattr(service, "version", "") or None
    sources = list(getattr(service, "version_sources", []) or [])
    payload = {
        "id": service.id,
        "declared_version": declared,
        "live_version": None,
        "status": "unknown",
        "source": None,
        "error": None,
        "detail": None,
        "attempts": [],
    }

    if not sources:
        if declared:
            payload["status"] = "ok"
            payload["source"] = "config"
            payload["live_version"] = declared
        return payload

    for src in sources:
        source_type = src.source
        fields = src.fields
        if source_type == "config":
            value = fields.get("value") or declared
            attempt = {
                "source": "config",
                "status": "ok" if value else "unknown",
                "live_version": value or None,
                "error": None if value else "empty_config_version",
            }
            payload["attempts"].append(attempt)
            if value:
                payload["status"] = "ok"
                payload["source"] = "config"
                payload["live_version"] = value
                payload["error"] = None
                # Continue — prefer later live sources if they succeed.
            continue

        if source_type == "http":
            attempt = probe_http(
                fields.get("url", ""),
                json_path=fields.get("json_path", ""),
                header=fields.get("header", ""),
                timeout=_TIMEOUT_S,
            )
            payload["attempts"].append(attempt)
            if attempt.get("live_version"):
                payload["status"] = "ok"
                payload["source"] = "http"
                payload["live_version"] = attempt["live_version"]
                payload["error"] = None
                payload["detail"] = attempt.get("detail")
                return payload
            payload["error"] = attempt.get("error")
            continue

        if source_type == "kubernetes":
            attempt = probe_kubernetes(
                namespace=fields.get("namespace", ""),
                kind=fields.get("kind", "Deployment"),
                name=fields.get("name", ""),
                label_selector=fields.get("label_selector", ""),
                from_field=fields.get("from_field", "image_tag"),
                container=fields.get("container", ""),
                key=fields.get("key", ""),
                timeout=_TIMEOUT_S,
            )
            payload["attempts"].append(attempt)
            if attempt.get("live_version"):
                payload["status"] = "ok"
                payload["source"] = "kubernetes"
                payload["live_version"] = attempt["live_version"]
                payload["error"] = None
                payload["detail"] = attempt.get("detail")
                return payload
            payload["error"] = attempt.get("error")
            continue

    # Prefer any version already found (config mid-loop, or declared fallback).
    if payload.get("live_version"):
        payload["status"] = "ok"
        if not payload.get("source"):
            payload["source"] = "config"
        # Soft-warn only: keep last live-probe error in attempts, not as hard failure.
        if payload["source"] == "config":
            live_errors = [
                a.get("error")
                for a in payload["attempts"]
                if a.get("source") in {"http", "kubernetes"} and a.get("error")
            ]
            payload["error"] = live_errors[-1] if live_errors else None
        else:
            payload["error"] = None
        return payload

    if declared:
        payload["live_version"] = declared
        payload["source"] = "config"
        payload["status"] = "ok"
        return payload
    return payload


def resolve_service_versions(services) -> list[dict]:
    """
    Resolve versions for services that have version_sources (or legacy version_url).

    Live sources (http/kubernetes) are preferred when they succeed; config is fallback.
    """
    targets = [
        svc
        for svc in services
        if getattr(svc, "version_sources", None)
        or getattr(svc, "version_url", "")
        or getattr(svc, "version", "")
    ]
    # Only spend probe workers on services that actually have live discovery.
    live_targets = [svc for svc in targets if getattr(svc, "has_live_version_discovery", lambda: False)()]
    config_only = [svc for svc in targets if svc not in live_targets]

    results_by_id = {}
    for svc in config_only:
        results_by_id[svc.id] = _resolve_one(svc)

    if live_targets:
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(live_targets))) as pool:
            futures = {pool.submit(_resolve_one, svc): svc.id for svc in live_targets}
            for future in as_completed(futures):
                svc_id = futures[future]
                try:
                    results_by_id[svc_id] = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("version resolve failed for %s: %s", svc_id, exc)
                    results_by_id[svc_id] = {
                        "id": svc_id,
                        "declared_version": None,
                        "live_version": None,
                        "status": "unknown",
                        "source": None,
                        "error": type(exc).__name__,
                        "detail": None,
                        "attempts": [],
                    }

    order = {svc.id: index for index, svc in enumerate(targets)}
    results = list(results_by_id.values())
    results.sort(key=lambda item: order.get(item["id"], 999))
    return results
