"""Code review agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base_agent import BaseAgent, ValidationResult


@dataclass
class ChecklistResult:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failed_checks: list[str] = field(default_factory=list)


class CRAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("cr_agent", llm_client, "prompts/cr_agent")

    def execute(self, input_data: dict) -> dict:
        program_name = input_data["program_name"]
        code = input_data["code"]
        context_summary = input_data.get("context_summary", "").strip()
        findings = []

        if "monitor" not in code.lower():
            findings.append("缺少 monitor/on-error 异常处理。")
        if "write ORDLOGPF".lower() not in code.lower():
            findings.append("日志文件写入不明确。")
        if not findings:
            findings.append("未发现阻塞性问题，代码结构满足 mock 评审标准。")

        checklist_result = self._run_checklist(code, program_name)
        if not checklist_result.passed:
            findings.append(
                "提交前清单未通过: " + "、".join(checklist_result.failed_checks)
            )

        report = (
            f"# 代码评审报告\n\n"
            f"## 程序\n- {program_name}\n\n"
            f"## 执行上下文\n{context_summary or '暂无上游阶段上下文。'}\n\n"
            f"## 结论\n"
            + "\n".join(f"- {item}" for item in findings)
        )
        return {
            "program_name": program_name,
            "review_report": report,
            "reviewed_code": code,
            "findings": findings,
            "checklist": checklist_result,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        if not output.get("review_report"):
            issues.append("Review report is missing.")
        checklist = output.get("checklist")
        if checklist and not checklist.passed:
            issues.append(
                "Pre-submit checklist failed: " + ", ".join(checklist.failed_checks)
            )
        return ValidationResult(not issues, issues)

    def _run_checklist(self, code: str, program_name: str) -> ChecklistResult:
        normalized = code.lower()
        checks = {
            "状态码完整性": all(status in code for status in ("02", "08", "09")),
            "monitor/on-error": "monitor" in normalized and "on-error" in normalized,
            "日志写入": "writeorderlog" in normalized or "write ordlogpf" in normalized,
            "文件操作": "dcl-f" in normalized,
            "程序入口": "*inlr = *on" in normalized,
            "无 TODO": "todo" not in normalized,
        }
        failed_checks = [name for name, passed in checks.items() if not passed]
        return ChecklistResult(
            passed=not failed_checks,
            checks=checks,
            failed_checks=failed_checks,
        )
