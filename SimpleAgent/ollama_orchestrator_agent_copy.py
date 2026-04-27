import argparse
from typing import Any, Callable, Dict

from ollama_agents_from_scratch import get_temperature, get_temperature_tool_schema
from ollama_core import Agent, OllamaClient, print_final_output
from ollama_search_agent import SYSTEM_PROMPT as SEARCH_SYSTEM_PROMPT
from ollama_search_agent import web_fetch, web_fetch_tool_schema, web_search, web_search_tool_schema


ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are an orchestrator agent. Your job is to route user requests to specialized sub-agents.\n\n"
    "Available sub-agents (via delegate_to_agent):\n"
    "- weather-agent: handles weather questions\n"
    "- search-agent: handles general research/current topics\n\n"
    "Rules:\n"
    "1. Never answer weather or research questions directly.\n"
    "2. Always delegate to one or more sub-agents first.\n"
    "3. If the user asks both weather and research, call both agents.\n"
    "4. Pass complete context to each sub-agent since they do not share memory with you.\n"
    "5. After sub-agent results return, synthesize one final response for the user.\n"
    "6. Before each delegation, include a brief planning sentence in the assistant content."
)


WEATHER_SYSTEM_PROMPT = (
    "You are a weather assistant. Use the available weather tool when needed and answer clearly."
)


delegate_to_agent_tool_schema = {
    "type": "function",
    "function": {
        "name": "delegate_to_agent",
        "description": "Delegate a task to a specialized sub-agent and return its result.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["weather-agent", "search-agent"],
                    "description": "Which sub-agent should handle the task.",
                },
                "task_context": {
                    "type": "object",
                    "description": "Complete task context for the sub-agent.",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Question the sub-agent should answer.",
                        }
                    },
                    "required": ["question"],
                },
            },
            "required": ["agent_name", "task_context"],
        },
    },
}


def build_weather_agent(client: OllamaClient, trace: bool) -> Agent:
    return Agent(
        client=client,
        system=WEATHER_SYSTEM_PROMPT,
        tools=[get_temperature_tool_schema],
        tool_registry={"get_temperature": get_temperature},
        trace=trace,
    )


def build_search_agent(client: OllamaClient, trace: bool) -> Agent:
    return Agent(
        client=client,
        system=SEARCH_SYSTEM_PROMPT,
        tools=[web_search_tool_schema, web_fetch_tool_schema],
        tool_registry={
            "web_search": web_search,
            "web_fetch": web_fetch,
        },
        trace=trace,
    )


def make_delegate_tool(client: OllamaClient, trace: bool) -> Callable[..., Dict[str, Any]]:
    def delegate_to_agent(agent_name: str, task_context: Dict[str, Any]) -> Dict[str, Any]:
        question = str(task_context.get("question", "")).strip()
        if not question:
            return {
                "agent_name": agent_name,
                "error": "Missing task_context.question",
            }

        if trace:
            print(
                "\n[TRACE] orchestrator.delegate_to_agent\n"
                f"agent_name={agent_name} question={question}"
            )

        if agent_name == "weather-agent":
            sub_agent = build_weather_agent(client, trace)
        elif agent_name == "search-agent":
            sub_agent = build_search_agent(client, trace)
        else:
            return {
                "agent_name": agent_name,
                "error": f"Unknown agent_name '{agent_name}'",
            }

        answer = sub_agent.execute(question)
        return {
            "agent_name": agent_name,
            "question": question,
            "answer": answer,
        }

    return delegate_to_agent


def demo_agent(client: OllamaClient, prompt: str, trace: bool, render_markdown: bool) -> None:
    print("\n=== Orchestrator multi-agent demo ===")

    delegate_tool = make_delegate_tool(client, trace)
    orchestrator = Agent(
        client=client,
        system=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[delegate_to_agent_tool_schema],
        tool_registry={"delegate_to_agent": delegate_tool},
        trace=trace,
        max_iterations=10,
    )

    response = orchestrator.execute(prompt)
    print("\nFinal answer:")
    print_final_output(response, render_markdown=render_markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent orchestrator demo using Ollama")
    parser.add_argument("--model", default="gemma4:latest")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--prompt",
        default="What's the weather in Tokyo, and summarize the latest agentic AI trends?",
        help="Prompt sent to the orchestrator execute() method.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print full trace (orchestrator and delegated sub-agents).",
    )
    markdown_group = parser.add_mutually_exclusive_group()
    markdown_group.add_argument(
        "--render-markdown",
        dest="render_markdown",
        action="store_true",
        help="Render final answer as markdown in terminal.",
    )
    markdown_group.add_argument(
        "--raw",
        dest="render_markdown",
        action="store_false",
        help="Print final answer as plain text.",
    )
    parser.set_defaults(render_markdown=True)
    args = parser.parse_args()

    client = OllamaClient(model=args.model, base_url=args.base_url, timeout=args.timeout)
    demo_agent(client, args.prompt, args.trace, args.render_markdown)


if __name__ == "__main__":
    main()
