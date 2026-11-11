# Changelog

## Unreleased

- Default links: add **CI**, **VictoriaMetrics**, and **ECR** tiles (dev + prod).
- UI: replace card grid with a split layout — tool list on the left, name/URL table on the right.

## 0.1.0 — 2026-11-11

- Initial public extract from the private lab ops landing (Flask + Jinja2).
- Sanitized default `links.yaml` (no private lab remotes).
- Docker image target: `ghcr.io/liveelement/devops-backoffice:0.1.0`.
- Minimal `deploy/` Kubernetes manifests (Deployment, Service, ConfigMap).
