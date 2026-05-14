/**
 * ComputationalDesign/app.js — Pipeline UI controller + Three.js STL viewer
 * ES module, loaded via <script type="module">
 */

import * as THREE from 'three';
import { STLLoader }     from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const API = 'http://localhost:8004';

// Track active design, iteration count, stage timers, and prompt history
let _currentDesignId = null;
let _iterationCount = 0;
const _stageTimers = {};  // stage -> intervalId
const _promptHistory = []; // array of prompt strings

function getTimeout() {
  const input = document.getElementById('timeout-input');
  return parseInt(input.value, 10) || 300;
}

function addToHistory(prompt) {
  _promptHistory.push(prompt);
  renderHistory();
}

function renderHistory() {
  const container = document.getElementById('prompt-history');
  if (_promptHistory.length === 0) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');
  container.innerHTML = _promptHistory.map((text, i) => {
    const label = i === 0 ? 'Original' : `Refinement #${i}`;
    return `<div class="prompt-entry">
      <span class="prompt-label">${label}</span>
      <span class="prompt-text">${esc(text)}</span>
    </div>`;
  }).join('');
  container.scrollTop = container.scrollHeight;
}

// ── Example buttons ──────────────────────────────────────────────────────────

document.querySelectorAll('.example-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('description').value = btn.dataset.text;
  });
});

// ── Form submit ───────────────────────────────────────────────────────────────

document.getElementById('design-btn').addEventListener('click', startPipeline);
document.getElementById('description').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) startPipeline();
});

async function startPipeline() {
  const description = document.getElementById('description').value.trim();
  if (!description) return;

  const btn = document.getElementById('design-btn');
  btn.disabled = true;
  btn.textContent = '⬡ Processing…';

  resetPipeline();
  document.getElementById('pipeline').classList.remove('hidden');
  document.getElementById('pipeline').scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Immediately show stage 1 as running (before SSE connects)
  updateStage(1, 'running', null, null);

  // Record this prompt in the visible history
  addToHistory(description);

  try {
    // If we already have a design, this is a refinement — re-run full pipeline
    if (_currentDesignId && _iterationCount > 0) {
      const res = await fetch(`${API}/design/${_currentDesignId}/refine`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ prompt: description, timeout: getTimeout() }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      await res.json();
      listenToStream(_currentDesignId);
    } else {
      // First run: create design + run stage 1 only
      const res = await fetch(`${API}/design`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ description, timeout: getTimeout() }),
      });
      const { id } = await res.json();
      _currentDesignId = id;
      _iterationCount = 0;
      updateIterationBadge();
      listenToStream(id);
    }
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">⬡</span> Start';
    alert(`Could not connect to the server: ${err.message}`);
  }
}

function updateIterationBadge() {
  const badge = document.getElementById('iteration-badge');
  if (_iterationCount > 0) {
    badge.textContent = `Iteration ${_iterationCount}`;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

// ── Retry buttons ─────────────────────────────────────────────────────────────

document.querySelectorAll('.stage-retry-btn').forEach((btn, idx) => {
  btn.addEventListener('click', () => retryStage(idx + 1));
});

async function retryStage(stageNum) {
  if (!_currentDesignId) return;
  const card = document.getElementById(`stage-${stageNum}`);
  const subpromptInput = card.querySelector('.stage-subprompt');
  const subprompt = subpromptInput ? subpromptInput.value.trim() : '';

  // Reset only this stage visually
  card.classList.remove('done', 'error');
  card.classList.add('running');
  card.querySelector('.stage-placeholder').classList.remove('hidden');
  card.querySelector('.stage-placeholder').innerHTML = '<span class="spin">⬡</span> Processing…';
  card.querySelector('.stage-content').classList.add('hidden');
  card.querySelector('.stage-retry-btn').disabled = true;
  setBadge(stageNum, 'running', 'Running');
  startStageTimer(stageNum);

  // Disable next stage button while this one runs
  if (stageNum < 5) {
    document.getElementById(`stage-${stageNum + 1}`).querySelector('.stage-retry-btn').disabled = true;
  }

  try {
    const body = { timeout: getTimeout() };
    if (subprompt) body.prompt = subprompt;
    const res = await fetch(`${API}/design/${_currentDesignId}/stage/${stageNum}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}: ${await res.text()}`);
    listenToStream(_currentDesignId);
  } catch (err) {
    stopStageTimer(stageNum);
    card.classList.remove('running');
    card.classList.add('error');
    setBadge(stageNum, 'error', 'Error');
    card.querySelector('.stage-placeholder').textContent = `Error: ${err.message}`;
    card.querySelector('.stage-retry-btn').disabled = false;
  }
}

// ── Pipeline reset ────────────────────────────────────────────────────────────

function resetPipeline() {
  for (let i = 1; i <= 5; i++) {
    stopStageTimer(i);
    const card = document.getElementById(`stage-${i}`);
    card.className = 'stage-card';
    setBadge(i, 'pending', 'Pending');
    card.querySelector('.stage-placeholder').classList.remove('hidden');
    card.querySelector('.stage-placeholder').textContent = 'Waiting…';
    card.querySelector('.stage-content').classList.add('hidden');
    card.querySelector('.stage-retry-btn').disabled = true;
  }
  // Clear stage 3 viewer
  const wrap = document.getElementById('stl-canvas-wrap');
  wrap.innerHTML = '';
  document.getElementById('stl-loading').classList.remove('hidden');
  document.getElementById('stl-unavailable').classList.add('hidden');
  _stlRendered = false;
}

// ── Elapsed timer ─────────────────────────────────────────────────────────────

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

function startStageTimer(stage) {
  stopStageTimer(stage);
  const startTime = Date.now();
  const card = document.getElementById(`stage-${stage}`);
  const placeholder = card.querySelector('.stage-placeholder');

  _stageTimers[stage] = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    placeholder.innerHTML = `<span class="spin">⬡</span> Processing… ${formatElapsed(elapsed)}`;
  }, 1000);
}

function stopStageTimer(stage) {
  if (_stageTimers[stage]) {
    clearInterval(_stageTimers[stage]);
    delete _stageTimers[stage];
  }
}

// ── SSE stream handler ────────────────────────────────────────────────────────

function listenToStream(designId) {
  const es = new EventSource(`${API}/design/${designId}/stream`);

  es.onmessage = e => {
    const event = JSON.parse(e.data);

    if (event.type === 'complete') {
      es.close();
      const btn = document.getElementById('design-btn');
      btn.disabled = false;
      // If all 5 stages are done, switch to Refine mode
      const allDone = [1,2,3,4,5].every(i =>
        document.getElementById(`stage-${i}`).classList.contains('done')
      );
      if (allDone) {
        btn.innerHTML = '<span class="btn-icon">⬡</span> Refine';
        const textarea = document.getElementById('description');
        textarea.value = '';
        textarea.placeholder = 'Describe how to refine the design (e.g. "make it taller", "add ventilation slots")…';
        _iterationCount++;
        updateIterationBadge();
      } else {
        btn.innerHTML = '<span class="btn-icon">⬡</span> Start';
      }
      return;
    }

    if (event.type === 'error') {
      es.close();
      const btn = document.getElementById('design-btn');
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">⬡</span> Start';
      showError(event.message);
      return;
    }

    const { stage, status, data } = event;
    if (stage) updateStage(stage, status, data, designId);
  };

  es.onerror = () => {
    es.close();
    const btn = document.getElementById('design-btn');
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">⬡</span> Start';
  };
}

function showError(message) {
  for (let i = 1; i <= 5; i++) {
    const card = document.getElementById(`stage-${i}`);
    if (card.classList.contains('running')) {
      stopStageTimer(i);
      setBadge(i, 'error', 'Error');
      card.classList.remove('running');
      card.classList.add('error');
      card.querySelector('.stage-placeholder').textContent = `Error: ${message}`;
      card.querySelector('.stage-retry-btn').disabled = false;
    }
  }
}

// ── Stage updaters ────────────────────────────────────────────────────────────

function updateStage(stage, status, data, designId) {
  const card = document.getElementById(`stage-${stage}`);
  const retryBtn = card.querySelector('.stage-retry-btn');

  if (status === 'running') {
    card.classList.add('running');
    setBadge(stage, 'running', 'Running');
    retryBtn.disabled = true;
    if (!_stageTimers[stage]) {
      card.querySelector('.stage-placeholder').innerHTML =
        '<span class="spin">⬡</span> Processing… 0s';
      startStageTimer(stage);
    }
    return;
  }

  if (status === 'done') {
    stopStageTimer(stage);
    card.classList.remove('running');
    card.classList.add('done');
    setBadge(stage, 'done', 'Done');
    card.querySelector('.stage-placeholder').classList.add('hidden');
    card.querySelector('.stage-content').classList.remove('hidden');
    retryBtn.disabled = false;

    // Enable the next stage's ▶ button so user can advance
    if (stage < 5) {
      const nextCard = document.getElementById(`stage-${stage + 1}`);
      nextCard.querySelector('.stage-retry-btn').disabled = false;
    }

    switch (stage) {
      case 1: renderBrief(data);                    break;
      case 2: renderCode(data, designId);           break;
      case 3: renderPreview(data, designId);        break;
      case 4: renderPrintSettings(data);            break;
      case 5: renderBOM(data);                      break;
    }
  }

  if (status === 'error') {
    stopStageTimer(stage);
    card.classList.remove('running');
    card.classList.add('error');
    setBadge(stage, 'error', 'Error');
    card.querySelector('.stage-placeholder').textContent = `Error: ${data?.message || 'Unknown error'}`;
    retryBtn.disabled = false;
  }
}

function setBadge(stage, cls, text) {
  const badge = document.querySelector(`#stage-${stage} .stage-badge`);
  badge.className = `stage-badge ${cls}`;
  badge.textContent = text;
}

// ── Stage 1: Brief ────────────────────────────────────────────────────────────

function renderBrief(brief) {
  const grid = document.getElementById('brief-grid');
  grid.innerHTML = '';

  const dims = brief.dimensions || {};
  const dimStr = dims.width_mm
    ? `${dims.width_mm} × ${dims.height_mm} × ${dims.depth_mm} mm`
    : 'Not specified';

  const fields = [
    { label: 'Project',     value: brief.project_name || '—' },
    { label: 'Material',    value: brief.material      || '—' },
    { label: 'Dimensions',  value: dimStr },
    { label: 'Purpose',     value: brief.purpose       || '—', full: true },
  ];

  fields.forEach(({ label, value, full }) => {
    const item = el('div', `brief-item${full ? ' full' : ''}`);
    item.innerHTML = `<div class="brief-label">${label}</div><div class="brief-value">${esc(value)}</div>`;
    grid.appendChild(item);
  });

  // Features
  if (brief.features?.length) {
    const item = el('div', 'brief-item full');
    item.innerHTML = `<div class="brief-label">Features</div><div class="brief-value">
      ${brief.features.map(f => `<span class="brief-tag">${esc(f)}</span>`).join('')}
    </div>`;
    grid.appendChild(item);
  }

  // Hardware
  if (brief.hardware?.length) {
    const item = el('div', 'brief-item full');
    item.innerHTML = `<div class="brief-label">Hardware</div><div class="brief-value">
      ${brief.hardware.map(h => `<span class="brief-tag">${esc(h)}</span>`).join('')}
    </div>`;
    grid.appendChild(item);
  }

  // Constraints
  if (brief.constraints?.length) {
    const item = el('div', 'brief-item full');
    item.innerHTML = `<div class="brief-label">Constraints</div><div class="brief-value">
      ${brief.constraints.map(c => `<span class="brief-tag">${esc(c)}</span>`).join('')}
    </div>`;
    grid.appendChild(item);
  }
}

// ── Stage 2: OpenSCAD Code ────────────────────────────────────────────────────

function renderCode(data, designId) {
  const code = document.getElementById('scad-code');
  code.textContent = data.scad_code;
  hljs.highlightElement(code);

  const dl = document.getElementById('scad-download');
  dl.href = `${API}/design/${designId}/scad`;
  dl.classList.remove('hidden');
}

// ── Stage 3: Render ───────────────────────────────────────────────────────────

let _stlRendered = false;

function renderPreview(data, designId) {
  if (data.has_png) {
    const wrap = document.getElementById('render-png-wrap');
    const img  = document.getElementById('render-png');
    img.src = `${API}/design/${designId}/png?t=${Date.now()}`;
    wrap.classList.remove('hidden');
  } else {
    document.getElementById('render-fallback').classList.remove('hidden');
  }

  if (data.has_stl) {
    const dl = document.getElementById('stl-download');
    dl.href = `${API}/design/${designId}/stl`;
    dl.classList.remove('hidden');

    const stlUrl = `${API}/design/${designId}/stl`;
    initSTLViewer(stlUrl);
  } else {
    document.getElementById('stl-loading').classList.add('hidden');
    document.getElementById('stl-unavailable').classList.remove('hidden');
  }
}

function initSTLViewer(stlUrl) {
  if (_stlRendered) return;
  _stlRendered = true;

  const container = document.getElementById('stl-canvas-wrap');
  const w = container.parentElement.clientWidth  || 320;
  const h = container.parentElement.clientHeight || 220;

  // Scene
  const scene    = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0a10);

  // Camera
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000);
  camera.position.set(0, 100, 200);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  // Lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(1, 2, 3);
  scene.add(dirLight);

  // Grid
  const grid = new THREE.GridHelper(300, 30, 0x2c3050, 0x1a1d27);
  scene.add(grid);

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  // Load STL
  const loader = new STLLoader();
  loader.load(
    stlUrl,
    geometry => {
      document.getElementById('stl-loading').classList.add('hidden');
      geometry.computeBoundingBox();
      geometry.computeVertexNormals();

      // Centre and scale
      const box    = new THREE.Box3().setFromObject(new THREE.Mesh(geometry));
      const size   = new THREE.Vector3();
      const centre = new THREE.Vector3();
      box.getSize(size);
      box.getCenter(centre);

      const maxDim  = Math.max(size.x, size.y, size.z);
      const scale   = 100 / maxDim;
      geometry.translate(-centre.x, -centre.y, -centre.z);

      const material = new THREE.MeshPhongMaterial({
        color:     0xf97316,
        specular:  0x333333,
        shininess: 60,
        side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.scale.set(scale, scale, scale);
      mesh.position.y = size.z * scale / 2;
      scene.add(mesh);

      camera.position.set(
        size.x * scale * 1.2,
        size.y * scale * 1.2,
        size.z * scale * 1.5,
      );
      controls.update();
    },
    undefined,
    err => {
      console.warn('STL load failed', err);
      document.getElementById('stl-loading').classList.add('hidden');
      document.getElementById('stl-unavailable').classList.remove('hidden');
    }
  );

  // Animate
  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // Resize
  const resizeObs = new ResizeObserver(() => {
    const nw = container.parentElement.clientWidth;
    const nh = container.parentElement.clientHeight;
    camera.aspect = nw / nh;
    camera.updateProjectionMatrix();
    renderer.setSize(nw, nh);
  });
  resizeObs.observe(container.parentElement);
}

// ── Stage 4: Print Settings ───────────────────────────────────────────────────

function renderPrintSettings(s) {
  const grid = document.getElementById('print-settings-grid');
  grid.innerHTML = '';

  const fields = [
    { label: 'Material',     value: s.material,           unit: '' },
    { label: 'Layer Height', value: s.layer_height_mm,    unit: 'mm' },
    { label: 'Infill',       value: s.infill_percent,     unit: '%' },
    { label: 'Infill Pattern',value: s.infill_pattern,    unit: '' },
    { label: 'Wall Count',   value: s.wall_count,         unit: 'lines' },
    { label: 'Nozzle Temp',  value: s.nozzle_temp_c,      unit: '°C' },
    { label: 'Bed Temp',     value: s.bed_temp_c,         unit: '°C' },
    { label: 'Print Speed',  value: s.print_speed_mms,    unit: 'mm/s' },
    { label: 'Supports',     value: s.supports,           unit: '' },
    { label: 'Cooling',      value: s.cooling,            unit: '' },
    { label: 'Est. Time',    value: s.estimated_time_hours, unit: 'h' },
    { label: 'Filament',     value: s.estimated_filament_g, unit: 'g' },
  ];

  fields.forEach(({ label, value, unit }) => {
    if (value === undefined || value === null) return;
    const item = el('div', 'setting-item');
    item.innerHTML = `
      <div class="setting-label">${label}</div>
      <div class="setting-value">${esc(String(value))}</div>
      ${unit ? `<div class="setting-unit">${unit}</div>` : ''}
    `;
    grid.appendChild(item);
  });

  // Notes
  const notesEl = document.getElementById('print-notes');
  notesEl.innerHTML = '';
  const notes = [...(s.notes || [])];
  if (s.orientation_tip) notes.unshift(`Orientation: ${s.orientation_tip}`);
  notes.forEach(n => {
    const item = el('div', 'print-note-item');
    item.textContent = n;
    notesEl.appendChild(item);
  });
}

// ── Stage 5: BOM ─────────────────────────────────────────────────────────────

function renderBOM(data) {
  const tbody = document.getElementById('bom-tbody');
  tbody.innerHTML = '';
  (data.bom || []).forEach((row, i) => {
    const subtotal = row.qty && row.price_brl
      ? (row.qty * row.price_brl).toFixed(2)
      : '—';
    const inStock  = row.in_stock !== false;
    const tr       = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${esc(row.item)}</td>
      <td><span class="sku-tag">${esc(row.sku || '—')}</span></td>
      <td>${row.qty ?? '—'}</td>
      <td>${esc(row.unit || '—')}</td>
      <td>R$ ${row.price_brl?.toFixed(2) ?? '—'}</td>
      <td>R$ ${subtotal}</td>
      <td><span class="stock-badge ${inStock ? 'in' : 'out'}">${inStock ? 'In Stock' : 'Check'}</span></td>
    `;
    tbody.appendChild(tr);
  });

  const footer = document.getElementById('bom-footer');
  footer.innerHTML = `
    <div>
      <div class="bom-total-label">Estimated Total</div>
      <div class="bom-total">R$ ${(data.total_estimated_brl || 0).toFixed(2)}</div>
    </div>
    ${data.sourcing_notes ? `<div class="bom-sourcing-note">${esc(data.sourcing_notes)}</div>` : ''}
  `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function el(tag, className) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  return e;
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
