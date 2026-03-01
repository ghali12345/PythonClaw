"""
Google Gemini provider — adapts the Gemini API to the OpenAI-compatible
response format used by Agent.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import content_types

from .base import LLMProvider
from .response import MockChoice, MockFunction, MockMessage, MockResponse, MockToolCall


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def _convert_tool_calls_to_parts(self, tool_calls_data: list) -> list:
        parts = []
        for tc in tool_calls_data:
            func = tc["function"] if isinstance(tc, dict) else tc.function
            name = func["name"] if isinstance(func, dict) else func.name
            args = json.loads(func["arguments"] if isinstance(func, dict) else func.arguments)
            parts.append(content_types.FunctionCall(name=name, args=args))
        return parts

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = "auto",
    ) -> Any:
        gemini_history: list[dict] = []
        system_instruction: str | None = None

        for msg in messages:
            role = msg["role"]
            content = msg.get("content")

            if role == "system":
                system_instruction = (
                    content if system_instruction is None
                    else system_instruction + "\n" + content
                )

            elif role == "user":
                gemini_history.append({"role": "user", "parts": [content]})

            elif role == "assistant":
                parts: list = []
                if content:
                    parts.append(content)
                if msg.get("tool_calls"):
                    parts.extend(self._convert_tool_calls_to_parts(msg["tool_calls"]))
                gemini_history.append({"role": "model", "parts": parts})

            elif role == "tool":
                func_name = self._find_tool_name(messages, msg["tool_call_id"])
                try:
                    resp_dict = json.loads(msg["content"])
                except (json.JSONDecodeError, TypeError):
                    resp_dict = {"result": msg["content"]}
                gemini_history.append({
                    "role": "user",
                    "parts": [content_types.FunctionResponse(name=func_name, response=resp_dict)],
                })

        # Convert tool schemas
        gemini_tools = None
        if tools:
            declarations = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description"),
                    "parameters": t["function"].get("parameters"),
                }
                for t in tools if t["type"] == "function"
            ]
            if declarations:
                gemini_tools = [declarations]

        # Inject system instruction into the first user message
        if gemini_history and gemini_history[0]["role"] == "model":
            gemini_history.insert(0, {"role": "user", "parts": ["Hi"]})
        if system_instruction and gemini_history:
            first_parts = gemini_history[0]["parts"]
            if isinstance(first_parts, list):
                first_parts.insert(0, f"System Instruction: {system_instruction}")

        response = self.model.generate_content(
            contents=gemini_history,
            tools=gemini_tools,
        )

        # Convert to OpenAI-compatible format
        try:
            _ = response.parts[0]
        except (IndexError, AttributeError, ValueError):
            return MockResponse(choices=[
                MockChoice(message=MockMessage(content="Error: empty response from Gemini", tool_calls=None))
            ])

        content_text: str | None = None
        tool_calls: list[MockToolCall] = []
        for part in response.parts:
            if part.text:
                content_text = (content_text or "") + part.text
            if part.function_call:
                tool_calls.append(MockToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    function=MockFunction(
                        name=part.function_call.name,
                        arguments=json.dumps(dict(part.function_call.args)),
                    ),
                ))

        return MockResponse(choices=[
            MockChoice(message=MockMessage(
                content=content_text,
                tool_calls=tool_calls or None,
            ))
        ])

    @staticmethod
    def _find_tool_name(messages: list[dict], tool_call_id: str) -> str:
        """Walk backwards through messages to find the function name for a tool_call_id."""
        for prev in reversed(messages):
            for tc in prev.get("tool_calls") or []:
                tc_id = tc["id"] if isinstance(tc, dict) else tc.id
                if tc_id == tool_call_id:
                    func = tc["function"] if isinstance(tc, dict) else tc.function
                    return func["name"] if isinstance(func, dict) else func.name
        return "unknown_tool"
