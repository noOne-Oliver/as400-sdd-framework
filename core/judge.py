"""LLM-as-Judge implementation with deterministic fallback heuristics.

Harness Engineering 理念:
- 每阶段输出必须经过 Judge 评分验证
- 低分强制重试或阻塞，确保质量底线
- 提供详细的 issues 和 recommendations 反馈
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from .llm_client import LLMClient


class JudgeLevel(str, Enum):
    """Judge 评估等级，对应不同的处理策略"""
    PASS = "pass"        # 分数 >= pass_score，通过
    RETRY = "retry"      # 分数 < pass_score 但 >= blocking_threshold，需重试
    BLOCK = "block"      # 分数 < blocking_threshold，强制阻塞


@dataclass
class JudgeResult:
    score: int
    passed: bool
    level: JudgeLevel = JudgeLevel.PASS
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["level"] = self.level.value
        return result


class Judge:
    """Scores artifacts with deterministic rules and optional LLM assistance.

    Harness Engineering 增强:
    - blocking_threshold: 低于此分数强制阻塞
    - max_retries: 最大重试次数
    - 提供详细的改进建议
    """

    def __init__(
        self,
        llm_client: "LLMClient" = None,
        pass_score: int = 7,
        blocking_threshold: int = 4,
        max_retries: int = 3,
    ):
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.pass_score = pass_score
        self.blocking_threshold = blocking_threshold
        self.max_retries = max_retries

    def evaluate(self, content: str, eval_type: str) -> JudgeResult:
        """统一评估入口，根据类型分发到具体评估方法"""
        if eval_type == "spec":
            return self.evaluate_spec(content)
        elif eval_type == "tests":
            return self.evaluate_tests(content)
        elif eval_type == "code":
            return self.evaluate_code(content)
        else:
            return JudgeResult(
                score=0,
                passed=False,
                level=JudgeLevel.BLOCK,
                issues=[f"Unknown eval_type: {eval_type}"],
            )

    def _determine_level(self, score: int) -> JudgeLevel:
        """根据分数确定评估等级"""
        if score >= self.pass_score:
            return JudgeLevel.PASS
        elif score >= self.blocking_threshold:
            return JudgeLevel.RETRY
        else:
            return JudgeLevel.BLOCK

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
        level = self._determine_level(score)
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            level=level,
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
        level = self._determine_level(score)
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            level=level,
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
        level = self._determine_level(score)
        return JudgeResult(
            score=score,
            passed=score >= self.pass_score,
            level=level,
            issues=issues,
            recommendations=recommendations,
        )
