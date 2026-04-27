import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from tools import execute_tool, tool_specs, tool_specs_json
from use_cases import USE_CASES, get_use_case


MODEL_ID = os.getenv("MODEL_ID", "google/gemma-4-E2B-it")
HF_TOKEN = os.getenv("HF_TOKEN")


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def pick_dtype(device: torch.device) -> torch.dtype:
    if device.type == "cuda":
        return torch.bfloat16
    return torch.float32


device = pick_device()

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN,
    use_fast=True,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN,
    dtype=pick_dtype(device),
)
model.to(device)
model.eval()


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SESSIONS: Dict[str, Dict[str, Any]] = {}


class StartSessionRequest(BaseModel):
    use_case_id: str
    user_query: Optional[str] = None


class StepSessionRequest(BaseModel):
    session_id: str


class ResetSessionRequest(BaseModel):
    session_id: str


def _format_history_for_model(messages: List[Dict[str, Any]]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, dict) or isinstance(content, list):
            text = json.dumps(content, ensure_ascii=True)
        else:
            text = str(content)
        lines.append(f"{role.upper()}: {text}")
    return "\n".join(lines)


def _extract_json(text: str) -> Dict[str, Any]:
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output.")

    depth = 0
    in_str = False
    escaped = False
    end = -1

    for i, ch in enumerate(text[start:], start=start):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        raise ValueError("Incomplete JSON object in model output.")

    return json.loads(text[start : end + 1])


def _build_action_prompt(session: Dict[str, Any]) -> str:
    tool_json = tool_specs_json(session["tool_names"])
    history_text = _format_history_for_model(session["messages"])

    return (
        "You are an agent orchestrator. Decide the next single action.\n"
        "You must return exactly one JSON object and no extra text.\n\n"
        "Allowed actions:\n"
        "1) tool_call\n"
        "2) final_response\n\n"
        "JSON schema:\n"
        "{\n"
        '  "action": "tool_call" | "final_response",\n'
        '  "plan_summary": "short sentence",\n'
        '  "reason_summary": "short sentence",\n'
        '  "tool_name": "name or null",\n'
        '  "tool_args": {"arg": "value"} or {},\n'
        '  "response": "final response text or empty"\n'
        "}\n\n"
        "Rules:\n"
        "- If information is missing, choose tool_call.\n"
        "- If you can answer confidently, choose final_response.\n"
        "- Keep summaries concise and user-safe.\n"
        "- tool_name must be one of available tools.\n\n"
        f"Available tools:\n{tool_json}\n\n"
        "Conversation so far:\n"
        f"{history_text}\n"
    )


def _generate_model_text(prompt: str) -> str:
    encoded = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **encoded,
            max_new_tokens=320,
            temperature=0.25,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_ids = output_ids[0][encoded["input_ids"].shape[1] :]
    return tokenizer.decode(new_ids, skip_special_tokens=True)


def _event(
    event_type: str,
    label: str,
    summary: str,
    content: str,
    detail: Dict[str, Any],
    raw_request: Optional[Dict[str, Any]] = None,
    raw_response: Optional[Dict[str, Any]] = None,
    raw_note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "label": label,
        "summary": summary,
        "content": content,
        "detail": detail,
        "raw": {
            "request": raw_request,
            "response": raw_response,
            "note": raw_note,
        },
    }


def _step_session(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    if session["done"]:
        return []
    if session["iteration"] >= session["max_iterations"]:
        session["done"] = True
        limit_event = _event(
            "loop",
            "Loop Stop",
            "Reached max iterations. Returning safe completion.",
            "The orchestrator hit the configured iteration limit and stopped the loop.",
            {
                "iteration": session["iteration"],
                "max_iterations": session["max_iterations"],
                "stop_reason": "max_iterations",
            },
            raw_note="No additional model call was made.",
        )
        session["events"].append(limit_event)
        return [limit_event]

    session["iteration"] += 1
    prompt = _build_action_prompt(session)
    request_payload = {
        "model": MODEL_ID,
        "iteration": session["iteration"],
        "messages": session["messages"],
        "tools": tool_specs(session["tool_names"]),
    }

    generated = _generate_model_text(prompt)

    try:
        action = _extract_json(generated)
    except Exception as err:
        action = {
            "action": "final_response",
            "plan_summary": "Parsing fallback",
            "reason_summary": "Model output was not valid JSON.",
            "tool_name": None,
            "tool_args": {},
            "response": (
                "I could not safely parse the model action in this iteration. "
                "Please retry or pick a simpler use case."
            ),
        }
        parse_event = _event(
            "loop",
            "Parser Fallback",
            "Model output was not valid JSON; fallback path used.",
            f"Raw model output:\n{generated}",
            {"error": str(err)},
            raw_request=request_payload,
            raw_response={"raw_text": generated},
            raw_note="Fallback keeps the demo resilient for local models.",
        )
        session["events"].append(parse_event)

    planning_event = _event(
        "planning",
        "Agent Planning",
        action.get("plan_summary", "Plan next step"),
        action.get("reason_summary", "No reasoning summary provided."),
        {
            "iteration": session["iteration"],
            "chosen_action": action.get("action", "unknown"),
        },
        raw_request=request_payload,
        raw_response={"raw_text": generated, "parsed": action},
    )
    new_events = [planning_event]
    session["events"].append(planning_event)

    if action.get("action") == "tool_call":
        tool_name = action.get("tool_name")
        tool_args = action.get("tool_args") or {}

        if tool_name not in session["tool_names"]:
            tool_name = session["tool_names"][0] if session["tool_names"] else ""
            tool_args = {}

        tool_call_event = _event(
            "tool_call",
            "Tool Call",
            f"{tool_name}()",
            json.dumps({"name": tool_name, "args": tool_args}, ensure_ascii=True, indent=2),
            {
                "tool": tool_name,
                "iteration": session["iteration"],
            },
            raw_response={"type": "tool_call", "name": tool_name, "args": tool_args},
        )
        session["events"].append(tool_call_event)
        new_events.append(tool_call_event)

        start = time.perf_counter()
        result = execute_tool(tool_name, tool_args)
        latency_ms = int((time.perf_counter() - start) * 1000)

        tool_result_event = _event(
            "tool_result",
            "Tool Result",
            f"{tool_name} returned data",
            json.dumps(result, ensure_ascii=True, indent=2),
            {
                "tool": tool_name,
                "latency_ms": latency_ms,
                "iteration": session["iteration"],
            },
            raw_request={"tool": tool_name, "args": tool_args},
            raw_response={"result": result},
        )
        session["events"].append(tool_result_event)
        new_events.append(tool_result_event)

        session["messages"].append(
            {
                "role": "assistant",
                "content": {
                    "type": "tool_call",
                    "name": tool_name,
                    "args": tool_args,
                    "plan_summary": action.get("plan_summary", ""),
                },
            }
        )
        session["messages"].append(
            {
                "role": "tool",
                "content": {
                    "name": tool_name,
                    "result": result,
                },
            }
        )

        return new_events

    final_text = action.get("response") or "Done."
    response_event = _event(
        "response",
        "Final Response",
        "Agent returns the final answer.",
        final_text,
        {
            "iteration": session["iteration"],
            "stop_reason": "final_response",
        },
        raw_response={"action": action},
    )
    session["events"].append(response_event)
    new_events.append(response_event)
    session["messages"].append({"role": "assistant", "content": final_text})
    session["done"] = True
    return new_events


@app.get("/")
async def root():
    return {
        "message": "Agentic Flow demo backend is running.",
        "endpoints": [
            "/health",
            "/use-cases",
            "/session/start",
            "/session/step",
            "/session/{session_id}",
            "/session/reset",
        ],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": str(device),
    }


@app.get("/use-cases")
async def list_use_cases():
    return {
        "use_cases": [
            {
                "id": case["id"],
                "icon": case["icon"],
                "title": case["title"],
                "description": case["description"],
                "complexity": case["complexity"],
            }
            for case in USE_CASES
        ]
    }


@app.post("/session/start")
async def start_session(payload: StartSessionRequest):
    case = get_use_case(payload.use_case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Unknown use case")

    session_id = str(uuid.uuid4())
    user_query = payload.user_query or case["user_query"]

    session = {
        "id": session_id,
        "use_case_id": case["id"],
        "title": case["title"],
        "tool_names": case["tool_names"],
        "max_iterations": case["max_iterations"],
        "iteration": 0,
        "done": False,
        "messages": [
            {"role": "system", "content": case["system_prompt"]},
            {"role": "user", "content": user_query},
        ],
        "events": [],
    }

    system_event = _event(
        "system",
        "System Prompt",
        "Define role, tools, and behavior constraints.",
        case["system_prompt"],
        {
            "model": MODEL_ID,
            "tool_count": len(case["tool_names"]),
            "max_iterations": case["max_iterations"],
        },
        raw_request={
            "model": MODEL_ID,
            "tools": tool_specs(case["tool_names"]),
            "system": case["system_prompt"],
        },
        raw_note="This initializes the orchestrator context.",
    )
    user_event = _event(
        "user",
        "User Query",
        user_query,
        user_query,
        {"use_case_id": case["id"]},
        raw_request={"role": "user", "content": user_query},
    )

    session["events"].extend([system_event, user_event])
    SESSIONS[session_id] = session

    return {
        "session_id": session_id,
        "done": False,
        "events": session["events"],
        "iteration": session["iteration"],
        "max_iterations": session["max_iterations"],
    }


@app.post("/session/step")
async def step_session(payload: StepSessionRequest):
    session = SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session")

    new_events = _step_session(session)
    return {
        "session_id": payload.session_id,
        "done": session["done"],
        "new_events": new_events,
        "events": session["events"],
        "iteration": session["iteration"],
        "max_iterations": session["max_iterations"],
    }


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session")
    return {
        "session_id": session_id,
        "done": session["done"],
        "events": session["events"],
        "iteration": session["iteration"],
        "max_iterations": session["max_iterations"],
        "use_case_id": session["use_case_id"],
    }


@app.post("/session/reset")
async def reset_session(payload: ResetSessionRequest):
    if payload.session_id in SESSIONS:
        del SESSIONS[payload.session_id]
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
