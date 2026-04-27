# SimpleAgent (Ollama)

Minimal demos of tool-calling agents using local Ollama inference (`gemma4:latest` by default).

## Files

- `ollama_core.py` - shared Ollama client + generic `Agent` runtime
- `ollama_agents_from_scratch.py` - weather mock tool demo (`get_temperature`)
- `ollama_search_agent.py` - search agent demo (`web_search`, `web_fetch`)
- `fluxo-agente-pesquisa.md` - target research-agent behavior
- `01_agents_from_scratch.ipynb` - original notebook reference

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Run

Weather demo:

```bash
uv run python ollama_agents_from_scratch.py --prompt "what is the weather in tokyo?"
```

Search demo:

```bash
uv run python ollama_search_agent.py --prompt "Top 3 agentic AI trends in 2025 with sources"
```

Enable full loop trace in either demo:

```bash
uv run python ollama_search_agent.py --trace
```

`--trace` now includes user input, assistant raw message, tool executions, and any available planning/reasoning text from the model.

Render final answer as markdown in terminal (default) or raw text:

```bash
uv run python ollama_search_agent.py --render-markdown
uv run python ollama_search_agent.py --raw
```

Both scripts support:

- `--model` (default: `gemma4:latest`)
- `--base-url` (default: `http://localhost:11434/v1`)
- `--timeout` (default: `120` seconds)
- `--prompt`
- `--trace`
- `--render-markdown` / `--raw`
