# AGENTS.md

## Repo Layout (what is actually runnable)
- `Tokenization/` and `AgenticFlow/` are code-backed apps (FastAPI backend + static frontend).
- `Training_Stages/llm_training.html` and `agentic_flow.html` are standalone HTML demos (open directly in browser, no build/dev server).
- Root `README.md` is minimal; rely on per-app READMEs and `server.py` files for real behavior.

## Tokenization App: Correct Run Flow
- Work from `Tokenization/` when running the app.
- Setup: `uv venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- Start backend: `HF_TOKEN=... uv run server.py`
- Optional model override: `MODEL_ID=google/gemma-4-E4B-it HF_TOKEN=... uv run server.py`
- Frontend has no build step: open `Tokenization/index.html` directly.

## AgenticFlow App: Correct Run Flow
- Work from `AgenticFlow/` when running the app.
- Setup: `uv venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- Start backend: `HF_TOKEN=... uv run server.py`
- Optional model override: `MODEL_ID=google/gemma-4-E4B-it HF_TOKEN=... uv run server.py`
- Frontend has no build step: open `AgenticFlow/index.html` directly.

## Verified Backend/Frontend Contract
- Backend binds to `0.0.0.0:8000` (`server.py`), and frontend is hardcoded to `http://localhost:8000` in `Tokenization/app.js`.
- If backend port/host changes, update `API_BASE` in `Tokenization/app.js` or the UI will fail.
- Core generation flow uses `POST /tokenize` and `POST /step`; UI also depends on `GET /info` and `GET /vocab` for model/tokenizer modals.
- `/step` is stateless: each call re-sends prompt + generated text and re-runs a full forward pass (no KV cache).
- AgenticFlow backend binds to `0.0.0.0:8001`, and frontend is hardcoded to `http://localhost:8001` in `AgenticFlow/app.js`.
- AgenticFlow UI loop depends on `GET /use-cases`, `POST /session/start`, `POST /session/step`, `GET /session/{id}`, and `POST /session/reset`.

## Runtime Quirks That Matter
- `HF_TOKEN` is optional in code but required in practice for Gemma downloads; missing license acceptance/token access causes model load failure at startup.
- Device/dtype are selected automatically in `server.py`: CUDA -> bfloat16, MPS/CPU -> float32.
- EOS is treated as `eos_token_id` or token string `<end_of_turn>`.

## Verification (no formal test/lint config in repo)
- Health check after backend start: `curl http://localhost:8000/health`
- Quick UI check: open `Tokenization/index.html`, click **Tokenize Prompt**, then **Generate Next Token**.
- AgenticFlow health check: `curl http://localhost:8001/health`
- AgenticFlow UI check: open `AgenticFlow/index.html`, select a case, click **Next** to see planning -> tool call -> tool result -> final response cards.
