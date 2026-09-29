/* Live adapter: Scenarios screen -> GET /api/meta.
 * Rebuilds the bounds table and optimizer list from the real engine
 * metadata. The builder form has no engine endpoint behind it, so
 * submitting says so honestly instead of faking a POST.
 */
(function () {
  "use strict";
  var R = window.RIFT;

  function boundsTbody() {
    var ths = document.querySelectorAll("th");
    for (var i = 0; i < ths.length; i++) {
      if (/variable\s*name/i.test(ths[i].textContent)) {
        var tb = ths[i].closest("table");
        if (tb) return tb.querySelector("tbody");
      }
    }
    return null;
  }

  window.handleScenarioSubmit = function (e) {
    if (e) e.preventDefault();
    var modal = document.getElementById("scenario-builder-modal");
    var note = document.getElementById("rift-builder-note");
    if (!note && modal) {
      note = document.createElement("p");
      note.id = "rift-builder-note";
      note.className = "text-xs text-amber-300";
      var form = modal.querySelector("form");
      if (form) form.appendChild(note);
    }
    if (note) note.textContent = "Not submitted: the engine exposes no scenario-create endpoint. Only the built-in scenario exists (see banner).";
  };

  document.addEventListener("DOMContentLoaded", function () {
    R.get("/api/meta").then(function (meta) {
      var bounds = ((meta.limits || {}).scenario_bounds) || {};
      var names = Object.keys(bounds);
      var tb = boundsTbody();
      if (tb && names.length) {
        tb.innerHTML = names.map(function (name) {
          var b = bounds[name] || [0, 0];
          return '<tr class="hover:bg-surface-container/50 transition-colors">' +
            '<td class="py-3.5 px-4 font-mono font-medium text-white">' + R.esc(name) + "</td>" +
            '<td class="py-3.5 px-4 font-mono text-on-surface-variant">' + R.esc(String(b[0])) + "</td>" +
            '<td class="py-3.5 px-4 font-mono text-on-surface-variant">' + R.esc(String(b[1])) + "</td>" +
            '<td class="py-3.5 px-4 font-mono text-xs text-on-surface-variant">[' + R.esc(String(b[0])) + ", " + R.esc(String(b[1])) + "]</td></tr>";
        }).join("");
      }
      // "N Parameters Configured" badge.
      var badges = document.querySelectorAll("span");
      badges.forEach(function (s) {
        if (/Parameters Configured/.test(s.textContent)) {
          s.textContent = names.length + " Parameters Configured";
        }
        if (/MESH_ID/.test(s.textContent) || (/SMART-BUILDING-EMERGENCY \/\//.test(s.textContent))) {
          s.textContent = "SMART-BUILDING-EMERGENCY // ENGINE v" +
            String(meta.engine_version || "?").replace(/^v/, "");
        }
      });
      // Optimizer list.
      var opts = meta.optimizers || [];
      var cards = document.querySelectorAll("div.space-y-2\\.5");
      if (!cards.length) {
        var all = document.querySelectorAll("div.space-y-2");
        for (var i = 0; i < all.length; i++) {
          if (/QAOA-CVaR/.test(all[i].textContent) && /exact/.test(all[i].textContent)) { cards = [all[i]]; break; }
        }
      }
      if (cards.length && opts.length) {
        cards[0].innerHTML = opts.map(function (o, i) {
          var tag = i === 0
            ? '<span class="text-[10px] uppercase font-label tracking-wider px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">Available</span>'
            : '<span class="text-[10px] uppercase font-label tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant">Available</span>';
          return '<div class="p-3 rounded-lg bg-surface-container border border-outline-variant flex items-center justify-between">' +
            '<div class="flex items-center gap-2.5"><span class="w-2 h-2 rounded-full bg-primary"></span>' +
            '<span class="font-mono text-sm text-white font-medium">' + R.esc(o) + "</span></div>" + tag + "</div>";
        }).join("");
      }
      var backs = (meta.backends || []).join(", ");
      if (backs) {
        var ps = document.querySelectorAll("p");
        ps.forEach(function (p) {
          if (/Compatible execution backends/.test(p.textContent)) {
            p.textContent = "Compatible execution backends: " + backs + ".";
          }
        });
      }
    }).catch(function (e) {
      if (R.isAuthError(e)) R.showAuth("scenario metadata", function () { window.location.reload(); });
    });
  });
})();

window.toggleScenarioBuilder = function () {
  var m = document.getElementById("scenario-builder-modal");
  if (m) m.classList.toggle("hidden");
};
