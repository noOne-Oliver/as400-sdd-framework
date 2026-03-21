"""Code review agent."""

from __future__ import annotations

from .base_agent import BaseAgent, ValidationResult


class CRAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("cr_agent", llm_client, "prompts/cr_agent")

    def execute(self, input_data: dict) -> dict:
        program_name = input_data["program_name"]
        code = input_data["code"]
        findings = []

        if "monitor" not in code.lower():
            findings.append("缺少 monitor/on-error 异常处理。")
        if "write ORDLOGPF".lower() not in code.lower():
            findings.append("日志文件写入不明确。")
        if not findings:
            findings.append("未发现阻塞性问题，代码结构满足 mock 评审标准。")

        report = (
            f"# 代码评审报告\n\n"
            f"## 程序\n- {program_name}\n\n"
            f"## 结论\n"
            + "\n".join(f"- {item}" for item in findings)
        )
        return {
            "program_name": program_name,
            "review_report": report,
            "reviewed_code": code,
            "findings": findings,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        if not output.get("review_report"):
            issues.append("Review report is missing.")
        return ValidationResult(not issues, issues)
