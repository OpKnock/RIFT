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

function render(d) {
  $("#state").innerHTML = Object.entries(d.scenario.initial_state)
    .map(([key, value]) =>
      '<div class="finding"><span>' +
      escapeHtml(key.replaceAll("_", " ")) +
      "</span><b>" + Number(value).toFixed(1) + "</b></div>"
    ).join("");

  $("#futureCount").textContent = d.futures.length;
  $("#robustCount").textContent = d.robust.length;
  $("#bestScore").textContent = d.robust.length
    ? d.robust[0].score.toFixed(1) : "—";
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
    "</small></span><strong>" +
    item.worst_case_score.toFixed(1) + "</strong></div>"
  ).join("");

  $("#causal").innerHTML = d.causal_graph.edges.map((edge) =>
    '<div class="branch"><b>' + escapeHtml(edge.cause) +
    "</b><small>→ " + escapeHtml(edge.effect) +
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
      '</strong></div><div class="finding"><span>QAOA CVaR α=0.25</span><strong>' +
      robust.cvar_qaoa.energy.toFixed(2) +
      '</strong></div><div class="finding"><span>ASSIGNMENTS</span><small>' +
      escapeHtml(JSON.stringify(robust.classical.assignment)) + " ↔ " +
      escapeHtml(JSON.stringify(robust.qaoa.assignment)) + " ↔ " +
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
      '<div style="font-size:11px;color:var(--muted);margin-top:8px">' +
      escapeHtml(guardian.scope) + " · " +
      guardian.checks.length + " checks · " + failedChecks +
      " failed</div>";
  } else {
    $("#guardian").textContent = "NO VERIFICATION DATA";
  }
}

async function run() {
  const button = $("#run");
  button.disabled = true;
  button.textContent = "RUNNING…";
  try {
    const response = await fetch("/api/demo?" + query(), {
      headers: { Accept: "application/json" },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    render(data);
  } catch (error) {
    $("#guardian").textContent = "ENGINE ERROR · " + error.message;
  } finally {
    button.disabled = false;
    button.textContent = "RUN EXPERIMENT ↗";
  }
}

["crowd", "smoke", "capacity"].forEach((id) => {
  $("#" + id).oninput = () => {
    $("#" + id + "Out").value = $("#" + id).value;
  };
});

$("#run").onclick = run;
run();
