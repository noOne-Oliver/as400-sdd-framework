"""Test execution agent."""

from __future__ import annotations

from .base_agent import BaseAgent, ValidationResult


class TEAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("te_agent", llm_client, None)

    def execute(self, input_data: dict) -> dict:
        program_name = input_data["program_name"]
        tests = input_data["tests"]
        code = input_data["code"]

        cases = {
            "TC-001": "02" in code and "02" in tests,
            "TC-002": "09" in code and "09" in tests,
            "TC-003": "08" in code and "08" in tests,
            "TC-004": "ORDLOGPF" in code and "日志" in tests,
        }
        passed_count = sum(1 for passed in cases.values() if passed)
        total_count = len(cases)
        passed = passed_count == total_count

        detail_lines = [
            "| Case | Result |",
            "| --- | --- |",
            *[
                f"| {case_id} | {'PASS' if result else 'FAIL'} |"
                for case_id, result in cases.items()
            ],
        ]
        report = (
            f"# 测试执行报告\n\n"
            f"## 程序\n- {program_name}\n\n"
            f"## 汇总\n- 通过: {passed_count}/{total_count}\n\n"
            f"## 结果明细\n" + "\n".join(detail_lines)
        )

        return {
            "program_name": program_name,
            "passed": passed,
            "passed_count": passed_count,
            "total_count": total_count,
            "execution_report": report,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        if "execution_report" not in output:
            issues.append("Execution report is missing.")
        return ValidationResult(not issues, issues)
