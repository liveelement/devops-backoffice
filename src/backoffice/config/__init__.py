"""Load YAML config for the DevOps landing page."""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).resolve().parent / "links.yaml"
_REPO_CONFIG = Path(__file__).resolve().parents[3] / "config" / "links.yaml"


class OpsLink:
    def __init__(self, id, label, url, description="", external=True):
        self.id = id
        self.label = label
        self.url = url
        self.description = description
        self.external = external


class EnvironmentLinks:
    def __init__(self, name, label, links=None):
        self.name = name
        self.label = label
        self.links = list(links or [])


class LandingConfig:
    def __init__(self, title, subtitle, default_environment="dev", environments=None):
        self.title = title
        self.subtitle = subtitle
        self.default_environment = default_environment
        self.environments = list(environments or [])

    def environment_names(self):
        return [env.name for env in self.environments]

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


def _default_landing():
    return LandingConfig(
        title="DevOps Operations Hub",
        subtitle="Daily links for GitOps, observability, cloud, and source control.",
        default_environment="dev",
        environments=[],
    )


def _parse_link(raw, index):
    url = str(raw.get("url") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not url or not label:
        logger.warning("skipping invalid link at index %s", index)
        return None
    link_id = str(raw.get("id") or label).strip().lower().replace(" ", "-")
    return OpsLink(
        id=link_id,
        label=label,
        url=url,
        description=str(raw.get("description") or "").strip(),
        external=bool(raw.get("external", True)),
    )


def _parse_links(raw_links):
    links = []
    if not isinstance(raw_links, list):
        return links
    for index, item in enumerate(raw_links):
        if isinstance(item, dict):
            parsed = _parse_link(item, index)
            if parsed is not None:
                links.append(parsed)
    return links


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
            parsed.append(
                EnvironmentLinks(
                    name=env_name,
                    label=label,
                    links=_parse_links(body.get("links")),
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
            parsed.append(
                EnvironmentLinks(
                    name=env_name,
                    label=label,
                    links=_parse_links(item.get("links")),
                )
            )

    if parsed:
        return parsed

    legacy = _parse_links(data.get("links"))
    if legacy:
        return [EnvironmentLinks(name="dev", label="Development", links=legacy)]
    return []


def load_landing_config(path=None):
    """
    Load landing-page config from YAML.

    Order when path is omitted:
      1. LINKS_CONFIG_PATH
      2. packaged backoffice/config/links.yaml
      3. repo apps/devops-backoffice/config/links.yaml
    """
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    else:
        env_path = os.environ.get("LINKS_CONFIG_PATH", "").strip()
        if env_path:
            candidates.append(Path(env_path))
        candidates.extend([_DEFAULT_CONFIG, _REPO_CONFIG])

    config_path = next((p for p in candidates if p.is_file()), None)
    if config_path is None:
        logger.warning("links config missing, using empty defaults")
        return _default_landing()

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.error("failed to load links config %s: %s", config_path, exc)
        return _default_landing()

    if not isinstance(data, dict):
        logger.error("links config root must be a mapping: %s", config_path)
        return _default_landing()

    environments = _parse_environments(data)
    default_env = str(data.get("default_environment") or "dev").strip().lower()
    if environments and default_env not in {e.name for e in environments}:
        default_env = environments[0].name

    title = str(data.get("title") or _default_landing().title).strip()
    subtitle = str(data.get("subtitle") or _default_landing().subtitle).strip()
    logger.info(
        "loaded links config from %s (%s envs)",
        config_path,
        [e.name for e in environments],
    )
    return LandingConfig(
        title=title,
        subtitle=subtitle,
        default_environment=default_env,
        environments=environments,
    )
