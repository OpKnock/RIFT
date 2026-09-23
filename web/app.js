const $ = (selector) => document.querySelector(selector);

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

function finding(label, value) {
  return '<div class="finding"><span>' + escapeHtml(label) +
    "</span><b>" + escapeHtml(value) + "</b></div>";
}

function policyKey(policy) {
  const parts = [];
  if (policy.sleep_plus) parts.push("sleep");
  if (policy.exertion_cut) parts.push("cut");
  return parts.length ? parts.join("+") : "none";
}

function selectedPolicyPath(data) {
  const want = ($("#policy") && $("#policy").value) || "none";
  const match = (data.trajectories || []).find((t) => policyKey(t.policy) === want)
    || (data.trajectories || [])[0];
  return match;
}

function renderTrajectories(data) {
  const el = $("#trajectories");
  const trajs = data.trajectories || [];
  if (!trajs.length) { el.innerHTML = '<span class="muted">No trajectories.</span>'; return; }
  const W = 640, H = 180, PAD = 28;
  const maxRisk = 1.0;
  const x = (day) => PAD + (day / 3) * (W - 2 * PAD);
  const y = (risk) => H - PAD - (risk / maxRisk) * (H - 2 * PAD);
  const colors = { none: "#b8ff5a", sleep: "#7dd7ff", cut: "#ffbd55", "sleep+cut": "#c792ff" };
  let svg = '<svg viewBox="0 0 ' + W + " " + H + '" style="width:100%;height:auto" role="img" aria-label="Future risk trajectories per policy">';
  svg += '<line x1="' + PAD + '" y1="' + y(0.6) + '" x2="' + (W - PAD) + '" y2="' + y(0.6) + '" stroke="#ff6472" stroke-dasharray="5,4" stroke-width="1"/>';
  svg += '<text x="' + (W - PAD) + '" y="' + (y(0.6) - 5) + '" fill="#ff6472" font-size="10" text-anchor="end">high-strain 0.60</text>';
  trajs.forEach((t) => {
    const key = policyKey(t.policy);
    const color = colors[key] || "#f2f4f7";
    const pts = t.path.map((p) => x(p.day).toFixed(1) + "," + y(p.risk).toFixed(1)).join(" ");
    const active = (($("#policy") && $("#policy").value) || "none") === key;
    svg += '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="' + (active ? 3 : 1.5) + '" opacity="' + (active ? 1 : 0.75) + '"/>';
    t.path.forEach((p) => {
      const hot = p.risk >= 0.6;
      svg += '<circle cx="' + x(p.day).toFixed(1) + '" cy="' + y(p.risk).toFixed(1) + '" r="' + (hot ? 4.5 : 3) + '" fill="' + (hot ? "#ff6472" : color) + '"/>';
    });
    const last = t.path[t.path.length - 1];
    svg += '<text x="' + (x(last.day) + 6) + '" y="' + (y(last.risk) + 3) + '" fill="' + color + '" font-size="10">' + escapeHtml(key) + " " + last.risk.toFixed(2) + "</text>";
  });
  svg += "</svg>";
  el.innerHTML = svg;
}

function render(d) {
  clearError();
  const ehr = d.ehr || {};
  $("#patientLine").textContent =
    "Demo patient " + (ehr.patient_id || "?") + " · age " + (ehr.age ?? "?") +
    " · " + (ehr.conditions || []).join(", ") + " · meds: " + (ehr.medications || []).join(", ");
  $("#engineStatus").textContent = "TWIN SYNCED · DAY " + d.day_index + " · ENGINE v" + ((d.meta && d.meta.engine_version) || "?");
  $("#engineMeta").textContent = "engine v" + ((d.meta && d.meta.engine_version) || "?");

  $("#patient").innerHTML =
    finding("patient", ehr.patient_id || "?") +
    finding("age", String(ehr.age ?? "?")) +
    finding("conditions", (ehr.conditions || []).join(", ") || "—") +
    finding("medications", (ehr.medications || []).join(", ") || "—") +
    finding("clinic resting HR", String(ehr.resting_hr_clinic ?? "?")) +
    finding("systolic BP", String(ehr.systolic_bp ?? "?"));

  const risk = d.risk || {};
  $("#riskValue").textContent = Number(risk.risk ?? NaN).toFixed(2);
  $("#riskValue").style.color = risk.event_predicted ? "var(--danger)" : "var(--accent)";
  $("#riskLabel").textContent = "high-strain-day risk · 24h" + (risk.event_predicted ? " · EVENT PREDICTED" : "");
  const iv = risk.interval || [0, 0];
  $("#riskInterval").textContent = Number(iv[0]).toFixed(2) + "–" + Number(iv[1]).toFixed(2);
  $("#riskQuality").textContent = Number(risk.input_quality ?? 0).toFixed(2);
  const calibEl = $("#riskCalib");
  if (calibEl) calibEl.textContent = String(risk.calibration || "unknown").toUpperCase();

  const st = d.state || {};
  $("#twinDay").textContent = "DAY " + d.day_index;
  $("#twinState").innerHTML =
    finding("resting HR", st.resting_hr == null ? "missing" : Number(st.resting_hr).toFixed(0) + " bpm") +
    finding("HRV", st.hrv_rmssd == null ? "missing" : Number(st.hrv_rmssd).toFixed(0) + " ms") +
    finding("sleep", st.sleep_hours == null ? "missing" : Number(st.sleep_hours).toFixed(1) + " h") +
    finding("activity", st.activity_load == null ? "missing" : Number(st.activity_load).toFixed(0)) +
    finding("data quality", Number(st.data_quality ?? 0).toFixed(2)) +
    finding("stale", String(st.stale_days ?? 0) + " d");

  $("#baseline").innerHTML = (d.deviations || []).map((v) =>
    '<div class="finding"><span>' + escapeHtml(String(v.field).replaceAll("_", " ")) +
    "<br><small>baseline " + escapeHtml(String(v.baseline ?? "?")) +
    "</small></span><strong>" + (v.delta == null ? "unknown" : (v.delta > 0 ? "+" : "") + Number(v.delta).toFixed(1) + " " + v.direction) +
    "</strong></div>"
  ).join("");

  renderTrajectories(d);

  $("#reasons").innerHTML = (d.reasons || []).map((r) =>
    '<div class="branch"><small>' + escapeHtml(r) + "</small></div>"
  ).join("");

  const sel = selectedPolicyPath(d);
  const fut = (d.futures && d.futures.robust_ranking) || [];
  $("#whatif").innerHTML = fut.map((f) =>
    '<div class="finding"><span>' + escapeHtml(policyKey(f.policy)) +
    "<br><small>worst " + Number(f.worst_case_risk).toFixed(2) +
    (f.feasible_under_all ? "" : " · REJECTED UNDER VARIATION") +
    "</small></span><strong>" + Number(f.nominal_risk).toFixed(2) + "</strong></div>"
  ).join("") + (sel ? '<div class="formula">selected path ends at risk ' +
    Number(sel.path[sel.path.length - 1].risk).toFixed(2) + "</div>" : "");

  const rob = d.robustness || {};
  $("#robustness").innerHTML =
    finding("worst-case spread", Number(rob.worst_case_spread ?? 0).toFixed(3)) +
    '<div class="formula">perturbations: sensor noise, stale/missing data, parameter variation</div>';

  const g = d.guardian || {};
  const passed = g.display_allowed;
  $("#guardian").innerHTML =
    '<span class="' + (passed ? "valid" : "invalid") + '">' +
    (passed ? "DISPLAYABLE" : "WITHHELD") + "</span>" +
    '<div style="font-size:11px;margin-top:8px">' +
    ((g.flags || []).map(escapeHtml).join("<br>") || "no warnings") +
    ((g.rejections || []).length ? "<br>" + (g.rejections || []).map(escapeHtml).join("<br>") : "") +
    "</div>";
}

async function loadEvidence() {
  const el = $("#evidence");
  if (!el) return;
  try {
    const response = await fetch("/api/twin/evidence", { headers: { Accept: "application/json" } });
    const ev = await response.json();
    if (!response.ok) throw new Error(ev.error || "Request failed");
    const fmt = (v) => (v == null ? "—" : Number(v).toFixed(2));
    el.innerHTML =
      "<div>agreement " + fmt(ev.event_agreement) + " · Brier " + fmt(ev.brier) +
      " · coverage " + fmt(ev.interval_coverage) + "</div>" +
      "<div>sensitivity " + fmt(ev.sensitivity) + " · specificity " + fmt(ev.specificity) +
      " · mean onset lag " + escapeHtml(String(ev.mean_onset_lag ?? "—")) + " d</div>" +
      "<div>" + escapeHtml(String(ev.days_evaluated)) + " held-out days · labels: " +
      escapeHtml(String(ev.outcome_rule || "?")) + "</div>";
  } catch (error) {
    el.textContent = "evidence unavailable · " + error.message;
  }
}

async function run() {
  const button = $("#run");
  button.disabled = true;
  button.textContent = "SYNCING…";
  try {
    const day = ($("#day") && $("#day").value) || "13";
    const response = await fetch("/api/twin/demo?t=" + encodeURIComponent(day), {
      headers: { Accept: "application/json" },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || "Request failed");
    render(data);
  } catch (error) {
    showError("TWIN ERROR · " + error.message);
    const guardian = $("#guardian");
    if (guardian) guardian.textContent = "TWIN ERROR · " + error.message;
  } finally {
    button.disabled = false;
    button.textContent = "SYNC TWIN";
  }
}

["day"].forEach((id) => {
  const el = $("#" + id);
  if (el) {
    el.oninput = () => { $("#" + id + "Out").value = el.value; };
    el.onchange = run;
  }
});
const policyEl = $("#policy");
if (policyEl) policyEl.onchange = run;

$("#run").onclick = run;
loadEvidence();
run();
