"""Tests for tools/ — base_tool, tool_registry, shell_tool, file_tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools import BaseTool, FileTool, ShellTool, ToolRegistry
from tools.base_tool import ToolResult


class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing."

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="dummy ok")


# ─── ToolResult ────────────────────────────────────────────────────────────────


def test_tool_result_to_dict():
    r = ToolResult(success=True, output="hello", error="", artifacts={"k": "v"})
    d = r.to_dict()
    assert d["success"] is True
    assert d["output"] == "hello"
    assert d["artifacts"]["k"] == "v"


# ─── ShellTool ────────────────────────────────────────────────────────────────


def test_shell_tool_run_echo():
    tool = ShellTool()
    result = tool.execute("echo hello")
    assert result.success is True
    assert "hello" in result.output


def test_shell_tool_run_pwd():
    tool = ShellTool()
    result = tool.execute("pwd")
    assert result.success is True
    assert result.output


def test_shell_tool_returns_error_on_failure():
    tool = ShellTool()
    result = tool.execute("exit 1")
    assert result.success is False


def test_shell_tool_allowed_list_ok():
    tool = ShellTool(allowed_commands=["echo"])
    result = tool.execute("echo allowed")
    assert result.success is True


def test_shell_tool_allowed_list_rejects():
    tool = ShellTool(allowed_commands=["echo"])
    result = tool.execute("python3 --version")
    assert result.success is False
    assert "not allowed" in result.error


# ─── FileTool ────────────────────────────────────────────────────────────────


def test_file_tool_read(tmp_path):
    tool = FileTool(base_dir=str(tmp_path))
    (tmp_path / "hello.txt").write_text("world", encoding="utf-8")

    result = tool.execute(operation="read", path="hello.txt")
    assert result.success is True
    assert result.output == "world"


def test_file_tool_write_and_read(tmp_path):
    tool = FileTool(base_dir=str(tmp_path))

    result = tool.execute(operation="write", path="written.txt", content="fresh content")
    assert result.success is True
    assert (tmp_path / "written.txt").read_text(encoding="utf-8") == "fresh content"


def test_file_tool_list(tmp_path):
    tool = FileTool(base_dir=str(tmp_path))
    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")

    result = tool.execute(operation="list", path=".")
    assert result.success is True
    assert "a.txt" in result.output
    assert "b.txt" in result.output


def test_file_tool_read_not_found(tmp_path):
    tool = FileTool(base_dir=str(tmp_path))
    result = tool.execute(operation="read", path="nonexistent.txt")
    assert result.success is False
    assert "not found" in result.error


# ─── ToolRegistry ─────────────────────────────────────────────────────────────


def test_registry_singleton():
    ToolRegistry.reset()
    r1 = ToolRegistry.get_instance()
    r2 = ToolRegistry.get_instance()
    assert r1 is r2


def test_registry_register_and_get():
    ToolRegistry.reset()
    registry = ToolRegistry.get_instance()
    registry.register(DummyTool())
    assert registry.get("dummy") is not None
    assert registry.get("dummy").name == "dummy"


def test_registry_list_tools():
    ToolRegistry.reset()
    registry = ToolRegistry.get_instance()
    registry.register(ShellTool())
    registry.register(FileTool())
    tools = registry.list_tools()
    assert "shell" in tools
    assert "file" in tools


def test_registry_execute_success():
    ToolRegistry.reset()
    registry = ToolRegistry.get_instance()
    registry.register(ShellTool())
    result = registry.execute("shell", command="echo registry_test")
    assert result.success is True
    assert "registry_test" in result.output


def test_registry_execute_unknown_returns_error():
    ToolRegistry.reset()
    registry = ToolRegistry.get_instance()
    result = registry.execute("nonexistent_tool", foo="bar")
    assert result.success is False
    assert "not found" in result.error


def test_registry_tool_schemas():
    ToolRegistry.reset()
    registry = ToolRegistry.get_instance()
    registry.register(ShellTool())
    schemas = registry.tool_schemas()
    assert any(s["name"] == "shell" for s in schemas)
