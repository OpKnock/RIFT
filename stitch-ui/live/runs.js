/* Live adapter: Runs screen -> GET /api/ops/monitor (poll 5s).
 * Replaces Stitch's static demo numbers with real telemetry.
 * Same elements and styling; data only. Honors pause toggle.
 */
(function () {
  "use strict";
  var R = window.RIFT;
  var paused = false;
  var timer = null;
  var lastOk = 0;

  function $(id) { return document.getElementById(id); }

  function findCardValue(labelText) {
    var spans = document.querySelectorAll("span.text-xs.font-label, span.font-label");
    for (var i = 0; i < spans.length; i++) {
      if (spans[i].textContent.trim().toLowerCase() === labelText.toLowerCase()) {
        var card = spans[i].closest("div.bg-surface-container");
        if (!card) continue;
        var val = card.querySelector("div.text-2xl");
        if (val) return val;
      }
    }
    return null;
  }

  function findSectionList(headingText) {
    var want = headingText.toLowerCase();
    var hs = document.querySelectorAll("h1,h2,h3,h4");
    for (var i = 0; i < hs.length; i++) {
      if (hs[i].textContent.trim().toLowerCase().indexOf(want) === -1) continue;
      var node = hs[i].parentElement;
      while (node && node !== document.body) {
        var list = node.querySelector("div.divide-y");
        if (list) return list;
        node = node.parentElement;
      }
    }
    return null;
  }
  function clearToSignIn() {
    ["Total Request Volume", "Failure Rate (Global)", "p95 Latency"].forEach(function (label) {
      var el = findCardValue(label);
      if (el) el.textContent = "--";
    });
    var list = findSectionList("Alert Rules");
    if (list) list.innerHTML = '<div class="p-3.5 text-xs text-on-surface-variant">Sign in to load alert rules.</div>';
    var tbody = findRoutesTbody();
    if (tbody) tbody.innerHTML = '<tr><td class="py-3 px-4 text-xs text-on-surface-variant" colspan="7">Sign in to load per-route traffic.</td></tr>';
  }

  function findRoutesTbody() {
    var ths = document.querySelectorAll("th");
    for (var i = 0; i < ths.length; i++) {
      if (/route\s*path/i.test(ths[i].textContent)) {
        var table = ths[i].closest("table");
        if (table) return table.querySelector("tbody");
      }
    }
    return null;
  }

  function badge(text, ok) {
    var cls = ok
      ? "bg-emerald-500/20 text-emerald-400"
      : "bg-rose-500/20 text-rose-400 font-bold";
    return '<span class="px-2 py-0.5 rounded text-[10px] font-mono ' + cls + '">' + R.esc(text) + "</span>";
  }

  function setTrend(label, text) {
    var want = label.toLowerCase();
    var spans = document.querySelectorAll("span");
    for (var i = 0; i < spans.length; i++) {
      if (spans[i].textContent.trim().toLowerCase() !== want) continue;
      var card = spans[i].closest("div.bg-surface-container");
      if (!card) continue;
      var val = card.querySelector("div.text-2xl");
      if (!val) continue;
      var trend = val.nextElementSibling;
      if (trend) {
        trend.innerHTML = "";
        var s = document.createElement("span");
        s.className = "text-xs text-on-surface-variant";
        s.textContent = text;
        trend.appendChild(s);
      }
      return;
    }
  }

  function render(snapshot) {
    var monitor = snapshot.monitor || {};
    var alerts = snapshot.alerts || [];
    var routes = monitor.routes || {};

    // Metric cards.
    var total = monitor.requests_total || 0;
    var fails = 0, p95max = 0;
    Object.keys(routes).forEach(function (r) {
      var s = routes[r] || {};
      fails += s.failures || 0;
      if (typeof s.p95_ms === "number" && s.p95_ms > p95max) p95max = s.p95_ms;
    });
    var failRate = total > 0 ? (100 * fails / total) : 0;
    var firing = alerts.filter(function (a) { return a.firing; }).length;
    function set(label, text) {
      var el = findCardValue(label);
      if (el) el.textContent = text;
    }
    set("Total Request Volume", String(total));
    set("Failure Rate (Global)", R.num(failRate, 3) + "%");
    set("p95 Latency", R.num(p95max, 1) + "ms");
    setTrend("Total Request Volume", "live total, this server process");
    setTrend("Failure Rate (Global)", "across " + total + " request(s)");
    setTrend("p95 Latency", "max across routes");
    var firingEl = findCardValue("Alert Evaluation Engine");
    if (!firingEl) {
      // Fourth card shows "N / M" — find by label then value.
      var spans = document.querySelectorAll("span.text-xs.font-label, span.font-label");
      for (var i = 0; i < spans.length; i++) {
        if (/alert/i.test(spans[i].textContent)) {
          var card = spans[i].closest("div.bg-surface-container");
          if (card) firingEl = card.querySelector("div.text-2xl");
        }
      }
    }
    if (firingEl) {
      firingEl.textContent = firing + " / " + alerts.length;
      var fcard = firingEl.closest("div.bg-surface-container");
      var sub = fcard ? fcard.querySelector("div.flex.items-center.gap-2, div.flex.items-center.gap-1") : null;
      if (sub) {
        sub.innerHTML = "";
        var a = document.createElement("span");
        a.className = "text-xs font-medium";
        a.style.color = firing ? "#f87171" : "#34d399";
        a.textContent = firing + " firing";
        var b = document.createElement("span");
        b.className = "text-xs text-on-surface-variant";
        b.textContent = "· " + (alerts.length - firing) + " ok";
        sub.appendChild(a);
        sub.appendChild(document.createTextNode(" "));
        sub.appendChild(b);
      }
    }

    // Alerts list.
    var list = findSectionList("Alert Rules Evaluation Matrix");
    if (list) {
      if (alerts.length === 0) {
        list.innerHTML = '<div class="p-3.5 text-xs text-on-surface-variant">No alert rules evaluated.</div>';
      } else {
        list.innerHTML = alerts.map(function (a) {
          return '<div class="p-3.5 flex items-center justify-between hover:bg-surface-container-high/50 transition-colors">' +
            '<div class="flex flex-col gap-0.5"><span class="text-xs font-semibold text-on-surface font-mono">' + R.esc(a.rule) + '</span>' +
            '<span class="text-[10px] text-on-surface-variant">' + R.esc(a.reason || "") + "</span></div>" +
            '<div class="flex flex-col items-end gap-1">' + badge(a.firing ? "FIRING" : "OK", !a.firing) + "</div></div>";
        }).join("");
      }
    }

    // Routes table.
    var tbody = findRoutesTbody();
    if (tbody) {
      var names = Object.keys(routes);
      if (names.length === 0) {
        tbody.innerHTML = '<tr><td class="py-3 px-4 text-xs text-on-surface-variant" colspan="7">No requests recorded yet in this server process.</td></tr>';
      } else {
        tbody.innerHTML = names.map(function (name) {
          var s = routes[name] || {};
          var req = s.requests || 0, fl = s.failures || 0;
          var pct = req > 0 ? (100 * fl / req) : 0;
          var degraded = pct >= 1;
          return '<tr class="hover:bg-surface-container-high/50 transition-colors" data-route="' + R.esc(name.toLowerCase()) + '">' +
            '<td class="py-3 px-4 text-primary font-medium">' + R.esc(name) + "</td>" +
            '<td class="py-3 px-3 text-on-surface">' + req + "</td>" +
            '<td class="py-3 px-3 text-on-surface">' + fl + "</td>" +
            '<td class="py-3 px-3 ' + (degraded ? "text-amber-400" : "text-emerald-400") + '">' + R.num(pct, 3) + "%</td>" +
            '<td class="py-3 px-3 text-on-surface">' + R.num(s.p50_ms, 1) + "ms</td>" +
            '<td class="py-3 px-3 text-on-surface">' + R.num(s.p95_ms, 1) + "ms</td>" +
            '<td class="py-3 px-3">' + badge(degraded ? "Degraded" : "Healthy", !degraded) + "</td></tr>";
        }).join("");
      }
      applyFilter();
    }

    lastOk = Date.now();
    var auth = $("auth-alert-card");
    if (auth) auth.style.display = "none";
  }

  function applyFilter() {
    var input = document.querySelector('input[placeholder="Filter routes..."]');
    var q = input ? input.value.trim().toLowerCase() : "";
    document.querySelectorAll("tbody tr[data-route]").forEach(function (tr) {
      tr.style.display = !q || tr.getAttribute("data-route").indexOf(q) !== -1 ? "" : "none";
    });
  }

  async function poll(manual) {
    if (paused && !manual) return;
    try {
      var snapshot = await R.get("/api/ops/monitor");
      render(snapshot);
    } catch (e) {
      if (R.isAuthError(e)) {
        clearToSignIn();
        var auth = $("auth-alert-card");
        if (auth) auth.style.display = "";
        R.showAuth("operations telemetry", function () { poll(true); });
      } else {
        var t = $("poll-text");
        if (t) t.textContent = "Error: " + (e.message || "request failed");
      }
    }
  }

  // Real behavior for Stitch's buttons (replaces simulated versions).
  window.togglePolling = function () {
    paused = !paused;
    var btn = $("poll-toggle-btn"), dot = $("poll-dot"),
        ping = $("poll-ping"), text = $("poll-text");
    if (!paused) {
      if (btn) btn.innerText = "Pause";
      if (dot) dot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500";
      if (ping) ping.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75";
      if (text) text.innerText = "Polling Active (5s)";
      poll(true);
    } else {
      if (btn) btn.innerText = "Resume";
      if (dot) dot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500";
      if (ping) ping.className = "hidden";
      if (text) text.innerText = "Polling Paused";
    }
  };
  window.simulateRetry = function () { poll(true); };

  document.addEventListener("DOMContentLoaded", function () {
    var input = document.querySelector('input[placeholder="Filter routes..."]');
    if (input) input.addEventListener("input", applyFilter);
    setInterval(function () {
      var el = $("sync-timer");
      if (el) el.innerText = lastOk ? Math.max(0, Math.round((Date.now() - lastOk) / 1000)) + "s" : "--";
    }, 1000);
    poll(true);
    timer = setInterval(function () { poll(false); }, 5000);
  });
})();
