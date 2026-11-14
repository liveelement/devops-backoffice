# DevOps backoffice

Free Kubernetes **ops landing** for teams: one instance, many teams, per-environment shortcuts to platform services (Argo CD, Grafana, VictoriaMetrics, Kibana, Jaeger, CI, ECR, AWS Console, Git) and each team's products.

This is a **sibling product** to [Apply Path · AWS EKS](https://github.com/liveelement/apply-path-aws-eks). It is not part of the paid Apply Path tree.

| Asset | Location |
| --- | --- |
| Source | https://github.com/liveelement/devops-backoffice |
| Image | `ghcr.io/liveelement/devops-backoffice:0.2.0` |
| License | MIT |

## Run locally

```bash
export PYTHONPATH=src
export LINKS_CONFIG_PATH=config
export OTEL_SDK_DISABLED=true
python -c "from backoffice.app import create_app; create_app().run(host='127.0.0.1', port=8080)"
```

Or with Docker:

```bash
docker run --rm -p 8080:8080 \
  -e OTEL_SDK_DISABLED=true \
  -e LINKS_CONFIG_PATH=/config \
  -v "$PWD/config:/config:ro" \
  ghcr.io/liveelement/devops-backoffice:0.2.0
```

Open http://127.0.0.1:8080/ (team picker) or http://127.0.0.1:8080/t/payments?env=dev

## Configure

**Full guide:** [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — layout, field reference, version discovery, credentials, merge rules, env vars, starter checklist.

Quick shape:

```text
config/
  hub.yaml                 # title, defaults, order
  environments/
    dev.yaml               # platform services + metadata
    prod.yaml
  teams/
    platform.yaml          # products / service overlays
    payments.yaml
```

Set `LINKS_CONFIG_PATH` to that directory (or a single monolithic YAML). Flat ConfigMap keys work too: `environments.dev.yaml`, `teams.payments.yaml`. Hot-reload is on by default (`LINKS_CONFIG_RELOAD=true`).

| Route | Purpose |
| --- | --- |
| `/` | Team picker |
| `/t/<team>?env=` | Team landing (services + products) |
| `/api/teams` | Team list |
| `/api/links?team=&env=` | Merged JSON payload |
| `/api/service-status?team=&env=` | Version discovery (config / http / kubernetes) |
| `/api/config` | Config sources + reload status |

Replace `REPLACE_WITH_DOMAIN` and example URLs before production.

## Observability hooks

| Signal | How |
| --- | --- |
| Logs | JSON on stdout |
| Metrics | `/metrics` (prometheus-flask-exporter) |
| Traces | OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; disable with `OTEL_SDK_DISABLED=true` |

## Deploy sketch

Point a Deployment at `ghcr.io/liveelement/devops-backoffice:0.2.0`, mount the config directory (`LINKS_CONFIG_PATH=/config`), use the included ServiceAccount + RBAC if you want Kubernetes version discovery, and expose via Service / Ingress / Gateway of your choice. Helm charts from private labs are not required for v0. If you change the release namespace, update the `ClusterRoleBinding` subject namespace in `deploy/rbac.yaml`.

## Not included

- Auth / per-team visibility
- Credentialed Argo/Grafana APIs (HTTP probes are unauthenticated GETs)
- Terraform / EKS bootstrap (see Apply Path)
- Managed hosting
