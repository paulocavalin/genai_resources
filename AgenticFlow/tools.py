import json
from datetime import date


TOOLS = {
    "get_weather": {
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "units": {"type": "string", "enum": ["metric", "imperial"]},
            },
            "required": ["city"],
        },
    },
    "web_search": {
        "description": "Search curated mock web snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
    },
    "scrape_page": {
        "description": "Return mock page content for a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    "summarize": {
        "description": "Summarize text into key bullets.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    "lookup_order": {
        "description": "Find mock order details.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    "check_policy": {
        "description": "Read a support policy topic.",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    "issue_refund": {
        "description": "Issue a mock refund.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
    "escalate_to_human": {
        "description": "Create an escalation ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["reason"],
        },
    },
    "run_code": {
        "description": "Run mock Python code in a deterministic sandbox simulation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "language": {"type": "string", "enum": ["python"]},
            },
            "required": ["code", "language"],
        },
    },
    "read_file": {
        "description": "Read from a mock in-memory file map.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "write_file": {
        "description": "Write to a mock in-memory file map.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
}


MOCK_FILES = {
    "main.py": "print('hello world')\n",
}


def _mock_weather(city: str, units: str = "metric"):
    data = {
        "city": city,
        "condition": "Partly cloudy",
        "humidity": 72,
        "wind_kph": 14,
        "uv_index": 6,
    }
    if units == "imperial":
        data.update({"temperature": 79, "feels_like": 82, "units": "F"})
    else:
        data.update({"temperature": 26, "feels_like": 28, "units": "C"})
    return data


def _mock_search(query: str, max_results: int = 3):
    corpus = [
        {
            "title": "RAG in Production",
            "url": "https://example.com/rag-prod",
            "snippet": "RAG grounds answers on external knowledge and supports citations.",
        },
        {
            "title": "Fine-tuning Practical Guide",
            "url": "https://example.com/finetune-guide",
            "snippet": "Fine-tuning adjusts model behavior, style, and domain-specific output.",
        },
        {
            "title": "RAG vs Fine-tuning",
            "url": "https://example.com/rag-vs-ft",
            "snippet": "RAG is faster to update; fine-tuning is better for style and skills.",
        },
        {
            "title": "Hybrid Architectures",
            "url": "https://example.com/hybrid",
            "snippet": "Teams often combine retrieval with a lightly fine-tuned base model.",
        },
    ]
    query_l = query.lower()
    scored = sorted(
        corpus,
        key=lambda row: (query_l in row["title"].lower()) + (query_l in row["snippet"].lower()),
        reverse=True,
    )
    return scored[: max(1, min(max_results, 10))]


def _mock_scrape(url: str):
    return {
        "url": url,
        "content": (
            "RAG injects retrieved context at inference time, preserving model weights. "
            "Fine-tuning modifies weights and is useful for stable formatting, task behavior, "
            "or domain language."
        ),
    }


def _mock_summarize(text: str):
    compact = " ".join(text.split())
    return {
        "bullets": [
            "RAG updates knowledge without retraining.",
            "Fine-tuning updates behavior and style.",
            "Many production systems combine both approaches.",
        ],
        "source_excerpt": compact[:260],
    }


def _mock_lookup_order(order_id: str):
    if order_id.upper() == "SE-88421":
        return {
            "order_id": "SE-88421",
            "customer": "Maria Silva",
            "item": "TemperedShield Pro Screen Protector",
            "amount": 24.99,
            "status": "Delivered",
            "delivery_date": "2026-03-22",
            "previous_refund_count": 1,
        }
    return {
        "order_id": order_id,
        "status": "Not found",
    }


def _mock_check_policy(topic: str):
    return {
        "topic": topic,
        "policy": (
            "Damaged items are eligible for a full refund within 30 days. "
            "Agents may auto-approve refunds up to $100."
        ),
        "effective_date": "2025-01-01",
    }


def _mock_issue_refund(order_id: str, amount: float, reason: str):
    return {
        "status": "approved",
        "refund_id": f"REF-{date.today().strftime('%Y%m%d')}-7742",
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "estimated_arrival": "3-5 business days",
    }


def _mock_escalate(reason: str, urgency: str = "medium"):
    return {
        "ticket_id": "ESC-2048",
        "status": "open",
        "urgency": urgency,
        "reason": reason,
    }


def _mock_run_code(code: str, language: str):
    if language != "python":
        return {"exit_code": 1, "stdout": "", "stderr": "Only python is supported in this mock.", "execution_time_ms": 1}
    if "is_palindrome" in code and "hello" in code:
        return {
            "exit_code": 0,
            "stdout": "✅ 'racecar' -> True\n✅ 'A man a plan a canal Panama' -> True\n✅ 'hello' -> False",
            "stderr": "",
            "execution_time_ms": 35,
        }
    return {
        "exit_code": 0,
        "stdout": "Mock execution completed.",
        "stderr": "",
        "execution_time_ms": 22,
    }


def _mock_read_file(path: str):
    return {
        "path": path,
        "content": MOCK_FILES.get(path, ""),
        "exists": path in MOCK_FILES,
    }


def _mock_write_file(path: str, content: str):
    MOCK_FILES[path] = content
    return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}


def execute_tool(name: str, args: dict):
    if name == "get_weather":
        return _mock_weather(args.get("city", "Unknown"), args.get("units", "metric"))
    if name == "web_search":
        return _mock_search(args.get("query", ""), int(args.get("max_results", 3)))
    if name == "scrape_page":
        return _mock_scrape(args.get("url", ""))
    if name == "summarize":
        return _mock_summarize(args.get("text", ""))
    if name == "lookup_order":
        return _mock_lookup_order(args.get("order_id", ""))
    if name == "check_policy":
        return _mock_check_policy(args.get("topic", ""))
    if name == "issue_refund":
        return _mock_issue_refund(args.get("order_id", ""), float(args.get("amount", 0)), args.get("reason", ""))
    if name == "escalate_to_human":
        return _mock_escalate(args.get("reason", ""), args.get("urgency", "medium"))
    if name == "run_code":
        return _mock_run_code(args.get("code", ""), args.get("language", "python"))
    if name == "read_file":
        return _mock_read_file(args.get("path", ""))
    if name == "write_file":
        return _mock_write_file(args.get("path", ""), args.get("content", ""))
    return {"error": f"Unknown tool: {name}"}


def tool_specs(tool_names):
    specs = []
    for name in tool_names:
        if name in TOOLS:
            item = TOOLS[name]
            specs.append(
                {
                    "name": name,
                    "description": item["description"],
                    "input_schema": item["input_schema"],
                }
            )
    return specs


def tool_specs_json(tool_names):
    return json.dumps(tool_specs(tool_names), ensure_ascii=True, indent=2)
