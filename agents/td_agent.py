"""Test design agent."""

from __future__ import annotations

from pathlib import Path

from .base_agent import BaseAgent, ValidationResult


class TDAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("td_agent", llm_client, "prompts/td_agent")

    def execute(self, input_data: dict) -> dict:
        analysis = input_data["analysis"]
        template = Path("templates/test_template.md").read_text(encoding="utf-8")
        tests = template.format(program_name=analysis["program_name"])
        return {
            "program_name": analysis["program_name"],
            "tests": tests,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        tests = output.get("tests", "")
        for token in ["TC-001", "预期结果", "状态 02", "状态 08", "状态 09"]:
            if token not in tests:
                issues.append(f"Test design missing token: {token}")
        return ValidationResult(not issues, issues)
