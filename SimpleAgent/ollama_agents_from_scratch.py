import argparse

from ollama_core import Agent, OllamaClient, print_final_output


def get_temperature(city: str) -> str:
    """Get the current weather in a given city."""
    if city.lower() == "san francisco":
        return "72"
    if city.lower() == "paris":
        return "75"
    if city.lower() == "tokyo":
        return "73"
    return "70"


get_temperature_tool_schema = {
    "type": "function",
    "function": {
        "name": "get_temperature",
        "description": "Get the current temperature in a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to get the temperature for.",
                }
            },
            "required": ["city"],
        },
    },
}


def demo_agent(client: OllamaClient, prompt: str, trace: bool, render_markdown: bool) -> None:
    print("\n=== Agent loop demo ===")
    agent = Agent(
        client=client,
        system="You are a helpful assistant that can answer questions using the provided tools.",
        tools=[get_temperature_tool_schema],
        tool_registry={"get_temperature": get_temperature},
        trace=trace,
    )
    response = agent.execute(prompt)
    print("\nFinal answer:")
    print_final_output(response, render_markdown=render_markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extracted agents-from-scratch demo using Ollama")
    parser.add_argument("--model", default="gemma4:latest")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--prompt",
        default="what is the weather in san francisco?",
        help="Prompt sent to the agent execute() method.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print full agent loop trace (messages, tool calls, and outputs).",
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
