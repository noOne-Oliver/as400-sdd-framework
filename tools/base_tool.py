"""Tool system for AS400 SDD agents — discoverable, schema-described external capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class ToolResult:
    """Structured result returned by every tool execution."""

    success: bool
    output: str = ""
    error: str = ""
    artifacts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseTool(ABC):
    """Abstract base for all agent tools (shell, file, http, as400)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier, e.g. 'shell', 'file'."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown to the LLM."""

    @property
    def schema(self) -> dict:
        """JSON Schema describing accepted parameters. Override per tool."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Run the tool with validated parameters. Returns ToolResult."""
