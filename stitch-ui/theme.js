/* RIFT single-theme layer (Stitch UI unification).
 * All 9 screens shipped with different palettes. This file is the one
 * source of truth: every screen loads it where its inline tailwind.config
 * used to be, so the whole app renders one coherent theme.
 *
 * - "console" (default): the RIFT Console look most screens already used,
 *   pinned to the Stitch design system (cyan #0891b2).
 * - "slate": the evidence/settings slate variant.
 * - "midnight": the simulation midnight variant.
 * Pick in Settings -> Appearance; stored in localStorage `rift-theme-name`
 * and applied on every screen on load. No markup differs between themes.
 */
(function () {
  "use strict";

  var FONTS = {
    headline: ["Space Grotesk", "sans-serif"],
    display: ["Space Grotesk", "sans-serif"],
    body: ["Inter", "sans-serif"],
    label: ["Public Sans", "sans-serif"],
    mono: ["JetBrains Mono", "monospace"],
    sans: ["Inter", "sans-serif"],
  };
  var RADII = { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", full: "9999px" };

  var THEMES = {
    console: {
      label: "RIFT Console",
      desc: "Default. Deep-navy surfaces, cyan accents.",
      swatch: ["#090d16", "#0891b2"],
      colors: {
        surface: "#090d16",
        "surface-container": "#111827",
        "surface-container-high": "#1f2937",
        primary: "#0891b2",
        "primary-container": "#0e7490",
        "on-surface": "#f3f4f6",
        "on-surface-variant": "#9ca3af",
        "on-primary": "#ffffff",
        "outline-variant": "#374151",
        success: "#10b981",
        warning: "#f59e0b",
        error: "#f43f5e",
        brand: { DEFAULT: "#0891b2", hover: "#0e7490", muted: "rgba(8,145,178,0.15)", border: "rgba(8,145,178,0.3)" },
        // Compat tokens used by the simulation screen markup.
        // (Tailwind flattens `surface` string + `surface-*` keys side by side.)
        "surface-base": "#090d16",
        "surface-panel": "#111827",
        "surface-elevated": "#1f2937",
        "surface-border": "#374151",
        "surface-subtle": "#4b5563",
      },
    },
    slate: {
      label: "Slate",
      desc: "The evidence/settings slate variant.",
      swatch: ["#0f172a", "#06b6d4"],
      colors: {
        surface: "#0f172a",
        "surface-container": "#1e293b",
        "surface-container-high": "#334155",
        primary: "#06b6d4",
        "primary-container": "#0891b2",
        "on-surface": "#f8fafc",
        "on-surface-variant": "#cbd5e1",
        "on-primary": "#ffffff",
        "outline-variant": "#475569",
        success: "#10b981",
        warning: "#f59e0b",
        error: "#f43f5e",
        brand: { DEFAULT: "#06b6d4", hover: "#0891b2", muted: "rgba(6,182,212,0.15)", border: "rgba(6,182,212,0.3)" },
        "surface-base": "#0f172a",
        "surface-panel": "#1e293b",
        "surface-elevated": "#334155",
        "surface-border": "#475569",
        "surface-subtle": "#64748b",
      },
    },
    midnight: {
      label: "Midnight",
      desc: "The simulation midnight variant.",
      swatch: ["#0B0F17", "#06b6d4"],
      colors: {
        surface: "#0B0F17",
        "surface-container": "#111726",
        "surface-container-high": "#1F293D",
        primary: "#06b6d4",
        "primary-container": "#0891b2",
        "on-surface": "#E2E8F0",
        "on-surface-variant": "#94a3b8",
        "on-primary": "#ffffff",
        "outline-variant": "#26334D",
        success: "#10b981",
        warning: "#f59e0b",
        error: "#f43f5e",
        brand: { DEFAULT: "#06b6d4", hover: "#0891b2", muted: "rgba(6,182,212,0.15)", border: "rgba(6,182,212,0.3)" },
        "surface-base": "#0B0F17",
        "surface-panel": "#111726",
        "surface-elevated": "#172033",
        "surface-border": "#1F293D",
        "surface-subtle": "#26334D",
      },
    },
  };

  var KEY = "rift-theme-name";
  function currentName() {
    try {
      var n = localStorage.getItem(KEY);
      if (n && THEMES[n]) return n;
    } catch (e) {}
    return "console";
  }
  function build(name) {
    var t = THEMES[name] || THEMES.console;
    return { darkMode: "class", theme: { extend: { colors: t.colors, borderRadius: RADII, fontFamily: FONTS } } };
  }
  function apply(name) {
    if (!THEMES[name]) name = "console";
    try { localStorage.setItem(KEY, name); } catch (e) {}
    var el = document.documentElement;
    // If this theme's palette is already live, only refresh picker states:
    // swapping config.theme while the CDN does its initial build silently
    // kills generation, so never re-mutate for the active theme.
    if (el.getAttribute("data-rift-theme") === name && window.tailwind && window.tailwind.config) {
      paintPicks(name);
      return;
    }
    try {
      // Mutate the live config object in place (never replace the
      // reference: the Play CDN snapshots it at init), then nudge the
      // DOM so its observer rebuilds utilities from the new palette.
      var built = build(name);
      if (window.tailwind && window.tailwind.config) {
        window.tailwind.config.darkMode = built.darkMode;
        window.tailwind.config.theme = built.theme;
      } else {
        window.tailwind.config = built;
      }
      try { el.style.setProperty("--rift-surface", THEMES[name].colors.surface); } catch (e2) {}
      el.setAttribute("data-rift-theme", name);
    } catch (e) {}
    paintPicks(name);
  }
  function paintPicks(name) {
    document.querySelectorAll("[data-theme-pick]").forEach(function (b) {
      var on = b.getAttribute("data-theme-pick") === name;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.style.borderColor = on ? "#0891b2" : "";
    });
  }

  window.RIFT_THEME = {
    names: function () { return Object.keys(THEMES); },
    meta: function (n) { return THEMES[n]; },
    current: currentName,
    apply: apply,
    build: build,
  };

  // Apply (saved or default) synchronously: this script replaces the old
  // inline tailwind.config block, so timing matches what Stitch had.
  // The data-rift-theme marker lets apply() skip re-mutation later.
  try {
    var initial = currentName();
    window.tailwind.config = build(initial);
    document.documentElement.style.setProperty(
      "--rift-surface", (THEMES[initial] || THEMES.console).colors.surface);
    document.documentElement.setAttribute("data-rift-theme", initial);
  } catch (e) {}
  try { document.documentElement.classList.add("dark"); } catch (e) {}
  if (document.readyState !== "loading") {
    try { apply(currentName()); } catch (e) {}
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      try { apply(currentName()); } catch (e) {}
    });
  }
})();
