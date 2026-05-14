"""
ComputationalDesign/server.py
AI-Driven Computational Design Pipeline — FastAPI backend on port 8004.

5-stage agentic pipeline (iterative):
  1  Brief          — extract/refine structured spec from natural language
  2  Model          — generate parametric OpenSCAD source code
  3  Render         — PNG preview + STL export via OpenSCAD CLI
  4  Print Settings — slicer recommendations
  5  BOM & Sourcing — bill of materials matched against parts catalog

Run:
  uv run uvicorn server:app --port 8004 --reload
  # then open index.html in browser or visit http://localhost:8004
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from huggingface_hub import InferenceClient
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Computational Design Pipeline")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_STATIC = Path(__file__).parent

HF_TOKEN = os.getenv("HF_TOKEN")
MODEL    = os.getenv("MODEL_ID", "google/gemma-4-31B-it")
PROVIDER = os.getenv("HF_PROVIDER", "novita")
TIMEOUT  = int(os.getenv("HF_TIMEOUT", "300"))

def _make_client(timeout: int = TIMEOUT) -> InferenceClient:
    return InferenceClient(token=HF_TOKEN, provider=PROVIDER, timeout=timeout)

hf_client = _make_client()

# Design sessions: design_id → state dict
DESIGNS: Dict[str, Dict] = {}

# ── Simulated parts catalog ───────────────────────────────────────────────────

PARTS_CATALOG = [
    {"sku": "HW-M3x8",   "name": "M3×8mm Socket Head Cap Screw",    "category": "fastener", "unit": "50 pcs",  "price_brl": 12.90},
    {"sku": "HW-M3x16",  "name": "M3×16mm Socket Head Cap Screw",   "category": "fastener", "unit": "50 pcs",  "price_brl": 14.50},
    {"sku": "HW-M3x25",  "name": "M3×25mm Socket Head Cap Screw",   "category": "fastener", "unit": "50 pcs",  "price_brl": 16.00},
    {"sku": "HW-M3N",    "name": "M3 Hex Nut",                      "category": "fastener", "unit": "100 pcs", "price_brl": 8.50},
    {"sku": "HW-M3I",    "name": "M3 Brass Heat-Set Insert (4×5mm)","category": "insert",   "unit": "50 pcs",  "price_brl": 28.00},
    {"sku": "HW-M4x10",  "name": "M4×10mm Button Head Screw",       "category": "fastener", "unit": "50 pcs",  "price_brl": 15.90},
    {"sku": "HW-M4N",    "name": "M4 Hex Nut",                      "category": "fastener", "unit": "100 pcs", "price_brl": 9.80},
    {"sku": "HW-M4I",    "name": "M4 Brass Heat-Set Insert",        "category": "insert",   "unit": "50 pcs",  "price_brl": 32.00},
    {"sku": "FIL-PLA-WH","name": "PLA Filament 1kg White",          "category": "filament", "unit": "spool",   "price_brl": 79.90},
    {"sku": "FIL-PLA-BK","name": "PLA Filament 1kg Black",          "category": "filament", "unit": "spool",   "price_brl": 79.90},
    {"sku": "FIL-PLA-GR","name": "PLA Filament 1kg Gray",           "category": "filament", "unit": "spool",   "price_brl": 79.90},
    {"sku": "FIL-PETG-GR","name":"PETG Filament 1kg Gray",          "category": "filament", "unit": "spool",   "price_brl": 119.90},
    {"sku": "FIL-PETG-BK","name":"PETG Filament 1kg Black",         "category": "filament", "unit": "spool",   "price_brl": 119.90},
    {"sku": "FIL-ABS-WH","name": "ABS Filament 1kg White",          "category": "filament", "unit": "spool",   "price_brl": 89.90},
    {"sku": "FIL-TPU-BK","name": "TPU 95A Flexible Filament 0.5kg", "category": "filament", "unit": "spool",   "price_brl": 99.90},
    {"sku": "HW-625ZZ",  "name": "625ZZ Miniature Ball Bearing",    "category": "bearing",  "unit": "2 pcs",   "price_brl": 22.00},
    {"sku": "HW-608ZZ",  "name": "608ZZ Skate Bearing (22×8×7mm)", "category": "bearing",  "unit": "2 pcs",   "price_brl": 12.00},
    {"sku": "HW-MGNET",  "name": "6mm×3mm Neodymium Disc Magnet",   "category": "magnet",   "unit": "20 pcs",  "price_brl": 18.00},
    {"sku": "HW-SPRING", "name": "5mm OD×15mm Compression Spring",  "category": "spring",   "unit": "10 pcs",  "price_brl": 14.00},
    {"sku": "HW-ROD3",   "name": "3mm Steel Smooth Rod (300mm)",    "category": "rod",      "unit": "2 pcs",   "price_brl": 19.00},
]
_CATALOG_BY_SKU = {p["sku"]: p for p in PARTS_CATALOG}

# ── LLM helpers ───────────────────────────────────────────────────────────────

def _llm(system: str, user: str, model: str = MODEL, timeout: int = TIMEOUT) -> str:
    client = _make_client(timeout) if timeout != TIMEOUT else hf_client
    response = client.chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=4096,
    )
    return str(response.choices[0].message.content)


def _llm_json(system: str, user: str, model: str = MODEL, timeout: int = TIMEOUT) -> Any:
    raw = _llm(system, user, model, timeout)
    # Extract JSON from markdown fences or raw text
    for pattern in (
        r'```(?:json)?\s*(\{.*?\})\s*```',
        r'```(?:json)?\s*(\[.*?\])\s*```',
        r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',  # nested one level
        r'(\{.*\})',
        r'(\[.*\])',
    ):
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON found in LLM response:\n{raw[:400]}")


# ── Pipeline stage functions ──────────────────────────────────────────────────

def stage_brief(description: str, model: str, timeout: int = TIMEOUT) -> Dict:
    system = textwrap.dedent("""
        You are a product design engineer. Extract a structured design brief.
        Return ONLY a valid JSON object — no explanation, no markdown:
        {
          "project_name": "short descriptive name",
          "purpose": "one sentence describing what it does",
          "dimensions": {"width_mm": 80, "height_mm": 50, "depth_mm": 30},
          "material": "PLA",
          "features": ["hinged lid", "cable routing slot"],
          "constraints": ["must fit standard 9V battery", "wall thickness >= 2mm"],
          "hardware": ["4x M3x8 screws", "4x M3 heat-set inserts"]
        }
        Use realistic defaults when dimensions are not specified.
        Material must be one of: PLA, PETG, ABS, TPU.
    """).strip()
    return _llm_json(system, f"Project description:\n{description}", model, timeout)


def stage_generate_scad(brief: Dict, model: str, timeout: int = TIMEOUT, extra_prompt: str = "") -> str:
    system = textwrap.dedent("""
        You are a parametric CAD engineer expert in OpenSCAD.
        Generate a complete, working OpenSCAD script for the design brief.

        REQUIREMENTS:
        - Variables at the top for ALL dimensions (wall_t, corner_r, etc.)
        - Modular structure: use module definitions for repeated shapes
        - Comments on each section
        - Printable geometry (manifold, no self-intersections)
        - Real geometry — no placeholder comments like "// add feature here"
        - Return ONLY the raw OpenSCAD code. No explanations. No markdown fences.
    """).strip()
    user_msg = f"Design brief:\n{json.dumps(brief, indent=2, ensure_ascii=False)}"
    if extra_prompt:
        user_msg += f"\n\nAdditional guidance: {extra_prompt}"
    raw = _llm(system, user_msg, model, timeout)
    # Strip any accidental markdown fences
    raw = re.sub(r'^```[a-z]*\s*', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip(), flags=re.MULTILINE)
    return raw.strip()


def stage_render(scad_code: str, design_id: str) -> Dict:
    """Run OpenSCAD CLI to produce PNG preview and STL file."""
    work_dir = Path(tempfile.gettempdir()) / "cd_pipeline" / design_id
    work_dir.mkdir(parents=True, exist_ok=True)

    scad_file = work_dir / "model.scad"
    png_file  = work_dir / "preview.png"
    stl_file  = work_dir / "model.stl"
    scad_file.write_text(scad_code, encoding="utf-8")

    openscad = shutil.which("openscad") or shutil.which("openscad-nightly")
    result: Dict[str, Any] = {
        "scad_path":          str(scad_file),
        "png_path":           None,
        "stl_path":           None,
        "openscad_available": openscad is not None,
        "render_error":       None,
    }

    if not openscad:
        result["render_error"] = (
            "OpenSCAD not found — install from openscad.org to enable rendering. "
            "The .scad code is still valid and can be opened in OpenSCAD manually."
        )
        return result

    def _run_openscad(args):
        return subprocess.run(
            [openscad] + args,
            check=True, timeout=90, capture_output=True,
        )

    # PNG preview — try modern --export-format flag first
    for png_args in (
        ["--export-format", "png", "--render", "-o", str(png_file), str(scad_file)],
        ["-o", str(png_file), str(scad_file)],
    ):
        try:
            _run_openscad(png_args)
            if png_file.exists():
                result["png_path"] = str(png_file)
                break
        except Exception:
            continue

    # STL export
    try:
        _run_openscad(["-o", str(stl_file), str(scad_file)])
        if stl_file.exists():
            result["stl_path"] = str(stl_file)
    except Exception as e:
        result["render_error"] = (result["render_error"] or "") + f" STL failed: {e}"

    return result


def stage_print_settings(brief: Dict, code: str, model: str, timeout: int = TIMEOUT, extra_prompt: str = "") -> Dict:
    system = textwrap.dedent("""
        You are a 3D printing specialist. Recommend slicer settings.
        Return ONLY a valid JSON object:
        {
          "material": "PLA",
          "nozzle_mm": 0.4,
          "layer_height_mm": 0.2,
          "first_layer_height_mm": 0.3,
          "infill_percent": 20,
          "infill_pattern": "gyroid",
          "wall_count": 3,
          "top_bottom_layers": 5,
          "supports": "none",
          "support_style": "tree",
          "bed_temp_c": 60,
          "nozzle_temp_c": 215,
          "print_speed_mms": 60,
          "cooling": "full",
          "orientation_tip": "one sentence on best print orientation",
          "estimated_time_hours": 2.5,
          "estimated_filament_g": 45,
          "notes": ["special consideration 1"]
        }
    """).strip()
    user = f"Design brief:\n{json.dumps(brief, indent=2, ensure_ascii=False)}"
    if extra_prompt:
        user += f"\n\nAdditional guidance: {extra_prompt}"
    return _llm_json(system, user, model, timeout)


def stage_source_parts(brief: Dict, model: str, timeout: int = TIMEOUT, extra_prompt: str = "") -> Dict:
    catalog_summary = "\n".join(
        f"  {p['sku']}: {p['name']} — {p['unit']} @ R${p['price_brl']:.2f}"
        for p in PARTS_CATALOG
    )
    system = textwrap.dedent(f"""
        You are a procurement engineer. Create a Bill of Materials for the design.

        Available catalog:
        {catalog_summary}

        Return ONLY a valid JSON object:
        {{
          "bom": [
            {{
              "item": "description",
              "qty": 4,
              "sku": "HW-M3x8",
              "unit": "50 pcs",
              "price_brl": 12.90,
              "notes": "optional"
            }}
          ],
          "total_estimated_brl": 95.80,
          "print_material_sku": "FIL-PLA-BK",
          "sourcing_notes": "any special note"
        }}

        Include the filament as a BOM line item.
        Estimate quantities realistically.
    """).strip()
    user = f"Design brief (hardware field is key):\n{json.dumps(brief, indent=2, ensure_ascii=False)}"
    if extra_prompt:
        user += f"\n\nAdditional guidance: {extra_prompt}"
    result = _llm_json(system, user, model, timeout)

    # Enrich BOM entries with real catalog data
    for item in result.get("bom", []):
        sku = item.get("sku")
        if sku and sku in _CATALOG_BY_SKU:
            cat = _CATALOG_BY_SKU[sku]
            item["unit"]      = cat["unit"]
            item["price_brl"] = cat["price_brl"]
            item["in_stock"]  = True

    return result


# ── Pipeline runner (async) ───────────────────────────────────────────────────


async def _run_pipeline(design_id: str, description: str, model: str, timeout: int = TIMEOUT) -> None:
    queue: asyncio.Queue = DESIGNS[design_id]["queue"]
    sp = DESIGNS[design_id].get("stage_prompts", {})

    async def emit(data: Dict) -> None:
        await queue.put(data)

    try:
        # Stage 1
        await emit({"stage": 1, "status": "running"})
        desc = description
        if sp.get(1):
            desc += f"\n\nAdditional guidance: {sp[1]}"
        brief = await asyncio.to_thread(stage_brief, desc, model, timeout)
        DESIGNS[design_id]["brief"] = brief
        await emit({"stage": 1, "status": "done", "data": brief})

        # Stage 2
        await emit({"stage": 2, "status": "running"})
        scad_code = await asyncio.to_thread(
            stage_generate_scad, brief, model, timeout, sp.get(2, "")
        )
        DESIGNS[design_id]["scad_code"] = scad_code
        await emit({"stage": 2, "status": "done", "data": {"scad_code": scad_code}})

        # Stage 3
        await emit({"stage": 3, "status": "running"})
        render = await asyncio.to_thread(stage_render, scad_code, design_id)
        DESIGNS[design_id]["render"] = render
        await emit({"stage": 3, "status": "done", "data": {
            "has_png":             render["png_path"] is not None,
            "has_stl":             render["stl_path"] is not None,
            "openscad_available":  render["openscad_available"],
            "render_error":        render.get("render_error"),
        }})

        # Stage 4 — Print Settings
        await emit({"stage": 4, "status": "running"})
        settings = await asyncio.to_thread(
            stage_print_settings, brief, scad_code, model, timeout, sp.get(4, "")
        )
        DESIGNS[design_id]["print_settings"] = settings
        await emit({"stage": 4, "status": "done", "data": settings})

        # Stage 5 — BOM
        await emit({"stage": 5, "status": "running"})
        bom = await asyncio.to_thread(
            stage_source_parts, brief, model, timeout, sp.get(5, "")
        )
        DESIGNS[design_id]["bom"] = bom
        await emit({"stage": 5, "status": "done", "data": bom})

        DESIGNS[design_id]["status"] = "complete"
        await emit({"type": "complete"})

    except Exception as exc:
        DESIGNS[design_id]["status"] = "error"
        DESIGNS[design_id]["error"] = str(exc)
        await emit({"type": "error", "message": str(exc)})


# ── Request models ────────────────────────────────────────────────────────────

class DesignRequest(BaseModel):
    description: str
    model: Optional[str] = None
    timeout: Optional[int] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return HTMLResponse((_STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/styles.css")
async def serve_css():
    return FileResponse(_STATIC / "styles.css", media_type="text/css")


@app.get("/app.js")
async def serve_js():
    return FileResponse(_STATIC / "app.js", media_type="application/javascript")


@app.post("/design")
async def start_design(req: DesignRequest):
    design_id = str(uuid.uuid4())[:8]
    timeout = req.timeout or TIMEOUT
    model = req.model or MODEL
    DESIGNS[design_id] = {
        "status":      "running",
        "description": req.description,
        "iterations":  [],
        "stage_prompts": {},
        "queue":       asyncio.Queue(),
    }

    async def run_stage_1():
        d = DESIGNS[design_id]
        queue = d["queue"]
        try:
            await queue.put({"stage": 1, "status": "running"})
            brief = await asyncio.to_thread(stage_brief, req.description, model, timeout)
            d["brief"] = brief
            d["_current_prompt"] = req.description
            await queue.put({"stage": 1, "status": "done", "data": brief})
            await queue.put({"type": "complete"})
        except Exception as exc:
            await queue.put({"stage": 1, "status": "error", "data": {"message": str(exc)}})
            await queue.put({"type": "error", "message": str(exc)})

    asyncio.create_task(run_stage_1())
    return {"id": design_id}


@app.get("/design/{design_id}/stream")
async def stream_design(design_id: str):
    if design_id not in DESIGNS:
        raise HTTPException(404, "Design not found")

    queue: asyncio.Queue = DESIGNS[design_id]["queue"]

    async def event_gen():
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("complete", "error"):
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Per-stage retry ───────────────────────────────────────────────────────────

class StageRetryRequest(BaseModel):
    prompt: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = None


@app.post("/design/{design_id}/stage/{stage_num}")
async def retry_stage(design_id: str, stage_num: int, req: Optional[StageRetryRequest] = None):
    if design_id not in DESIGNS:
        raise HTTPException(404, "Design not found")
    if stage_num < 1 or stage_num > 5:
        raise HTTPException(400, "Stage must be 1-5")

    if req is None:
        req = StageRetryRequest()

    d = DESIGNS[design_id]
    d["queue"] = asyncio.Queue()
    d["status"] = "running"

    timeout = req.timeout or TIMEOUT
    model = req.model or MODEL

    # Store the sub-prompt for this stage
    stage_prompts = d.setdefault("stage_prompts", {})
    if req.prompt:
        stage_prompts[stage_num] = req.prompt

    async def run_single():
        queue = d["queue"]
        extra = d.get("stage_prompts", {}).get(stage_num, "")
        try:
            await queue.put({"stage": stage_num, "status": "running"})

            if stage_num == 1:
                desc = d.get("_current_prompt") or d["description"]
                if extra:
                    desc += f"\n\nAdditional guidance: {extra}"
                brief = await asyncio.to_thread(stage_brief, desc, model, timeout)
                d["brief"] = brief
                await queue.put({"stage": 1, "status": "done", "data": brief})
            elif stage_num == 2:
                scad_code = await asyncio.to_thread(
                    stage_generate_scad, d["brief"], model, timeout, extra
                )
                d["scad_code"] = scad_code
                await queue.put({"stage": 2, "status": "done", "data": {"scad_code": scad_code}})
            elif stage_num == 3:
                render = await asyncio.to_thread(stage_render, d["scad_code"], design_id)
                d["render"] = render
                await queue.put({"stage": 3, "status": "done", "data": {
                    "has_png": render["png_path"] is not None,
                    "has_stl": render["stl_path"] is not None,
                    "openscad_available": render["openscad_available"],
                    "render_error": render.get("render_error"),
                }})
            elif stage_num == 4:
                code = d.get("scad_code", "")
                settings = await asyncio.to_thread(
                    stage_print_settings, d["brief"], code, model, timeout, extra
                )
                d["print_settings"] = settings
                await queue.put({"stage": 4, "status": "done", "data": settings})
            elif stage_num == 5:
                bom = await asyncio.to_thread(
                    stage_source_parts, d["brief"], model, timeout, extra
                )
                d["bom"] = bom
                await queue.put({"stage": 5, "status": "done", "data": bom})

            await queue.put({"type": "complete"})
        except Exception as exc:
            await queue.put({"stage": stage_num, "status": "error", "data": {"message": str(exc)}})
            await queue.put({"type": "error", "message": str(exc)})

    asyncio.create_task(run_single())
    return {"id": design_id, "stage": stage_num}


# ── Iterative Refinement ──────────────────────────────────────────────────────

class RefineRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    timeout: Optional[int] = None


@app.post("/design/{design_id}/refine")
async def refine_design(design_id: str, req: RefineRequest):
    if design_id not in DESIGNS:
        raise HTTPException(404, "Design not found")

    d = DESIGNS[design_id]
    # Append the refinement to history
    iterations = d.setdefault("iterations", [])
    iterations.append({
        "prompt": req.prompt,
        "previous_brief": d.get("brief"),
    })

    # Build context-aware description for stage_brief
    history_context = f"Original description: {d['description']}\n\n"
    for i, it in enumerate(iterations, 1):
        history_context += f"Refinement #{i}: {it['prompt']}\n"
    if d.get("brief"):
        history_context += f"\nPrevious design brief:\n{json.dumps(d['brief'], indent=2, ensure_ascii=False)}\n"
    history_context += f"\nLatest refinement request: {req.prompt}\nUpdate the design brief to incorporate this change while keeping previous decisions intact."

    d["_current_prompt"] = history_context
    d["queue"] = asyncio.Queue()
    d["status"] = "running"

    asyncio.create_task(_run_pipeline(
        design_id, history_context,
        req.model or MODEL,
        req.timeout or TIMEOUT,
    ))
    return {"id": design_id, "iteration": len(iterations)}


@app.get("/design/{design_id}/png")
async def get_png(design_id: str):
    d = DESIGNS.get(design_id)
    if not d:
        raise HTTPException(404)
    path = (d.get("render") or {}).get("png_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "PNG not available — OpenSCAD may not be installed")
    return FileResponse(path, media_type="image/png")


@app.get("/design/{design_id}/stl")
async def get_stl(design_id: str):
    d = DESIGNS.get(design_id)
    if not d:
        raise HTTPException(404)
    path = (d.get("render") or {}).get("stl_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "STL not available — OpenSCAD may not be installed")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename="model.stl",
    )


@app.get("/design/{design_id}/scad")
async def get_scad(design_id: str):
    d = DESIGNS.get(design_id)
    if not d or not d.get("scad_code"):
        raise HTTPException(404)
    return PlainTextResponse(
        d["scad_code"],
        headers={"Content-Disposition": "attachment; filename=model.scad"},
    )


app.mount("/static", StaticFiles(directory=_STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8004, reload=True)
