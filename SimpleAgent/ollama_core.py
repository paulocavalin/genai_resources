import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    from rich.console import Console
    from rich.markdown import Markdown
except Exception:  # pragma: no cover
    Console = None
    Markdown = None


@dataclass
class FunctionCall:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str
    function: FunctionCall

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            },
        }


@dataclass
class Message:
    role: str
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = [call.to_dict() for call in self.tool_calls]
        if self.reasoning:
            payload["reasoning"] = self.reasoning
        return payload


@dataclass
class Choice:
    message: Message


@dataclass
class ChatCompletionResponse:
    choices: List[Choice]


class _ChatCompletions:
    def __init__(self, outer: "OllamaClient") -> None:
        self.outer = outer

    def create(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> ChatCompletionResponse:
        payload: Dict[str, Any] = {
            "model": self.outer.model,
            "messages": messages,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        resp = requests.post(
            f"{self.outer.base_url}/chat/completions",
            json=payload,
            timeout=self.outer.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_message = data["choices"][0]["message"]
        raw_tool_calls = raw_message.get("tool_calls") or []

        tool_calls: List[ToolCall] = []
        for item in raw_tool_calls:
            fn = item.get("function") or {}
            args = fn.get("arguments", "{}")
            if isinstance(args, dict):
                args = json.dumps(args)
            tool_calls.append(
                ToolCall(
                    id=str(item.get("id", "")),
                    type=str(item.get("type", "function")),
                    function=FunctionCall(
                        name=str(fn.get("name", "")),
                        arguments=str(args),
                    ),
                )
            )

        reasoning = (
            raw_message.get("reasoning")
            or raw_message.get("reasoning_content")
            or raw_message.get("thinking")
            or ""
        )

        message = Message(
            role=str(raw_message.get("role", "assistant")),
            content=str(raw_message.get("content", "")),
            tool_calls=tool_calls or None,
            reasoning=str(reasoning) if reasoning else None,
        )
        return ChatCompletionResponse(choices=[Choice(message=message)])


class _Chat:
    def __init__(self, outer: "OllamaClient") -> None:
        self.completions = _ChatCompletions(outer)


class OllamaClient:
    def __init__(
        self,
        model: str = "gemma4:latest",
        base_url: str = "http://localhost:11434/v1",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.chat = _Chat(self)


class Agent:
    def __init__(
        self,
        client: OllamaClient,
        system: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_registry: Optional[Dict[str, Callable[..., Any]]] = None,
        max_iterations: int = 8,
        trace: bool = False,
    ) -> None:
        self.client = client
        self.system = system
        self.messages: List[Dict[str, Any]] = []
        self.tools = tools if tools is not None else []
        self.tool_registry = tool_registry if tool_registry is not None else {}
        self.max_iterations = max_iterations
        self.trace = trace
        if self.system:
            self.messages.append({"role": "system", "content": system})

    def __call__(self, message: str = "") -> str:
        return self.execute(message)

    def _trace_print(self, label: str, payload: Any) -> None:
        if not self.trace:
            return
        if isinstance(payload, (dict, list)):
            text = json.dumps(payload, ensure_ascii=True, indent=2)
        else:
            text = str(payload)
        print(f"\n[TRACE] {label}\n{text}")

    def execute(self, message: str = "") -> str:
        if message:
            self.messages.append({"role": "user", "content": message})
            self._trace_print("user", {"content": message})

        for iteration in range(1, self.max_iterations + 1):
            self._trace_print("iteration", {"index": iteration})

            completion = self.client.chat.completions.create(
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto",
            )

            response_message = completion.choices[0].message
            self._trace_print("assistant_raw", response_message.to_dict())

            if response_message.reasoning:
                self._trace_print("assistant_reasoning", response_message.reasoning)

            if response_message.tool_calls and response_message.content.strip():
                self._trace_print("assistant_plan", response_message.content.strip())

            if response_message.tool_calls:
                self.messages.append(response_message.to_dict())

                tool_outputs: List[Dict[str, Any]] = []
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        function_args = {}

                    function_to_call = self.tool_registry.get(function_name)
                    if function_to_call is None:
                        tool_output = {"error": f"Tool '{function_name}' not found."}
                    else:
                        try:
                            tool_output = function_to_call(**function_args)
                        except Exception as err:  # pragma: no cover
                            tool_output = {"error": f"Tool execution failed: {err}"}

                    self._trace_print(
                        "tool_execution",
                        {
                            "name": function_name,
                            "args": function_args,
                            "output": tool_output,
                        },
                    )

                    tool_outputs.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(tool_output, ensure_ascii=True),
                        }
                    )

                self.messages.extend(tool_outputs)
                continue

            final_assistant_content = response_message.content
            if final_assistant_content:
                self.messages.append({"role": "assistant", "content": final_assistant_content})
            self._trace_print("final_response", final_assistant_content)
            return final_assistant_content

        fallback = "Nao consegui concluir em tempo habil. Tente novamente com um prompt mais especifico."
        self.messages.append({"role": "assistant", "content": fallback})
        self._trace_print("fallback", fallback)
        return fallback


def print_final_output(text: str, render_markdown: bool = True) -> None:
    if not render_markdown:
        print(text)
        return
    if Console is None or Markdown is None:
        print(text)
        return
    console = Console()
    console.print(Markdown(text))
