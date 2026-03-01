"""
Anthropic (Claude) provider — adapts the Anthropic API to the OpenAI-compatible
response format used by Agent.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import anthropic

from .base import LLMProvider
from .response import MockChoice, MockFunction, MockMessage, MockResponse, MockToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model_name

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = "auto",
    ) -> Any:
        system_prompt = ""
        filtered_messages: list[dict] = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt += msg["content"] + "\n"

            elif msg["role"] == "tool":
                filtered_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg["tool_call_id"],
                        "content": msg["content"],
                    }],
                })

            elif msg["role"] == "assistant" and "tool_calls" in msg:
                content_block: list[dict] = []
                if msg.get("content"):
                    content_block.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    tc_id = tc["id"] if isinstance(tc, dict) else tc.id
                    func = tc["function"] if isinstance(tc, dict) else tc.function
                    fname = func["name"] if isinstance(func, dict) else func.name
                    fargs = json.loads(func["arguments"] if isinstance(func, dict) else func.arguments)
                    content_block.append({
                        "type": "tool_use",
                        "id": tc_id,
                        "name": fname,
                        "input": fargs,
                    })
                filtered_messages.append({"role": "assistant", "content": content_block})

            else:
                filtered_messages.append(msg)

        # Convert tool schemas
        anthropic_tools = []
        if tools:
            for t in tools:
                if t["type"] == "function":
                    anthropic_tools.append({
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "input_schema": t["function"]["parameters"],
                    })

        kwargs: dict = {
            "model": self.model_name,
            "messages": filtered_messages,
            "max_tokens": 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            if tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}

        response = self.client.messages.create(**kwargs)

        # Convert to OpenAI-compatible format
        content_text = ""
        tool_calls: list[MockToolCall] = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(MockToolCall(
                    id=block.id,
                    function=MockFunction(name=block.name, arguments=json.dumps(block.input)),
                ))

        return MockResponse(choices=[
            MockChoice(message=MockMessage(
                content=content_text or None,
                tool_calls=tool_calls or None,
            ))
        ])
