"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = "auto",
    ) -> Any:
        """
        Send a chat request to the LLM.

        All providers must return an object compatible with OpenAI's response
        structure: ``response.choices[0].message.content`` and
        ``response.choices[0].message.tool_calls``.

        Non-OpenAI providers should use the Mock* dataclasses from
        ``llm.response`` to build compatible return values.
        """
