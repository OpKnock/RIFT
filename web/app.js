const $ = (selector) => document.querySelector(selector);

function query() {
  return new URLSearchParams({
    crowd: $("#crowd").value,
    smoke: $("#smoke").value,
    corridor_capacity: $("#capacity").value,
    block_b: $("#blockB").checked ? "1" : "0",
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function showError(message) {
  const banner = $("#errorBanner");
  if (!banner) return;
  banner.hidden = false;
  banner.textContent = message;
}

function clearError() {
  const banner = $("#errorBanner");
  if (!banner) return;
  banner.hidden = true;
  banner.textContent = "";
}

function statusLine(label, info) {
  if (!info) return label + ": unknown";
  if (info.configured) return label + ": configured";
  return label + ": not configured (offline mode)";
}

async function refreshSystemStatus() {
  const sysEl = $("#sysStatus");
  const settingsEl = $("#settingsPanel");
  try {
    const [healthRes, metaRes] = await Promise.all([
      fetch("/api/health", { headers: { Accept: "application/json" } }),
      fetch("/api/meta", { headers: { Accept: "application/json" } }),
    ]);
    const health = await healthRes.json();
    const meta = metaRes.ok ? await metaRes.json() : null;
    const persist = health.persistence || {};
    const billing = health.billing || {};
    if (sysEl) {
      sysEl.innerHTML =
        "<div>engine v" + escapeHtml(health.version || "?") + " · " +
        escapeHtml(health.quantum_backend || "statevector") + "</div>" +
        "<div>" + escapeHtml(statusLine("persistence", persist)) + "</div>" +
        "<div>" + escapeHtml(statusLine("billing", billing)) + "</div>";
    }
    refreshPersistPanel(persist);
    const engine = $("#engineStatus");
    if (engine) engine.textContent = "ENGINE ONLINE · " + String(health.version || "") + " · STATEVECTOR QAOA";
    if (settingsEl) {
      if (meta) {
        settingsEl.innerHTML =
          "<div>optimizers: " + escapeHtml((meta.optimizers || []).join(", ")) + "</div>" +
          "<div>backends: " + escapeHtml((meta.backends || []).join(", ")) + "</div>" +
          "<div>max policy vars: " + escapeHtml(String(meta.limits?.max_policy_variables ?? "?")) +
          " · max perturbations: " + escapeHtml(String(meta.limits?.max_perturbations ?? "?")) + "</div>" +
          "<div>service token: " + escapeHtml(meta.auth?.service_token_configured ? "required" : "open (dev mode)") + "</div>";
      } else {
        settingsEl.textContent = "backend capabilities unavailable";
      }
    }
  } catch (error) {
    if (sysEl) sysEl.textContent = "backend status unavailable · " + error.message;
    if (settingsEl) settingsEl.textContent = "backend capabilities unavailable";
    refreshPersistPanel(null);
  }
}

let savedExperimentId = null;

function currentSpecBody() {
  return {
    name: ($("#expName") && $("#expName").value.trim()) || "lab-run",
    scenario_name: "smart-building-emergency",
    initial_state: {
      crowd: Number($("#crowd").value),
      smoke: Number($("#smoke").value),
      corridor_capacity: Number($("#capacity").value),
      blocked_b_penalty: $("#blockB").checked ? 35.0 : 0.0,
    },
    perturbations: [{ smoke: 2.0 }, { crowd: 80.0 }, { smoke: 2.0, crowd: 80.0 }, { corridor_capacity: -70.0 }],
    policy_variables: ["route_a", "route_c", "stairwell_b"],
    optimizer: ($("#expOpt") && $("#expOpt").value) || "exact",
    backend: "statevector-simulator",
  };
}

function refreshPersistPanel(persist) {
  const statusEl = $("#persistStatus");
  const saveBtn = $("#saveExp");
  const execBtn = $("#execExp");
  const online = Boolean(persist && persist.configured);
  if (statusEl) {
    statusEl.textContent = online
      ? "persistence: configured — experiments save server-side"
      : "persistence: not configured — saving is disabled until Supabase is set up on the server";
  }
  if (saveBtn) {
    saveBtn.disabled = !online;
    saveBtn.title = online ? "" : "Requires server-side Supabase configuration";
  }
  if (execBtn) {
    execBtn.disabled = !online || !savedExperimentId;
    execBtn.title = !online
      ? "Requires server-side Supabase configuration"
      : (!savedExperimentId ? "Save an experiment first" : "");
  }
}

async function saveExperiment() {
  clearError();
  const resultEl = $("#expResult");
  try {
    const response = await fetch("/api/experiments", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(currentSpecBody()),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "save failed");
    const row = Array.isArray(data) ? data[0] : data;
    savedExperimentId = (row && row.id) || null;
    if (resultEl) {
      resultEl.textContent = savedExperimentId
        ? "saved " + savedExperimentId + " · fingerprint " + String((row && row.fingerprint) || "?").slice(0, 12) + "…"
        : "saved (no id returned)";
    }
    refreshPersistPanel({ configured: true });
  } catch (error) {
    showError("SAVE FAILED · " + error.message);
  }
}

async function executeSaved() {
  clearError();
  const resultEl = $("#expResult");
  if (!savedExperimentId) {
    showError("NOTHING TO EXECUTE · save an experiment first");
    return;
  }
  try {
    const response = await fetch("/api/experiments/" + encodeURIComponent(savedExperimentId) + "/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: "{}",
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "execute failed");
    const record = data.result || {};
    const guardian = record.guardian || {};
    if (resultEl) {
      resultEl.textContent =
        "run " + String(data.id || "?") + " · policy " + JSON.stringify(record.assignment || {}) +
        " · robust " + Number(record.robust_cost ?? NaN).toFixed(1) +
        " · " + (record.feasible ? "feasible" : "infeasible") +
        " · guardian " + (guardian.passed ? "PASS" : "REJECT");
    }
  } catch (error) {
    showError("EXECUTE FAILED · " + error.message);
  }
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem("rift-history") || "[]");
  } catch (error) {
    return [];
  }
}

function saveHistoryEntry(entry) {
  try {
    const history = loadHistory();
    history.unshift(entry);
    localStorage.setItem("rift-history", JSON.stringify(history.slice(0, 10)));
  } catch (error) {
    /* storage full or unavailable: history is best-effort */
  }
  renderHistory();
}

function renderHistory() {
  const el = $("#historyList");
  if (!el) return;
  const history = loadHistory();
  if (!history.length) {
    el.innerHTML = '<span class="muted">No runs yet. Each successful experiment is stored locally for reopen.</span>';
    return;
  }
  el.innerHTML = history.map((item, index) =>
    '<div class="branch"><b>RUN ' + String(history.length - index).padStart(2, "0") +
    "</b><small>" + escapeHtml(item.when) + " · best " + escapeHtml(String(item.best)) +
    '</small><small><button data-history="' + index + '" type="button">REOPEN</button></small></div>'
  ).join("");
  el.querySelectorAll("[data-history]").forEach((button) => {
    button.onclick = () => {
      const item = loadHistory()[Number(button.getAttribute("data-history"))];
      if (item && item.snapshot) render(item.snapshot, { fromHistory: true });
    };
  });
}

function render(d, options) {
  clearError();
  $("#state").innerHTML = Object.entries(d.scenario.initial_state)
    .map(([key, value]) =>
      '<div class="finding"><span>' +
      escapeHtml(key.replaceAll("_", " ")) +
      "</span><b>" + Number(value).toFixed(1) + "</b></div>"
    ).join("");

  $("#futureCount").textContent = d.futures.length;
  $("#robustCount").textContent = d.robust.length;
  $("#bestScore").textContent = d.robust.length
    ? d.robust[0].score.toFixed(1) : "-";
  $("#latticeState").textContent =
    "EXPLORED · H=" + Number(d.uncertainty?.risk_entropy || 0).toFixed(2);

  $("#branches").innerHTML = d.future_tree.map((future, index) =>
    '<div class="branch"><b>BRANCH ' +
    String(index + 1).padStart(2, "0") +
    "</b><small>" + escapeHtml(JSON.stringify(future.policy)) +
    '</small><small>objective <strong>' + future.score.toFixed(1) +
    '</strong> · <span class="' + (future.valid ? "valid" : "invalid") +
    '">' + (future.valid ? "GUARDIAN PASS" : "GUARDIAN REJECT") +
    "</span></small></div>"
  ).join("");

  $("#chaos").innerHTML = d.robust.slice(0, 4).map((item) =>
    '<div class="finding"><span>' +
    escapeHtml(JSON.stringify(item.policy)) +
    "<br><small>perturbation " +
    escapeHtml(JSON.stringify(item.worst_perturbation)) +
    (item.feasible_under_all ? "" : "<br><strong>REJECTED UNDER PERTURBATION</strong>") +
    "</small></span><strong>" +
    item.worst_case_score.toFixed(1) + "</strong></div>"
  ).join("");

  $("#causal").innerHTML = d.causal_graph.edges.map((edge) =>
    '<div class="branch"><b>' + escapeHtml(edge.cause) +
    "</b><small>-> " + escapeHtml(edge.effect) +
    '</small><small>strength ' + Number(edge.strength).toFixed(2) +
    "</small></div>"
  ).join("");

  const values = d.futures.map((item) => item.score);
  const max = Math.max(...values);
  const min = Math.min(...values);
  $("#bars").innerHTML = values.map((value) =>
    '<div class="bar" style="height:' +
    (30 + 70 * (max - value) / Math.max(max - min, 1)) +
    '%"><span>' + value.toFixed(0) + "</span></div>"
  ).join("");

  const robust = d.robust_optimization;
  $("#robustQubo").innerHTML = robust
    ? '<div class="finding"><span>CLASSICAL ROBUST</span><strong>' +
      robust.classical.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>QAOA EXPECTATION</span><strong>' +
      robust.qaoa.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>QAOA CVaR a=0.25</span><strong>' +
      robust.cvar_qaoa.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>ASSIGNMENTS</span><small>' +
      escapeHtml(JSON.stringify(robust.classical.assignment)) + " | " +
      escapeHtml(JSON.stringify(robust.qaoa.assignment)) + " | " +
      escapeHtml(JSON.stringify(robust.cvar_qaoa.assignment)) +
      "</small></div>"
    : "";

  $("#benchmark").innerHTML = d.benchmark.map((item) =>
    '<div class="finding"><span>' + escapeHtml(item.method) +
    "<br><small>" + escapeHtml(item.note) +
    '</small></span><strong>' + item.energy.toFixed(2) +
    " · " + item.runtime_ms.toFixed(2) + "ms</strong></div>"
  ).join("");

  const qaoa = d.benchmark.find(
    (item) => item.method === "qaoa-statevector-simulator"
  );
  $("#qaoaMeta").textContent = qaoa
    ? "p=1 · expected energy " + qaoa.expected_energy.toFixed(2) +
      " · probability " + (qaoa.probability * 100).toFixed(1) + "%"
    : "";

  if (d.multivariable) {
    const multi = d.multivariable;
    $("#multiPolicy").innerHTML =
      '<div class="finding"><span>EXACT ROBUST</span><strong>' +
      multi.exact.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>CVaR-QAOA / QUADRATIC PROJECTION</span><strong>' +
      multi.qaoa_projection.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>PROJECTION MAX GAP</span><strong>' +
      multi.projection_error.max_absolute_gap.toFixed(2) +
      '</strong></div><div class="finding"><span>SEARCH SPACE</span><small>' +
      multi.policy_count + " binary policies · " +
      escapeHtml(multi.variables.join(", ")) +
      "</small></div>" +
      multi.top_policies.map((policy, index) =>
        '<div class="branch"><b>#' + (index + 1) +
        "</b><small>" + escapeHtml(JSON.stringify(policy.assignment)) +
        " · robust " + policy.robust_cost.toFixed(1) +
        " · nominal " + policy.nominal_cost.toFixed(1) +
        " · " + (policy.feasible ? "feasible" : "rejected") +
        "</small></div>"
      ).join("");
  }

  const guardian = d.guardian;
  if (guardian) {
    const passed = guardian.passed;
    const failedChecks = guardian.checks.filter((check) => !check.passed).length;
    $("#guardian").innerHTML =
      '<span class="' + (passed ? "valid" : "invalid") + '">' +
      (passed ? "PASS" : "REJECT") + "</span> · " +
      escapeHtml(JSON.stringify(guardian.policy)) +
      '<div style="font-size:11px;margin-top:8px">' +
      escapeHtml(guardian.scope) + " · " +
      guardian.checks.length + " checks · " + failedChecks +
      " failed</div>";
  } else {
    $("#guardian").textContent = "NO VERIFICATION DATA";
  }

  const repro = d.reproducibility;
  const reproEl = $("#reproMeta");
  if (reproEl && repro) {
    reproEl.textContent =
      "engine v" + repro.engine_version + " · " + repro.backend +
      " · " + repro.policy_variables.length + " policy vars · deterministic demo";
  }

  if (!options?.fromHistory) {
    saveHistoryEntry({
      when: new Date().toISOString(),
      best: d.robust.length ? Number(d.robust[0].score.toFixed(1)) : null,
      snapshot: d,
    });
  }
}

async function run() {
  const button = $("#run");
  button.disabled = true;
  button.textContent = "RUNNING...";
  try {
    const response = await fetch("/api/demo?" + query(), {
      headers: { Accept: "application/json" },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || "Request failed");
    render(data);
  } catch (error) {
    showError("ENGINE ERROR · " + error.message);
    const guardian = $("#guardian");
    if (guardian) guardian.textContent = "ENGINE ERROR · " + error.message;
  } finally {
    button.disabled = false;
    button.textContent = "RUN EXPERIMENT";
  }
}

["crowd", "smoke", "capacity"].forEach((id) => {
  $("#" + id).oninput = () => {
    $("#" + id + "Out").value = $("#" + id).value;
  };
});

$("#run").onclick = run;
const saveBtn = $("#saveExp");
if (saveBtn) saveBtn.onclick = saveExperiment;
const execBtn = $("#execExp");
if (execBtn) execBtn.onclick = executeSaved;
refreshSystemStatus();
renderHistory();
run();
