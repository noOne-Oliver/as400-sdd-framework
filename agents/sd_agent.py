"""Specification design agent that produces SDD documents."""

from __future__ import annotations

from pathlib import Path

from .base_agent import BaseAgent, ValidationResult


class SDAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("sd_agent", llm_client, "prompts/sd_agent")

    def execute(self, input_data: dict) -> dict:
        analysis = input_data["analysis"]
        context_summary = input_data.get("context_summary", "").strip()
        template = Path("templates/sdd_template.md").read_text(encoding="utf-8")
        sdd = template.format(
            program_name=analysis["program_name"],
            summary=analysis["summary"],
            process_steps="\n".join(f"- {item}" for item in analysis["process_steps"]),
            data_entities="\n".join(f"- {item}" for item in analysis["data_entities"]),
            business_rules="\n".join(f"- {item}" for item in analysis["business_rules"]),
            open_questions="\n".join(f"- {item}" for item in analysis["open_questions"])
            if analysis["open_questions"]
            else "- 无阻塞性问题，进入设计阶段。",
        )
        if context_summary:
            sdd = f"# 执行上下文\n{context_summary}\n\n{sdd}"
        return {
            "program_name": analysis["program_name"],
            "sdd": sdd,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        sdd = output.get("sdd", "")
        for token in ["# 软件设计说明书", "业务规则", "处理流程", "错误处理", "测试策略"]:
            if token not in sdd:
                issues.append(f"SDD missing token: {token}")
        return ValidationResult(not issues, issues)
