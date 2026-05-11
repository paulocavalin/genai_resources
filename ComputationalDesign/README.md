# AI-Driven Computational Design Pipeline

An end-to-end agentic design pipeline: describe a project in natural language and get back parametric CAD code, a 3D preview, print settings, and a sourced Bill of Materials — all generated via the HuggingFace Inference API using Gemma 4.

## What it teaches

- **LLM as a code generator** — the agent writes OpenSCAD source code, not just descriptions
- **External tool integration** — OpenSCAD CLI is invoked as a pipeline step (subprocess)
- **Iterative refinement** — generated code is optimized for printability in a separate pass
- **Structured output** — each pipeline stage returns typed JSON, not free text
- **Graceful degradation** — pipeline continues even if OpenSCAD isn't installed

## 5-Stage Iterative Pipeline

| # | Stage | What it does |
|---|-------|-------------|
| 🎯 01 | **Design Brief** | Extracts/refines structured spec (dimensions, material, features, hardware) |
| 🔧 02 | **Parametric Model** | Generates OpenSCAD source code with variables and modules |
| 🖼 03 | **Render & Export** | Runs OpenSCAD CLI → PNG preview + STL file |
| 📐 04 | **Print Settings** | Recommends slicer config (layer height, infill, supports, temps) |
| 🛒 05 | **BOM & Sourcing** | Generates Bill of Materials with catalog matches and prices |

The pipeline is **iterative**: after a run completes, the user can provide refinement prompts (e.g. "make it taller", "add ventilation slots") and the pipeline re-runs with full conversation context.

## Setup

### Prerequisites

- A [HuggingFace](https://huggingface.co) account with an API token (`HF_TOKEN`). You must accept the [Gemma 4 license](https://huggingface.co/google/gemma-4-E4B-it) before using the model.
- (Optional but recommended) [OpenSCAD](https://openscad.org/downloads.html) for 3D rendering. The pipeline works without it — the .scad code is still generated and downloadable.

### Install & Run

```bash
cd ComputationalDesign
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
HF_TOKEN=your_hf_token uv run uvicorn server:app --port 8004 --reload
```

Then open `index.html` in your browser, or visit `http://localhost:8004`.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | *(required)* | HuggingFace API token |
| `MODEL_ID` | `google/gemma-4-31B-it` | Model for all pipeline LLM calls |
| `HF_PROVIDER` | `novita` | HuggingFace inference provider (novita, together, fireworks, etc.) |
| `HF_TIMEOUT` | `300` | Seconds per LLM call |

## Example prompts

- *A wall-mount holder for a Raspberry Pi 4 with ventilation slots and a magnetic front cover*
- *A parametric gear box with 4:1 ratio, 3mm input and 5mm output shafts, fits 60×60×40mm*
- *A snap-fit enclosure for an Arduino Uno with USB access, power jack, and ventilation slots*
- *A modular desktop pen organizer with 3 compartments and a 65° phone cradle*

## Architecture

```
User (browser)
    │  POST /design  {description}
    ▼
FastAPI (server.py, port 8004)
    │  asyncio.create_task(_run_pipeline)
    │
    ├─ stage_brief()       → HF Inference API  → structured JSON
    ├─ stage_generate_scad() → HF Inference API  → OpenSCAD source
    ├─ stage_render()      → openscad CLI      → PNG + STL files
    ├─ stage_print_settings() → HF Inference API  → slicer config
    └─ stage_source_parts() → HF API + PARTS_CATALOG → BOM
    │
    │  GET /design/{id}/stream  (Server-Sent Events)
    ▼
Browser (app.js)
    ├─ Updates stage cards in real-time
    ├─ Syntax-highlights OpenSCAD code (highlight.js)
    ├─ Loads STL into Three.js 3D viewer with OrbitControls
    └─ Renders BOM table
```

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/design` | Start pipeline, returns `{id}` |
| `GET`  | `/design/{id}/stream` | SSE stream of pipeline events |
| `GET`  | `/design/{id}/png` | Rendered PNG preview |
| `GET`  | `/design/{id}/stl` | Exported STL file |
| `GET`  | `/design/{id}/scad` | Generated OpenSCAD source |

## Design language: OpenSCAD vs. alternatives

OpenSCAD was chosen because its declarative CSG syntax is compact and predictable for LLM generation. CadQuery (Python) is more powerful but produces longer, harder-to-validate code for a single-shot prompt.

```openscad
// OpenSCAD — easy for LLMs to generate correctly
wall_t = 2.0;
difference() {
    cube([box_w, box_d, box_h]);
    translate([wall_t, wall_t, wall_t])
        cube([box_w - wall_t*2, box_d - wall_t*2, box_h]);
}
```

## Notes

- The generated OpenSCAD code is LLM output — always review before sending to a printer
- Pipeline runs all 5 stages sequentially; expect 2–4 minutes per design depending on model and provider
- The parts catalog is simulated (fictional SKUs and prices) — replace `PARTS_CATALOG` in `server.py` with real supplier data for production use
