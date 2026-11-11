(() => {
  const refreshButton = document.getElementById("refresh-version");
  const dashVersion = document.getElementById("dash-version");
  const heroVersion = document.getElementById("hero-version");
  const pill = document.getElementById("version-pill");
  const envSelect = document.getElementById("environment-select");

  async function loadVersion() {
    try {
      const response = await fetch("/version", { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      const version = data.version || "unknown";
      if (dashVersion) dashVersion.textContent = version;
      if (heroVersion) heroVersion.textContent = version;
      if (pill) {
        pill.textContent = `v${version}`;
        pill.dataset.version = version;
      }
    } catch (err) {
      console.error("version refresh failed", err);
    }
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", loadVersion);
  }

  // Dropdown updates the browser URL (?env=) and reloads links for that environment.
  if (envSelect) {
    envSelect.addEventListener("change", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("env", envSelect.value);
      window.location.assign(url.toString());
    });
  }
})();
