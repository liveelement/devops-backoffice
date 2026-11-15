# Configuration guide

How to configure **devops-backoffice**: one hub instance, many teams × environments, with platform services, team products, version discovery, and credential cheat-sheets.

Point the process at your files with `LINKS_CONFIG_PATH` (directory preferred). Changes reload automatically when `LINKS_CONFIG_RELOAD=true` (default).

---

## Mental model

```text
                    ┌──────────── hub.yaml ────────────┐
                    │  title, defaults, display order  │
                    └───────────────┬──────────────────┘
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
  environments/<env>.yaml                          teams/<team>.yaml
  (shared platform tools)                          (products + overlays)
           │                                                 │
           └────────────────────┬────────────────────────────┘
                                ▼
                     landing for /t/<team>?env=<env>
              platform services  ∪  team services  ∪  products
```

| Layer | File | What it defines |
| --- | --- | --- |
| Hub | `hub.yaml` | Site title, default team/env, sort order |
| Environment | `environments/<name>.yaml` | Cloud/account metadata + **platform** services (Argo, Grafana, …) |
| Team | `teams/<id>.yaml` | Team label + per-env **products** and optional extra/overridden **services** |

On a team landing, each viewer sees:

1. **Platform services** from the selected environment (shared by every team).
2. **Team service overlays** for that env (same `id` replaces the platform row; new `id` appends).
3. **Team products** for that env (domain apps, APIs, admin UIs).

---

## File layout

### Multi-file (recommended)

```text
config/
  hub.yaml
  environments/
    dev.yaml
    prod.yaml
  teams/
    platform.yaml
    payments.yaml
    checkout.yaml
```

Set:

```bash
export LINKS_CONFIG_PATH=/path/to/config
```

### Flat names (ConfigMap-friendly)

Kubernetes ConfigMaps often cannot nest directories. Put the same content in one directory with dotted names:

```text
config/
  hub.yaml
  environments.dev.yaml
  environments.prod.yaml
  teams.platform.yaml
  teams.payments.yaml
```

`deploy/configmap-links.yaml` uses this shape.

### Single file (legacy)

A monolithic `links.yaml` (or any one YAML that contains hub + `environments` + `teams`) still works:

```bash
export LINKS_CONFIG_PATH=/path/to/links.yaml
```

---

## Hub (`hub.yaml`)

```yaml
title: DevOps Operations Hub
subtitle: Team landings for platform services and products across environments.
default_environment: dev
default_team: platform
environment_order:
  - dev
  - prod
team_order:
  - platform
  - payments
  - checkout
```

| Field | Required | Description |
| --- | --- | --- |
| `title` | no | Header title on every page |
| `subtitle` | no | Short line under the title |
| `default_environment` | no | Env used when `?env=` is missing |
| `default_team` | no | Team used for redirects / first pick |
| `environment_order` | no | Display order of env tabs (others follow alphabetically) |
| `team_order` | no | Display order on the team picker |

---

## Environment (`environments/<name>.yaml`)

File stem is the environment id (`dev`, `prod`, …).

```yaml
label: Development
metadata:
  type: dev                 # dev | qa | uat | prod
  cloud: aws                # aws | azure | gcp | on-prem (aliases ok)
  account: "111111111111"
  region: eu-central-1
  cluster: lab-dev          # kubectl context / cluster name hint
services:
  - id: argocd
    label: Argo CD
    # ... see Service / product entries
```

### Metadata

Shown as compact env chips on the landing. Also used to fill `{{placeholders}}` in credentials.

| Field | Values / notes |
| --- | --- |
| `type` | `dev`, `qa`, `uat`, `prod` (aliases: `development`→dev, `production`→prod, `staging`→uat) |
| `cloud` | `aws`, `azure`, `gcp`, `on-prem` (aliases: `amazon`, `google`, …) |
| `account` | Cloud account id (quoted if numeric) |
| `region` | Region string |
| `cluster` | Cluster / kube-context name |

You may put the same keys flat on the env root instead of under `metadata:`.

### Platform `services`

List of ops tools shared across teams for this environment. Legacy key `links:` is accepted as an alias for `services:`.

---

## Team (`teams/<id>.yaml`)

File stem is the team id used in URLs: `/t/payments`.

```yaml
label: Payments
description: Payments domain — APIs and admin surfaces per environment.
default_environment: dev
environments:
  dev:
    products:
      - id: payments-api
        label: Payments API
        url: https://payments-api.dev.example
        description: Core payments HTTP API (dev).
        version: "1.4.2"
        external: true
    services:
      - id: payments-runbook
        label: Payments runbook
        category: other
        url: https://wiki.example/payments/runbook
        description: Team on-call and incident runbook.
        external: true
  prod:
    products:
      - id: payments-api
        label: Payments API
        url: https://payments-api.example.com
        version: "1.4.0"
        external: true
```

| Field | Description |
| --- | --- |
| `label` | Human name on the picker and landing |
| `description` | Short blurb on the team card |
| `default_environment` | Optional team-specific default env |
| `environments.<env>.products` | Domain apps for that env |
| `environments.<env>.services` | Extra services, or overrides of platform services by matching `id` |

---

## Service / product entries

Platform services, team services, and products share the same shape.

```yaml
- id: grafana                 # stable id (slug); required for merges / badges
  label: Grafana              # required — UI title
  url: https://grafana.example
  description: Metrics dashboards.
  category: observability     # services only — see categories
  kind: service               # optional; products default to product
  version: "11.2.0"           # declared version (see Version discovery)
  external: true              # open in new tab when true
  credentials:                # optional cheat-sheet (never fetches secrets)
    ...
```

| Field | Required | Notes |
| --- | --- | --- |
| `label` | **yes** | Display name |
| `url` | **yes** | Absolute or relative URL |
| `id` | recommended | Slug; derived from label if omitted. Must be unique within services or products for a view |
| `description` | no | One-line help under the name |
| `category` | no | `gitops` \| `observability` \| `cloud` \| `ci` \| `other` (unknown → `other`) |
| `icon` | no | Catalog key for the row mark (see Icons). Alias: `logo`. If omitted, inferred from `id` / category |
| `version` | no | Declared version and/or discovery map (below) |
| `version_url` | no | Legacy HTTP probe URL |
| `version_discovery` | no | Ordered list of discovery sources |
| `external` | no | Default `true` |
| `credentials` | no | How operators fetch secrets themselves |

**Categories** control table grouping order: gitops → observability → cloud → ci → other.

### Icons

Small tinted marks next to the tool name for fast visual scan. Pick from the built-in catalog:

| Key | Typical use |
| --- | --- |
| `argocd` | Argo CD / GitOps |
| `grafana` | Grafana |
| `victoria` | VictoriaMetrics |
| `jaeger` | Jaeger |
| `kibana` | Kibana / Elastic |
| `github` / `gitlab` | Source or Actions / GitLab CI |
| `aws` / `ecr` | AWS console / ECR |
| `git` | Git remote |
| `pipeline` | Generic CI |
| `cloud` / `container` | Cloud / registry |
| `api` / `admin` / `web` | Team products |
| `docs` | Runbooks / wiki |
| `hub` | This backoffice / platform hub |
| `tool` | Default fallback |

```yaml
- id: grafana
  label: Grafana
  icon: grafana
  url: https://grafana.example
```

List keys at runtime: `GET /api/icons`. Unknown `icon` values fall back via `id` aliases, then category default, then `tool`.

---

## Version discovery

Versions appear as badges on the landing. The browser calls `GET /api/service-status?team=&env=`; the server tries each configured source and returns the winner.

**Priority:** first successful **live** source (`http` or `kubernetes`) wins. If every live probe fails, the **config** value is shown. Declared-only entries never leave the process.

### 1. Config (declared)

```yaml
version: "2.12.3"
```

or inside a map:

```yaml
version:
  config: "2.12.3"
```

### 2. HTTP API

Unauthenticated `GET`. Response may be JSON (`version`, `Version`, `gitVersion`, …), plain text, or a header.

```yaml
# Short form
version_url: https://argocd.example/api/version

# Explicit
version_discovery:
  - source: http
    url: https://argocd.example/api/version
    json_path: Version        # optional dotted or /pointer path
    header: X-App-Version     # optional response header name
```

### 3. Kubernetes (in-cluster service account)

Only works when the pod has a mounted service account and `KUBERNETES_SERVICE_HOST` is set. Outside the cluster the attempt returns `not_in_cluster` and the next/fallback source is used.

You **must** say where the version comes from with `from`:

| `from` | Reads |
| --- | --- |
| `image_tag` | Tag of the container image (default) |
| `image_digest` | Image digest (shortened); falls back to tag |
| `label` | Object label (`key`, default `app.kubernetes.io/version`) |
| `annotation` | Object annotation (`key`) |

```yaml
version_discovery:
  - source: kubernetes
    namespace: argocd
    kind: Deployment            # Deployment | StatefulSet | DaemonSet | Pod
    name: argocd-server         # OR label_selector: app.kubernetes.io/name=argocd-server
    from: image_tag
    container: argocd-server    # optional; first container if omitted
    # key: app.kubernetes.io/version   # for label | annotation
```

Aliases: `source: k8s`, `selector` for `label_selector`, `resource: deployment/argocd-server`.

### Combining sources

**List form** — try order is the list order (config often first as fallback after lives fail):

```yaml
version: "2.12.3"
version_discovery:
  - source: http
    url: https://argocd.example/api/version
  - source: kubernetes
    namespace: argocd
    kind: Deployment
    name: argocd-server
    from: image_tag
    container: argocd-server
```

**Map form** — compact:

```yaml
version:
  config: "11.2.0"
  http:
    url: https://grafana.example/api/health
    json_path: version
  kubernetes:
    namespace: observability
    kind: Deployment
    name: grafana
    from: image_tag
    container: grafana
```

### Cluster RBAC

`deploy/` ships a ServiceAccount + ClusterRole with `get`/`list` on Deployments, StatefulSets, DaemonSets, and Pods. Narrow to namespaced Roles if you prefer. Toggle with `K8S_VERSION_DISCOVERY=true|false`.

---

## Port-forward cheat-sheet

Optional — only add on services that need a local tunnel (lab UIs, break-glass). **The backoffice never opens tunnels**; it shows copy-paste `kubectl port-forward` commands.

```yaml
port_forward:
  title: Port-forward Argo CD UI
  namespace: argocd
  service: argocd-server      # → svc/argocd-server
  # or resource: svc/argocd-server
  # or deployment: grafana / pod: …
  ports: "8081:443"           # local:remote
  address: 127.0.0.1          # optional (default)
  # commands:                 # optional full override
  #   - label: Port-forward
  #     command: kubectl -n {{namespace}} port-forward --address {{address}} {{resource}} {{ports}}
```

If `commands` are omitted, a default `kubectl -n … port-forward --address …` line is generated. When env `metadata.cluster` is set, a context-hint command is prepended. Placeholders: `{{namespace}}`, `{{resource}}`, `{{ports}}`, `{{local_port}}`, `{{remote_port}}`, `{{address}}`, plus the same env placeholders as credentials.

Demo config enables this only for Argo CD, Grafana, VictoriaMetrics, Jaeger, and Kibana — not for CI / cloud / git tiles.

## Credentials cheat-sheet

Optional block on any service/product. **The backoffice never reads secret values** — it only shows where they live and copy-paste commands for humans.

```yaml
credentials:
  title: Grafana admin
  provider: eks                 # eks | aws-secrets-manager | vault | external-secrets
  namespace: observability
  secret: grafana-admin
  keys:                         # key *names* only
    - admin-user
    - admin-password
  commands:
    - label: Username
      command: kubectl -n observability get secret grafana-admin -o jsonpath="{.data.admin-user}" | base64 -d
    - label: Password
      command: kubectl -n observability get secret grafana-admin -o jsonpath="{.data.admin-password}" | base64 -d
  links:
    - label: AWS account console
      url: https://{{account}}.signin.aws.amazon.com/console?region={{region}}
```

### Placeholders

Filled from environment metadata (+ credential fields):

| Placeholder | Source |
| --- | --- |
| `{{cluster}}` | `credentials.cluster` or env `metadata.cluster` |
| `{{region}}` | env `metadata.region` |
| `{{account}}` | env `metadata.account` |
| `{{cloud}}` | env `metadata.cloud` |
| `{{type}}` | env `metadata.type` |
| `{{namespace}}` | credentials `namespace` |
| `{{secret}}` | credentials `secret` |

---

## Merge rules (team × env)

For `GET /t/payments?env=dev` (and matching APIs):

1. Start from `environments/dev.yaml` → `services`.
2. Apply `teams/payments.yaml` → `environments.dev.services` (same `id` overwrites; new ids append).
3. Attach `teams/payments.yaml` → `environments.dev.products`.

Platform-only teams (e.g. `platform`) can ship just a product self-link and rely entirely on shared services.

If no `teams/` exist, a synthetic `default` team exposes all platform services.

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `LINKS_CONFIG_PATH` | packaged / repo `config` | Config **file** or **directory** |
| `LINKS_CONFIG_RELOAD` | `true` | Hot-reload YAML on change |
| `K8S_VERSION_DISCOVERY` | `true` | Allow in-cluster Kubernetes probes |
| `APP_VERSION` | image / build | Self `/version` and log field |
| `PORT` / `BIND_HOST` | `8080` / `0.0.0.0` | Listen address |
| `OTEL_SDK_DISABLED` | unset | Set `true` to skip OpenTelemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Enable OTLP export when set |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENVIRONMENT` | `dev` | Log / trace environment attribute |

Useful debug endpoints:

| Route | Returns |
| --- | --- |
| `GET /api/config` | Loaded sources + reload fingerprint |
| `GET /api/links?team=&env=` | Merged services + products JSON |
| `GET /api/service-status?team=&env=` | Version discovery results (`source`, `live_version`, `attempts`) |

---

## Minimal starter

```text
config/
  hub.yaml
  environments/
    dev.yaml
  teams/
    platform.yaml
```

**hub.yaml**

```yaml
title: Ops Hub
default_environment: dev
default_team: platform
```

**environments/dev.yaml**

```yaml
label: Development
metadata:
  type: dev
  cloud: aws
  region: eu-central-1
services:
  - id: argocd
    label: Argo CD
    category: gitops
    url: https://argocd.example
    version: "2.12.3"
    version_url: https://argocd.example/api/version
```

**teams/platform.yaml**

```yaml
label: Platform
description: Shared tooling.
environments:
  dev:
    products: []
```

Replace example URLs, add more envs/teams, then mount the directory into the Deployment (`LINKS_CONFIG_PATH=/config`).

---

## Checklist before production

- [ ] Replace every `REPLACE_WITH_DOMAIN` / example URL
- [ ] Set real `metadata.account`, `region`, `cluster` per env
- [ ] Prefer HTTPS URLs for prod services
- [ ] Decide version strategy: config-only, HTTP, and/or Kubernetes `from`
- [ ] If using Kubernetes discovery: ServiceAccount + RBAC; fix ClusterRoleBinding namespace
- [ ] Credentials: commands and key *names* only — no secret values in YAML
- [ ] Mount config as ConfigMap/Secret volume; enable or disable hot-reload deliberately
