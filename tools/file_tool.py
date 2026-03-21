"""File tool — read/write/list files via ToolRegistry."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from tools.base_tool import BaseTool, ToolResult


class FileTool(BaseTool):
    def __init__(
        self,
        allowed_operations: Optional[List[str]] = None,
        base_dir: Optional[str] = None,
    ):
        self._allowed_ops = set(allowed_operations or ["read", "write", "list"])
        self._base_dir = Path(base_dir) if base_dir else None

    @property
    def name(self) -> str:
        return "file"

    @property
    def description(self) -> str:
        return "Read, write, or list files in the workspace."

    @property
    def schema(self) -> dict:
        return {
            "name": "file",
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list"],
                        "description": "File operation",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (required for write operation)",
                    },
                },
                "required": ["operation", "path"],
            },
        }

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if self._base_dir:
            p = self._base_dir / p
        return p

    def execute(
        self,
        operation: str,
        path: str,
        content: str = None,
    ) -> ToolResult:
        if operation not in self._allowed_ops:
            return ToolResult(
                success=False,
                error=f"Operation '{operation}' not allowed. Allowed: {sorted(self._allowed_ops)}",
            )

        try:
            if operation == "read":
                resolved = self._resolve(path)
                if not resolved.exists():
                    return ToolResult(success=False, error=f"File not found: {path}")
                text = resolved.read_text(encoding="utf-8")
                return ToolResult(success=True, output=text)

            elif operation == "write":
                resolved = self._resolve(path)
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(content or "", encoding="utf-8")
                return ToolResult(success=True, output=f"Written to {path}")

            elif operation == "list":
                resolved = self._resolve(path)
                if not resolved.is_dir():
                    return ToolResult(success=False, error=f"Not a directory: {path}")
                entries = [f"{e.name}{'/' if e.is_dir() else ''}" for e in sorted(resolved.iterdir())]
                return ToolResult(success=True, output="\n".join(entries))

            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except PermissionError as exc:
            return ToolResult(success=False, error=f"Permission denied: {exc}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
