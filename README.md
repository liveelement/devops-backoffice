# DevOps backoffice

Free Kubernetes **ops landing**: one page for Argo CD, Grafana, Kibana, Jaeger, AWS Console, and your Git remote — per environment.

This is a **sibling product** to [Apply Path · AWS EKS](https://github.com/liveelement/apply-path-aws-eks). It is not part of the paid Apply Path tree.

| Asset | Location |
| --- | --- |
| Source | https://github.com/liveelement/devops-backoffice |
| Image | `ghcr.io/liveelement/devops-backoffice:0.1.0` |
| License | MIT |

## Run locally

```bash
export PYTHONPATH=src
export LINKS_CONFIG_PATH=config/links.yaml
export OTEL_SDK_DISABLED=true
python -c "from backoffice.app import create_app; create_app().run(host='127.0.0.1', port=8080)"
```

Or with Docker:

```bash
docker run --rm -p 8080:8080 \
  -e OTEL_SDK_DISABLED=true \
  -e LINKS_CONFIG_PATH=/config/links.yaml \
  -v "$PWD/config/links.yaml:/config/links.yaml:ro" \
  ghcr.io/liveelement/devops-backoffice:0.1.0
```

Open http://127.0.0.1:8080/

## Configure links

Edit `config/links.yaml` (or mount it and set `LINKS_CONFIG_PATH`). Use `/?env=dev` or `/?env=prod`. JSON: `GET /api/links?env=prod`.

Replace `REPLACE_WITH_DOMAIN` and the example Git URL before you use this in a real cluster.

## Observability hooks

| Signal | How |
| --- | --- |
| Logs | JSON on stdout |
| Metrics | `/metrics` (prometheus-flask-exporter) |
| Traces | OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; disable with `OTEL_SDK_DISABLED=true` |

## Deploy sketch

Point a Deployment at `ghcr.io/liveelement/devops-backoffice:0.1.0`, mount your `links.yaml`, and expose via Service / Ingress / Gateway of your choice. Helm charts from private labs are not required for v0.

## Not included

- Terraform / EKS bootstrap (see Apply Path)
- Istio / Rollouts canary vehicle wiring from the private lab
- Managed hosting
