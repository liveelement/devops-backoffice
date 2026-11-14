(() => {
  const STORAGE_KEY = "devops-backoffice:last";
  const THEME_KEY = "devops-backoffice:theme";
  const pill = document.getElementById("version-pill");
  const heroVersion = document.getElementById("hero-version");
  const envSelect = document.getElementById("environment-select");
  const themeToggle = document.getElementById("theme-toggle");
  const body = document.body;
  const selectedTeam = body?.dataset?.selectedTeam || "";
  const selectedEnv = body?.dataset?.selectedEnv || "";

  function readStored() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
    } catch {
      return {};
    }
  }

  function writeStored(patch) {
    const next = { ...readStored(), ...patch };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore quota / private mode */
    }
  }

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  function currentTheme() {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored === "light" || stored === "dark") return stored;
    } catch {
      /* ignore */
    }
    return systemTheme();
  }

  function applyTheme(theme) {
    const next = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore */
    }
    if (themeToggle) {
      const isLight = next === "light";
      const icon = themeToggle.querySelector(".theme-icon");
      const label = themeToggle.querySelector(".theme-label");
      if (icon) icon.textContent = isLight ? "☀" : "☾";
      if (label) label.textContent = isLight ? "Light" : "Dark";
      themeToggle.setAttribute("aria-pressed", isLight ? "true" : "false");
      themeToggle.title = isLight ? "Switch to dark theme" : "Switch to light theme";
    }
  }

  applyTheme(currentTheme());

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      applyTheme(currentTheme() === "light" ? "dark" : "light");
    });
  }

  // Persist current team/env when on a team page.
  if (selectedTeam) {
    writeStored({ team: selectedTeam, env: selectedEnv || undefined });
  }

  // On the teams index, offer a one-time jump to the last team if stored.
  if (!selectedTeam && body && !sessionStorage.getItem("devops-backoffice:skip-restore")) {
    const stored = readStored();
    if (stored.team) {
      const params = new URLSearchParams();
      if (stored.env) params.set("env", stored.env);
      const qs = params.toString();
      const target = `/t/${encodeURIComponent(stored.team)}${qs ? `?${qs}` : ""}`;
      // Soft hint: mark restore so refresh on / doesn't loop; user can still pick another team.
      sessionStorage.setItem("devops-backoffice:skip-restore", "1");
      const card = document.querySelector(`[data-team-id="${CSS.escape(stored.team)}"]`);
      if (card) {
        card.classList.add("team-card-recent");
        card.setAttribute("title", "Last opened team");
      }
      // Auto-redirect only when arriving at bare /
      if (window.location.pathname === "/" && !window.location.search) {
        window.location.replace(target);
        return;
      }
    }
  }

  async function loadAppVersion() {
    try {
      const response = await fetch("/version", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const version = data.version || "unknown";
      if (heroVersion) heroVersion.textContent = version;
      if (pill) {
        pill.textContent = `v${version}`;
        pill.dataset.version = version;
      }
    } catch (err) {
      console.error("version refresh failed", err);
    }
  }

  async function loadServiceStatus() {
    const badges = document.querySelectorAll(".version-badge[data-has-probe='1']");
    if (!badges.length || !selectedTeam) return;

    const params = new URLSearchParams({ team: selectedTeam });
    if (selectedEnv) params.set("env", selectedEnv);

    badges.forEach((badge) => {
      badge.classList.add("is-probing");
      if (!badge.dataset.declared) badge.textContent = "…";
    });

    try {
      const response = await fetch(`/api/service-status?${params}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const byId = new Map((data.services || []).map((item) => [item.id, item]));
      badges.forEach((badge) => {
        const id = badge.dataset.serviceId;
        const declared = badge.dataset.declared || "";
        const status = byId.get(id);
        badge.classList.remove("is-probing");
        if (!status) {
          badge.textContent = declared || "—";
          return;
        }
        const live = status.live_version;
        const source = status.source || "";
        if (status.status === "ok" && live) {
          badge.textContent = live;
          const bits = [`source: ${source || "config"}`];
          if (declared && declared !== live) bits.push(`config: ${declared}`);
          if (status.detail) bits.push(status.detail);
          badge.title = bits.join(" · ");
          badge.classList.toggle("is-live", source === "http" || source === "kubernetes");
          badge.classList.toggle("is-unknown", false);
          badge.dataset.source = source;
        } else {
          badge.textContent = declared || "unknown";
          badge.title = status.error ? `discovery: ${status.error}` : "discovery unknown";
          badge.classList.add("is-unknown");
        }
      });
    } catch (err) {
      console.error("service status probe failed", err);
      badges.forEach((badge) => {
        badge.classList.remove("is-probing");
        badge.classList.add("is-unknown");
        badge.textContent = badge.dataset.declared || "unknown";
      });
    }
  }

  if (envSelect) {
    envSelect.addEventListener("change", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("env", envSelect.value);
      if (selectedTeam) writeStored({ team: selectedTeam, env: envSelect.value });
      window.location.assign(url.toString());
    });
  }

  function setupColumnSearch() {
    document.querySelectorAll(".tool-table").forEach((table) => {
      const section = table.closest("[data-filter-section]");
      const empty = section?.querySelector(".filter-empty");
      const groups = Array.from(table.querySelectorAll(".th-with-search"));
      if (!groups.length) return;

      let active = null;

      function syncCredsPanels() {
        table.querySelectorAll("tr.link-row[data-has-creds]").forEach((row) => {
          const id = row.dataset.serviceId;
          const panel = id ? table.querySelector(`tr.creds-panel-row[data-creds-for="${CSS.escape(id)}"]`) : null;
          if (!panel) return;
          if (row.hidden) {
            panel.hidden = true;
            const toggle = row.querySelector(".creds-toggle");
            if (toggle) {
              toggle.classList.remove("is-open");
              toggle.setAttribute("aria-expanded", "false");
            }
          }
        });
      }

      function clearRows() {
        table.querySelectorAll("tbody tr.link-row").forEach((row) => {
          row.hidden = false;
        });
        syncCredsPanels();
        if (empty) empty.hidden = true;
      }

      function applyFilter(group) {
        if (!group) {
          clearRows();
          return;
        }
        const field = group.dataset.searchField === "url" ? "url" : "tool";
        const input = group.querySelector(".col-search-input");
        const query = (input?.value || "").trim().toLowerCase();
        const attr = field === "url" ? "data-filter-url" : "data-filter-tool";
        const rows = table.querySelectorAll(`tbody tr.link-row[${attr}]`);
        let visible = 0;
        rows.forEach((row) => {
          const haystack = (row.getAttribute(attr) || "").toLowerCase();
          const match = !query || haystack.includes(query);
          row.hidden = !match;
          if (match) visible += 1;
        });
        syncCredsPanels();
        if (empty) empty.hidden = !query || visible > 0;
      }

      function closeGroup(group) {
        if (!group) return;
        group.classList.remove("is-open");
        const input = group.querySelector(".col-search-input");
        if (input) {
          input.hidden = true;
          input.value = "";
        }
      }

      function openGroup(group) {
        groups.forEach((item) => {
          if (item !== group) closeGroup(item);
        });
        group.classList.add("is-open");
        const input = group.querySelector(".col-search-input");
        if (input) {
          input.hidden = false;
          input.focus();
          input.select();
        }
        active = group;
        applyFilter(group);
      }

      groups.forEach((group) => {
        const btn = group.querySelector(".col-search-btn");
        const input = group.querySelector(".col-search-input");
        if (!btn || !input) return;

        btn.addEventListener("click", (event) => {
          event.preventDefault();
          if (group.classList.contains("is-open")) {
            closeGroup(group);
            active = null;
            clearRows();
            return;
          }
          openGroup(group);
        });

        input.addEventListener("input", () => applyFilter(group));
        input.addEventListener("search", () => {
          if (!input.value) applyFilter(group);
        });
        input.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            closeGroup(group);
            active = null;
            clearRows();
            event.preventDefault();
          }
        });
      });
    });
  }

  function setupCredentialsPanels() {
    document.querySelectorAll(".creds-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const controls = btn.getAttribute("aria-controls");
        const panel = controls ? document.getElementById(controls) : null;
        if (!panel) return;
        const open = panel.hidden;
        // Close other panels in the same table.
        const table = btn.closest("table");
        if (table) {
          table.querySelectorAll(".creds-panel-row").forEach((row) => {
            row.hidden = true;
          });
          table.querySelectorAll(".creds-toggle").forEach((other) => {
            other.classList.remove("is-open");
            other.setAttribute("aria-expanded", "false");
          });
        }
        panel.hidden = !open;
        btn.classList.toggle("is-open", open);
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });

    document.querySelectorAll(".copy-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const text = btn.getAttribute("data-copy") || "";
        if (!text) return;
        try {
          await navigator.clipboard.writeText(text);
          btn.classList.add("is-copied");
          const prev = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.classList.remove("is-copied");
            btn.textContent = prev || "Copy";
          }, 1200);
        } catch (err) {
          console.error("copy failed", err);
          btn.textContent = "Failed";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 1200);
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".creds-panel-row").forEach((row) => {
        row.hidden = true;
      });
      document.querySelectorAll(".creds-toggle.is-open").forEach((btn) => {
        btn.classList.remove("is-open");
        btn.setAttribute("aria-expanded", "false");
      });
    });
  }

  setupColumnSearch();
  setupCredentialsPanels();
  loadAppVersion();
  loadServiceStatus();
})();
