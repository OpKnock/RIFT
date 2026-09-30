/* Live adapter: Explainability screen -> /api/twin/demo + /api/twin/evidence
 * + /api/explainability/audit. Overrides Stitch's mockPayload (fabricated
 * patient, fake ledger rows, fake gates) with real engine data.
 */
(function () {
  "use strict";
  var R = window.RIFT;
  var DAY = 5;

  function $(id) { return document.getElementById(id); }
  function set(id, text) { var el = $(id); if (el) el.textContent = text; }

  function hydrateOverview(twin) {
    var risk = (twin && twin.risk) || {};
    set("card-patient-id", twin.patient_id || "--");
    set("card-sim-day", "Day " + (twin.day_index !== undefined ? twin.day_index : "--"));
    set("card-risk-score", typeof risk.risk === "number" ? (risk.risk * 100).toFixed(1) + "%" : "--");
    set("card-uncertainty", typeof risk.uncertainty === "number" ? "±" + (risk.uncertainty * 100).toFixed(1) + "%" : "--");
    set("card-risk-interval", Array.isArray(risk.interval)
      ? "[" + risk.interval.map(function (v) { return R.num(v, 3); }).join(" - ") + "]" : "--");
    var g = (twin && twin.guardian) || {};
    set("card-guardian-badge", g.action || "--");
    var box = $("causal-reasons-container");
    if (box) {
      var reasons = (twin && twin.reasons) || [];
      box.innerHTML = reasons.length ? reasons.map(function (r, i) {
        return '<div class="p-4 rounded-xl bg-surface-container border border-outline-variant flex flex-col gap-2">' +
          '<div class="flex items-center gap-2"><span class="font-mono text-xs px-2 py-0.5 rounded bg-primary-container text-primary">#' + (i + 1) + "</span></div>" +
          '<p class="text-xs text-on-surface-variant">' + R.esc(r) + "</p></div>";
      }).join("") : '<div class="text-xs text-on-surface-variant">No reasons reported for this snapshot.</div>';
      var contribs = risk.contributions || [];
      if (contribs.length) {
        box.innerHTML += '<div class="p-4 rounded-xl bg-surface-container border border-outline-variant"><div class="text-xs font-semibold mb-2">Top risk contributors</div>' +
          contribs.map(function (c) {
            return '<div class="flex justify-between text-xs font-mono text-on-surface-variant"><span>' + R.esc(c.factor) + "</span><span>+" + R.num(c.value, 3) + "</span></div>";
          }).join("") + "</div>";
      }
    }
  }

  function hydrateGuardian(twin) {
    var tab = $("tab-guardian");
    if (!tab) return;
    var grid = tab.querySelector("div.grid");
    if (!grid) return;
    var g = (twin && twin.guardian) || {};
    var findings = g.findings || [];
    var cards = '<div class="p-4 rounded-xl bg-surface-container border border-outline-variant flex flex-col gap-3">' +
      '<div class="flex items-center justify-between"><span class="font-semibold text-sm">Action: ' + R.esc(g.action || "--") + "</span>" +
      '<span class="px-2 py-0.5 rounded font-mono text-xs ' + (g.display_allowed ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400") + '">' +
      (g.display_allowed ? "DISPLAY ALLOWED" : "DISPLAY WITHHELD") + "</span></div>" +
      '<p class="text-xs text-on-surface-variant">Guardian verdict for day ' + (twin.day_index !== undefined ? twin.day_index : "--") + ".</p></div>";
    cards += findings.map(function (f) {
      var sev = String(f.severity || "").toUpperCase();
      var cls = sev === "HIGH" || sev === "CRITICAL" ? "text-rose-400" : sev === "MEDIUM" || f.action === "WARN" ? "text-amber-400" : "text-emerald-400";
      return '<div class="p-4 rounded-xl bg-surface-container border border-outline-variant flex flex-col gap-3">' +
        '<div class="flex items-center justify-between"><span class="font-semibold text-sm">' + R.esc(f.rule_id || "?") + " · " + R.esc(f.stage || "?") + "</span>" +
        '<span class="px-2 py-0.5 rounded font-mono text-xs ' + cls + '">' + R.esc(f.action || sev || "?") + "</span></div>" +
        '<p class="text-xs text-on-surface-variant">' + R.esc(f.message || "") + "</p></div>";
    }).join("");
    if ((g.flags || []).length) {
      cards += '<div class="p-4 rounded-xl bg-surface-container border border-outline-variant"><div class="text-xs font-semibold mb-2">Flags</div>' +
        g.flags.map(function (f) { return '<p class="text-xs text-on-surface-variant font-mono">' + R.esc(f) + "</p>"; }).join("") + "</div>";
    }
    grid.innerHTML = cards;
  }

  function hydrateProvenance(twin) {
    var tab = $("tab-provenance");
    if (!tab) return;
    var p = (twin && twin.provenance) || {};
    var box = tab.querySelector("div.font-mono.text-xs");
    if (box && Object.keys(p).length) {
      box.style.whiteSpace = "pre-wrap";
      box.textContent = Object.keys(p).map(function (k) { return k + ": " + p[k]; }).join("\n");
    }
  }

  function hydrateEvidence(bundle) {
    var tab = $("tab-evidence");
    if (!tab || !bundle) return;
    var tb = tab.querySelector("tbody");
    if (!tb) return;
    var rows = [
      ["days_evaluated", bundle.days_evaluated, "", ""],
      ["sensitivity", bundle.sensitivity, "", ""],
      ["specificity", bundle.specificity, "", ""],
      ["brier", bundle.brier, "", ""],
      ["interval_coverage", bundle.interval_coverage, "", ""],
      ["event_agreement", bundle.event_agreement, "", ""],
      ["mean_onset_lag", bundle.mean_onset_lag, "", ""],
    ];
    tb.innerHTML = rows.map(function (r, i) {
      return '<tr><td class="p-3 text-primary">EV-' + (9900 + i) + "</td>" +
        '<td class="p-3">' + R.esc(r[0]) + "</td>" +
        '<td class="p-3">' + (r[1] === undefined || r[1] === null ? "--" : R.esc(String(r[1]))) + "</td>" +
        '<td class="p-3">--</td><td class="p-3 text-emerald-400">REPORTED</td></tr>';
    }).join("");
  }

  function hydrateFingerprint(twin) {
    var tab = $("tab-fingerprint");
    if (!tab) return;
    var box = tab.querySelector("div.break-all");
    var p = (twin && twin.provenance) || {};
    if (box && p.prediction_id) box.textContent = p.prediction_id;
  }

  function hydrateAudit() {
    var tab = $("tab-audit");
    if (!tab) return;
    R.get("/api/explainability/audit").then(function (body) {
      var records = (body && body.records) || [];
      var tb = tab.querySelector("tbody");
      var counter = tab.querySelector("span.text-xs.font-mono");
      if (counter) counter.textContent = "Showing " + records.length + " record(s)";
      if (!tb) return;
      tb.innerHTML = records.length ? records.map(function (r) {
        return '<tr class="hover:bg-surface-container-high/50 transition-colors">' +
          '<td class="p-3.5 text-on-surface-variant">' + R.esc(r.timestamp || "") + "</td>" +
          '<td class="p-3.5 text-primary">' + R.esc(String(r.hash || "").slice(0, 18)) + "</td>" +
          '<td class="p-3.5">' + R.esc(r.record_type || "") + "</td>" +
          '<td class="p-3.5">' + R.esc(r.actor || "") + "</td>" +
          '<td class="p-3.5 text-on-surface-variant">' + R.esc(String(r.record_id || "").slice(0, 18)) + "</td>" +
          '<td class="p-3.5 text-emerald-400 font-semibold">RECORDED</td></tr>';
      }).join("") : '<tr><td class="p-3.5 text-on-surface-variant" colspan="6">No audit records yet. Reviews and decisions append here.</td></tr>';
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("audit ledger");
    });
  }

  window.triggerExport = function () {
    R.get("/api/explainability/audit").then(function (body) {
      var blob = new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "rift-audit-ledger.json";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("audit ledger");
    });
  };

  window.riftVerify = function () { window.location.reload(); };
  document.addEventListener("DOMContentLoaded", function () {
    R.get("/api/twin/demo?t=" + DAY).then(function (twin) {
      hydrateOverview(twin);
      hydrateGuardian(twin);
      hydrateProvenance(twin);
      hydrateFingerprint(twin);
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("twin evidence");
    });
    R.get("/api/twin/evidence").then(hydrateEvidence).catch(function () {});
    hydrateAudit();
  });
})();

window.switchTab = function (targetId) {
  document.querySelectorAll(".tab-content").forEach(function (el) { el.classList.add("hidden"); });
  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.classList.remove("border-primary", "text-primary");
    btn.classList.add("border-transparent", "text-on-surface-variant");
  });
  var c = document.getElementById("tab-" + targetId);
  if (c) { c.classList.remove("hidden"); c.classList.add("flex"); }
  var b = document.querySelector('[data-target="' + targetId + '"]');
  if (b) {
    b.classList.remove("border-transparent", "text-on-surface-variant");
    b.classList.add("border-primary", "text-primary");
  }
};
