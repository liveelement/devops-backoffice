"""Load YAML config for the DevOps landing page."""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PACKAGE_CONFIG_DIR = Path(__file__).resolve().parent
_REPO_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

_CATEGORY_ORDER = ("gitops", "observability", "cloud", "ci", "other")


class CredentialRef:
    """How to obtain credentials externally — never holds secret values."""

    def __init__(
        self,
        title="",
        provider="eks",
        cluster="",
        namespace="",
        secret="",
        keys=None,
        links=None,
        commands=None,
    ):
        self.title = title
        self.provider = provider  # eks | aws-secrets-manager | vault | external-secrets
        self.cluster = cluster
        self.namespace = namespace
        self.secret = secret
        self.keys = list(keys or [])
        self.links = list(links or [])  # [{label, url}]
        self.commands = list(commands or [])  # [{label, command}]

    def to_dict(self):
        return {
            "title": self.title,
            "provider": self.provider,
            "cluster": self.cluster,
            "namespace": self.namespace,
            "secret": self.secret,
            "location": self.location,
            "keys": list(self.keys),
            "links": [dict(item) for item in self.links],
            "commands": [dict(item) for item in self.commands],
        }

    @property
    def location(self):
        if self.namespace and self.secret:
            return f"{self.namespace}/{self.secret}"
        return self.secret or self.namespace or ""

    def rendered(self, environment=None):
        """Fill {{cluster}}, {{region}}, … placeholders from env metadata."""
        meta = environment.metadata_dict() if environment is not None else {}
        cluster = self.cluster or meta.get("cluster") or ""
        ctx = {
            "cluster": cluster,
            "region": meta.get("region") or "",
            "account": meta.get("account") or "",
            "cloud": meta.get("cloud") or "",
            "type": meta.get("type") or "",
            "namespace": self.namespace or "",
            "secret": self.secret or "",
        }

        def fill(text):
            out = str(text or "")
            for key, value in ctx.items():
                out = out.replace("{{" + key + "}}", value)
            return out

        return CredentialRef(
            title=self.title or "Credentials",
            provider=self.provider,
            cluster=fill(cluster),
            namespace=fill(self.namespace),
            secret=fill(self.secret),
            keys=list(self.keys),
            links=[
                {"label": item.get("label", "Open"), "url": fill(item.get("url", ""))}
                for item in self.links
                if item.get("url")
            ],
            commands=[
                {
                    "label": item.get("label", "Command"),
                    "command": fill(item.get("command", "")).strip(),
                }
                for item in self.commands
                if str(item.get("command") or "").strip()
            ],
        )


class VersionSource:
    """One way to resolve a service/product version (config | http | kubernetes)."""

    def __init__(self, source, **fields):
        self.source = source  # config | http | kubernetes
        self.fields = dict(fields)

    def to_dict(self):
        payload = {"source": self.source}
        payload.update(self.fields)
        return payload

    @property
    def is_live(self):
        return self.source in {"http", "kubernetes"}


class OpsLink:
    def __init__(
        self,
        id,
        label,
        url,
        description="",
        external=True,
        category="other",
        version="",
        version_url="",
        kind="service",
        credentials=None,
        version_sources=None,
    ):
        self.id = id
        self.label = label
        self.url = url
        self.description = description
        self.external = external
        self.category = category or "other"
        self.version = version
        self.version_url = version_url  # legacy alias for http discovery
        self.kind = kind  # service | product
        self.credentials = credentials  # CredentialRef | None
        self.version_sources = list(version_sources or [])  # list[VersionSource]

    def has_live_version_discovery(self):
        return any(src.is_live for src in self.version_sources)

    def to_dict(self, environment=None):
        creds = None
        if self.credentials is not None:
            creds = self.credentials.rendered(environment).to_dict()
        return {
            "id": self.id,
            "label": self.label,
            "url": self.url,
            "description": self.description,
            "external": self.external,
            "category": self.category,
            "version": self.version,
            "version_url": self.version_url,
            "version_sources": [src.to_dict() for src in self.version_sources],
            "kind": self.kind,
            "credentials": creds,
        }

    def credentials_view(self, environment=None):
        if self.credentials is None:
            return None
        return self.credentials.rendered(environment)


_ENV_TYPES = ("dev", "qa", "uat", "prod")
_CLOUD_ALIASES = {
    "aws": "aws",
    "amazon": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google": "gcp",
    "on-prem": "on-prem",
    "onprem": "on-prem",
    "on_prem": "on-prem",
    "bare-metal": "on-prem",
    "baremetal": "on-prem",
}


class EnvironmentLinks:
    def __init__(
        self,
        name,
        label,
        services=None,
        links=None,
        env_type="",
        cloud="",
        region="",
        account="",
        cluster="",
    ):
        self.name = name
        self.label = label
        # Metadata per environment
        self.env_type = env_type  # dev | qa | uat | prod
        self.cloud = cloud  # aws | azure | gcp | on-prem | …
        self.region = region
        self.account = account  # AWS account ID (or cloud project id)
        self.cluster = cluster
        # Platform-layer services shared across teams on this env.
        self.services = list(services or [])
        # Backward-compat alias used by older templates/callers.
        self.links = list(links if links is not None else self.services)

    def metadata_dict(self):
        return {
            "type": self.env_type,
            "cloud": self.cloud,
            "account": self.account,
            "region": self.region,
            "cluster": self.cluster,
        }


class TeamEnvironment:
    def __init__(self, name, services=None, products=None):
        self.name = name
        self.services = list(services or [])
        self.products = list(products or [])


class Team:
    def __init__(
        self,
        id,
        label,
        description="",
        default_environment="",
        environments=None,
    ):
        self.id = id
        self.label = label
        self.description = description
        self.default_environment = default_environment
        self.environments = list(environments or [])  # TeamEnvironment

    def resolve_team_environment(self, env_name):
        wanted = (env_name or "").strip().lower()
        for item in self.environments:
            if item.name == wanted:
                return item
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "default_environment": self.default_environment,
        }


class LandingConfig:
    def __init__(
        self,
        title,
        subtitle,
        default_environment="dev",
        default_team="",
        environments=None,
        teams=None,
    ):
        self.title = title
        self.subtitle = subtitle
        self.default_environment = default_environment
        self.default_team = default_team
        self.environments = list(environments or [])
        self.teams = list(teams or [])

    def environment_names(self):
        return [env.name for env in self.environments]

    def team_ids(self):
        return [team.id for team in self.teams]

    def resolve_environment(self, name=None):
        if not self.environments:
            return None
        wanted = (name or self.default_environment or self.environments[0].name).strip().lower()
        for env in self.environments:
            if env.name == wanted:
                return env
        for env in self.environments:
            if env.name == self.default_environment:
                return env
        return self.environments[0]

    def resolve_team(self, team_id=None):
        if not self.teams:
            return None
        wanted = (team_id or self.default_team or self.teams[0].id).strip().lower()
        for team in self.teams:
            if team.id == wanted:
                return team
        for team in self.teams:
            if team.id == self.default_team:
                return team
        return self.teams[0]

    def resolve_view(self, team_id=None, env_name=None):
        """
        Merge platform services + team overlays/products for team × env.

        Returns (team, environment, services, products).
        """
        team = self.resolve_team(team_id)
        environment = self.resolve_environment(env_name)
        if environment is None:
            return team, None, [], []

        # Prefer team default env when caller omitted env and team has one.
        if not (env_name or "").strip() and team and team.default_environment:
            preferred = self.resolve_environment(team.default_environment)
            if preferred is not None:
                environment = preferred

        merged = {svc.id: svc for svc in environment.services}
        products = []
        if team is not None:
            team_env = team.resolve_team_environment(environment.name)
            if team_env is not None:
                for svc in team_env.services:
                    merged[svc.id] = svc
                products = list(team_env.products)

        services = list(merged.values())
        return team, environment, services, products


def _default_landing():
    return LandingConfig(
        title="DevOps Operations Hub",
        subtitle="Daily links for GitOps, observability, cloud, and source control.",
        default_environment="dev",
        default_team="",
        environments=[],
        teams=[],
    )


def _slug(value):
    return str(value or "").strip().lower().replace(" ", "-")


def _parse_credential_links(raw):
    links = []
    if not isinstance(raw, list):
        return links
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        label = str(item.get("label") or "Open").strip() or "Open"
        if url:
            links.append({"label": label, "url": url})
    return links


def _parse_credential_commands(raw):
    commands = []
    if not isinstance(raw, list):
        return commands
    for item in raw:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "").strip()
        label = str(item.get("label") or "Command").strip() or "Command"
        if command:
            commands.append({"label": label, "command": command})
    return commands


def _parse_credentials(raw):
    if not isinstance(raw, dict):
        return None
    keys_raw = raw.get("keys") or []
    keys = []
    if isinstance(keys_raw, list):
        keys = [str(k).strip() for k in keys_raw if str(k).strip()]
    provider = _slug(raw.get("provider") or "eks") or "eks"
    title = str(raw.get("title") or "").strip()
    namespace = str(raw.get("namespace") or "").strip()
    secret = str(raw.get("secret") or raw.get("name") or "").strip()
    cluster = str(raw.get("cluster") or "").strip()
    links = _parse_credential_links(raw.get("links"))
    commands = _parse_credential_commands(raw.get("commands"))
    if not (namespace or secret or links or commands):
        return None
    return CredentialRef(
        title=title or "Credentials",
        provider=provider,
        cluster=cluster,
        namespace=namespace,
        secret=secret,
        keys=keys,
        links=links,
        commands=commands,
    )


def _http_source_from_mapping(body, default_url=""):
    if not isinstance(body, dict):
        if isinstance(body, str) and body.strip():
            return VersionSource("http", url=body.strip())
        return None
    url = str(body.get("url") or default_url or "").strip()
    if not url:
        return None
    return VersionSource(
        "http",
        url=url,
        json_path=str(body.get("json_path") or body.get("json_pointer") or "").strip(),
        header=str(body.get("header") or "").strip(),
    )


def _k8s_source_from_mapping(body):
    if not isinstance(body, dict):
        return None
    namespace = str(body.get("namespace") or "").strip()
    kind = str(body.get("kind") or "Deployment").strip() or "Deployment"
    name = str(body.get("name") or "").strip()
    label_selector = str(body.get("label_selector") or body.get("selector") or "").strip()
    resource = str(body.get("resource") or "").strip()
    # resource: "deployment/argocd-server"
    if resource and "/" in resource and not name:
        kind_part, name = resource.split("/", 1)
        kind = kind_part.strip() or kind
        name = name.strip()
    if not namespace or not (name or label_selector):
        return None
    from_field = _slug(body.get("from") or "image_tag") or "image_tag"
    if from_field not in {"image_tag", "image_digest", "label", "annotation"}:
        from_field = "image_tag"
    return VersionSource(
        "kubernetes",
        namespace=namespace,
        kind=kind,
        name=name,
        label_selector=label_selector,
        from_field=from_field,
        container=str(body.get("container") or "").strip(),
        key=str(body.get("key") or body.get("label") or body.get("annotation") or "").strip(),
    )


def _parse_version_sources(raw_link):
    """
    Build ordered version discovery sources.

    Supported shapes:
      version: "1.2.3"
      version_url: https://.../version
      version_discovery:
        - source: config
        - source: http
          url: ...
        - source: kubernetes
          namespace: ...
          kind: Deployment
          name: ...
          from: image_tag|image_digest|label|annotation
          container: ...
          key: ...
      version:
        config: "1.2.3"
        http: {url: ...}
        kubernetes: {namespace, kind, name, from, ...}
    """
    sources = []
    version_raw = raw_link.get("version")
    declared = ""
    version_url = str(raw_link.get("version_url") or "").strip()

    if isinstance(version_raw, dict):
        declared = str(version_raw.get("config") or version_raw.get("value") or "").strip()
        if declared:
            sources.append(VersionSource("config", value=declared))
        http_src = _http_source_from_mapping(version_raw.get("http"), default_url=version_url)
        if http_src:
            sources.append(http_src)
        k8s_src = _k8s_source_from_mapping(
            version_raw.get("kubernetes") or version_raw.get("k8s")
        )
        if k8s_src:
            sources.append(k8s_src)
    else:
        declared = str(version_raw or "").strip()

    discovery = raw_link.get("version_discovery") or raw_link.get("discovery")
    if isinstance(discovery, list):
        for item in discovery:
            if not isinstance(item, dict):
                continue
            source_type = _slug(item.get("source") or item.get("type") or "")
            if source_type == "config":
                value = str(item.get("value") or declared or "").strip()
                if value:
                    sources.append(VersionSource("config", value=value))
                    if not declared:
                        declared = value
            elif source_type == "http":
                http_src = _http_source_from_mapping(item, default_url=version_url)
                if http_src:
                    sources.append(http_src)
            elif source_type in {"kubernetes", "k8s"}:
                k8s_src = _k8s_source_from_mapping(item)
                if k8s_src:
                    sources.append(k8s_src)
    elif isinstance(discovery, dict):
        if discovery.get("http"):
            http_src = _http_source_from_mapping(discovery.get("http"), default_url=version_url)
            if http_src:
                sources.append(http_src)
        if discovery.get("kubernetes") or discovery.get("k8s"):
            k8s_src = _k8s_source_from_mapping(discovery.get("kubernetes") or discovery.get("k8s"))
            if k8s_src:
                sources.append(k8s_src)

    # Legacy / defaults: ensure config + version_url are represented once.
    if declared and not any(src.source == "config" for src in sources):
        sources.insert(0, VersionSource("config", value=declared))
    if version_url and not any(src.source == "http" for src in sources):
        sources.append(VersionSource("http", url=version_url))

    # Deduplicate identical source dicts while preserving order.
    seen = set()
    unique = []
    for src in sources:
        key = tuple(sorted(src.to_dict().items()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(src)
    return declared, version_url, unique


def _parse_link(raw, index, default_kind="service"):
    url = str(raw.get("url") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not url or not label:
        logger.warning("skipping invalid link at index %s", index)
        return None
    link_id = _slug(raw.get("id") or label)
    category = _slug(raw.get("category") or "other") or "other"
    if category not in _CATEGORY_ORDER:
        category = "other"
    kind = _slug(raw.get("kind") or default_kind) or default_kind
    if kind not in {"service", "product"}:
        kind = default_kind
    declared, version_url, version_sources = _parse_version_sources(raw)
    return OpsLink(
        id=link_id,
        label=label,
        url=url,
        description=str(raw.get("description") or "").strip(),
        external=bool(raw.get("external", True)),
        category=category,
        version=declared,
        version_url=version_url,
        kind=kind,
        credentials=_parse_credentials(raw.get("credentials")),
        version_sources=version_sources,
    )


def _parse_links(raw_links, default_kind="service"):
    links = []
    if not isinstance(raw_links, list):
        return links
    for index, item in enumerate(raw_links):
        if isinstance(item, dict):
            parsed = _parse_link(item, index, default_kind=default_kind)
            if parsed is not None:
                links.append(parsed)
    return links


def _normalize_env_type(value, env_name=""):
    raw = str(value or "").strip().lower()
    if raw in _ENV_TYPES:
        return raw
    # Common aliases
    aliases = {"development": "dev", "production": "prod", "staging": "uat", "stage": "uat"}
    if raw in aliases:
        return aliases[raw]
    if env_name in _ENV_TYPES:
        return env_name
    return raw


def _normalize_cloud(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return _CLOUD_ALIASES.get(raw, raw)


def _env_meta(body, env_name=""):
    """
    Read environment metadata from nested `metadata:` or flat keys.

    Fields: type, cloud, account, region, cluster.
    """
    nested = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}

    def pick(*keys):
        for key in keys:
            if nested.get(key) not in (None, ""):
                return nested.get(key)
            if body.get(key) not in (None, ""):
                return body.get(key)
        return ""

    env_type = _normalize_env_type(pick("type", "env_type"), env_name=env_name)
    cloud = _normalize_cloud(pick("cloud", "provider", "infrastructure"))
    return {
        "env_type": env_type,
        "cloud": cloud,
        "account": str(pick("account", "aws_account", "aws_account_id") or "").strip(),
        "region": str(pick("region") or "").strip(),
        "cluster": str(pick("cluster") or "").strip(),
    }


def _services_from_env_body(body):
    """Prefer services:; fall back to legacy links:."""
    if isinstance(body.get("services"), list):
        return _parse_links(body.get("services"), default_kind="service")
    return _parse_links(body.get("links"), default_kind="service")


def _parse_environments(data):
    # Prefer environments: {dev: {...}, prod: {...}}.
    # Old flat `links:` list becomes a single `dev` env.
    raw_envs = data.get("environments")
    parsed = []

    if isinstance(raw_envs, dict):
        for name, body in raw_envs.items():
            env_name = str(name).strip().lower()
            if not env_name or not isinstance(body, dict):
                continue
            label = str(body.get("label") or env_name).strip()
            meta = _env_meta(body, env_name=env_name)
            services = _services_from_env_body(body)
            parsed.append(
                EnvironmentLinks(
                    name=env_name,
                    label=label,
                    services=services,
                    env_type=meta["env_type"],
                    cloud=meta["cloud"],
                    account=meta["account"],
                    region=meta["region"],
                    cluster=meta["cluster"],
                )
            )
    elif isinstance(raw_envs, list):
        for item in raw_envs:
            if not isinstance(item, dict):
                continue
            env_name = str(item.get("name") or "").strip().lower()
            if not env_name:
                continue
            label = str(item.get("label") or env_name).strip()
            meta = _env_meta(item, env_name=env_name)
            services = _services_from_env_body(item)
            parsed.append(
                EnvironmentLinks(
                    name=env_name,
                    label=label,
                    services=services,
                    env_type=meta["env_type"],
                    cloud=meta["cloud"],
                    account=meta["account"],
                    region=meta["region"],
                    cluster=meta["cluster"],
                )
            )

    if parsed:
        return parsed

    legacy = _parse_links(data.get("links"), default_kind="service")
    if legacy:
        return [EnvironmentLinks(name="dev", label="Development", services=legacy)]
    return []


def _parse_team_environments(raw_envs, platform_env_names):
    parsed = []
    if isinstance(raw_envs, dict):
        items = raw_envs.items()
    elif isinstance(raw_envs, list):
        items = []
        for item in raw_envs:
            if isinstance(item, dict) and item.get("name"):
                items.append((item.get("name"), item))
    else:
        items = []

    for name, body in items:
        env_name = str(name).strip().lower()
        if not env_name:
            continue
        if not isinstance(body, dict):
            body = {}
        if platform_env_names and env_name not in platform_env_names:
            logger.warning("team environment %s not in platform environments", env_name)
        parsed.append(
            TeamEnvironment(
                name=env_name,
                services=_parse_links(body.get("services"), default_kind="service"),
                products=_parse_links(body.get("products"), default_kind="product"),
            )
        )
    return parsed


def _parse_teams(data, environments):
    raw_teams = data.get("teams")
    platform_names = {env.name for env in environments}
    parsed = []

    if isinstance(raw_teams, dict):
        items = raw_teams.items()
    elif isinstance(raw_teams, list):
        items = []
        for item in raw_teams:
            if isinstance(item, dict) and (item.get("id") or item.get("name")):
                tid = item.get("id") or item.get("name")
                items.append((tid, item))
    else:
        items = []

    for team_id, body in items:
        tid = _slug(team_id)
        if not tid or not isinstance(body, dict):
            continue
        label = str(body.get("label") or tid).strip()
        description = str(body.get("description") or "").strip()
        default_environment = str(body.get("default_environment") or "").strip().lower()
        team_envs = _parse_team_environments(body.get("environments"), platform_names)
        parsed.append(
            Team(
                id=tid,
                label=label,
                description=description,
                default_environment=default_environment,
                environments=team_envs,
            )
        )

    if parsed:
        return parsed

    # Backward compat: no teams → single "default" team; all platform services visible.
    if environments:
        team_envs = [
            TeamEnvironment(name=env.name, services=[], products=[]) for env in environments
        ]
        return [
            Team(
                id="default",
                label="Default",
                description="Legacy single-team landing (no teams: in config).",
                default_environment=environments[0].name,
                environments=team_envs,
            )
        ]
    return []


def group_by_category(links):
    """Group OpsLink list by category, preserving category order then link order."""
    buckets = {name: [] for name in _CATEGORY_ORDER}
    for link in links:
        key = link.category if link.category in buckets else "other"
        buckets[key].append(link)
    return [(name, buckets[name]) for name in _CATEGORY_ORDER if buckets[name]]


def _read_yaml(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _stem_name(path: Path, prefixes=()):
    """environments.dev.yaml / environments/dev.yaml → dev."""
    name = path.stem
    for prefix in prefixes:
        if name.startswith(f"{prefix}."):
            name = name[len(prefix) + 1 :]
            break
    return _slug(name)


def _resolve_config_root(path=None):
    """
    Resolve LINKS_CONFIG_PATH / explicit path to a file or directory.

    Returns Path or None.
    """
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    else:
        env_path = os.environ.get("LINKS_CONFIG_PATH", "").strip()
        if env_path:
            candidates.append(Path(env_path))
        candidates.extend([_PACKAGE_CONFIG_DIR, _REPO_CONFIG_DIR])

    for candidate in candidates:
        if candidate.is_dir() or candidate.is_file():
            return candidate
    return None


def _hub_candidates(root: Path):
    if root.is_file():
        return [root]
    return [
        root / "hub.yaml",
        root / "hub.yml",
        root / "links.yaml",
        root / "links.yml",
    ]


def _list_split_files(root: Path, kind: str):
    """
    Collect split YAML files for environments or teams.

    Supports:
      <root>/<kind>/*.yaml
      <root>/<kind>.<id>.yaml   (ConfigMap-friendly flat keys)
    """
    files = []
    if root.is_dir():
        sub = root / kind
        if sub.is_dir():
            files.extend(sorted(sub.glob("*.yaml")))
            files.extend(sorted(sub.glob("*.yml")))
        files.extend(sorted(root.glob(f"{kind}.*.yaml")))
        files.extend(sorted(root.glob(f"{kind}.*.yml")))
    # Dedupe while preserving order
    seen = set()
    unique = []
    for item in files:
        key = str(item.resolve()) if item.exists() else str(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def discover_config_sources(path=None):
    """Return YAML files that make up the landing config (for hot-reload fingerprint)."""
    root = _resolve_config_root(path)
    if root is None:
        return []

    sources = []
    if root.is_file():
        return [root]

    hub = next((p for p in _hub_candidates(root) if p.is_file()), None)
    if hub is not None:
        sources.append(hub)
        # Monolithic hub/links already has everything — still watch split overlays.
    sources.extend(_list_split_files(root, "environments"))
    sources.extend(_list_split_files(root, "teams"))

    # If no hub and no splits, nothing to watch.
    return sources


def _merge_split_config(root: Path):
    """
    Build a monolithic dict from hub + environments/* + teams/*.

    Split files overlay / extend keys from the hub (or empty root).
    """
    data = {}
    hub = next((p for p in _hub_candidates(root) if p.is_file()), None)
    if hub is not None:
        data = _read_yaml(hub)

    # If hub is a full monolithic file and there are no split files, use as-is.
    env_files = _list_split_files(root, "environments")
    team_files = _list_split_files(root, "teams")

    if env_files:
        environments = dict(data.get("environments") or {}) if isinstance(data.get("environments"), dict) else {}
        for env_file in env_files:
            body = _read_yaml(env_file)
            env_name = _stem_name(env_file, prefixes=("environments",))
            # Allow file to wrap {dev: {...}} or be the body itself.
            if env_name in body and isinstance(body.get(env_name), dict) and "services" not in body and "links" not in body:
                environments[env_name] = body[env_name]
            elif len(body) == 1:
                only_key = next(iter(body))
                if isinstance(body[only_key], dict) and _slug(only_key) == env_name:
                    environments[env_name] = body[only_key]
                else:
                    environments[env_name] = body
            else:
                environments[env_name] = body
        data["environments"] = environments

    if team_files:
        teams = dict(data.get("teams") or {}) if isinstance(data.get("teams"), dict) else {}
        for team_file in team_files:
            body = _read_yaml(team_file)
            team_id = _stem_name(team_file, prefixes=("teams",))
            if "id" in body:
                team_id = _slug(body.get("id")) or team_id
            if team_id in body and isinstance(body.get(team_id), dict) and "label" not in body:
                teams[team_id] = body[team_id]
            elif len(body) == 1:
                only_key = next(iter(body))
                if isinstance(body[only_key], dict) and _slug(only_key) == team_id:
                    teams[team_id] = body[only_key]
                else:
                    teams[team_id] = body
            else:
                teams[team_id] = body
        data["teams"] = teams

    return data


def _apply_order(items, order_keys, key_fn):
    """Stable reorder by explicit id list; unknown ids keep relative order at end."""
    if not order_keys or not items:
        return items
    wanted = [_slug(x) for x in order_keys if _slug(x)]
    by_key = {key_fn(item): item for item in items}
    ordered = [by_key[k] for k in wanted if k in by_key]
    seen = set(wanted)
    ordered.extend([item for item in items if key_fn(item) not in seen])
    return ordered


def _landing_from_data(data, source_label=""):
    if not isinstance(data, dict):
        logger.error("links config root must be a mapping: %s", source_label or "?")
        return _default_landing()

    environments = _parse_environments(data)
    teams = _parse_teams(data, environments)
    environments = _apply_order(environments, data.get("environment_order"), lambda env: env.name)
    teams = _apply_order(teams, data.get("team_order"), lambda team: team.id)

    default_env = str(data.get("default_environment") or "dev").strip().lower()
    if environments and default_env not in {e.name for e in environments}:
        default_env = environments[0].name

    default_team = str(data.get("default_team") or "").strip().lower()
    if teams and default_team not in {t.id for t in teams}:
        default_team = teams[0].id
    elif not default_team and teams:
        default_team = teams[0].id

    title = str(data.get("title") or _default_landing().title).strip()
    subtitle = str(data.get("subtitle") or _default_landing().subtitle).strip()
    logger.info(
        "loaded links config from %s (%s envs, %s teams)",
        source_label or "?",
        [e.name for e in environments],
        [t.id for t in teams],
    )
    return LandingConfig(
        title=title,
        subtitle=subtitle,
        default_environment=default_env,
        default_team=default_team,
        environments=environments,
        teams=teams,
    )


def load_landing_config(path=None):
    """
    Load landing-page config from YAML file or directory.

    Order when path is omitted:
      1. LINKS_CONFIG_PATH (file or directory)
      2. packaged backoffice/config/
      3. repo products/devops-backoffice/config/

    Directory layout:
      hub.yaml                 # title, defaults (optional inline envs/teams)
      environments/<name>.yaml # platform services + metadata
      teams/<id>.yaml          # team products / overlays

    Flat ConfigMap-friendly names also work: environments.dev.yaml, teams.payments.yaml.
    Single monolithic links.yaml / hub.yaml still supported.
    """
    root = _resolve_config_root(path)
    if root is None:
        logger.warning("links config missing, using empty defaults")
        return _default_landing()

    try:
        if root.is_file():
            data = _read_yaml(root)
            return _landing_from_data(data, source_label=str(root))
        data = _merge_split_config(root)
        if not data:
            logger.warning("links config directory empty: %s", root)
            return _default_landing()
        return _landing_from_data(data, source_label=str(root))
    except (OSError, yaml.YAMLError, ValueError) as exc:
        logger.error("failed to load links config %s: %s", root, exc)
        return _default_landing()
