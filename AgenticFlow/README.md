# Agentic Loop Explorer

Interactive demo that visualizes an agentic backend loop step by step:

- system prompt + tool registration
- user query
- planning/reasoning summary
- tool call and tool result
- final response

The backend uses a local Hugging Face model and deterministic mock tools.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Run backend

```bash
HF_TOKEN=your_hf_token uv run server.py
```

Optional model override:

```bash
MODEL_ID=google/gemma-4-E4B-it HF_TOKEN=your_hf_token uv run server.py
```

Backend runs on `http://localhost:8001`.

## Run frontend

Open `index.html` directly in your browser.

The frontend is hardcoded to `http://localhost:8001` in `app.js`.
