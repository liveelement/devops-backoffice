"""In-cluster Kubernetes version discovery via the pod service account."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_SA_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
_SA_CA = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
_DEFAULT_TIMEOUT_S = 1.5

_KIND_PATH = {
    "deployment": "deployments",
    "deployments": "deployments",
    "statefulset": "statefulsets",
    "statefulsets": "statefulsets",
    "daemonset": "daemonsets",
    "daemonsets": "daemonsets",
    "pod": "pods",
    "pods": "pods",
}


def in_cluster() -> bool:
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST")) and os.path.isfile(_SA_TOKEN)


def _api_root() -> str:
    host = os.environ.get("KUBERNETES_SERVICE_HOST", "").strip()
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443").strip() or "443"
    return f"https://{host}:{port}"


def _ssl_context():
    ctx = ssl.create_default_context()
    if os.path.isfile(_SA_CA):
        ctx.load_verify_locations(_SA_CA)
    return ctx


def _request_json(path: str, timeout: float = _DEFAULT_TIMEOUT_S) -> dict:
    token = open(_SA_TOKEN, encoding="utf-8").read().strip()
    url = _api_root() + path
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "devops-backoffice-discovery/0.2",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _image_tag(image: str) -> str | None:
    if not image:
        return None
    # strip digest
    if "@" in image:
        image = image.split("@", 1)[0]
    if ":" not in image:
        return "latest"
    # registry:port/name:tag — split on last ':'
    tag = image.rsplit(":", 1)[-1]
    if "/" in tag:
        return "latest"
    return tag or None


def _image_digest(image: str) -> str | None:
    if not image or "@" not in image:
        return None
    digest = image.split("@", 1)[1].strip()
    if digest.startswith("sha256:") and len(digest) > 15:
        return digest[:15] + "…"
    return digest or None


def _containers_from_workload(obj: dict) -> list[dict]:
    spec = obj.get("spec") or {}
    # Pod
    if "containers" in spec:
        return list(spec.get("containers") or [])
    # Deployment / StatefulSet / DaemonSet
    template = spec.get("template") or {}
    pod_spec = template.get("spec") or {}
    return list(pod_spec.get("containers") or [])


def _pick_container(containers: list[dict], name: str) -> dict | None:
    if not containers:
        return None
    if name:
        for item in containers:
            if item.get("name") == name:
                return item
    return containers[0]


def _version_from_object(obj: dict, from_field: str, container: str, key: str) -> str | None:
    meta = obj.get("metadata") or {}
    if from_field == "label":
        labels = meta.get("labels") or {}
        label_key = key or "app.kubernetes.io/version"
        value = labels.get(label_key)
        return str(value).strip() if value else None
    if from_field == "annotation":
        annotations = meta.get("annotations") or {}
        ann_key = key or "app.kubernetes.io/version"
        value = annotations.get(ann_key)
        return str(value).strip() if value else None

    container_obj = _pick_container(_containers_from_workload(obj), container)
    if not container_obj:
        return None
    image = str(container_obj.get("image") or "")
    if from_field == "image_digest":
        return _image_digest(image) or _image_tag(image)
    return _image_tag(image)


def probe_kubernetes(
    *,
    namespace: str,
    kind: str = "Deployment",
    name: str = "",
    label_selector: str = "",
    from_field: str = "image_tag",
    container: str = "",
    key: str = "",
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> dict:
    detail = f"{namespace}/{kind}/{name or label_selector}"
    result = {
        "source": "kubernetes",
        "status": "unknown",
        "live_version": None,
        "error": None,
        "detail": detail,
    }
    if not in_cluster():
        result["error"] = "not_in_cluster"
        return result
    if os.environ.get("K8S_VERSION_DISCOVERY", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        result["error"] = "k8s_discovery_disabled"
        return result

    resource = _KIND_PATH.get(kind.strip().lower())
    if not resource:
        result["error"] = f"unsupported_kind:{kind}"
        return result
    if not namespace:
        result["error"] = "missing_namespace"
        return result

    try:
        if name:
            path = f"/apis/apps/v1/namespaces/{urllib.parse.quote(namespace)}/{resource}/{urllib.parse.quote(name)}"
            if resource == "pods":
                path = f"/api/v1/namespaces/{urllib.parse.quote(namespace)}/pods/{urllib.parse.quote(name)}"
            obj = _request_json(path, timeout=timeout)
        elif label_selector:
            base = f"/apis/apps/v1/namespaces/{urllib.parse.quote(namespace)}/{resource}"
            if resource == "pods":
                base = f"/api/v1/namespaces/{urllib.parse.quote(namespace)}/pods"
            query = urllib.parse.urlencode({"labelSelector": label_selector})
            listing = _request_json(f"{base}?{query}", timeout=timeout)
            items = listing.get("items") or []
            if not items:
                result["error"] = "no_matching_resources"
                return result
            obj = items[0]
        else:
            result["error"] = "missing_name_or_selector"
            return result

        live = _version_from_object(obj, from_field=from_field, container=container, key=key)
        result["status"] = "ok"
        if live:
            result["live_version"] = live
        else:
            result["error"] = "no_version_in_resource"
    except urllib.error.HTTPError as exc:
        result["error"] = f"http_{exc.code}"
        logger.debug("k8s discovery failed %s: %s", detail, exc)
    except Exception as exc:  # noqa: BLE001
        result["error"] = type(exc).__name__
        logger.debug("k8s discovery failed %s: %s", detail, exc)
    return result
