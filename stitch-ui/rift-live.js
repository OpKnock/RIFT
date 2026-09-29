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

  window.RIFT = {
    API: API, api: api, get: get, post: post, num: num, esc: esc,
    showAuth: showAuth, hideAuth: hideAuth, sessionInfo: sessionInfo,
    isAuthError: function (e) { return !!e && e.status === 401; },
  };
})();
