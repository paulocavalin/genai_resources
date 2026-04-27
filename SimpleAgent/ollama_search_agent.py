import argparse
import re
from html import unescape
from typing import Any, Dict, List

import requests
from ddgs import DDGS

from ollama_core import Agent, OllamaClient, print_final_output


SYSTEM_PROMPT = (
    "Voce e um assistente de pesquisa especializado. Seu objetivo e responder perguntas complexas "
    "com base em evidencias atuais encontradas na web.\n\n"
    "Ferramentas disponiveis:\n"
    "- web_search(query, max_results): Pesquisa na web e retorna resultados com titulo, URL e snippet.\n"
    "- web_fetch(url): Recupera o conteudo completo de uma pagina web.\n\n"
    "Instrucoes de comportamento:\n"
    "1. Antes de pesquisar, pense cuidadosamente em quais queries vao encontrar as informacoes mais relevantes.\n"
    "2. Faca entre 2 e 4 buscas - nao mais que isso, a menos que seja estritamente necessario.\n"
    "3. Se um resultado parecer incompleto, use web_fetch para obter mais detalhes.\n"
    "4. Na resposta final, sempre cite as fontes utilizadas.\n"
    "5. Seja objetivo e estruturado. Use markdown para organizar a resposta.\n"
    "6. Se nao encontrar informacao suficiente, diga isso claramente.\n"
    "7. Antes de cada tool call, escreva um plano curto (1-2 frases) no content do assistente explicando o proximo passo."
)


def _clean_html(raw_html: str) -> str:
    no_script = re.sub(r"<script[\s\S]*?</script>", " ", raw_html, flags=re.IGNORECASE)
    no_style = re.sub(r"<style[\s\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
    no_tags = re.sub(r"<[^>]+>", " ", no_style)
    text = unescape(no_tags)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    limit = max(1, min(int(max_results), 10))
    rows = list(DDGS().text(query, max_results=limit))
    results: List[Dict[str, str]] = []
    for row in rows:
        title = row.get("title") or "Untitled"
        url = row.get("href") or row.get("url") or ""
        snippet = row.get("body") or row.get("snippet") or ""
        if not url:
            continue
        results.append(
            {
                "title": str(title),
                "url": str(url),
                "snippet": str(snippet),
            }
        )
        if len(results) >= limit:
            break
    return results


def web_fetch(url: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": "SimpleAgent/1.0",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, timeout=15, headers=headers)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "html" in content_type.lower():
        content = _clean_html(response.text)
    else:
        content = response.text

    return {
        "url": url,
        "status_code": response.status_code,
        "content": content[:3000],
    }


web_search_tool_schema = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web and return relevant results with title, URL, and snippet.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to run on the web.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
}


web_fetch_tool_schema = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Fetch full content from a given URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch content from.",
                }
            },
            "required": ["url"],
        },
    },
}


def demo_agent(client: OllamaClient, prompt: str, trace: bool, render_markdown: bool) -> None:
    print("\n=== Search Agent loop demo ===")
    agent = Agent(
        client=client,
        system=SYSTEM_PROMPT,
        tools=[web_search_tool_schema, web_fetch_tool_schema],
        tool_registry={
            "web_search": web_search,
            "web_fetch": web_fetch,
        },
        trace=trace,
    )
    response = agent.execute(prompt)
    print("\nFinal answer:")
    print_final_output(response, render_markdown=render_markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search agent demo using Ollama + DuckDuckGo")
    parser.add_argument("--model", default="gemma4:latest")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--prompt",
        default=(
            "Quais sao as principais tendencias em IA agentica para 2025? "
            "Preciso de um resumo com dados recentes para uma apresentacao."
        ),
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
