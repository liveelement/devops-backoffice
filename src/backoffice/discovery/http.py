"""HTTP /version-style probes."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 1.5


def _dig(data, path: str):
    """Resolve dotted path or JSON-pointer-like /a/b path."""
    if not path:
        return None
    parts = [p for p in path.replace(".", "/").strip("/").split("/") if p]
    cur = data
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def extract_version(body: bytes, content_type: str, headers, json_path="", header="") -> str | None:
    if header:
        value = headers.get(header)
        if value and str(value).strip():
            return str(value).strip()

    header_version = (
        headers.get("Version") or headers.get("X-Version") or headers.get("X-App-Version")
    )
    if header_version:
        return str(header_version).strip() or None

    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return None

    if "json" in (content_type or "").lower() or text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            if json_path:
                value = _dig(data, json_path)
                if value is not None and str(value).strip():
                    return str(value).strip()
            for key in ("version", "Version", "app_version", "gitVersion", "serverVersion"):
                value = data.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
            status = data.get("Status") or data.get("status")
            if isinstance(status, dict):
                for key in ("version", "Version"):
                    value = status.get(key)
                    if value is not None and str(value).strip():
                        return str(value).strip()
        if isinstance(data, str) and data.strip():
            return data.strip()

    if len(text) <= 64 and "\n" not in text and "<" not in text:
        return text
    return None


def probe_http(url: str, json_path="", header="", timeout: float = _DEFAULT_TIMEOUT_S) -> dict:
    result = {
        "source": "http",
        "status": "unknown",
        "live_version": None,
        "error": None,
        "detail": url,
    }
    if not url:
        result["error"] = "empty_url"
        return result

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "devops-backoffice-discovery/0.2",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            content_type = resp.headers.get("Content-Type", "")
            live = extract_version(body, content_type, resp.headers, json_path=json_path, header=header)
            result["status"] = "ok"
            if live:
                result["live_version"] = live
            else:
                result["error"] = "no_version_in_response"
    except urllib.error.HTTPError as exc:
        result["error"] = f"http_{exc.code}"
        logger.debug("http discovery failed %s: %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        result["error"] = type(exc).__name__
        logger.debug("http discovery failed %s: %s", url, exc)
    return result
