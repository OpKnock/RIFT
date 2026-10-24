/* RIFT Track A — anatomical heart viewer with model-output overlays.
 * Base heart geometry is loaded from a CC0 GLB model. Colored vessel traces
 * are approximate explanatory overlays of the selected patient's model
 * probabilities; they are not patient-specific anatomy or measured lesions.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const DATA_URL = './live/cardio/demo_patients.json';
const HEART_MODELS = [
  {
    url: 'https://grab3d.com/dl/human-heart-cutaway/human-heart-cutaway-light.glb',
    name: 'High-detail anatomical heart',
    source: 'https://grab3d.com/models/anatomy/human-heart-cutaway/',
    license: 'CC0'
  },
  {
    url: 'https://cdn.3dassets.dev/assets/38952/v1/model.glb',
    name: 'Lightweight anatomical heart',
    source: 'https://3dassets.dev/assets/human-anatomy-and-education-kit-heart-model-79e77e2b',
    license: 'CC0'
  }
];

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
  if (p === null || p === undefined || !Number.isFinite(Number(p))) return NEUTRAL.clone();
  const value = Math.max(0, Math.min(1, Number(p)));
  const c = new THREE.Color();
  if (value <= 0.5) c.lerpColors(GREEN, AMBER, value / 0.5);
  else c.lerpColors(AMBER, RED, (value - 0.5) / 0.5);
  return c;
}

let renderer, scene, camera, controls, raycaster, pointer;
let rendererReady = false;
let frameId = 0;
let meshes = [];
let markers = [];
let heartRoot = null;
let heartDimensions = null;
let currentPatient = null;
let heartLoadingPromise = null;

function init() {
  const canvas = document.getElementById('coronary-canvas');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.setClearColor(0x0b1220, 1);
  const w = canvas.clientWidth || 800, h = canvas.clientHeight || 500;
  renderer.setSize(w, h, false);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1220);
  camera = new THREE.PerspectiveCamera(38, w / h, 0.1, 100);
  camera.position.set(0, 0.1, 6.1);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.target.set(0, 0, 0);
  controls.minDistance = 3.0;
  controls.maxDistance = 14;
  scene.add(new THREE.HemisphereLight(0xe5f3ff, 0x21151d, 1.35));
  const dir = new THREE.DirectionalLight(0xffe4d6, 2.2);
  dir.position.set(3.5, 5, 6);
  scene.add(dir);
  const fill = new THREE.DirectionalLight(0x77b9ff, 0.8);
  fill.position.set(-4, 1, -3);
  scene.add(fill);
  const glow = new THREE.PointLight(0x0891b2, 7, 18);
  glow.position.set(0, 1, 3);
  scene.add(glow);
  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();
  canvas.addEventListener('pointermove', onHover);
  window.addEventListener('resize', onResize);
  rendererReady = true;
  animate();
}

function setHeartModelStatus(message, asset) {
  const el = document.getElementById('heart-model-status');
  if (!el) return;
  el.textContent = message;
  el.dataset.state = asset ? 'loaded' : 'loading';
  el.style.borderColor = asset ? 'rgba(34,197,94,.45)' : 'rgba(148,163,184,.3)';
  el.style.color = asset ? '#bbf7d0' : '#cbd5e1';
  const source = document.getElementById('heart-model-source');
  if (source) {
    source.replaceChildren();
    if (asset) {
      const link = document.createElement('a');
      link.href = asset.source;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = asset.name + ' · ' + asset.license;
      link.style.cssText = 'color:#67e8f9;text-decoration:underline;text-underline-offset:3px;';
      source.appendChild(link);
    } else {
      source.textContent = 'Loading open-licensed anatomical model…';
    }
  }
}

function loadGltf(loader, asset, index, count) {
  return new Promise((resolve, reject) => {
    loader.load(asset.url, resolve, event => {
      if (event && event.total > 0) {
        const pct = Math.max(0, Math.min(100, Math.round(event.loaded / event.total * 100)));
        setHeartModelStatus('Loading anatomical model · ' + pct + '%', null);
      } else {
        setHeartModelStatus('Loading anatomical model…', null);
      }
    }, reject);
  });
}

async function loadHeartModel() {
  if (heartLoadingPromise) return heartLoadingPromise;
  heartLoadingPromise = (async () => {
    if (!rendererReady || !scene) return false;
    const loader = new GLTFLoader();
    const statusEl = document.getElementById('heart-model-status');
    if (statusEl) statusEl.style.display = 'block';

    for (let i = 0; i < HEART_MODELS.length; i++) {
      const asset = HEART_MODELS[i];
      try {
        setHeartModelStatus(i === 0
          ? 'Loading high-detail heart model…'
          : 'Loading lightweight anatomical backup…', null);
        const gltf = await loadGltf(loader, asset, i, HEART_MODELS.length);
        const model = gltf.scene;
        model.updateMatrixWorld(true);
        const bounds = new THREE.Box3().setFromObject(model);
        const size = bounds.getSize(new THREE.Vector3());
        const center = bounds.getCenter(new THREE.Vector3());
        if (!Number.isFinite(size.y) || size.y <= 0) throw new Error('Model has invalid dimensions');

        // Center and fit the downloaded asset to the viewer without changing its meshes.
        model.position.sub(center);
        const root = new THREE.Group();
        root.name = 'RIFT anatomical heart model';
        root.add(model);
        const fitHeight = 4.15;
        const fitScale = fitHeight / size.y;
        root.scale.setScalar(fitScale);
        root.traverse(object => {
          if (!object.isMesh) return;
          object.castShadow = true;
          object.receiveShadow = true;
          if (object.material) {
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            materials.forEach(material => {
              if ('roughness' in material && material.roughness > 0.9) material.roughness = 0.72;
              if ('metalness' in material && material.metalness > 0.55) material.metalness = 0.12;
              material.needsUpdate = true;
            });
          }
        });
        scene.add(root);
        heartRoot = root;
        heartDimensions = size.multiplyScalar(fitScale);
        setHeartModelStatus(asset.name + ' loaded', asset);
        if (currentPatient) buildTree(currentPatient);
        return true;
      } catch (error) {
        console.warn('Could not load ' + asset.name + '; trying next CC0 model.', error);
      }
    }
    setHeartModelStatus('Anatomical asset unavailable · schematic overlay only', null);
    return false;
  })();
  return heartLoadingPromise;
}

function clearOverlays() {
  for (const m of meshes) {
    scene.remove(m);
    m.geometry.dispose();
    if (Array.isArray(m.material)) m.material.forEach(material => material.dispose());
    else m.material.dispose();
  }
  for (const m of markers) {
    scene.remove(m);
    m.geometry.dispose();
    if (Array.isArray(m.material)) m.material.forEach(material => material.dispose());
    else m.material.dispose();
  }
  meshes = [];
  markers = [];
}

function buildTree(patient) {
  if (!rendererReady || !scene || !patient || !patient.calibrated_probabilities) return;
  currentPatient = patient;
  clearOverlays();

  const usingAnatomicalModel = Boolean(heartRoot && heartDimensions);
  // Map the existing explanatory coronary paths onto the front of the real heart mesh.
  // The paths stay explicitly schematic and are not claimed to be patient-specific anatomy.
  const xScale = usingAnatomicalModel ? heartDimensions.x / 6.6 : 1;
  const yScale = usingAnatomicalModel ? heartDimensions.y / 4.8 : 1;
  const frontZ = usingAnatomicalModel ? heartDimensions.z * 0.5 + 0.035 : 0;
  const radiusScale = usingAnatomicalModel ? Math.min(xScale, yScale) * 0.52 : 1;

  for (const [id, label, target, pts, radius, markerT] of SEGMENTS) {
    // The asset already provides the great vessels, so avoid drawing a second arch.
    if (usingAnatomicalModel && id === 'aorta') continue;

    const prob = target ? patient.calibrated_probabilities[target] : null;
    const mapped = pts.map(([x, y, z]) => new THREE.Vector3(
      x * xScale,
      y * yScale,
      usingAnatomicalModel ? frontZ + z * 0.015 : z
    ));
    const curve = new THREE.CatmullRomCurve3(mapped);
    const actualRadius = radius * radiusScale;
    const geo = new THREE.TubeGeometry(curve, 48, actualRadius, 10, false);
    const tint = probColor(prob);
    const mat = new THREE.MeshStandardMaterial({
      color: tint, roughness: 0.38, metalness: 0.05,
      emissive: tint, emissiveIntensity: usingAnatomicalModel ? 0.12 : 0.25,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { id, label, target, prob };
    scene.add(mesh);
    meshes.push(mesh);

    if (markerT >= 0) {
      const pos = curve.getPoint(markerT);
      const ringRadius = actualRadius + (usingAnatomicalModel ? 0.018 : 0.05);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(ringRadius, usingAnatomicalModel ? 0.012 : 0.022, 10, 28),
        new THREE.MeshBasicMaterial({ color: prob >= 0.5 ? 0xef4444 : 0xf59e0b }));
      ring.position.copy(pos);
      ring.userData = { pulse: Math.random() * Math.PI * 2, base: ringRadius };
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
  frameId = requestAnimationFrame(animate);
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
  currentPatient = p;
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
    void loadHeartModel();
  } catch (err) {
    rendererReady = false;
    if (frameId) cancelAnimationFrame(frameId);
    const fallback = document.getElementById('coronary-fallback');
    const canvas = document.getElementById('coronary-canvas');
    if (fallback) {
      fallback.style.display = 'flex';
      fallback.textContent = '3D rendering is unavailable in this browser. Demo-patient probabilities and explanation details remain available below.';
    }
    if (canvas) canvas.style.display = 'none';
    console.warn('RIFT coronary 3D renderer unavailable; showing numeric fallback.', err);
  }
  let patients;
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    patients = await res.json();
  } catch (err) {
    rendererReady = false;
    if (frameId) cancelAnimationFrame(frameId);
    const fallback = document.getElementById('coronary-fallback');
    const canvas = document.getElementById('coronary-canvas');
    if (fallback) {
      fallback.style.display = 'flex';
      fallback.textContent = 'Demo-patient data could not be loaded. Check that the Track A data files are deployed, then refresh this page.';
    }
    if (canvas) canvas.style.display = 'none';
    document.getElementById('patient-desc').textContent = 'Demo-patient data unavailable.';
    console.warn('RIFT coronary demo-patient data failed to load.', err);
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
