"""Shell tool — execute approved shell commands via ToolRegistry."""

from __future__ import annotations

import subprocess
from typing import List, Optional

from tools.base_tool import BaseTool, ToolResult


class ShellTool(BaseTool):
    def __init__(
        self,
        allowed_commands: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
    ):
        self._allowed = set(allowed_commands or [])
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute an approved shell command. Returns stdout/stderr."

    @property
    def schema(self) -> dict:
        return {
            "name": "shell",
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds (default: 30)",
                    },
                },
                "required": ["command"],
            },
        }

    def execute(self, command: str, timeout: float = 30.0) -> ToolResult:
        if self._allowed:
            first_word = command.strip().split()[0]
            if first_word not in self._allowed:
                return ToolResult(
                    success=False,
                    error=f"Command '{first_word}' not allowed. Allowed: {sorted(self._allowed)}",
                )
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self._working_dir,
            )
            return ToolResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                error=proc.stderr,
                artifacts={"returncode": proc.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
