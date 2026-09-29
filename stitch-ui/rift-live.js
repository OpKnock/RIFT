/* RIFT live wiring layer (Stitch UI -> RIFT engine API).
 * This file connects Stitch-built screens to the real backend. It does not
 * change any screen design: same elements, same styling, real data only.
 *
 * - RIFT_API_BASE: override with ?api= or window.RIFT_API_BASE. Default
 *   same-origin when served beside the API, else http://localhost:8080.
 * - All API calls send credentials (HttpOnly session cookie after the
 *   Settings screen exchanges a service token). 401s surface the
 *   authentication panel instead of raw errors; nothing is fabricated.
 */
(function () {
  "use strict";

  function base() {
    try {
      var q = new URLSearchParams(window.location.search).get("api");
      if (q) return q.replace(/\/$/, "");
    } catch (e) { /* ignore */ }
    if (window.RIFT_API_BASE) return String(window.RIFT_API_BASE).replace(/\/$/, "");
    if (window.location.port === "8080") return window.location.origin;
    return "http://localhost:8080";
  }
  var API = base();

  function ApiError(status, message) {
    this.status = status;
    this.message = message || ("HTTP " + status);
  }

  async function api(path, opts) {
    opts = opts || {};
    var res = await fetch(API + path, {
      method: opts.method || "GET",
      credentials: "include",
      headers: Object.assign({ "Accept": "application/json" }, opts.headers || {}),
      body: opts.body,
    });
    var data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      var msg = (data && (data.detail || data.error)) || ("HTTP " + res.status);
      throw new ApiError(res.status, msg);
    }
    return data;
  }

  function get(path) { return api(path); }
  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  // Null-safe number formatting: never throws, never renders NaN.
  function num(v, dp) {
    if (dp === undefined) dp = 2;
    return (typeof v === "number" && isFinite(v)) ? v.toFixed(dp) : "--";
  }

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Redirect relative /api/* fetches written by Stitch to the live API
  // (same behavior, real backend, session cookie attached).
  if (!window.__riftFetchShimmed) {
    window.__riftFetchShimmed = true;
    var nativeFetch = window.fetch.bind(window);
    window.fetch = function (url, opts) {
      if (typeof url === "string" && url.indexOf("/api/") === 0) {
        opts = opts || {};
        if (!opts.credentials) opts.credentials = "include";
        return nativeFetch(API + url, opts);
      }
      return nativeFetch(url, opts);
    };
  }

  // Authentication panel: shown on 401. Exchanges a service token once via
  // POST /api/auth/session (server sets HttpOnly cookie), then retries.
  var authRetry = null;
  function showAuth(resource, onDone) {
    authRetry = onDone || null;
    var panel = document.getElementById("rift-auth-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "rift-auth-panel";
      panel.setAttribute("style", "position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(2,6,12,.72);backdrop-filter:blur(2px);");
      panel.innerHTML =
        '<div style="width:min(440px,92vw);background:#0b1220;border:1px solid #1e293b;border-radius:14px;padding:24px;font-family:Inter,system-ui,sans-serif;color:#e2e8f0;">' +
        '<h2 style="margin:0 0 8px;font-size:17px;">Authentication required</h2>' +
        '<p id="rift-auth-msg" style="margin:0 0 14px;font-size:13px;color:#94a3b8;">This server gates ' + esc(resource || "this resource") + ' behind authentication. Paste a service token once; it is exchanged for an HttpOnly session cookie.</p>' +
        '<input id="rift-auth-token" type="password" placeholder="Service token" style="width:100%;box-sizing:border-box;background:#020617;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:9px 12px;font-size:13px;margin-bottom:10px;" />' +
        '<div style="display:flex;gap:8px;align-items:center;">' +
        '<button id="rift-auth-go" style="background:#0891b2;border:0;border-radius:8px;color:#fff;font-size:13px;font-weight:600;padding:8px 16px;cursor:pointer;">Sign in</button>' +
        '<button id="rift-auth-cancel" style="background:transparent;border:1px solid #334155;border-radius:8px;color:#94a3b8;font-size:13px;padding:8px 14px;cursor:pointer;">Cancel</button>' +
        '<span id="rift-auth-err" style="font-size:12px;color:#f87171;"></span>' +
        "</div></div>";
      document.body.appendChild(panel);
      document.getElementById("rift-auth-cancel").addEventListener("click", hideAuth);
      document.getElementById("rift-auth-go").addEventListener("click", doExchange);
      document.getElementById("rift-auth-token").addEventListener("keydown", function (e) {
        if (e.key === "Enter") doExchange();
      });
    }
    panel.style.display = "flex";
    var err = document.getElementById("rift-auth-err");
    if (err) err.textContent = "";
  }
  function hideAuth() {
    var panel = document.getElementById("rift-auth-panel");
    if (panel) panel.style.display = "none";
  }
  async function doExchange() {
    var token = document.getElementById("rift-auth-token").value;
    var err = document.getElementById("rift-auth-err");
    try {
      await post("/api/auth/session", { token: token });
      hideAuth();
      if (authRetry) { var f = authRetry; authRetry = null; f(); }
      else window.location.reload();
    } catch (e) {
      err.textContent = "Sign-in failed: " + (e.message || e.status || "error");
    }
  }

  async function sessionInfo() {
    try { return await get("/api/auth/session-info"); }
    catch (e) { return null; }
  }

  // Topbar honesty: Stitch hardcoded "Engine: v0.9.4-rc", "Cluster-01:
  // Online", "Latency: 24ms". Replace those text nodes with the live
  // health response and measured fetch duration (elements and their
  // listeners are preserved — only text changes).
  document.addEventListener("DOMContentLoaded", function () {
    var started = performance.now();
    get("/api/health").then(function (h) {
      var rtt = Math.round(performance.now() - started);
      var version = "v" + String(h.version || h.engine_version || "unknown").replace(/^v/, "");
      var status = String(h.status || "unknown").toUpperCase();
      var pairs = [
        ["v0.9.4-rc", version],
        ["Cluster-01: Online", "Engine: " + status],
        ["Latency: 24ms", "Latency: " + rtt + "ms"],
      ];
      try {
        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        var nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(function (node) {
          pairs.forEach(function (p) {
            if (node.nodeValue && node.nodeValue.indexOf(p[0]) !== -1) {
              node.nodeValue = node.nodeValue.split(p[0]).join(p[1]);
            }
          });
        });
      } catch (e) { /* leave Stitch text offline */ }
    }).catch(function () { /* topbar keeps Stitch defaults offline */ });
  });

  // Hide the page-level scrollbar (inner panels keep their own).
  try {
    var rootCss = document.createElement("style");
    rootCss.textContent = "html{scrollbar-width:none;-ms-overflow-style:none}" +
      "html::-webkit-scrollbar{width:0 !important;height:0 !important;display:none !important}" +
      "body::-webkit-scrollbar{width:0 !important;height:0 !important}";
    document.head.appendChild(rootCss);
  } catch (e) {}

  // Account menu (top-right avatar). Stitch rendered it dead; this makes it
  // open a real menu: display name, session state, settings links, sign out.
  function setupAccountMenu() {
    var header = document.querySelector("header");
    if (!header) return null;
    var avatar = null;
    var cands = header.querySelectorAll("div.rounded-full");
    for (var i = 0; i < cands.length; i++) {
      var el = cands[i];
      if (/\bLR\b/.test(el.textContent) || el.querySelector("img")) { avatar = el; break; }
    }
    if (!avatar) {
      avatar = document.createElement("button");
      avatar.id = "rift-avatar";
      avatar.setAttribute("aria-label", "Account");
      avatar.style.cssText = "width:28px;height:28px;border-radius:9999px;background:#1f2937;border:1px solid #374151;color:#0891b2;font-size:12px;font-weight:700;margin-left:4px;cursor:pointer;";
      avatar.textContent = "R";
      var cluster = header.querySelector("div.flex.items-center.gap-2, div.flex.items-center.gap-3");
      (cluster || header).appendChild(avatar);
    } else if (avatar.tagName !== "BUTTON") {
      avatar.style.cursor = "pointer";
      avatar.setAttribute("role", "button");
      avatar.setAttribute("tabindex", "0");
      avatar.setAttribute("aria-label", "Account");
    }
    var menu = document.createElement("div");
    menu.id = "rift-account-menu";
    menu.style.cssText = "display:none;position:fixed;z-index:10000;min-width:250px;background:#0b1220;border:1px solid #1e293b;border-radius:12px;padding:14px;font-family:Inter,system-ui,sans-serif;color:#e2e8f0;box-shadow:0 12px 40px rgba(0,0,0,.5);";
    menu.innerHTML =
      '<div id="rift-acct-name" style="font-size:14px;font-weight:600;">Research User</div>' +
      '<div id="rift-acct-sess" style="font-size:12px;color:#94a3b8;margin:2px 0 10px;">checking session...</div>' +
      '<div style="display:flex;flex-direction:column;gap:6px;">' +
      '<a href="./settings.html" style="font-size:13px;color:#e2e8f0;text-decoration:none;background:#111827;border:1px solid #1e293b;border-radius:8px;padding:7px 10px;">Profile settings</a>' +
      '<a href="./settings.html" style="font-size:13px;color:#e2e8f0;text-decoration:none;background:#111827;border:1px solid #1e293b;border-radius:8px;padding:7px 10px;">API token</a>' +
      '<button id="rift-acct-out" style="font-size:13px;color:#f87171;background:transparent;border:1px solid #334155;border-radius:8px;padding:7px 10px;cursor:pointer;text-align:left;">Sign out</button>' +
      "</div>";
    document.body.appendChild(menu);
    function refresh() {
      var name = null;
      try { name = localStorage.getItem("rift_display_name"); } catch (e) {}
      var nEl = document.getElementById("rift-acct-name");
      if (nEl && name) nEl.textContent = name;
      sessionInfo().then(function (info) {
        var sEl = document.getElementById("rift-acct-sess");
        if (!sEl) return;
        sEl.textContent = (info && info.user_id)
          ? "signed in as " + info.user_id + " (" + (info.mechanism || "session") + ")"
          : "not signed in (open dev or token required)";
      });
    }
    function toggle() {
      if (menu.style.display === "block") { menu.style.display = "none"; return; }
      refresh();
      var r = avatar.getBoundingClientRect();
      menu.style.top = (r.bottom + 8 + window.scrollY) + "px";
      menu.style.left = Math.max(8, r.right - 250 + window.scrollX) + "px";
      menu.style.display = "block";
    }
    avatar.addEventListener("click", function (e) { e.stopPropagation(); toggle(); });
    if (avatar.tagName !== "BUTTON") {
      avatar.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    }
    document.addEventListener("click", function (e) {
      if (menu.style.display === "block" && !menu.contains(e.target)) menu.style.display = "none";
    });
    document.getElementById("rift-acct-out").addEventListener("click", function () {
      post("/api/auth/logout", {}).catch(function () {}).then(function () { window.location.reload(); });
    });
  }
  if (document.readyState !== "loading") setupAccountMenu();
  else document.addEventListener("DOMContentLoaded", setupAccountMenu);

  // Collapsible sidebar + entrance stagger (one web polish).
  // Desktop: hamburger collapses the rail (content goes full width).
  // Mobile: hamburger slides the rail over as an overlay with a scrim.
  // Preference persists in localStorage `rift-nav`.
  function setupNav() {
    var header = document.querySelector("header");
    if (!header) return;
    var btn = document.createElement("button");
    btn.id = "rift-nav-toggle";
    btn.setAttribute("aria-label", "Toggle navigation");
    btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:20px">menu</span>';
    header.insertBefore(btn, header.firstChild);
    var scrim = document.createElement("div");
    scrim.id = "rift-scrim";
    document.body.appendChild(scrim);
    scrim.addEventListener("click", function () { document.body.classList.remove("rift-nav-open"); });
    function isMobile() {
      return window.matchMedia("(max-width: 767px)").matches;
    }
    btn.addEventListener("click", function () {
      if (isMobile()) {
        document.body.classList.toggle("rift-nav-open");
      } else {
        var collapsed = document.body.classList.toggle("rift-nav-collapsed");
        try { localStorage.setItem("rift-nav", collapsed ? "collapsed" : "open"); } catch (e) {}
      }
    });
    try {
      if (localStorage.getItem("rift-nav") === "collapsed" && !isMobile()) {
        document.body.classList.add("rift-nav-collapsed");
      }
    } catch (e) {}
  }
  function staggerEntrance() {
    try {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      var main = document.querySelector("main");
      if (!main || main.classList.contains("rift-anim")) return;
      var kids = main.children;
      var n = Math.min(kids.length, 12);
      for (var i = 0; i < n; i++) {
        kids[i].style.animationDelay = Math.min(i * 60, 500) + "ms";
      }
      main.classList.add("rift-anim");
    } catch (e) {}
  }
  if (document.readyState !== "loading") { setupNav(); staggerEntrance(); }
  else document.addEventListener("DOMContentLoaded", function () { setupNav(); staggerEntrance(); });

  window.RIFT = {
    API: API, api: api, get: get, post: post, num: num, esc: esc,
    showAuth: showAuth, hideAuth: hideAuth, sessionInfo: sessionInfo,
    isAuthError: function (e) { return !!e && e.status === 401; },
  };
})();
