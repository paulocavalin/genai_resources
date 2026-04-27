# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Visual demo of LLM inference mechanics: tokenization, token-by-token generation, and top-k probability sampling. FastAPI backend loads a local Hugging Face model (default: `google/gemma-4-E2B-it`); static HTML/CSS/JS frontend communicates with it directly.

## Setup & Running

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

HF_TOKEN=your_hf_token uv run server.py
# Optional: override model
MODEL_ID=google/gemma-4-E4B-it HF_TOKEN=your_hf_token uv run server.py
```

Open `index.html` directly in the browser (no build step). API runs on `http://localhost:8000`.

## Architecture

**Backend (`server.py`)** — FastAPI app that loads the model at startup (model/tokenizer are module-level globals). Three endpoints:
- `GET /health` — returns model ID and device
- `POST /tokenize` — tokenizes a prompt, returns token strings (no special tokens)
- `POST /step` — takes `{prompt, generated_text, temperature, top_k}`, runs one forward pass, samples the next token via `torch.multinomial`, returns the token, updated generated text, generated token list, top-k probabilities, and EOS flag

Device selection: CUDA → MPS → CPU. dtype: bfloat16 on CUDA, float32 otherwise. BOS token is prepended to every forward pass. EOS is detected by `eos_token_id` or `<end_of_turn>` token string.

**Frontend (`index.html` + `styles.css` + `app.js`)** — Static files opened directly in browser. `app.js` calls `/tokenize` on button click and `/step` iteratively for generation. Note: `app.js` is referenced in `index.html` but may need to be created if missing.

## Notes

- Gemma models require accepting the license on Hugging Face before the token will grant download access.
- The `/step` endpoint is stateless — the full prompt + generated text is re-sent each call, and the model re-processes the entire sequence every step (no KV cache).
