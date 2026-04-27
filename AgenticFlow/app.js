const API_BASE = "http://localhost:8001";

const caseListEl = document.getElementById("caseList");
const flowScrollEl = document.getElementById("flowScroll");
const detailContentEl = document.getElementById("detailContent");
const rawContentEl = document.getElementById("rawContent");
const modelBadgeEl = document.getElementById("modelBadge");

const btnReset = document.getElementById("btnReset");
const btnPrev = document.getElementById("btnPrev");
const btnPlay = document.getElementById("btnPlay");
const btnNext = document.getElementById("btnNext");
const progressFillEl = document.getElementById("progressFill");
const stepCounterEl = document.getElementById("stepCounter");

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const paneDetails = document.getElementById("paneDetails");
const paneRaw = document.getElementById("paneRaw");

let useCases = [];
let selectedCaseId = null;
let sessionId = null;
let events = [];
let visibleCount = 0;
let selectedEventId = null;
let isPlaying = false;
let playHandle = null;
let done = false;
let maxIterations = 0;
let iteration = 0;

function jsonBlock(value) {
  return `<pre class="json">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function api(path, method = "GET", body = null) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Request failed");
  }
  return res.json();
}

async function loadHealth() {
  try {
    const data = await api("/health");
    modelBadgeEl.textContent = `Model: ${data.model.split("/").pop()} (${data.device})`;
  } catch {
    modelBadgeEl.textContent = "Model: unavailable";
  }
}

function renderUseCases() {
  caseListEl.innerHTML = "";
  useCases.forEach((item) => {
    const card = document.createElement("button");
    card.className = `case-card${selectedCaseId === item.id ? " active" : ""}`;
    card.innerHTML = `
      <div class="case-title">${item.icon} ${escapeHtml(item.title)}</div>
      <div class="case-desc">${escapeHtml(item.description)}</div>
    `;
    card.addEventListener("click", () => selectUseCase(item.id));
    caseListEl.appendChild(card);
  });
}

async function loadUseCases() {
  const data = await api("/use-cases");
  useCases = data.use_cases || [];
  if (useCases.length && !selectedCaseId) selectedCaseId = useCases[0].id;
  renderUseCases();
  setControlsEnabled(Boolean(selectedCaseId));
}

function setControlsEnabled(enabled) {
  btnPlay.disabled = !enabled;
  btnNext.disabled = !enabled;
  btnReset.disabled = !enabled;
  btnPrev.disabled = !enabled;
}

function stopPlay() {
  isPlaying = false;
  btnPlay.textContent = "Play";
  if (playHandle) {
    clearInterval(playHandle);
    playHandle = null;
  }
}

async function resetSession() {
  stopPlay();
  if (sessionId) {
    try {
      await api("/session/reset", "POST", { session_id: sessionId });
    } catch {
      // best effort
    }
  }
  sessionId = null;
  events = [];
  visibleCount = 0;
  selectedEventId = null;
  done = false;
  iteration = 0;
  maxIterations = 0;
  renderFlow();
  renderDetail(null);
  updateProgress();
}

async function selectUseCase(caseId) {
  selectedCaseId = caseId;
  renderUseCases();
  await resetSession();
}

async function ensureSessionStarted() {
  if (!selectedCaseId || sessionId) return;
  const data = await api("/session/start", "POST", { use_case_id: selectedCaseId });
  sessionId = data.session_id;
  events = data.events || [];
  visibleCount = Math.min(1, events.length);
  selectedEventId = events.length ? events[0].id : null;
  done = data.done;
  iteration = data.iteration || 0;
  maxIterations = data.max_iterations || 0;
  renderFlow();
  renderDetail(events[0] || null);
  updateProgress();
}

function eventIcon(type) {
  if (type === "system") return "⚙️";
  if (type === "user") return "👤";
  if (type === "planning") return "🧠";
  if (type === "tool_call") return "🔧";
  if (type === "tool_result") return "📦";
  if (type === "response") return "💬";
  return "🔄";
}

function renderFlow() {
  flowScrollEl.innerHTML = "";
  if (!events.length || visibleCount === 0) {
    flowScrollEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">👈</div>
        <div class="empty-title">Pick a use case to begin</div>
        <div class="empty-sub">Then click Play or Next to run the backend loop.</div>
      </div>
    `;
    return;
  }

  const shown = events.slice(0, visibleCount);
  shown.forEach((item, idx) => {
    const card = document.createElement("div");
    const cls = `step-card type-${item.type}${selectedEventId === item.id ? " active" : ""}`;
    card.className = cls;
    card.innerHTML = `
      <div class="step-header">
        <span>${eventIcon(item.type)}</span>
        <span>${escapeHtml(item.label)}</span>
      </div>
      <div class="step-summary">${escapeHtml(item.summary)}</div>
    `;
    card.addEventListener("click", () => {
      selectedEventId = item.id;
      renderFlow();
      renderDetail(item);
    });
    flowScrollEl.appendChild(card);

    if (idx < shown.length - 1) {
      const arrow = document.createElement("div");
      arrow.className = "arrow";
      flowScrollEl.appendChild(arrow);
    }
  });

  flowScrollEl.scrollTop = flowScrollEl.scrollHeight;
}

function renderDetail(item) {
  if (!item) {
    detailContentEl.className = "pane-content empty";
    detailContentEl.textContent = "Click a step card to inspect details.";
    rawContentEl.className = "pane-content empty";
    rawContentEl.textContent = "Click a step card to inspect payloads.";
    return;
  }

  detailContentEl.className = "pane-content";
  const detailRows = Object.entries(item.detail || {})
    .map(([k, v]) => `
      <div class="detail-field">
        <div class="detail-key">${escapeHtml(k)}</div>
        <div class="detail-val">${escapeHtml(v)}</div>
      </div>
    `)
    .join("");

  detailContentEl.innerHTML = `
    <div class="detail-field">
      <div class="detail-key">Summary</div>
      <div class="detail-val">${escapeHtml(item.summary || "")}</div>
    </div>
    <div class="detail-field">
      <div class="detail-key">Content</div>
      <div class="detail-val">${escapeHtml(item.content || "")}</div>
    </div>
    ${detailRows}
  `;

  rawContentEl.className = "pane-content";
  const raw = item.raw || {};
  const requestHtml = raw.request ? jsonBlock(raw.request) : "<div class='detail-val'>No request payload.</div>";
  const responseHtml = raw.response ? jsonBlock(raw.response) : "<div class='detail-val'>No response payload.</div>";
  const noteHtml = raw.note ? `<div class='detail-field'><div class='detail-key'>Note</div><div class='detail-val'>${escapeHtml(raw.note)}</div></div>` : "";
  rawContentEl.innerHTML = `
    <div class="detail-field">
      <div class="detail-key">Request</div>
      ${requestHtml}
    </div>
    <div class="detail-field">
      <div class="detail-key">Response</div>
      ${responseHtml}
    </div>
    ${noteHtml}
  `;
}

function updateProgress() {
  const total = Math.max(events.length, 1);
  const current = Math.min(visibleCount, total);
  const pct = (current / total) * 100;
  progressFillEl.style.width = `${pct}%`;
  stepCounterEl.textContent = `${current} / ${events.length}`;
  btnPrev.disabled = visibleCount <= 1;
}

async function generateStep() {
  if (!sessionId || done) return;
  const data = await api("/session/step", "POST", { session_id: sessionId });
  events = data.events || events;
  done = data.done;
  iteration = data.iteration || iteration;
  maxIterations = data.max_iterations || maxIterations;
}

async function stepForward() {
  await ensureSessionStarted();

  if (visibleCount < events.length) {
    visibleCount += 1;
    selectedEventId = events[visibleCount - 1].id;
    renderFlow();
    renderDetail(events[visibleCount - 1]);
    updateProgress();
    return;
  }

  if (done) {
    stopPlay();
    return;
  }

  await generateStep();
  if (visibleCount < events.length) {
    visibleCount += 1;
    selectedEventId = events[visibleCount - 1].id;
    renderFlow();
    renderDetail(events[visibleCount - 1]);
    updateProgress();
  }
  if (done) stopPlay();
}

function stepBack() {
  if (visibleCount <= 1) return;
  visibleCount -= 1;
  selectedEventId = events[visibleCount - 1].id;
  renderFlow();
  renderDetail(events[visibleCount - 1]);
  updateProgress();
}

function togglePlay() {
  if (isPlaying) {
    stopPlay();
    return;
  }
  isPlaying = true;
  btnPlay.textContent = "Pause";
  playHandle = setInterval(() => {
    stepForward().catch((err) => {
      stopPlay();
      console.error(err);
    });
  }, 900);
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((x) => x.classList.remove("active"));
    btn.classList.add("active");
    if (btn.dataset.tab === "details") {
      paneDetails.classList.add("active");
      paneRaw.classList.remove("active");
    } else {
      paneRaw.classList.add("active");
      paneDetails.classList.remove("active");
    }
  });
});

btnReset.addEventListener("click", resetSession);
btnPrev.addEventListener("click", stepBack);
btnNext.addEventListener("click", () => stepForward().catch(console.error));
btnPlay.addEventListener("click", togglePlay);

loadHealth().catch(console.error);
loadUseCases().catch(console.error);
