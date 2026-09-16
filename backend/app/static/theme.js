/**
 * TARA IDE — Dynamic Theme Engine
 * Switches CSS variables via data-theme on <html>, syncs Monaco Editor theme.
 *
 * Themes:
 *   dark   → vs-dark     (Antigravity Obsidian)
 *   light  → vs          (Clean Slate)
 *   cyber  → hc-black    (High-Contrast Cyber)
 */

(function () {
  "use strict";

  const THEME_MAP = {
    dark:  { monacoTheme: "vs-dark",  bodyClass: "dark-theme", label: "Dark Obsidian" },
    light: { monacoTheme: "vs",       bodyClass: "dark-theme", label: "Light Clean Slate" },
    cyber: { monacoTheme: "hc-black", bodyClass: "dark-theme", label: "Cyber High-Contrast" },
  };

  const STORAGE_KEY = "tara-ide-theme";

  /**
   * Apply a named theme across the entire IDE.
   */
  function applyTheme(themeName) {
    const config = THEME_MAP[themeName];
    if (!config) return;

    // 1. Set data-theme on root <html> element for CSS variable cascade
    document.documentElement.setAttribute("data-theme", themeName);

    // 2. Persist preference
    try { localStorage.setItem(STORAGE_KEY, themeName); } catch (_) {}

    // 3. Sync Monaco editor themes
    syncMonacoTheme(config.monacoTheme);

    // 4. Sync dropdown selector if present
    const selector = document.getElementById("theme-selector");
    if (selector && selector.value !== themeName) {
      selector.value = themeName;
    }

    console.log(`[TARA Theme] Applied: ${config.label} (${themeName})`);
  }

  /**
   * Update all Monaco editors to the matching theme.
   */
  function syncMonacoTheme(monacoTheme) {
    if (typeof monaco !== "undefined" && monaco.editor) {
      monaco.editor.setTheme(monacoTheme);
    }
  }

  /**
   * Get saved theme or fallback to default.
   */
  function getSavedTheme() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && THEME_MAP[saved]) return saved;
    } catch (_) {}
    return "dark";
  }

  /**
   * Initialize theme system on DOM ready.
   */
  function init() {
    // Apply saved/default theme immediately
    const initialTheme = getSavedTheme();
    applyTheme(initialTheme);

    // Bind dropdown change listener
    const selector = document.getElementById("theme-selector");
    if (selector) {
      selector.value = initialTheme;
      selector.addEventListener("change", function (e) {
        applyTheme(e.target.value);
      });
    }

    // Keyboard shortcut: Ctrl+Shift+T to cycle themes
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey && e.shiftKey && e.key === "T") {
        e.preventDefault();
        const themes = Object.keys(THEME_MAP);
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        const idx = themes.indexOf(current);
        const next = themes[(idx + 1) % themes.length];
        applyTheme(next);
      }
    });
  }

  // Run initialization
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Expose globally for programmatic access
  window.TaraTheme = {
    apply: applyTheme,
    current: function () { return document.documentElement.getAttribute("data-theme") || "dark"; },
    themes: Object.keys(THEME_MAP),
  };
})();
