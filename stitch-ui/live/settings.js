/* Live adapter: Settings screen -> /api/health + session endpoints.
 * Overrides Stitch's simulated health poll (fake 99.998% uptime, fake
 * node counts) and simulated token exchange (fake random session id)
 * with the real engine and session cookie flow.
 */
(function () {
  "use strict";
  var R = window.RIFT;

  function $(id) { return document.getElementById(id); }

  window.pollHealth = function () {
    var statusEl = $("health-status"), uptimeEl = $("health-uptime"), nodesEl = $("health-nodes");
    if (statusEl) statusEl.innerHTML = "Querying /api/health...";
    R.get("/api/health").then(function (h) {
      var ok = String(h.status || "").toLowerCase() === "ok";
      if (statusEl) {
        statusEl.innerHTML = ok
          ? '<span class="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span> Nominal'
          : '<span class="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></span> ' + R.esc(h.status || "unknown");
      }
      if (uptimeEl) uptimeEl.textContent = "engine v" + String(h.version || "?").replace(/^v/, "");
      if (nodesEl) {
        var p = h.persistence || {}, b = h.billing || {};
        nodesEl.textContent = "persistence " + (p.configured ? "on" : "off") +
          " · billing " + (b.configured ? "on" : "off") +
          " · backend " + (h.quantum_backend || "?");
      }
    }).catch(function (e) {
      if (statusEl) statusEl.textContent = "Unreachable: " + (e.message || "error");
    });
  };

  function renderSession(info) {
    var card = $("session-info-card");
    if (!card) return;
    if (info && info.user_id) {
      card.classList.remove("hidden");
      var v = $("session-id-val");
      if (v) v.textContent = info.user_id + " (" + (info.mechanism || "session") + ")";
    } else {
      card.classList.add("hidden");
    }
  }

  window.exchangeToken = function () {
    var input = $("apiTokenInput"), msg = $("auth-status-msg");
    var token = input ? input.value.trim() : "";
    if (!token) {
      if (msg) { msg.textContent = "Error: token cannot be empty."; msg.className = "text-xs text-red-400"; }
      return;
    }
    if (msg) { msg.textContent = "Status: exchanging via POST /api/auth/session..."; msg.className = "text-xs text-amber-400"; }
    R.post("/api/auth/session", { token: token }).then(function () {
      return R.sessionInfo();
    }).then(function (info) {
      renderSession(info);
      if (msg) { msg.textContent = "Status: session established (HttpOnly cookie set)."; msg.className = "text-xs text-emerald-400"; }
      if (input) input.value = "";
    }).catch(function (e) {
      if (msg) { msg.textContent = "Status: exchange failed — " + (e.message || ("HTTP " + e.status)); msg.className = "text-xs text-red-400"; }
    });
  };

  window.logoutSession = function () {
    R.post("/api/auth/logout", {}).catch(function () {}).then(function () {
      renderSession(null);
      var msg = $("auth-status-msg");
      if (msg) { msg.textContent = "Status: session terminated."; msg.className = "text-xs text-on-surface-variant"; }
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    R.sessionInfo().then(renderSession).catch(function () {});
    injectThemePicker();
  });

  // Color-theme picker: the other two Stitch palettes, listed here so the
  // whole app stays one theme (default Console) with opt-in alternatives.
  function injectThemePicker() {
    if (!window.RIFT_THEME || document.getElementById("rift-theme-picker")) return;
    var tab = document.getElementById("tab-content-appearance");
    if (!tab) return;
    var card = tab.querySelector("div.bg-surface-container");
    if (!card) return;
    var wrap = document.createElement("div");
    wrap.id = "rift-theme-picker";
    wrap.className = "flex flex-col gap-3 pt-2";
    var title = document.createElement("h3");
    title.className = "font-headline text-sm font-semibold";
    title.textContent = "Color theme (all screens)";
    var sub = document.createElement("p");
    sub.className = "text-xs text-on-surface-variant";
    sub.textContent = "One shared theme across the app. Console is the default; the other two are the palettes individual screens shipped with.";
    var grid = document.createElement("div");
    grid.className = "grid grid-cols-3 gap-4";
    window.RIFT_THEME.names().forEach(function (name) {
      var meta = window.RIFT_THEME.meta(name);
      var b = document.createElement("button");
      b.setAttribute("data-theme-pick", name);
      b.setAttribute("aria-pressed", "false");
      b.className = "p-4 rounded-lg border bg-surface-container-high flex flex-col items-center gap-2 font-medium text-sm hover:border-primary";
      b.style.borderWidth = "1px";
      b.innerHTML =
        '<span style="display:flex;gap:4px;">' +
        '<span style="width:22px;height:22px;border-radius:6px;background:' + meta.swatch[0] + ';border:1px solid #334155;"></span>' +
        '<span style="width:22px;height:22px;border-radius:6px;background:' + meta.swatch[1] + ';"></span></span>' +
        "<span></span>";
      b.lastChild.textContent = meta.label + (name === "console" ? " (default)" : "");
      var d = document.createElement("span");
      d.className = "text-[11px] text-on-surface-variant";
      d.textContent = meta.desc;
      b.appendChild(d);
      b.addEventListener("click", function () { window.RIFT_THEME.apply(name); });
      grid.appendChild(b);
    });
    wrap.appendChild(title);
    wrap.appendChild(sub);
    wrap.appendChild(grid);
    card.appendChild(wrap);
    window.RIFT_THEME.apply(window.RIFT_THEME.current());
  }
})();

window.switchTab = function (tabId) {
  document.querySelectorAll(".tab-content").forEach(function (el) { el.classList.add("hidden"); });
  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.classList.remove("border-primary", "text-primary");
    btn.classList.add("border-transparent", "text-on-surface-variant");
  });
  var c = document.getElementById("tab-content-" + tabId);
  if (c) c.classList.remove("hidden");
  var b = document.getElementById("btn-" + tabId);
  if (b) {
    b.classList.remove("border-transparent", "text-on-surface-variant");
    b.classList.add("border-primary", "text-primary");
  }
};
window.saveProfile = function () {
  var input = document.getElementById("displayNameInput");
  try { localStorage.setItem("rift_display_name", input ? input.value : ""); } catch (e) {}
};
window.setTheme = function (mode) {
  var html = document.documentElement;
  function apply(dark) { html.classList.toggle("dark", !!dark); try { localStorage.setItem("rift-theme", dark ? "dark" : "light"); } catch (e) {} }
  if (mode === "dark") apply(true);
  else if (mode === "light") apply(false);
  else apply(window.matchMedia("(prefers-color-scheme: dark)").matches);
};
(function () {
  try {
    var saved = localStorage.getItem("rift_display_name");
    if (saved) { var i = document.getElementById("displayNameInput"); if (i) i.value = saved; }
    var theme = localStorage.getItem("rift-theme");
    if (theme === "light") document.documentElement.classList.remove("dark");
    else document.documentElement.classList.add("dark");
  } catch (e) {}
})();
