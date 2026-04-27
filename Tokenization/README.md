# LLM Inference Explorer

A small, visual demo that shows how LLM inference works step‑by‑step:

- Prompt tokenization
- Token‑by‑token generation
- Live probability bars (top‑k)
- Temperature control
- Real model inference via a local Python `transformers` backend

## What’s Included

- `index.html` — UI
- `styles.css` — Styling
- `app.js` — Frontend logic
- `server.py` — FastAPI backend using `transformers`
- `requirements.txt` — Python deps

## Prerequisites

- Python 3.10+
- A Hugging Face token with access to Gemma 4

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Run the Backend

```bash
HF_TOKEN=your_hf_token uv run server.py
```

You can override the model if desired:

```bash
MODEL_ID=google/gemma-4-E4B-it HF_TOKEN=your_hf_token uv run server.py
```

The API runs on `http://localhost:8000`.

## Run the Frontend

Open `index.html` in your browser.

## How It Works

- The frontend calls `/tokenize` to display the prompt tokens.
- Each step calls `/step` for a single next‑token sample with temperature applied.
- The backend returns the top‑k token probabilities and the sampled token.
- Generation stops on EOS or `<end_of_turn>`.

## Notes

- The root API route (`/`) returns a small JSON status message.
- If you see a Hugging Face license prompt for Gemma, accept it on the Hugging Face site first.
