const promptInput = document.getElementById("promptInput");
const tokenizeBtn = document.getElementById("tokenizeBtn");
const resetBtn = document.getElementById("resetBtn");
const promptTokensEl = document.getElementById("promptTokens");
const generatedTokensEl = document.getElementById("generatedTokens");
const liveOutputEl = document.getElementById("liveOutput");
const stepBtn = document.getElementById("stepBtn");
const autoBtn = document.getElementById("autoBtn");
const tempSlider = document.getElementById("tempSlider");
const tempValue = document.getElementById("tempValue");
const maxTokensInput = document.getElementById("maxTokens");
const speedSlider = document.getElementById("speedSlider");
const speedValue = document.getElementById("speedValue");
const generatedCountEl = document.getElementById("generatedCount");
const mdToggle = document.getElementById("mdToggle");
const probsEl = document.getElementById("probabilities");
const tokenCountEl = document.getElementById("tokenCount");

const API_BASE = "http://localhost:8000";

const modelPill = document.getElementById("modelPill");
const tokenizerPill = document.getElementById("tokenizerPill");
const modalOverlay = document.getElementById("modalOverlay");
const modalTitle = document.getElementById("modalTitle");
const modalBody = document.getElementById("modalBody");
const modalClose = document.getElementById("modalClose");

let promptTokens = [];
let generatedTokens = [];
let generatedText = "";
let isAuto = false;
let autoHandle = null;
let serverInfo = null;
let vocabCache = null;

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openModal(title, html) {
  modalTitle.textContent = title;
  modalBody.innerHTML = html;
  modalOverlay.classList.add("active");
}

function closeModal() {
  modalOverlay.classList.remove("active");
}

async function fetchInfo() {
  try {
    const res = await fetch(`${API_BASE}/info`);
    serverInfo = await res.json();
    document.getElementById("modelName").textContent = serverInfo.model.id.split("/").pop();
    document.getElementById("tokenizerName").textContent = serverInfo.tokenizer.class;
  } catch {
    document.getElementById("modelName").textContent = "unavailable";
    document.getElementById("tokenizerName").textContent = "unavailable";
  }
}

function showModelModal() {
  if (!serverInfo) return;
  const m = serverInfo.model;
  openModal("Model Details", `
    <table class="info-table">
      <tr><td>Model ID</td><td class="mono">${escapeHtml(m.id)}</td></tr>
      <tr><td>Architecture</td><td class="mono">${escapeHtml(m.architecture)}</td></tr>
      <tr><td>Device</td><td class="mono">${escapeHtml(m.device)}</td></tr>
      <tr><td>Dtype</td><td class="mono">${escapeHtml(m.dtype)}</td></tr>
      <tr><td>Parameters</td><td class="mono">${m.num_parameters.toLocaleString()}</td></tr>
    </table>
  `);
}

async function showTokenizerModal() {
  if (!serverInfo) return;
  const t = serverInfo.tokenizer;

  const specialRows = Object.entries(t.special_tokens)
    .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td class="mono">${escapeHtml(v)}</td></tr>`)
    .join("");

  openModal("Tokenizer Details", `
    <table class="info-table">
      <tr><td>Class</td><td class="mono">${escapeHtml(t.class)}</td></tr>
      <tr><td>Vocab size</td><td class="mono">${t.vocab_size.toLocaleString()}</td></tr>
      <tr><td>Max length</td><td class="mono">${t.model_max_length.toLocaleString()}</td></tr>
    </table>
    <h3 class="modal-section-title">Special Tokens</h3>
    <table class="info-table">${specialRows}</table>
    <h3 class="modal-section-title">Vocabulary</h3>
    <input class="vocab-search" id="vocabSearch" placeholder="Search by token or ID…" />
    <div class="vocab-list" id="vocabList"><div class="vocab-loading">Loading vocabulary…</div></div>
  `);

  if (!vocabCache) {
    try {
      const res = await fetch(`${API_BASE}/vocab`);
      const data = await res.json();
      vocabCache = data.vocab;
    } catch {
      vocabCache = [];
    }
  }

  renderVocab("");
  document.getElementById("vocabSearch").addEventListener("input", e => renderVocab(e.target.value.trim()));
}

function renderVocab(query) {
  const list = document.getElementById("vocabList");
  if (!list) return;
  if (!vocabCache.length) { list.innerHTML = "<div class='vocab-loading'>Failed to load vocabulary.</div>"; return; }

  const q = query.toLowerCase();
  const filtered = q
    ? vocabCache.filter(e => e.token.toLowerCase().includes(q) || String(e.id).includes(q))
    : vocabCache;

  const shown = filtered.slice(0, 300);
  const extra = filtered.length - shown.length;
  list.innerHTML = shown.map(e =>
    `<div class="vocab-row"><span class="vocab-token">${escapeHtml(e.token)}</span><span class="vocab-id">${e.id}</span></div>`
  ).join("") + (extra > 0 ? `<div class="vocab-more">…and ${extra.toLocaleString()} more — refine your search</div>` : "");
}

function setLiveOutput(text) {
  if (mdToggle.checked) {
    liveOutputEl.innerHTML = marked.parse(text);
    liveOutputEl.classList.add("output-md");
  } else {
    liveOutputEl.textContent = text;
    liveOutputEl.classList.remove("output-md");
  }
  liveOutputEl.scrollTop = liveOutputEl.scrollHeight;
}

mdToggle.addEventListener("change", () => {
  const text = liveOutputEl.textContent || liveOutputEl.innerText;
  setLiveOutput(text);
});

modelPill.addEventListener("click", showModelModal);
tokenizerPill.addEventListener("click", showTokenizerModal);
modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", e => { if (e.target === modalOverlay) closeModal(); });

function renderTokens(container, tokens, isGenerated = false, ids = []) {
  container.innerHTML = "";
  tokens.forEach((token, i) => {
    const span = document.createElement("span");
    span.className = `token${isGenerated ? " generated" : ""}`;
    const text = document.createElement("span");
    text.className = "token-text";
    text.textContent = token;
    span.appendChild(text);
    if (ids.length) {
      const id = document.createElement("span");
      id.className = "token-id";
      id.textContent = ids[i];
      span.appendChild(id);
    }
    container.appendChild(span);
  });
}

function updateProbabilities(probabilities) {
  probsEl.innerHTML = "";
  probabilities.forEach(item => {
    const row = document.createElement("div");
    row.className = "prob-row";

    const label = document.createElement("div");
    label.textContent = item.token;

    const bar = document.createElement("div");
    bar.className = "prob-bar";

    const fill = document.createElement("div");
    fill.className = "prob-fill";
    fill.style.width = `${(item.prob * 100).toFixed(1)}%`;

    bar.appendChild(fill);

    const value = document.createElement("div");
    value.textContent = `${(item.prob * 100).toFixed(1)}%`;

    row.appendChild(label);
    row.appendChild(bar);
    row.appendChild(value);
    probsEl.appendChild(row);
  });
}

async function apiPost(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Request failed");
  }

  return res.json();
}

async function handleTokenize() {
  generatedTokens = [];
  generatedText = "";
  renderTokens(generatedTokensEl, []);
  liveOutputEl.textContent = "";

  const prompt = promptInput.value;
  try {
    const data = await apiPost("/tokenize", { prompt });
    promptTokens = data.tokens || [];
    renderTokens(promptTokensEl, promptTokens, false, data.token_ids || []);
    tokenCountEl.textContent = `${promptTokens.length} token${promptTokens.length !== 1 ? "s" : ""}`;
  } catch (err) {
    promptTokens = [];
    renderTokens(promptTokensEl, []);
    tokenCountEl.textContent = "";
    setLiveOutput(`Tokenization failed: ${err.message}`);
  }
}

async function generateNext() {
  if (!promptTokens.length) {
    await handleTokenize();
  }

  if (generatedTokens.length >= Number(maxTokensInput.value || 0)) {
    stopAuto();
    return;
  }

  const prompt = promptInput.value;
  const temperature = Number(tempSlider.value);

  try {
    const data = await apiPost("/step", {
      prompt,
      generated_text: generatedText,
      temperature,
      top_k: 8,
    });

    generatedTokens = data.generated_tokens || [];
    renderTokens(generatedTokensEl, generatedTokens, true);
    generatedCountEl.textContent = `${generatedTokens.length} token${generatedTokens.length !== 1 ? "s" : ""}`;
    updateProbabilities(data.top_probs || []);

    generatedText = data.generated_text || "";
    setLiveOutput((prompt + generatedText).trim());

    if (data.eos) {
      stopAuto();
    }
  } catch (err) {
    stopAuto();
    setLiveOutput(`Generation failed: ${err.message}`);
  }
}

function stopAuto() {
  isAuto = false;
  autoBtn.textContent = "Auto Play";
  if (autoHandle) {
    clearInterval(autoHandle);
    autoHandle = null;
  }
}

function startAuto() {
  if (isAuto) return;
  isAuto = true;
  autoBtn.textContent = "Stop";
  autoHandle = setInterval(generateNext, Number(speedSlider.value));
}

function resetInference() {
  generatedTokens = [];
  generatedText = "";
  generatedCountEl.textContent = "";
  renderTokens(generatedTokensEl, []);
  setLiveOutput("");
  probsEl.innerHTML = "";
  stopAuto();
}

function resetAll() {
  promptTokens = [];
  tokenCountEl.textContent = "";
  renderTokens(promptTokensEl, []);
  resetInference();
}

tokenizeBtn.addEventListener("click", handleTokenize);
resetBtn.addEventListener("click", resetAll);
document.getElementById("resetInferenceBtn").addEventListener("click", resetInference);
stepBtn.addEventListener("click", generateNext);

autoBtn.addEventListener("click", () => {
  if (isAuto) stopAuto();
  else startAuto();
});

tempSlider.addEventListener("input", () => {
  tempValue.textContent = Number(tempSlider.value).toFixed(2);
});

speedSlider.addEventListener("input", () => {
  const ms = Number(speedSlider.value);
  speedValue.textContent = (ms / 1000).toFixed(2).replace(/\.?0+$/, "") + "s";
  if (isAuto) {
    clearInterval(autoHandle);
    autoHandle = setInterval(generateNext, ms);
  }
});

tempValue.textContent = Number(tempSlider.value).toFixed(2);
speedValue.textContent = (Number(speedSlider.value) / 1000).toFixed(1) + "s";
fetchInfo();
handleTokenize();
