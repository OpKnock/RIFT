/* RIFT Track A — schematic coronary tree (Three.js, CDN).
 * Branch colors = calibrated model probabilities for the selected demo
 * patient. Geometry is illustrative, not anatomy; see on-page banner.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const DATA_URL = './live/cardio/demo_patients.json';

const SEGMENTS = [
  // [id, label, target, points, radius, markerT]
  ['aorta', 'Aorta (reference)', null,
    [[-2.6, 2.4, 0], [-0.8, 2.3, 0], [0.8, 2.3, 0], [2.6, 2.4, 0]], 0.22, -1],
  ['lm', 'Left main (LM)', null,
    [[-1.9, 2.25, 0], [-1.9, 1.8, 0], [-1.85, 1.45, 0]], 0.13, -1],
  ['lad', 'Left anterior descending (LAD)', 'lad',
    [[-1.85, 1.45, 0], [-1.7, 0.8, 0.05], [-1.55, -0.2, 0.1], [-1.45, -1.2, 0.15], [-1.4, -2.1, 0.2]], 0.11, 0.45],
  ['d1', 'Diagonal D1 (LAD territory)', 'lad',
    [[-1.62, 0.35, 0.07], [-1.1, -0.1, 0.2], [-0.6, -0.5, 0.3]], 0.06, -1],
  ['d2', 'Diagonal D2 (LAD territory)', 'lad',
    [[-1.5, -0.7, 0.12], [-1.0, -1.1, 0.25], [-0.5, -1.5, 0.35]], 0.06, -1],
  ['lcx', 'Left circumflex (LCX)', 'lcx',
    [[-1.85, 1.45, 0], [-2.3, 1.1, 0.1], [-2.8, 0.7, 0.2], [-3.2, 0.2, 0.3]], 0.10, 0.5],
  ['om1', 'Obtuse marginal OM1 (LCX territory)', 'lcx',
    [[-2.4, 1.0, 0.12], [-2.7, 0.4, 0.3], [-2.9, -0.3, 0.4]], 0.055, -1],
  ['om2', 'Obtuse marginal OM2 (LCX territory)', 'lcx',
    [[-2.9, 0.6, 0.22], [-3.2, 0.0, 0.35], [-3.3, -0.7, 0.45]], 0.055, -1],
  ['rca', 'Right coronary artery (RCA)', 'rca',
    [[1.9, 2.25, 0], [1.95, 1.6, 0.1], [2.0, 0.8, 0.15], [1.95, -0.2, 0.2], [1.8, -1.2, 0.25], [1.6, -2.0, 0.3]], 0.11, 0.45],
  ['rm', 'Right marginal (RCA territory)', 'rca',
    [[1.97, 0.3, 0.17], [1.4, -0.1, 0.35], [0.8, -0.4, 0.5]], 0.06, -1],
];

const GREEN = new THREE.Color('#22c55e');
const AMBER = new THREE.Color('#f59e0b');
const RED = new THREE.Color('#ef4444');
const NEUTRAL = new THREE.Color('#38bdf8');

function probColor(p) {
  if (p === null || p === undefined) return NEUTRAL.clone();
  const c = new THREE.Color();
  if (p <= 0.5) c.lerpColors(GREEN, AMBER, p / 0.5);
  else c.lerpColors(AMBER, RED, (p - 0.5) / 0.5);
  return c;
}

let renderer, scene, camera, controls, raycaster, pointer;
let meshes = [];
let markers = [];

function init() {
  const canvas = document.getElementById('coronary-canvas');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setClearColor(0x0b1220, 1);
  const w = canvas.clientWidth || 800, h = canvas.clientHeight || 500;
  renderer.setSize(w, h, false);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 100);
  camera.position.set(0, 0.4, 7.4);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const dir = new THREE.DirectionalLight(0xffffff, 1.4);
  dir.position.set(3, 5, 6);
  scene.add(dir);
  const glow = new THREE.PointLight(0x0891b2, 12, 30);
  glow.position.set(0, 1, 3);
  scene.add(glow);
  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();
  canvas.addEventListener('pointermove', onHover);
  window.addEventListener('resize', onResize);
  animate();
}

function buildTree(patient) {
  for (const m of meshes) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
  for (const m of markers) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
  meshes = []; markers = [];
  for (const [id, label, target, pts, radius, markerT] of SEGMENTS) {
    const prob = target ? patient.calibrated_probabilities[target] : null;
    const curve = new THREE.CatmullRomCurve3(pts.map(p => new THREE.Vector3(...p)));
    const geo = new THREE.TubeGeometry(curve, 48, radius, 12, false);
    const mat = new THREE.MeshStandardMaterial({
      color: probColor(prob), roughness: 0.35, metalness: 0.15,
      emissive: probColor(prob), emissiveIntensity: 0.25,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { id, label, target, prob };
    scene.add(mesh);
    meshes.push(mesh);
    if (markerT >= 0) {
      const pos = curve.getPoint(markerT);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius + 0.05, 0.022, 10, 28),
        new THREE.MeshBasicMaterial({ color: prob >= 0.5 ? 0xef4444 : 0xf59e0b }));
      ring.position.copy(pos);
      ring.userData = { pulse: Math.random() * Math.PI * 2, base: radius + 0.05 };
      scene.add(ring);
      markers.push(ring);
    }
  }
}

function onHover(event) {
  const canvas = document.getElementById('coronary-canvas');
  const tip = document.getElementById('coronary-tip');
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(meshes);
  if (hits.length) {
    const u = hits[0].object.userData;
    tip.style.display = 'block';
    tip.style.left = (event.clientX - rect.left + 14) + 'px';
    tip.style.top = (event.clientY - rect.top + 10) + 'px';
    tip.innerHTML = u.target
      ? `<b>${u.label}</b><br/>stenosis P = ${u.prob.toFixed(3)}<br/><span style="opacity:.65">representative site (schematic)</span>`
      : `<b>${u.label}</b><br/><span style="opacity:.65">anatomical reference</span>`;
  } else {
    tip.style.display = 'none';
  }
}

function onResize() {
  const canvas = document.getElementById('coronary-canvas');
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  for (const m of markers) {
    const s = 1 + 0.12 * Math.sin(2.2 * t + m.userData.pulse);
    m.scale.setScalar(s);
  }
  controls.update();
  renderer.render(scene, camera);
}

function probBar(target, label, prob, truth) {
  const pct = Math.round(prob * 100);
  const color = '#' + probColor(prob).getHexString();
  return `<div>
    <div class="flex justify-between text-xs mb-1">
      <span class="font-label uppercase tracking-wider">${label}</span>
      <span><b>${prob.toFixed(3)}</b> <span class="text-on-surface-variant">· truth ${truth ? 'Stenotic' : 'Normal'}</span></span>
    </div>
    <div class="h-2 rounded-full bg-surface-container-high overflow-hidden">
      <div class="h-2 rounded-full" style="width:${pct}%;background:${color}"></div>
    </div>
  </div>`;
}

function whatIfHtml(patient) {
  const names = { lad: 'LAD', lcx: 'LCX', rca: 'RCA' };
  return ['lad', 'lcx', 'rca'].map(t => {
    const flips = (patient.counterfactuals && patient.counterfactuals[t]) || [];
    const truth = patient.labels[t] ? 'Stenotic' : 'Normal';
    let body;
    if (!flips.length) {
      body = '<div class="text-on-surface-variant">Stable — no single observed-value change flips this prediction.</div>';
    } else {
      body = flips.map(f => {
        const dir = f.corrective
          ? '<span class="text-green-400">✓ toward truth</span>'
          : '<span class="text-amber-400">· away from truth</span>';
        const act = f.actionable ? '' : ' <span class="text-on-surface-variant">(demographic — explanation, not advice)</span>';
        const fmt = v => (typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(1) : String(v));
        return `<div class="rounded border border-outline-variant px-2 py-1.5">If <b>${f.feature}</b> were ` +
          `<b>${fmt(f.to)}</b> (was ${fmt(f.from)}) → P <b>${f.prob_after.toFixed(3)}</b> ${dir}${act}</div>`;
      }).join('');
    }
    return `<div><div class="font-label uppercase tracking-wider text-on-surface-variant mb-1">${names[t]} (truth ${truth})</div>${body}</div>`;
  }).join('');
}

function selectPatient(patients, slug) {
  const p = patients.find(x => x.slug === slug) || patients[0];
  buildTree(p);
  document.getElementById('patient-name').textContent =
    p.slug.replace(/-/g, ' ') + ` (test row ${p.test_row})`;
  const d = p.display;
  document.getElementById('patient-desc').textContent =
    `Age ${d['Age']} · Sex ${d['Sex']} · Typical chest pain ${d['Typical Chest Pain']} · HTN ${d['HTN']} · EF-TTE ${d['EF-TTE']}`;
  const pr = p.calibrated_probabilities;
  document.getElementById('prob-bars').innerHTML =
    `<div class="rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-xs mb-1">
       CAD overall <b class="text-base ml-1">${pr.cad.toFixed(3)}</b>
       <span class="text-on-surface-variant">· truth ${p.labels.cad ? 'CAD' : 'Normal'}</span></div>` +
    probBar('lad', 'LAD stenosis', pr.lad, p.labels.lad) +
    probBar('lcx', 'LCX stenosis', pr.lcx, p.labels.lcx) +
    probBar('rca', 'RCA stenosis', pr.rca, p.labels.rca);
  document.getElementById('patient-meta').textContent =
    `Models cad-v1 / lad-, lcx-, rca-stenosis-v1 · dataset ${p.dataset_hash.slice(0, 12)}…`;
  document.getElementById('whatif-panel').innerHTML = whatIfHtml(p);
  for (const btn of document.querySelectorAll('#patient-switch button')) {
    const active = btn.dataset.slug === p.slug;
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
    btn.className = 'px-3 py-1.5 rounded-lg text-xs font-label border transition-colors ' + (active
      ? 'bg-primary text-surface border-primary font-semibold'
      : 'border-outline-variant text-on-surface-variant hover:text-on-surface');
  }
}

async function main() {
  try {
    init();
  } catch (err) {
    document.getElementById('coronary-fallback').style.display = 'flex';
    console.error(err);
  }
  let patients;
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    patients = await res.json();
  } catch (err) {
    document.getElementById('patient-desc').textContent =
      'Could not load demo patients (' + err.message + '). Serve via `bash ./local ui`.';
    return;
  }
  const sw = document.getElementById('patient-switch');
  for (const p of patients) {
    const btn = document.createElement('button');
    btn.dataset.slug = p.slug;
    btn.setAttribute('role', 'tab');
    btn.textContent = p.slug.replace(/-/g, ' ');
    btn.onclick = () => selectPatient(patients, p.slug);
    sw.appendChild(btn);
  }
  selectPatient(patients, patients[0].slug);
}

main();
