/* Live adapter: Incidents screen -> /api/operations/incidents + /decisions.
 * Overrides Stitch's toast-only simulators with real CRUD. Same DOM and
 * styling; rows and cards are rebuilt from live responses.
 */
(function () {
  "use strict";
  var R = window.RIFT;
  var incidents = [];
  var decisions = [];

  var SEV = { "critical": "critical", "major": "high", "moderate": "medium" };
  function sevValue(label) {
    label = String(label || "").toLowerCase();
    if (label.indexOf("critical") !== -1 || label.indexOf("sev-1") !== -1) return "critical";
    if (label.indexOf("major") !== -1 || label.indexOf("sev-2") !== -1) return "high";
    if (label.indexOf("moderate") !== -1 || label.indexOf("sev-3") !== -1) return "medium";
    return "info";
  }
  function sevBadge(s) {
    s = String(s || "").toUpperCase();
    var cls = s === "CRITICAL" ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
      : s === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/30"
      : s === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
      : "bg-surface-container-high text-on-surface-variant border-outline-variant";
    return '<span class="px-2 py-0.5 rounded bg-rose-500/10 border text-[10px] ' + cls + '">' + R.esc(s) + "</span>";
  }

  function incidentsTbody() {
    var ths = document.querySelectorAll("th");
    for (var i = 0; i < ths.length; i++) {
      if (ths[i].textContent.trim() === "INCIDENT ID") {
        var tb = ths[i].closest("table");
        if (tb) return tb.querySelector("tbody");
      }
    }
    return null;
  }
  function decisionsGrid() {
    var divs = document.querySelectorAll("div.grid");
    for (var i = 0; i < divs.length; i++) {
      if (/DECISION #/.test(divs[i].textContent.slice(0, 400))) return divs[i];
    }
    return null;
  }

  function toast(title, msg, isErr) {
    if (typeof window.showToast === "function") window.showToast(title, msg, !!isErr);
  }

  function renderIncidents() {
    var tb = incidentsTbody();
    if (!tb) return;
    if (incidents.length === 0) {
      tb.innerHTML = '<tr><td class="p-4 text-xs text-on-surface-variant" colspan="6">No incidents. Create one to begin the lifecycle.</td></tr>';
      return;
    }
    tb.innerHTML = incidents.map(function (inc) {
      var id = inc.id || "?";
      return '<tr class="hover:bg-surface-container-high/50 transition-colors">' +
        '<td class="p-4 text-primary font-bold">#' + R.esc(id) + "</td>" +
        '<td class="p-4"><div class="font-bold text-on-surface font-headline text-sm">' + R.esc(inc.title || "(untitled)") + '</div>' +
        '<div class="text-on-surface-variant text-xs">' + R.esc(inc.description || "") + "</div></td>" +
        "<td class='p-4'>" + sevBadge(inc.severity) + "</td>" +
        '<td class="p-4 text-on-surface-variant">' + R.esc(inc.status || "") + "</td>" +
        '<td class="p-4 text-on-surface-variant">' + R.esc(inc.created_at || inc.updated_at || "") + "</td>" +
        '<td class="p-4 text-right"><button class="px-2.5 py-1 bg-surface-container-high hover:bg-primary hover:text-surface text-on-surface rounded transition-colors text-xs font-mono" data-inspect="' + R.esc(id) + '">Inspect</button></td></tr>';
    }).join("");
    tb.querySelectorAll("[data-inspect]").forEach(function (b) {
      b.addEventListener("click", function () { window.viewIncidentDetails(b.getAttribute("data-inspect")); });
    });
  }

  function renderDecisions() {
    var grid = decisionsGrid();
    if (!grid) return;
    if (decisions.length === 0) {
      grid.innerHTML = '<div class="text-xs text-on-surface-variant p-4 md:col-span-2">Decision queue is empty. Decisions appear here when proposed for review.</div>';
      return;
    }
    grid.innerHTML = decisions.map(function (d) {
      var id = d.id || "?";
      var policy = d.policy ? JSON.stringify(d.policy) : "{}";
      return '<div class="bg-surface-container border border-outline-variant rounded-xl p-5 space-y-4">' +
        '<div class="flex items-start justify-between"><div><span class="text-xs font-mono text-primary font-bold">DECISION #' + R.esc(id) + "</span>" +
        '<h3 class="font-headline text-lg font-bold text-on-surface mt-0.5">Scenario ' + R.esc(d.scenario_id || "?") + "</h3></div>" +
        '<span class="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant text-xs font-mono">' + R.esc(d.status || "") + "</span></div>" +
        '<p class="text-xs font-mono text-on-surface-variant break-all">policy ' + R.esc(policy) + "</p>" +
        '<div class="text-xs font-mono text-on-surface-variant">proposed by ' + R.esc(d.proposed_by || "?") + "</div>" +
        '<div class="flex items-center justify-end gap-3 pt-2 border-t border-outline-variant">' +
        '<button class="px-3 py-1.5 rounded border border-outline-variant text-xs font-mono" data-review="reject:' + R.esc(id) + '">Reject</button>' +
        '<button class="px-4 py-1.5 bg-primary text-surface font-bold text-xs rounded" data-review="accept:' + R.esc(id) + '">Approve</button>' +
        "</div></div>";
    }).join("");
    grid.querySelectorAll("[data-review]").forEach(function (b) {
      b.addEventListener("click", function () {
        var parts = b.getAttribute("data-review").split(":");
        window.reviewDecision(parts[1], parts[0] === "accept" ? "approve" : "reject");
      });
    });
  }

  async function authed(fn) {
    try { await fn(); }
    catch (e) {
      if (R.isAuthError(e)) R.showAuth("incidents and decisions", function () { refreshAll(); });
      else toast("Request failed", e.message || "error", true);
    }
  }

  function refreshAll() {
    window.fetchIncidentsAPI();
    window.fetchDecisionsAPI();
  }

  window.fetchIncidentsAPI = function () {
    authed(async function () {
      incidents = await R.get("/api/operations/incidents");
      if (!Array.isArray(incidents)) incidents = [];
      renderIncidents();
      toast("GET /api/operations/incidents", incidents.length + " incident(s) loaded.");
    });
  };
  window.fetchDecisionsAPI = function () {
    authed(function () {
      return R.get("/api/operations/decisions").then(function (list) {
        decisions = Array.isArray(list) ? list : [];
        renderDecisions();
        toast("GET /api/operations/decisions", decisions.length + " decision(s) in queue.");
      });
    });
  };
  window.viewIncidentDetails = function (id) {
    id = String(id || "").replace(/^#/, "");
    authed(async function () {
      var inc = await R.get("/api/operations/incidents/" + encodeURIComponent(id));
      var tl = (inc.timeline || []).length;
      toast("Incident " + id, (inc.title || "") + " · " + (inc.status || "") +
        " · owner " + (inc.owner || "?") + " · " + tl + " timeline event(s).");
    });
  };
  window.reviewDecision = function (id, action) {
    id = String(id || "").replace(/^#/, "");
    var verb = action === "approve" ? "accept" : "reject";
    authed(async function () {
      var info = await R.sessionInfo().catch(function () { return null; });
      await R.post("/api/operations/decisions/" + encodeURIComponent(id) + "/action",
        { action: verb, note: "reviewed from Stitch UI", user_id: info && info.user_id ? info.user_id : "stitch-ui" });
      toast("Decision " + verb + "ed", id + " recorded.");
      window.fetchDecisionsAPI();
    });
  };
  window.submitIncidentForm = function (e) {
    if (e) e.preventDefault();
    var title = document.getElementById("inc-title").value;
    var severity = sevValue(document.getElementById("inc-severity").value);
    var descEl = document.getElementById("inc-desc");
    var desc = descEl ? descEl.value : "";
    authed(async function () {
      var info = await R.sessionInfo().catch(function () { return null; });
      var created = await R.post("/api/operations/incidents", {
        title: title, description: desc, severity: severity, type: "manual",
        user_id: info && info.user_id ? info.user_id : "stitch-ui",
      });
      if (typeof window.closeCreateModal === "function") window.closeCreateModal();
      var form = document.getElementById("incident-form");
      if (form) form.reset();
      toast("Incident created", "id " + (created.id || created.incident_id || "?"));
      window.fetchIncidentsAPI();
    });
  };
  // Drop the fabricated OAuth2 toast.
  window.refreshAuthToken = function () {
    R.showAuth("incidents and decisions", function () { refreshAll(); });
  };

  document.addEventListener("DOMContentLoaded", function () {
    refreshAll();
    setInterval(function () {
      var decView = document.getElementById("view-decisions");
      var hidden = decView && decView.classList.contains("hidden");
      window.fetchIncidentsAPI();
      if (!hidden) window.fetchDecisionsAPI();
    }, 10000);
  });
})();

/* ---- UI behaviors (were Stitch inline; owned here now that it is stripped) ---- */
window.switchTab = function (tabName) {
  var incBtn = document.getElementById("tab-incidents-btn");
  var decBtn = document.getElementById("tab-decisions-btn");
  var incView = document.getElementById("view-incidents");
  var decView = document.getElementById("view-decisions");
  function on(btn) {
    btn.className = "py-3 font-headline text-sm font-semibold text-primary border-b-2 border-primary flex items-center gap-2 transition-colors";
  }
  function off(btn) {
    btn.className = "py-3 font-headline text-sm font-semibold text-on-surface-variant hover:text-on-surface flex items-center gap-2 transition-colors";
  }
  if (tabName === "incidents") {
    if (incBtn) on(incBtn); if (decBtn) off(decBtn);
    if (incView) incView.classList.remove("hidden");
    if (decView) decView.classList.add("hidden");
  } else {
    if (decBtn) on(decBtn); if (incBtn) off(incBtn);
    if (decView) decView.classList.remove("hidden");
    if (incView) incView.classList.add("hidden");
  }
};
window.openCreateModal = function () {
  var m = document.getElementById("create-incident-modal");
  if (m) m.classList.remove("hidden");
};
window.closeCreateModal = function () {
  var m = document.getElementById("create-incident-modal");
  if (m) m.classList.add("hidden");
};
window.toggleAuthWarning = function () {
  var content = document.getElementById("auth-warning-content");
  var chevron = document.getElementById("auth-chevron");
  if (!content) return;
  if (content.classList.contains("hidden")) {
    content.classList.remove("hidden");
    if (chevron) chevron.style.transform = "rotate(0deg)";
  } else {
    content.classList.add("hidden");
    if (chevron) chevron.style.transform = "rotate(180deg)";
  }
};
window.showToast = function (title, msg, isError) {
  var toast = document.getElementById("toast");
  if (!toast) return;
  var t = document.getElementById("toast-title"), m = document.getElementById("toast-msg"),
      ic = document.getElementById("toast-icon");
  if (t) t.innerText = title;
  if (m) m.innerText = msg;
  if (ic) {
    ic.innerText = isError ? "error" : "check_circle";
    ic.className = isError ? "material-symbols-outlined text-rose-400" : "material-symbols-outlined text-primary";
  }
  toast.classList.remove("translate-y-20", "opacity-0");
  setTimeout(function () { toast.classList.add("translate-y-20", "opacity-0"); }, 4000);
};
(function () {
  var left = 10;
  setInterval(function () {
    left = left <= 0 ? 10 : left - 1;
    var el = document.getElementById("poll-timer");
    if (el) el.innerText = left + "s";
  }, 1000);
})();
