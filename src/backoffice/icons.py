"""Curated service/product icon catalog for the ops landing."""

from __future__ import annotations

# Public icon keys usable in YAML: icon: grafana
ICON_CATALOG: tuple[str, ...] = (
    # Brand / product marks
    "argocd",
    "grafana",
    "victoria",
    "jaeger",
    "kibana",
    "github",
    "gitlab",
    "aws",
    "ecr",
    # Generic
    "git",
    "pipeline",
    "cloud",
    "container",
    "api",
    "admin",
    "web",
    "docs",
    "hub",
    "tool",
)

_ICON_SET = frozenset(ICON_CATALOG)

# Map link id / aliases → catalog key
_ALIASES = {
    "argocd": "argocd",
    "argo": "argocd",
    "argo-cd": "argocd",
    "grafana": "grafana",
    "victoriametrics": "victoria",
    "victoria-metrics": "victoria",
    "victoria": "victoria",
    "vm": "victoria",
    "jaeger": "jaeger",
    "kibana": "kibana",
    "elastic": "kibana",
    "elasticsearch": "kibana",
    "github": "github",
    "gh": "github",
    "gitlab": "gitlab",
    "aws": "aws",
    "aws-console": "aws",
    "console": "aws",
    "ecr": "ecr",
    "git": "git",
    "ci": "pipeline",
    "actions": "pipeline",
    "jenkins": "pipeline",
    "pipeline": "pipeline",
    "cloud": "cloud",
    "container": "container",
    "docker": "container",
    "api": "api",
    "payments-api": "api",
    "admin": "admin",
    "payments-admin": "admin",
    "web": "web",
    "checkout-web": "web",
    "bff": "api",
    "checkout-bff": "api",
    "docs": "docs",
    "runbook": "docs",
    "payments-runbook": "docs",
    "wiki": "docs",
    "hub": "hub",
    "backoffice": "hub",
    "tool": "tool",
}

_CATEGORY_DEFAULT = {
    "gitops": "argocd",
    "observability": "grafana",
    "cloud": "cloud",
    "ci": "pipeline",
    "other": "tool",
}


def list_icons() -> list[str]:
    return list(ICON_CATALOG)


def resolve_icon(raw_icon: str = "", link_id: str = "", category: str = "other") -> str:
    """
    Resolve a catalog icon key.

    Priority: explicit icon → link id / aliases → category default → tool.
    Unknown explicit values fall through to id/category (and log-friendly fallback).
    """
    explicit = _slug(raw_icon)
    if explicit in _ICON_SET:
        return explicit
    if explicit and explicit in _ALIASES:
        return _ALIASES[explicit]

    lid = _slug(link_id)
    if lid in _ICON_SET:
        return lid
    if lid in _ALIASES:
        return _ALIASES[lid]

    cat = _slug(category) or "other"
    return _CATEGORY_DEFAULT.get(cat, "tool")


def _slug(value) -> str:
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    return "".join(ch for ch in text if ch.isalnum() or ch == "-")
