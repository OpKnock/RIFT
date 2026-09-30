/* Live adapter: Experiments screen -> /api/experiments/* + /api/demo.
 * Overrides Stitch's fake submit/replay/token-refresh with real calls.
 * Persistence-gated endpoints (503 without Supabase) fail honestly.
 */
(function () {
  "use strict";
  var R = window.RIFT;

  function formFields() {
    var texts = document.querySelectorAll('input[type="text"]');
    var selects = document.querySelectorAll("select");
    var nums = document.querySelectorAll('input[type="number"], input[type="num"]');
    // First text input is the search box; the create form's is the one
    // near the "Experiment Name" label — take the last text input.
    return {
      name: texts.length ? texts[texts.length - 1] : null,
      scenario: selects[0] || null,
      optimizer: selects[1] || null,
      crowd: nums[0] || null,
      smoke: nums[1] || null,
      corridor: nums[2] || null,
    };
  }
  function optText(sel) {
    if (!sel) return "";
    var o = sel.options[sel.selectedIndex];
    return o ? o.textContent.trim().toLowerCase() : "";
  }

  function expTbody() {
    var ths = document.querySelectorAll("th");
    for (var i = 0; i < ths.length; i++) {
      if (/experiment\s*name/i.test(ths[i].textContent)) {
        var tb = ths[i].closest("table");
        if (tb) return tb.querySelector("tbody");
      }
    }
    return null;
  }
  function benchTbody() {
    var ths = document.querySelectorAll("th");
    for (var i = 0; i < ths.length; i++) {
      if (/model\s*variant/i.test(ths[i].textContent)) {
        var tb = ths[i].closest("table");
        if (tb) return tb.querySelector("tbody");
      }
    }
    return null;
  }

  function loadTemplates() {
    R.get("/api/experiments/templates").then(function (body) {
      var templates = (body && body.templates) || [];
      var tb = expTbody();
      document.querySelectorAll("div,span,p").forEach(function (el) {
        if (/^Showing \d+ of \d+ experiments$/.test(el.textContent.trim())) {
          el.textContent = "Showing " + templates.length + " template(s) from the engine";
        }
      });
      if (tb) {
        tb.innerHTML = templates.length ? templates.map(function (t) {
          var spec = t.spec || {};
          var st = spec.initial_state || {};
          return '<tr class="hover:bg-surface-container/50"><td class="py-2.5 px-3 text-on-surface font-semibold">' + R.esc(t.name || t.id) + "</td>" +
            '<td class="py-2.5 px-3 text-on-surface-variant">' + R.esc(spec.optimizer || (spec.policy_variables || []).join(",") || "--") + "</td>" +
            '<td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-mono bg-primary/10 text-primary">TEMPLATE</span></td>' +
            '<td class="py-2.5 px-3 text-on-surface-variant">' + R.esc(st.corridor_capacity !== undefined ? String(st.corridor_capacity) : "--") + "</td>" +
            '<td class="py-2.5 px-3 text-on-surface-variant">' + R.esc(t.id || "") + "</td></tr>";
        }).join("") : '<tr><td class="py-2.5 px-3 text-on-surface-variant" colspan="5">No templates registered.</td></tr>';
      }
    }).catch(function (e) {
      if (R.isAuthError(e)) {
        var tb = expTbody();
        if (tb) tb.innerHTML = '<tr><td class="py-2.5 px-3 text-on-surface-variant" colspan="5">Sign in to load experiment templates.</td></tr>';
        var notice = document.getElementById("auth-notice");
        if (notice) {
          notice.style.display = "";
          notice.querySelectorAll("div,span,p").forEach(function (el) {
            if (/token expired/i.test(el.textContent) && el.children.length === 0) {
              el.textContent = "Authentication required (HTTP 401).";
            }
          });
        }
        R.showAuth("experiment templates", loadTemplates);
      }
    });
  }

  function loadBenchmarks() {
    R.get("/api/experiments/benchmarks").then(function (body) {
      var benches = (body && body.benchmarks) || [];
      var tb = benchTbody();
      if (!tb) return;
      var rows = [];
      benches.forEach(function (b) {
        (b.datasets || []).forEach(function (ds) {
          (ds.scenarios || []).forEach(function (sc) {
            rows.push({ bench: b.name || b.id, scenario: sc.name, state: sc.initial_state || {} });
          });
        });
      });
      tb.innerHTML = rows.length ? rows.map(function (r) {
        return '<tr class="hover:bg-surface-container/50"><td class="py-2.5 px-3 text-on-surface font-semibold">' + R.esc(r.bench) + "</td>" +
          '<td class="py-2.5 px-3 text-cyan-400">' + R.esc(r.scenario) + "</td>" +
          '<td class="py-2.5 px-3 text-right text-on-surface-variant font-mono text-[11px]">' + R.esc(JSON.stringify(r.state)) + "</td></tr>";
      }).join("") : '<tr><td class="py-2.5 px-3 text-on-surface-variant" colspan="3">No benchmark datasets registered.</td></tr>';
    }).catch(function () {});
  }

  window.submitExperiment = function (el) {
    var f = formFields();
    var name = f.name ? f.name.value.trim() : "";
    if (!name) { if (el) el.textContent = "Name required"; return; }
    var optimizer = optText(f.optimizer);
    if (optimizer.indexOf("qaoa") === -1 && optimizer !== "exact") optimizer = "exact";
    if (optimizer.indexOf("cvar") !== -1) optimizer = "qaoa-cvar";
    else if (optimizer.indexOf("expectation") !== -1) optimizer = "qaoa-expectation";
    if (el) { el.disabled = true; el.textContent = "Dispatching..."; }
    R.sessionInfo().catch(function () { return null; }).then(function (info) {
      return R.post("/api/experiments", {
        name: name,
        scenario_name: "smart-building-emergency",
        optimizer: optimizer,
        initial_state: {
          crowd: Number(f.crowd && f.crowd.value) || 430,
          smoke: Number(f.smoke && f.smoke.value) || 3,
          corridor_capacity: Number(f.corridor && f.corridor.value) || 520,
        },
        user_id: info && info.user_id ? info.user_id : "stitch-ui",
      });
    }).then(function (created) {
      if (el) { el.disabled = false; el.textContent = "Created: " + (created.id || created.experiment_id || "ok"); }
      loadTemplates();
    }).catch(function (e) {
      if (el) { el.disabled = false; }
      if (R.isAuthError(e)) { R.showAuth("experiment creation", function () { window.submitExperiment(el); }); if (el) el.textContent = "Sign-in required"; }
      else if (e.status === 503) { if (el) el.textContent = "Persistence unavailable (503)"; }
      else { if (el) el.textContent = "Failed: " + (e.message || ("HTTP " + e.status)); }
    });
  };

  window.refreshAuthToken = function () {
    R.showAuth("experiments", function () { loadTemplates(); loadBenchmarks(); });
  };

  window.triggerSimulationReplay = function () {
    var container = document.getElementById("replay-container");
    R.get("/api/demo?crowd=430&smoke=3&corridor_capacity=520").then(function (d) {
      var g = d.guardian || {};
      if (container) {
        container.style.borderColor = g.passed ? "#10b981" : "#f43f5e";
        var p = container.querySelector("p.font-mono");
        if (p) p.textContent = "Live replay verdict: guardian " + (g.passed ? "PASSED" : "FAILED") +
          " · " + (d.robust || []).length + " robust policies.";
      }
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("simulation replay");
    });
  };

  function hideFakePager() {
    // Static demo pagination ("4 of 42") paginates nothing real.
    var divs = document.querySelectorAll("div,span,p");
    for (var i = 0; i < divs.length; i++) {
      var el = divs[i];
      if (/^Showing \d+ of \d+/.test(el.textContent.trim()) && el.children.length === 0) {
        el.style.display = "none";
      }
      if (/^(Prev|Next)$/.test(el.textContent.trim()) && el.tagName === "BUTTON") {
        el.style.display = "none";
      }
    }
  }
  function wireFilterAndReset() {
    var input = null;
    document.querySelectorAll('input[placeholder]').forEach(function (el) {
      if (/filter experiments/i.test(el.getAttribute("placeholder") || "")) input = el;
    });
    if (input) {
      input.addEventListener("input", function () {
        var q = input.value.trim().toLowerCase();
        document.querySelectorAll("tbody tr").forEach(function (tr) {
          tr.style.display = !q || tr.textContent.toLowerCase().indexOf(q) !== -1 ? "" : "none";
        });
      });
    }
    Array.prototype.forEach.call(document.querySelectorAll("button"), function (b) {
      if (/^reset form/i.test((b.textContent || "").trim())) {
        b.addEventListener("click", function () {
          document.querySelectorAll("input[type=text],input[type=number]").forEach(function (el) {
            if (/filter/i.test(el.getAttribute("placeholder") || "")) el.value = "";
          });
          var sels = document.querySelectorAll("select");
          if (sels[0]) sels[0].selectedIndex = 0;
          if (sels[1]) sels[1].selectedIndex = 0;
        });
      }
      if (/export json/i.test((b.textContent || ""))) {
        b.addEventListener("click", function () {
          RIFT.get("/api/experiments/templates").then(function (body) {
            var blob = new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "rift-experiment-templates.json";
            document.body.appendChild(a);
            a.click();
            setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
          }).catch(function (e) {
            if (RIFT.isAuthError(e)) RIFT.showAuth("experiment templates");
          });
        });
      }
      if (/import json/i.test((b.textContent || ""))) {
        b.addEventListener("click", function () {
          var file = document.createElement("input");
          file.type = "file";
          file.accept = "application/json";
          file.addEventListener("change", function () {
            if (!file.files.length) return;
            var reader = new FileReader();
            reader.onload = function () {
              try {
                var body = JSON.parse(reader.result);
                RIFT.sessionInfo().catch(function () { return null; }).then(function (info) {
                  body.user_id = info && info.user_id ? info.user_id : "stitch-ui";
                  return RIFT.post("/api/experiments/import", body);
                }).then(function () {
                  RIFT.toast("Import accepted; templates reloaded.");
                  loadTemplates();
                }).catch(function (e2) {
                  if (RIFT.isAuthError(e2)) RIFT.showAuth("experiment import");
                  else RIFT.toast("Import failed: " + (e2.message || ("HTTP " + e2.status)));
                });
              } catch (err) {
                RIFT.toast("Import failed: file is not valid JSON.");
              }
            };
            reader.readAsText(file.files[0]);
          });
          file.click();
        });
      }
    });
  }
  window.riftVerify = function () { loadTemplates(); loadBenchmarks(); };
  document.addEventListener("DOMContentLoaded", function () {
    var notice = document.getElementById("auth-notice");
    if (notice) notice.style.display = "none";
    loadTemplates();
    loadBenchmarks();
    hideFakePager();
    wireFilterAndReset();
  });
})();

window.dismissAuthNotice = function () {
  var notice = document.getElementById("auth-notice");
  if (!notice) return;
  notice.style.opacity = "0";
  setTimeout(function () { notice.remove(); }, 300);
};
