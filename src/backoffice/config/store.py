"""Hot-reloadable landing config store."""

from __future__ import annotations

import logging
import os
import threading

from backoffice.config.loader import (
    _default_landing,
    discover_config_sources,
    load_landing_config,
)

logger = logging.getLogger(__name__)


def _reload_enabled() -> bool:
    raw = os.environ.get("LINKS_CONFIG_RELOAD", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class LandingConfigStore:
    """
    Serve LandingConfig and reload when YAML sources change.

    Fingerprint = sorted (path, mtime_ns, size) for all discovered YAML files.
    On parse failure during reload, keep the last good config.
    """

    def __init__(self, path=None, reload=None):
        self.path = path
        self.reload = _reload_enabled() if reload is None else bool(reload)
        self._lock = threading.Lock()
        self._cfg = None
        self._fp = None
        self._sources = []
        self._load(initial=True)

    def _fingerprint(self, sources):
        parts = []
        for src in sources:
            try:
                st = src.stat()
                parts.append((str(src), st.st_mtime_ns, st.st_size))
            except OSError:
                parts.append((str(src), None, None))
        return tuple(parts)

    def _load(self, initial=False):
        sources = discover_config_sources(self.path)
        fingerprint = self._fingerprint(sources)
        try:
            cfg = load_landing_config(self.path)
        except Exception as exc:  # noqa: BLE001 — keep last good on hot reload
            if initial or self._cfg is None:
                logger.error("failed to load landing config: %s", exc)
                cfg = _default_landing()
            else:
                logger.error("config reload failed, keeping previous: %s", exc)
                return
        self._cfg = cfg
        self._fp = fingerprint
        self._sources = [str(p) for p in sources]
        logger.info(
            "landing config %s (%s sources)",
            "loaded" if initial else "reloaded",
            len(self._sources),
        )

    def get(self):
        if not self.reload:
            return self._cfg

        sources = discover_config_sources(self.path)
        fingerprint = self._fingerprint(sources)
        if fingerprint == self._fp:
            return self._cfg

        with self._lock:
            sources = discover_config_sources(self.path)
            fingerprint = self._fingerprint(sources)
            if fingerprint != self._fp:
                self._load(initial=False)
            return self._cfg

    def status(self):
        cfg = self.get()
        return {
            "reload": self.reload,
            "sources": list(self._sources),
            "title": cfg.title if cfg else None,
            "teams": [t.id for t in cfg.teams] if cfg else [],
            "environments": [e.name for e in cfg.environments] if cfg else [],
        }
