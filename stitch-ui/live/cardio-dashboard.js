/* RIFT Track A evaluation dashboard — renders the committed JSON reports. */
const BASE = './live/cardio/';

const TARGETS = ['cad', 'lad', 'lcx', 'rca'];
const NAMES = { cad: 'CAD', lad: 'LAD', lcx: 'LCX', rca: 'RCA' };

function fail(msg) {
  const el = document.getElementById('cardio-error');
  el.textContent = 'Could not load evaluation data (' + msg + '). Serve via `bash ./local ui`.';
  el.classList.remove('hidden');
}

function cell(v, digits) {
  return Number(v).toFixed(digits === undefined ? 3 : digits);
}

function renderMetrics(report) {
  document.getElementById('protocol-line').textContent = report.protocol;
  let html = '<thead><tr class="text-left text-on-surface-variant font-label uppercase tracking-wider">' +
    '<th class="py-1.5 pr-3">Target</th><th class="py-1.5 pr-3">Model</th>' +
    ['acc', 'prec', 'rec', 'F1', 'AUC'].map(h => `<th class="py-1.5 pr-3">${h}</th>`).join('') +
    '<th class="py-1.5 pr-3">CV AUC</th><th class="py-1.5 pr-3">Confusion tp/tn/fp/fn</th></tr></thead><tbody>';
  for (const t of TARGETS) {
    const e = report.targets[t], m = e.test, c = e.cv_train;
    const weak = (t === 'lcx' && m.recall < 0.5) || (t === 'rca' && m.roc_auc < 0.65);
    html += `<tr class="border-t border-outline-variant ${weak ? 'bg-amber-500/5' : ''}">` +
      `<td class="py-1.5 pr-3 font-semibold">${NAMES[t]}${weak ? ' ⚠' : ''}</td>` +
      `<td class="py-1.5 pr-3 font-mono">${e.model_id}</td>` +
      `<td class="py-1.5 pr-3">${cell(m.accuracy)}</td><td class="py-1.5 pr-3">${cell(m.precision)}</td>` +
      `<td class="py-1.5 pr-3">${cell(m.recall)}</td><td class="py-1.5 pr-3">${cell(m.f1)}</td>` +
      `<td class="py-1.5 pr-3 font-semibold">${cell(m.roc_auc)}</td>` +
      `<td class="py-1.5 pr-3">${cell(c.roc_auc_mean)}±${cell(c.roc_auc_std)}</td>` +
      `<td class="py-1.5 pr-3 font-mono">${m.confusion.tp}/${m.confusion.tn}/${m.confusion.fp}/${m.confusion.fn}</td></tr>`;
  }
  document.getElementById('metrics-table').innerHTML = html + '</tbody>';
}

function renderCalibration(calib) {
  let html = '<thead><tr class="text-left text-on-surface-variant font-label uppercase tracking-wider">' +
    '<th class="py-1.5 pr-3">Target</th><th class="py-1.5 pr-3">Method</th>' +
    '<th class="py-1.5 pr-3">OOF ECE</th><th class="py-1.5 pr-3">Test ECE</th><th class="py-1.5 pr-3">Test Brier</th></tr></thead><tbody>';
  for (const t of TARGETS) {
    const m = calib.models[t];
    html += `<tr class="border-t border-outline-variant">` +
      `<td class="py-1.5 pr-3 font-semibold">${NAMES[t]}</td>` +
      `<td class="py-1.5 pr-3 font-mono">${m.method}</td>` +
      `<td class="py-1.5 pr-3">${cell(m.oof.before.ece)} → ${cell(m.oof.after.ece)}</td>` +
      `<td class="py-1.5 pr-3 font-semibold">${cell(m.test.before.ece)} → ${cell(m.test.after.ece)}</td>` +
      `<td class="py-1.5 pr-3">${cell(m.test.before.brier)} → ${cell(m.test.after.brier)}</td></tr>`;
  }
  document.getElementById('calib-table').innerHTML = html + '</tbody>';
  const sw = document.getElementById('rel-switch');
  for (const t of TARGETS) {
    const btn = document.createElement('button');
    btn.dataset.target = t;
    btn.textContent = NAMES[t];
    btn.onclick = () => drawReliability(calib, t);
    sw.appendChild(btn);
  }
  drawReliability(calib, 'cad');
}

function drawReliability(calib, target) {
  for (const btn of document.querySelectorAll('#rel-switch button')) {
    const active = btn.dataset.target === target;
    btn.className = 'px-2 py-0.5 rounded text-xs border ' + (active
      ? 'bg-primary text-surface border-primary font-semibold' : 'border-outline-variant text-on-surface-variant');
  }
  const canvas = document.getElementById('rel-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height, PAD = 34;
  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = '#374151';
  ctx.strokeRect(PAD, 8, W - PAD - 8, H - PAD - 8);
  // diagonal
  ctx.strokeStyle = '#4b5563';
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(PAD, H - PAD);
  ctx.lineTo(W - 8, 8);
  ctx.stroke();
  ctx.setLineDash([]);
  const X = c => PAD + c * (W - PAD - 8);
  const Y = a => (H - PAD) - a * (H - PAD - 8);
  const series = [
    { bins: calib.models[target].test.reliability_before, color: '#f59e0b', mark: 'x' },
    { bins: calib.models[target].test.reliability_after, color: '#22c55e', mark: 'o' },
  ];
  ctx.fillStyle = '#9ca3af';
  ctx.font = '11px Inter, sans-serif';
  for (const s of series) {
    ctx.strokeStyle = s.color;
    ctx.fillStyle = s.color;
    let started = false;
    ctx.beginPath();
    for (const b of s.bins) {
      if (!b.count) continue;
      const x = X(b.confidence), y = Y(b.accuracy);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
    for (const b of s.bins) {
      if (!b.count) continue;
      const x = X(b.confidence), y = Y(b.accuracy);
      const r = 2 + Math.min(6, Math.sqrt(b.count));
      ctx.beginPath();
      if (s.mark === 'o') ctx.arc(x, y, r, 0, 7);
      else { ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r); ctx.moveTo(x + r, y - r); ctx.lineTo(x - r, y + r); }
      ctx.stroke();
    }
  }
  ctx.fillStyle = '#9ca3af';
  ctx.fillText('confidence →', W - 110, H - 12);
  ctx.fillText('accuracy', 4, 20);
}

function renderFeatures(expl) {
  const grid = document.getElementById('feat-grid');
  for (const t of TARGETS) {
    const div = document.createElement('div');
    const rows = expl.targets[t].permutation_top15.slice(0, 10).map((r, i) =>
      `<tr class="border-t border-outline-variant"><td class="py-1 pr-2 text-on-surface-variant">${i + 1}</td>` +
      `<td class="py-1 pr-2">${r.feature}</td>` +
      `<td class="py-1 text-right font-mono">${r.auc_drop_mean.toFixed(4)}</td></tr>`).join('');
    div.innerHTML = `<h3 class="font-headline text-sm font-bold mb-1">${NAMES[t]}</h3>` +
      `<table class="w-full text-xs"><tbody>${rows}</tbody></table>`;
    grid.appendChild(div);
  }
}

function renderCards(cards) {
  const grid = document.getElementById('cards-grid');
  const weak = { lcx: true, rca: true };
  for (const c of cards) {
    const div = document.createElement('div');
    div.className = 'rounded-lg border px-4 py-3 ' + (weak[c.target]
      ? 'border-amber-500/50 bg-amber-500/5' : 'border-outline-variant');
    div.innerHTML =
      `<div class="flex items-baseline gap-2 mb-1">` +
      `<h3 class="font-headline text-sm font-bold">${c.target.toUpperCase()}${weak[c.target] ? ' ⚠' : ''}</h3>` +
      `<span class="font-mono text-xs text-on-surface-variant">${c.model_id} · ${c.algorithm.replace(/_/g, ' ')}</span></div>` +
      `<p class="text-xs mb-2">${c.task}</p>` +
      `<p class="text-xs mb-2"><span class="font-label uppercase tracking-wider text-on-surface-variant">Use: </span>${c.intended_use}</p>` +
      `<p class="text-xs mb-2"><span class="font-label uppercase tracking-wider text-on-surface-variant">Test: </span>` +
      `AUC ${cell(c.test_metrics.roc_auc)} · F1 ${cell(c.test_metrics.f1)} · ` +
      `recall ${cell(c.test_metrics.recall)} · CV ${cell(c.cv_roc_auc.mean)}±${cell(c.cv_roc_auc.std)} · ` +
      `ECE ${cell(c.calibration.test_ece_before)}→${cell(c.calibration.test_ece_after)} (${c.calibration.method})</p>` +
      `<p class="text-xs mb-2"><span class="font-label uppercase tracking-wider text-on-surface-variant">Top drivers: </span>${c.top_drivers.join(' · ')}</p>` +
      `<p class="text-xs rounded bg-surface-container-high px-2 py-1.5"><span class="font-label uppercase tracking-wider">Limits: </span>${c.limitations}</p>`;
    grid.appendChild(div);
  }
}

async function main() {
  try {
    const [report, calib, expl, cards] = await Promise.all(
      ['report.json', 'calibration.json', 'explainability.json', 'model_cards.json'].map(async f => {
        const res = await fetch(BASE + f);
        if (!res.ok) throw new Error(f + ': HTTP ' + res.status);
        return res.json();
      }));
    renderMetrics(report);
    renderCalibration(calib);
    renderFeatures(expl);
    renderCards(cards);
    document.getElementById('manifest-line').textContent =
      `Dataset sha256 ${report.dataset_hash.slice(0, 16)}… · feature schema ${report.feature_schema_version} · ` +
      `split seed 7 (183/60/60) · 55 predictors · protocol: ${report.protocol}`;
  } catch (err) {
    fail(err.message);
  }
}

main();
