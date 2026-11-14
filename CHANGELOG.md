# Changelog

## Unreleased

- Docs: full configuration guide in `docs/CONFIGURATION.md` (hub/env/team layout, version discovery, credentials, merge rules).

## 0.2.0 — 2026-11-15

- Multi-team landing: `/` team picker and `/t/<team>?env=` landings.
- Config: platform `services` + team `products` / overlays; `category`, declared `version`.
- **Version discovery:** `config` | `http` (`version_url` / `version_discovery`) | `kubernetes` via in-cluster service account (`from`: `image_tag` | `image_digest` | `label` | `annotation`). Live sources preferred; config fallback. `GET /api/service-status`.
- Environment metadata: `type` (dev/qa/uat/prod), `cloud`, `account`, `region`, optional `cluster`.
- Multi-file config: `hub.yaml` + `environments/*.yaml` + `teams/*.yaml` (flat ConfigMap keys supported).
- Hot-reload of YAML (`LINKS_CONFIG_RELOAD=true` by default); `GET /api/config`.
- Credentials cheat-sheet on services (location, key names, copyable commands, external links — no secret fetch).
- UI: flat tables, descriptions, version badges (source in tooltip), dark/light theme, column search on Tool/URL.
- Deploy: ServiceAccount + ClusterRole for K8s discovery (`K8S_VERSION_DISCOVERY`).
- API: `/api/teams`, `/api/links?team=&env=`, `/api/service-status`.
- `/dashboard` redirects to the default team landing.
- Backward compatible with flat `environments.*.links` (implicit `default` team) and legacy `version_url`.
- Demo teams: `platform`, `payments`, `checkout`.
- Docker image target: `ghcr.io/liveelement/devops-backoffice:0.2.0`.

## 0.1.0 — 2026-11-11

- Initial public extract from the private lab ops landing (Flask + Jinja2).
- Sanitized default `links.yaml` (no private lab remotes).
- Docker image target: `ghcr.io/liveelement/devops-backoffice:0.1.0`.
- Minimal `deploy/` Kubernetes manifests (Deployment, Service, ConfigMap).
