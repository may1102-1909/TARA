/**
 * TARA IDE — Theme Engine (Monochrome Obsidian)
 * Single dark theme. Syncs Monaco to vs-dark.
 */
(function () {
  "use strict";

  function syncMonaco() {
    if (typeof monaco !== "undefined" && monaco.editor) {
      monaco.editor.setTheme("vs-dark");
    }
  }

  function init() {
    document.documentElement.setAttribute("data-theme", "obsidian");

    // Sync Monaco when it loads
    syncMonaco();

    // Re-sync after Monaco lazy-loads
    const observer = new MutationObserver(function () {
      if (typeof monaco !== "undefined") {
        syncMonaco();
        observer.disconnect();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.TaraTheme = {
    apply: function () { syncMonaco(); },
    current: function () { return "obsidian"; },
    themes: ["obsidian"],
  };
})();
