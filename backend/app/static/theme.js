/**
 * TARA IDE — Theme Engine (The Office Floor: Paper Company x Neobrutalism)
 * Registers and applies the custom 'tara-office' Monaco light theme.
 */
(function () {
  "use strict";

  function registerMonacoTheme() {
    if (typeof monaco !== "undefined" && monaco.editor && monaco.editor.defineTheme) {
      monaco.editor.defineTheme("tara-office", {
        base: "vs",
        inherit: true,
        rules: [
          { token: "", foreground: "111111", background: "ffffff" },
          { token: "keyword", foreground: "1d4f91", fontStyle: "bold" },
          { token: "string", foreground: "2f9e44" },
          { token: "comment", foreground: "555555", fontStyle: "italic" },
          { token: "number", foreground: "1d4f91" },
          { token: "type", foreground: "1d4f91", fontStyle: "bold" },
          { token: "function", foreground: "111111", fontStyle: "bold" },
          { token: "diff.deleted", foreground: "e03131", background: "ffe866" },
          { token: "diff.inserted", foreground: "2f9e44", background: "ffb3c1" },
        ],
        colors: {
          "editor.background": "#ffffff",
          "editor.foreground": "#111111",
          "editorLineNumber.foreground": "#888888",
          "editorLineNumber.activeForeground": "#111111",
          "editorCursor.foreground": "#1d4f91",
          "editor.lineHighlightBackground": "#f0f4f8",
          "editor.selectionBackground": "#9ec5f4",
          "editor.inactiveSelectionBackground": "#d0e2fa",
          "diffEditor.insertedTextBackground": "#ffb3c140",
          "diffEditor.removedTextBackground": "#ffe86650",
        }
      });
      monaco.editor.setTheme("tara-office");
    }
  }

  function init() {
    document.documentElement.setAttribute("data-theme", "office");
    registerMonacoTheme();

    // Re-sync once Monaco lazy-loads via vs/loader.js
    const observer = new MutationObserver(function () {
      if (typeof monaco !== "undefined" && monaco.editor) {
        registerMonacoTheme();
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
    apply: function () { registerMonacoTheme(); },
    current: function () { return "office"; },
    themes: ["office"],
  };
})();
