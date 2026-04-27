# SimpleAgent (Ollama)

Minimal demos of tool-calling agents using local Ollama inference (`gemma4:latest` by default).

## Files

- `ollama_core.py` - shared Ollama client + generic `Agent` runtime
- `ollama_agents_from_scratch.py` - weather mock tool demo (`get_temperature`)
- `ollama_search_agent.py` - search agent demo (`web_search`, `web_fetch`)
- `ollama_orchestrator_agent.py` - multi-agent orchestrator (delegates to weather/search agents)
- `ollama_orchestrator_agent_copy.py` - preserved copy of orchestrator before dynamic tool loader refactor
- `ollama_single_agent_skills.py` - single agent with on-demand skill loading via `load_skill` tool call
- `skills/weather/SKILL.md` - weather skill definition
- `skills/search/SKILL.md` - search skill definition
- `skills/planner/SKILL.md` - planning/roadmap skill definition
- `tools/*/{TOOL.md,schema.json,handler.py}` - tool skeletons loaded dynamically at runtime
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

Orchestrator demo (delegates to weather/search sub-agents):

```bash
uv run python ollama_orchestrator_agent.py --prompt "What's the weather in Tokyo, and summarize the latest agentic AI trends?"
```

Orchestrator demo with dynamic tool skeleton loading:

```bash
uv run python ollama_orchestrator_agent.py --tools-root tools --trace
```

Single-agent skills demo (`load_skill` activates skill details and tools on demand):

```bash
uv run python ollama_single_agent_skills.py --prompt "What's the weather in Tokyo, and summarize the latest agentic AI trends?"
```

Planner-focused example:

```bash
uv run python ollama_single_agent_skills.py --prompt "Build a 5-day plan to prepare a class on agentic AI" --trace
```

Single-agent skills demo with explicit skills/tools roots:

```bash
uv run python ollama_single_agent_skills.py --skills-root skills --tools-root tools --trace
```

Evaluate orchestrator routing/output accuracy using a test set:

```bash
uv run python evaluate_orchestrator.py
```

Run only first 2 cases while tuning prompts:

```bash
uv run python evaluate_orchestrator.py --max-cases 2
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
- `--skills-root` (default: `skills`)
- `--tools-root` (default: `tools`)
- `--prompt`
- `--trace`
- `--render-markdown` / `--raw`
