(() => {
  function profileId() {
    const key = "jansahayak:profile-id";
    let value = localStorage.getItem(key);
    if (!value) {
      value = crypto.randomUUID();
      localStorage.setItem(key, value);
    }
    return value;
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}), "X-Profile-Id": profileId() };
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(path, {
      ...options,
      headers
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }

  window.App = { api, profileId };

  async function loadCategories() {
    const { categories } = await api("/api/categories");
    const select = document.getElementById("category-filter");
    categories.forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = window.I18n.category(category);
      select.append(option);
    });
  }

  async function loadFilters() {
    const { government_levels } = await api("/api/filters");
    const levelSelect = document.getElementById("level-filter");
    government_levels.forEach((level) => {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = window.I18n.current() === "hi" && level === "Central"
        ? window.I18n.t("central")
        : window.I18n.current() === "hi" && level === "State"
          ? window.I18n.t("state")
          : level;
      levelSelect.append(option);
    });
  }

  async function initialize() {
    try {
      await Promise.all([loadCategories(), loadFilters(), window.Schemes.load()]);
      window.Schemes.setup();
      window.I18n.apply();
    } catch (error) {
      document.getElementById("scheme-results").innerHTML =
        `<p class="empty-state">${escapeHtml(window.I18n.current() === "hi" ? "योजना सूची लोड नहीं हो सकी।" : "Could not load the scheme catalogue.")} ${escapeHtml(error.message)}</p>`;
    }
    window.Chat.setup();
    window.Voice.setup();
    window.Tools.setup();
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  window.App.escapeHtml = escapeHtml;
  document.addEventListener("DOMContentLoaded", initialize);
})();
