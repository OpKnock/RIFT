/* Loads the coronary viewer with a graceful data-only fallback if the Three.js CDN is blocked. */
(async function () {
  try {
    await import("./coronary.js");
    return;
  } catch (err) {
    console.warn("RIFT 3D module could not load; enabling data-only viewer.", err);
  }

  const fallback = document.getElementById("coronary-fallback");
  const canvas = document.getElementById("coronary-canvas");
  if (canvas) canvas.style.display = "none";
  if (fallback) {
    fallback.style.display = "flex";
    fallback.textContent = "3D rendering could not load (WebGL or a required module is unavailable). Demo-patient probabilities and explanation details are still available.";
  }

  const names = { cad: "CAD overall", lad: "LAD stenosis", lcx: "LCX stenosis", rca: "RCA stenosis" };
  const switcher = document.getElementById("patient-switch");
  const nameEl = document.getElementById("patient-name");
  const descEl = document.getElementById("patient-desc");
  const barsEl = document.getElementById("prob-bars");
  const whatIfEl = document.getElementById("whatif-panel");
  const metaEl = document.getElementById("patient-meta");
  function renderPatient(p, buttons) {
    nameEl.textContent = p.slug.replace(/-/g, " ") + " (test row " + p.test_row + ")";
    const d = p.display || {};
    descEl.textContent = "Age " + (d.Age ?? "—") + " · Sex " + (d.Sex ?? "—") +
      " · Chest pain " + (d["Typical Chest Pain"] ?? "—") + " · HTN " + (d.HTN ?? "—");
    const scores = p.calibrated_probabilities || {};
    barsEl.replaceChildren();
    for (const key of ["cad", "lad", "lcx", "rca"]) {
      const raw = Number(scores[key]);
      const probability = Number.isFinite(raw) ? Math.max(0, Math.min(1, raw)) : null;
      const row = document.createElement("div");
      row.className = "mb-3";
      const label = document.createElement("div");
      label.className = "flex justify-between text-xs mb-1";
      const labelText = document.createElement("span");
      labelText.className = "font-label uppercase tracking-wider";
      labelText.textContent = names[key];
      const value = document.createElement("strong");
      value.textContent = probability === null ? "Unavailable" : probability.toFixed(3);
      label.append(labelText, value);
      const track = document.createElement("div");
      track.className = "h-2 rounded-full bg-surface-container-high overflow-hidden";
      const fill = document.createElement("div");
      fill.className = "h-2 rounded-full bg-primary";
      fill.style.width = probability === null ? "0%" : (probability * 100) + "%";
      track.appendChild(fill);
      row.append(label, track);
      barsEl.appendChild(row);
    }
    const flips = p.counterfactuals || {};
    whatIfEl.replaceChildren();
    for (const key of ["lad", "lcx", "rca"]) {
      const group = document.createElement("div");
      group.className = "mb-3";
      const heading = document.createElement("div");
      heading.className = "font-label uppercase tracking-wider text-on-surface-variant mb-1";
      heading.textContent = names[key] + " — explanation";
      group.appendChild(heading);
      const list = Array.isArray(flips[key]) ? flips[key] : [];
      const text = document.createElement("div");
      text.className = "text-on-surface-variant";
      text.textContent = list.length
        ? list.slice(0, 3).map(f => String(f.feature) + ": " + String(f.from) + " → " + String(f.to) +
            " (P " + Number(f.prob_after).toFixed(3) + ")").join(" · ")
        : "No single observed-value change flips this prediction.";
      group.appendChild(text);
      whatIfEl.appendChild(group);
    }
    metaEl.textContent = "Research demo data · probabilities are model outputs, not medical advice.";
    buttons.forEach(btn => {
      const active = btn.dataset.slug === p.slug;
      btn.setAttribute("aria-selected", String(active));
      btn.className = "px-3 py-1.5 rounded-lg text-xs font-label border transition-colors " +
        (active ? "bg-primary text-surface border-primary font-semibold" : "border-outline-variant text-on-surface-variant hover:text-on-surface");
    });
  }

  try {
    const res = await fetch("./live/cardio/demo_patients.json");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const patients = await res.json();
    switcher.replaceChildren();
    const buttons = [];
    for (const patient of patients) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.slug = patient.slug;
      btn.setAttribute("role", "tab");
      btn.textContent = patient.slug.replace(/-/g, " ");
      btn.addEventListener("click", () => renderPatient(patient, buttons));
      switcher.appendChild(btn);
      buttons.push(btn);
    }
    if (patients.length) renderPatient(patients[0], buttons);
    else throw new Error("No demo patients are configured");
  } catch (err) {
    if (fallback) fallback.textContent = "The 3D viewer and demo-patient data are unavailable. Check that the Track A files were included in the deployment, then refresh.";
    if (descEl) descEl.textContent = "Demo-patient data unavailable.";
    console.warn("RIFT coronary fallback data failed to load.", err);
  }
})();
