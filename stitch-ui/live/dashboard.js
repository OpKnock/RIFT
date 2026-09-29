/* Live adapter: Dashboard -> /api/health + /api/meta + /api/ops/monitor.
 * Replaces Stitch's mockApiFetch fabrication (fake Z3 solver, fake qubit
 * counts, fake daemons) with real engine responses. Same DOM ids and
 * styling; fields the engine has no concept of render "--".
 */
(function () {
  "use strict";
  var R = window.RIFT;

  function $(id) { return document.getElementById(id); }
  function set(id, text) { var el = $(id); if (el) el.textContent = text; }
  function show(el, on) {
    if (!el) return;
    if (on) el.classList.remove("hidden"); else el.classList.add("hidden");
  }

  async function realTriggerFetch() {
    var bannerText = $("banner-text"), bannerBadge = $("banner-badge"), bannerIcon = $("banner-icon");
    var banner = $("status-banner");
    if (banner) banner.classList.remove("hidden");
    if (bannerText) bannerText.textContent = "Fetching live engine telemetry...";
    if (bannerBadge) bannerBadge.textContent = "PENDING";
    if (bannerIcon) { bannerIcon.textContent = "sync"; bannerIcon.classList.add("animate-spin"); }

    ["topology", "optimizer", "quantum", "smt"].forEach(function (k) {
      show($("card-" + k + "-loading"), true);
      show($("card-" + k + "-content"), false);
    });

    var health = null, meta = null, ops = null, opsErr = null;
    try { health = await R.get("/api/health"); } catch (e) { health = null; }
    try { meta = await R.get("/api/meta"); } catch (e) { meta = null; }
    try { ops = await R.get("/api/ops/monitor"); }
    catch (e) { ops = null; opsErr = e; }

    if (!health && !meta) {
      if (bannerIcon) { bannerIcon.classList.remove("animate-spin"); bannerIcon.textContent = "error"; }
      if (bannerText) bannerText.textContent = "Engine unreachable. Is the API running? Click Retry Fetch.";
      if (bannerBadge) bannerBadge.textContent = "OFFLINE / ERROR";
      return;
    }

    var limits = (meta && meta.limits) || {};
    var version = (health && (health.version || health.engine_version)) ||
                  (meta && (meta.engine_version || meta.version)) || "unknown";
    var status = String((health && health.status) || "unknown").toUpperCase();
    var opts = (meta && meta.optimizers) || [];
    var qb = (health && health.quantum_backend_detail) || {};
    var backend = (health && health.quantum_backend) || (meta && meta.quantum_backend) || "--";

    set("topo-nodes", String(limits.max_policy_variables !== undefined ? limits.max_policy_variables : "--"));
    set("topo-depth", String(limits.max_tree_depth !== undefined ? limits.max_tree_depth : "--"));
    set("topo-state", status);
    set("opt-algo", opts.length ? opts.join(", ") : "--");
    set("opt-throughput", ((meta && meta.backends) || []).join(", ") || "--");
    set("opt-conv", "--");
    set("q-qubits", backend);
    set("q-coherence", qb.hardware_configured ? "hardware" : "simulator");
    set("q-fidelity", qb.aer_available ? "aer available" : "--");
    set("smt-solver", "--");
    set("smt-assertions", "--");
    set("smt-status", "--");

    ["topology", "optimizer", "quantum", "smt"].forEach(function (k) {
      show($("card-" + k + "-loading"), false);
      show($("card-" + k + "-content"), true);
    });

    var tbody = $("matrix-tbody");
    if (tbody) {
      var alerts = (ops && ops.alerts) || [];
      if (opsErr && R.isAuthError(opsErr)) {
        tbody.innerHTML = '<tr><td class="py-3 px-4 text-amber-400" colspan="5">Telemetry gated (401). <button id="rift-matrix-auth" style="text-decoration:underline">Sign in</button> to load alert rules.</td></tr>';
        var b = document.getElementById("rift-matrix-auth");
        if (b) b.addEventListener("click", function () {
          R.showAuth("operations telemetry", realTriggerFetch);
        });
      } else if (!alerts.length) {
        tbody.innerHTML = '<tr><td class="py-3 px-4 text-on-surface-variant" colspan="5">No alert rules evaluated.</td></tr>';
      } else {
        var now = new Date().toLocaleTimeString();
        tbody.innerHTML = alerts.map(function (a) {
          var firing = !!a.firing;
          var sev = firing ? "FIRING" : "INFO";
          var badge = firing
            ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
            : "bg-primary/10 text-primary border-primary/20";
          return '<tr class="hover:bg-surface-container-high/50 transition-colors">' +
            '<td class="py-3 px-4 font-medium text-on-surface">' + R.esc(a.rule || "?") + "</td>" +
            '<td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-mono border ' + badge + '">' + sev + "</span></td>" +
            '<td class="py-3 px-4 text-on-surface-variant">engine</td>' +
            '<td class="py-3 px-4 text-primary">' + (firing ? "FIRING" : "OK") + "</td>" +
            '<td class="py-3 px-4 text-right text-on-surface-variant">' + R.esc(a.reason || now) + "</td></tr>";
        }).join("");
      }
    }

    if (bannerIcon) { bannerIcon.classList.remove("animate-spin"); bannerIcon.textContent = "check_circle"; }
    if (bannerText) {
      bannerText.textContent = ops
        ? "All daemon endpoints synchronized successfully. Engine v" + String(version).replace(/^v/, "") + "."
        : "Engine reachable; telemetry gated (sign in to load alert rules). Engine v" + String(version).replace(/^v/, "") + ".";
    }
    if (bannerBadge) bannerBadge.textContent = ops ? "ONLINE (200 OK)" : "PARTIAL (401 TELEMETRY)";

    var term = $("terminal-dynamic-logs");
    if (term) {
      var ts = new Date().toLocaleTimeString();
      var div = document.createElement("div");
      div.className = "text-primary";
      div.textContent = "[" + ts + "] GET /api/health, /api/meta, /api/ops/monitor -> " +
        (health ? "200" : "fail") + " / " + (meta ? "200" : "fail") + " / " + (ops ? "200" : (opsErr ? opsErr.status || "fail" : "fail"));
      term.appendChild(div);
    }
  }

  window.triggerFetch = realTriggerFetch;
  // Header actions: Verify re-pulls live telemetry; Deploy Override has no
  // engine endpoint in this research build, so it says so in the terminal.
  function wireHeaderButtons() {
    var terms = $("terminal-dynamic-logs");
    function note(text) {
      if (!terms) return;
      var div = document.createElement("div");
      div.className = "text-primary";
      div.textContent = "[" + new Date().toLocaleTimeString() + "] " + text;
      terms.appendChild(div);
    }
    Array.prototype.forEach.call(document.querySelectorAll("button"), function (b) {
      var label = (b.textContent || "").trim();
      if (/^verify snapshot/i.test(label)) {
        b.addEventListener("click", function () { note("manual verify: re-fetching telemetry..."); realTriggerFetch(); });
      } else if (/deploy override/i.test(label)) {
        b.addEventListener("click", function () {
          note("deploy skipped: no deployment endpoint in this build (decision support only, never autonomous action).");
        });
      }
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    realTriggerFetch();
    wireHeaderButtons();
  });
})();
