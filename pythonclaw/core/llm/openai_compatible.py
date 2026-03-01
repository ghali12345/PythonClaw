"""OpenAI-compatible LLM provider.

Works with any API that follows the OpenAI chat-completions contract:
DeepSeek, Grok (xAI), Kimi (Moonshot), GLM (Zhipu), and others.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Thin wrapper around the OpenAI SDK for chat completions."""

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = "auto",
        **kwargs: Any,
    ) -> Any:
        req: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            **kwargs,
        }
        if tools:
            req["tools"] = tools
            req["tool_choice"] = tool_choice

        return self.client.chat.completions.create(**req)
