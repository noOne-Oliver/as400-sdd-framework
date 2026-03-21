"""LLM-as-Judge implementation with deterministic fallback heuristics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .llm_client import LLMClient


@dataclass
class JudgeResult:
    score: int
    passed: bool
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Judge:
    """Scores artifacts with deterministic rules and optional LLM assistance."""

    def __init__(
        self,
        llm_client: "LLMClient" = None,
        pass_score: int = 7,
    ):
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.pass_score = pass_score

    def evaluate_spec(self, sdd: str) -> JudgeResult:
        issues: list[str] = []
        recommendations: list[str] = []
        required_markers = [
            "#",
            "程序",
            "业务规则",
            "处理流程",
            "错误处理",
            "测试",
        ]

        for marker in required_markers:
            if marker.lower() not in sdd.lower():
                issues.append(f"Spec missing expected section or keyword: {marker}")

        if "ORDPF" not in sdd and "文件" not in sdd:
            issues.append("Spec does not clearly describe input or output files.")

        if "状态" not in sdd:
            issues.append("Spec does not define status transitions.")

        if not issues:
            recommendations.append("Spec is complete enough to proceed to test design.")
        else:
            recommendations.append("Add missing sections and explicit file-level traceability.")

        score = max(1, 10 - len(issues))
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            issues=issues,
            recommendations=recommendations,
        )

    def evaluate_tests(self, tests: str) -> JudgeResult:
        issues: list[str] = []
        recommendations: list[str] = []
        expected_tokens = [
            "TC-",
            "前置条件",
            "步骤",
            "预期结果",
            "正常",
            "异常",
        ]

        for token in expected_tokens:
            if token.lower() not in tests.lower():
                issues.append(f"Test artifact missing token: {token}")

        if "02" not in tests or "08" not in tests or "09" not in tests:
            issues.append("Tests do not cover all expected status outcomes 02/08/09.")

        if "日志" not in tests:
            issues.append("Tests do not validate processing log output.")

        if not issues:
            recommendations.append("Test design has enough coverage to support code generation.")
        else:
            recommendations.append("Add missing positive, negative, and audit-log scenarios.")

        score = max(1, 10 - len(issues))
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            issues=issues,
            recommendations=recommendations,
        )

    def evaluate_code(self, code: str) -> JudgeResult:
        issues: list[str] = []
        recommendations: list[str] = []
        expected_tokens = [
            "ctl-opt",
            "dcl-f",
            "ORDPF",
            "CUSTMF",
            "INVPF",
            "ORDLOGPF",
            "02",
            "08",
            "09",
        ]

        for token in expected_tokens:
            if token.lower() not in code.lower():
                issues.append(f"Code is missing expected token: {token}")

        if "monitor" not in code.lower() and "on-error" not in code.lower():
            issues.append("Code lacks explicit error handling.")

        if "write ordlogr" not in code.lower() and "ordlogpf" in code.lower():
            issues.append("Code references ORDLOGPF but does not clearly write log records.")

        if not issues:
            recommendations.append("Code satisfies deterministic structural rules.")
        else:
            recommendations.append("Add missing files, statuses, and error/logging branches.")

        score = max(1, 10 - len(issues))
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            issues=issues,
            recommendations=recommendations,
        )
