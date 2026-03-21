"""Global tool registry — singleton that tracks all registered BaseTool instances."""

from __future__ import annotations

from typing import Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult


class ToolRegistry:
    """Singleton registry for discoverable tools."""

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear registry. Used in tests."""
        cls._instance = None

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> Optional[BaseTool]:
        return self._tools.get(tool_name)

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found. Available: {self.list_tools()}",
            )
        try:
            return tool.execute(**kwargs)
        except Exception as exc:  # pragma: no cover — tools should handle their own
            return ToolResult(success=False, error=str(exc))

    def tool_schemas(self) -> List[dict]:
        return [tool.schema for tool in self._tools.values()]
