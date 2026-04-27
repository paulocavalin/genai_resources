USE_CASES = [
    {
        "id": "weather",
        "icon": "🌤️",
        "title": "Weather Assistant",
        "description": "Single-tool lookup with a quick finish.",
        "complexity": 1,
        "max_iterations": 4,
        "system_prompt": (
            "You are a helpful weather assistant. You can use get_weather(city, units). "
            "Use tools when needed, then answer clearly with practical advice."
        ),
        "user_query": "What's the weather like in Sao Paulo right now, and what should I wear?",
        "tool_names": ["get_weather"],
    },
    {
        "id": "research",
        "icon": "🔬",
        "title": "Research Agent",
        "description": "Search + synthesis with an explicit loop.",
        "complexity": 3,
        "max_iterations": 8,
        "system_prompt": (
            "You are an expert research assistant. You can use web_search(query, max_results), "
            "scrape_page(url), and summarize(text). Break complex queries into sub-queries and "
            "produce a concise final answer with citations."
        ),
        "user_query": (
            "What are the practical differences between RAG and fine-tuning for LLM systems, "
            "and when should a startup choose each?"
        ),
        "tool_names": ["web_search", "scrape_page", "summarize"],
    },
    {
        "id": "support",
        "icon": "🎧",
        "title": "Support Agent",
        "description": "CRM + policy + action tools.",
        "complexity": 3,
        "max_iterations": 8,
        "system_prompt": (
            "You are a customer support agent for ShopEasy. Available tools: "
            "lookup_order(order_id), check_policy(topic), issue_refund(order_id, amount, reason), "
            "escalate_to_human(reason, urgency). Be empathetic and policy-compliant."
        ),
        "user_query": (
            "My order SE-88421 arrived damaged and this is the second time. "
            "Can I get a refund?"
        ),
        "tool_names": ["lookup_order", "check_policy", "issue_refund", "escalate_to_human"],
    },
    {
        "id": "code",
        "icon": "💻",
        "title": "Code Helper",
        "description": "Write/test/fix loop with safe mock execution.",
        "complexity": 2,
        "max_iterations": 6,
        "system_prompt": (
            "You are a Python coding assistant. Available tools: run_code(code, language), "
            "read_file(path), write_file(path, content). Test before finalizing and explain "
            "what changed after each iteration."
        ),
        "user_query": (
            "Write a palindrome checker that ignores spaces and capitalization, then test it "
            "with racecar, A man a plan a canal Panama, and hello."
        ),
        "tool_names": ["run_code", "read_file", "write_file"],
    },
]


def get_use_case(case_id: str):
    for case in USE_CASES:
        if case["id"] == case_id:
            return case
    return None
