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
const probsEl = document.getElementById("probabilities");

const API_BASE = "http://localhost:8000";

let promptTokens = [];
let generatedTokens = [];
let generatedText = "";
let isAuto = false;
let autoHandle = null;

function renderTokens(container, tokens, isGenerated = false) {
  container.innerHTML = "";
  tokens.forEach(token => {
    const span = document.createElement("span");
    span.className = `token${isGenerated ? " generated" : ""}`;
    span.textContent = token;
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
    renderTokens(promptTokensEl, promptTokens);
  } catch (err) {
    promptTokens = [];
    renderTokens(promptTokensEl, []);
    liveOutputEl.textContent = `Tokenization failed: ${err.message}`;
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
    updateProbabilities(data.top_probs || []);

    generatedText = data.generated_text || "";
    liveOutputEl.textContent = (prompt + generatedText).trim();

    if (data.eos) {
      stopAuto();
    }
  } catch (err) {
    stopAuto();
    liveOutputEl.textContent = `Generation failed: ${err.message}`;
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
  autoHandle = setInterval(generateNext, 900);
}

function resetAll() {
  promptTokens = [];
  generatedTokens = [];
  generatedText = "";
  renderTokens(promptTokensEl, []);
  renderTokens(generatedTokensEl, []);
  liveOutputEl.textContent = "";
  probsEl.innerHTML = "";
  stopAuto();
}

tokenizeBtn.addEventListener("click", handleTokenize);
resetBtn.addEventListener("click", resetAll);
stepBtn.addEventListener("click", generateNext);

autoBtn.addEventListener("click", () => {
  if (isAuto) stopAuto();
  else startAuto();
});

tempSlider.addEventListener("input", () => {
  tempValue.textContent = Number(tempSlider.value).toFixed(2);
});

tempValue.textContent = Number(tempSlider.value).toFixed(2);
handleTokenize();
