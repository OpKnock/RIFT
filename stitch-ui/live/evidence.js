/* Live adapter: Evidence screen -> /api/twin/demo?t= + /api/twin/evidence.
 * Overrides Stitch's hardcoded 14-day mock dataset (fabricated clinical
 * events, fake signatures, fake MIMIC metrics) with real twin snapshots.
 * Same DOM ids, same styling, same snapshot localStorage shape.
 */
(function () {
  "use strict";
  var R = window.RIFT;
  var DAYS = 14;
  var cache = {};   // day -> twin snapshot
  var myPoll = null;

  function riskPct(snap) {
    var r = snap && snap.risk ? snap.risk.risk : null;
    return (typeof r === "number") ? r * 100 : null;
  }
  function verdictOf(snap) {
    var a = snap && snap.guardian ? snap.guardian.action : null;
    return a || "UNKNOWN";
  }
  function sigOf(snap) {
    var p = snap && snap.provenance ? snap.provenance.prediction_id : null;
    return p ? String(p).slice(0, 16) + "..." : "--";
  }
  function badgeClass(v) {
    if (v === "ALLOW") return "px-2.5 py-0.5 rounded text-xs font-label uppercase tracking-wider bg-success/20 text-success border border-success/30";
    if (v === "WARN") return "px-2.5 py-0.5 rounded text-xs font-label uppercase tracking-wider bg-warning/20 text-warning border border-warning/30";
    return "px-2.5 py-0.5 rounded text-xs font-label uppercase tracking-wider bg-error/20 text-error border border-error/30";
  }

  async function loadDay(day) {
    if (cache[day] !== undefined) return cache[day];
    var snap = await R.get("/api/twin/demo?t=" + day);
    cache[day] = snap;
    return snap;
  }
  async function loadAll(statusEl) {
    for (var d = 0; d < DAYS; d++) {
      try {
        await loadDay(d);
        if (statusEl) statusEl.textContent = "Loading twin days... " + (d + 1) + "/" + DAYS;
      } catch (e) {
        cache[d] = null;
        if (R.isAuthError(e)) { R.showAuth("twin replay", function () { loadAll(statusEl); }); return false; }
        if (statusEl) statusEl.textContent = "Twin replay failed: " + (e.message || "error");
        return false;
      }
    }
    return true;
  }

  window.updateReplayState = function (dayIndex) {
    dayIndex = Math.max(0, Math.min(DAYS - 1, Number(dayIndex) || 0));
    function paint(snap) {
      if (!snap) return;
      var risk = riskPct(snap), verdict = verdictOf(snap);
      document.getElementById("current-day-label").innerText = snap.day_index !== undefined ? snap.day_index : dayIndex;
      document.getElementById("risk-score-val").innerText = risk === null ? "--" : risk.toFixed(1) + "%";
      document.getElementById("risk-bar").style.width = (risk === null ? 0 : Math.max(0, Math.min(100, risk))) + "%";
      var prev = cache[dayIndex - 1], prevRisk = prev ? riskPct(prev) : null;
      var delta = (risk === null || prevRisk === null) ? "--" : ((risk - prevRisk >= 0 ? "+" : "") + (risk - prevRisk).toFixed(1) + "pp");
      document.getElementById("risk-delta-badge").innerText = delta;
      document.getElementById("timestamp-readout").innerText = "day " + dayIndex + " · patient " + (snap.patient_id || "--");
      var unc = snap.risk && typeof snap.risk.uncertainty === "number" ? snap.risk.uncertainty : null;
      document.getElementById("vector-velocity-val").innerText = unc === null ? "--" : "±" + unc.toFixed(3);
      var badge = document.getElementById("guardian-badge");
      badge.innerText = verdict;
      badge.className = badgeClass(verdict);
      var bars = document.querySelectorAll(".cal-bar");
      for (var bi = 0; bi < bars.length; bi++) {
        var h = risk === null ? 8 : Math.max(8, Math.min(100, risk * (0.55 + bi * 0.06)));
        bars[bi].style.height = h + "%";
      }
      window.renderDivergenceTable(dayIndex);
    }
    if (cache[dayIndex] !== undefined) { paint(cache[dayIndex]); return; }
    loadDay(dayIndex).then(paint).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("twin replay", function () { window.updateReplayState(dayIndex); });
    });
  };

  window.renderDivergenceTable = function (uptoDay) {
    var tbody = document.getElementById("divergence-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    for (var i = uptoDay; i >= Math.max(0, uptoDay - 4); i--) {
      (function (day) {
        var snap = cache[day];
        function row(s) {
          var risk = s ? riskPct(s) : null, v = s ? verdictOf(s) : "UNKNOWN";
          var prev = cache[day - 1], pr = prev ? riskPct(prev) : null;
          var delta = (risk === null || pr === null) ? "--" : ((risk - pr >= 0 ? "+" : "") + (risk - pr).toFixed(1) + "pp");
          var cls = v === "ALLOW" ? "text-success bg-success/10" : v === "WARN" ? "text-warning bg-warning/10" : "text-error bg-error/10";
          var tr = document.createElement("tr");
          tr.innerHTML =
            '<td class="py-3 text-primary">D' + day + "</td>" +
            '<td class="py-3">' + (risk === null ? "--" : risk.toFixed(1) + "% (" + delta + ")") + "</td>" +
            '<td class="py-3 text-on-surface">' + (s && s.patient_id ? R.esc(s.patient_id) : "--") + "</td>" +
            '<td class="py-3"><span class="px-2 py-0.5 rounded text-[10px] ' + cls + '">' + R.esc(v) + "</span></td>" +
            '<td class="py-3 text-on-surface-variant">' + R.esc(s ? sigOf(s) : "--") + "</td>";
          tbody.appendChild(tr);
        }
        if (snap !== undefined) row(snap);
        else loadDay(day).then(row).catch(function () { row(null); });
      })(i);
    }
  };

  window.captureSnapshot = function () {
    var day = Number(document.getElementById("day-slider").value || 0);
    function save(snap) {
      if (!snap) return;
      var snapshots = JSON.parse(localStorage.getItem("rift_snapshots") || "[]");
      var risk = riskPct(snap);
      snapshots.push({
        id: "SNAP-" + Date.now().toString(36).toUpperCase(),
        timestamp: new Date().toISOString(),
        day: day,
        risk: risk === null ? null : Math.round(risk * 10) / 10,
        verdict: verdictOf(snap),
        signature: sigOf(snap),
      });
      localStorage.setItem("rift_snapshots", JSON.stringify(snapshots));
      window.updateSnapshotCount();
    }
    if (cache[day] !== undefined) save(cache[day]);
    else loadDay(day).then(save).catch(function () {});
  };

  window.startPolling = function () {
    if (myPoll) clearInterval(myPoll);
    myPoll = setInterval(function () {
      var t0 = performance.now();
      var day = Number((document.getElementById("day-slider") || {}).value || 0);
      R.get("/api/twin/demo?t=" + day).then(function (snap) {
        cache[day] = snap;
        var el = document.getElementById("latency-metric");
        if (el) el.innerText = Math.round(performance.now() - t0) + "ms";
      }).catch(function () {});
    }, 5000);
  };
  window.stopPolling = function () {
    if (myPoll) { clearInterval(myPoll); myPoll = null; }
  };

  window.toggleJsonInspector = function () {
    var container = document.getElementById("json-inspector-container");
    var label = document.getElementById("json-toggle-label");
    if (container.classList.contains("hidden")) {
      container.classList.remove("hidden");
      label.innerText = "Hide Raw JSON";
      document.getElementById("raw-json-output").innerText = "Loading bundle...";
      R.get("/api/twin/evidence").then(function (b) {
        document.getElementById("raw-json-output").innerText = JSON.stringify(b, null, 2);
      }).catch(function (e) {
        document.getElementById("raw-json-output").innerText = "Bundle failed: " + (e.message || "error");
        if (R.isAuthError(e)) R.showAuth("evidence bundle");
      });
    } else {
      container.classList.add("hidden");
      label.innerText = "Inspect Raw JSON";
    }
  };

  window.downloadBundle = function () {
    R.get("/api/twin/evidence").then(function (b) {
      var blob = new Blob([JSON.stringify(b, null, 2)], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "rift-evidence-bundle.json";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("evidence bundle");
    });
  };

  window.riftVerify = function () {
    var s = document.getElementById("day-slider");
    window.updateReplayState(Number((s || {}).value || 0));
  };
  document.addEventListener("DOMContentLoaded", function () {
    var slider = document.getElementById("day-slider");
    if (slider) {
      slider.setAttribute("max", String(DAYS - 1));
      slider.addEventListener("input", function () { window.updateReplayState(Number(slider.value)); });
    }
    var ts = document.getElementById("timestamp-readout");
    loadAll(ts).then(function (ok) {
      if (ok) window.updateReplayState(Number((slider || {}).value || 0));
    });
    if (typeof window.updateSnapshotCount === "function") window.updateSnapshotCount();
    window.startPolling();
  });
})();

window.updateSnapshotCount = function () {
  var snapshots = [];
  try { snapshots = JSON.parse(localStorage.getItem("rift_snapshots") || "[]"); } catch (e) {}
  var el = document.getElementById("snapshot-count");
  if (el) el.innerText = snapshots.length;
};
window.openCompareModal = function () {
  var modal = document.getElementById("snapshot-modal");
  var list = document.getElementById("snapshot-slots-list");
  var snapshots = [];
  try { snapshots = JSON.parse(localStorage.getItem("rift_snapshots") || "[]"); } catch (e) {}
  if (list) {
    list.innerHTML = "";
    if (snapshots.length === 0) {
      var empty = document.createElement("div");
      empty.className = "text-center py-6 text-on-surface-variant text-xs";
      empty.textContent = "No snapshots captured yet. Use 'Capture Snapshot' to save states.";
      list.appendChild(empty);
    } else {
      snapshots.forEach(function (snap, idx) {
        var div = document.createElement("div");
        div.className = "flex justify-between items-center p-3 rounded bg-surface border border-outline-variant text-xs";
        var left = document.createElement("div");
        left.className = "flex flex-col gap-1";
        var title = document.createElement("span");
        title.className = "font-headline font-bold text-primary";
        title.textContent = snap.id + " (Day " + snap.day + ")";
        var ts = document.createElement("span");
        ts.className = "text-[10px] text-on-surface-variant font-mono";
        ts.textContent = snap.timestamp || "";
        left.appendChild(title);
        left.appendChild(ts);
        var right = document.createElement("div");
        right.className = "flex items-center gap-4";
        var risk = document.createElement("span");
        risk.className = "font-mono";
        risk.textContent = "Risk: " + (snap.risk === null || snap.risk === undefined ? "--" : snap.risk + "%");
        var badge = document.createElement("span");
        badge.className = "px-2 py-0.5 rounded text-[10px] bg-primary/20 text-primary";
        badge.textContent = snap.verdict || "";
        var del = document.createElement("button");
        del.className = "text-error hover:opacity-80";
        del.setAttribute("data-del", String(idx));
        del.textContent = "delete";
        del.addEventListener("click", function () { window.deleteSnapshot(idx); });
        right.appendChild(risk);
        right.appendChild(badge);
        right.appendChild(del);
        div.appendChild(left);
        div.appendChild(right);
        list.appendChild(div);
      });
    }
  }
  if (modal) modal.classList.remove("hidden");
};
window.closeCompareModal = function () {
  var m = document.getElementById("snapshot-modal");
  if (m) m.classList.add("hidden");
};
window.deleteSnapshot = function (index) {
  var snapshots = [];
  try { snapshots = JSON.parse(localStorage.getItem("rift_snapshots") || "[]"); } catch (e) {}
  snapshots.splice(index, 1);
  try { localStorage.setItem("rift_snapshots", JSON.stringify(snapshots)); } catch (e) {}
  window.updateSnapshotCount();
  window.openCompareModal();
};
window.clearSnapshots = function () {
  try { localStorage.removeItem("rift_snapshots"); } catch (e) {}
  window.updateSnapshotCount();
  window.openCompareModal();
};
window.toggleLivePoll = function () {
  var indicator = document.getElementById("poll-indicator");
  var stateLabel = document.getElementById("poll-state");
  var on = stateLabel && stateLabel.innerText.trim() === "ON";
  if (on) {
    if (indicator) indicator.className = "w-2 h-2 rounded-full bg-error";
    if (stateLabel) stateLabel.innerText = "OFF";
    window.stopPolling();
  } else {
    if (indicator) indicator.className = "w-2 h-2 rounded-full bg-success";
    if (stateLabel) stateLabel.innerText = "ON";
    window.startPolling();
  }
};
