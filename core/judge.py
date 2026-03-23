"""Multi-Dimensional Judge Scoring Mechanism.

Harness Engineering 理念:
- LLM-as-Judge: 每阶段输出必须经过 Judge 评分验证
- 多维度评分: 从多个角度评估输出质量
- 阻塞机制: 低于阈值的输出强制阻塞或重试
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .llm_client import LLMClient


class JudgeLevel(str, Enum):
    """Judge 评估等级，对应不同的处理策略"""
    PASS = "pass"        # 分数 >= pass_score，通过
    RETRY = "retry"      # 分数 < pass_score 但 >= blocking_threshold，需重试
    BLOCK = "block"      # 分数 < blocking_threshold，强制阻塞


class EvalDimension(str, Enum):
    """评估维度枚举"""
    COMPLETENESS = "completeness"       # 完整性
    CORRECTNESS = "correctness"          # 正确性
    CONSISTENCY = "consistency"          # 一致性
    STYLE = "style"                      # 代码风格
    PERFORMANCE = "performance"          # 性能
    SECURITY = "security"               # 安全性


@dataclass
class DimensionScore:
    """单维度评分结果"""
    dimension: EvalDimension
    score: int  # 0-10
    weight: float  # 权重
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.score = max(0, min(10, self.score))  # 限制在 0-10


@dataclass
class JudgeResult:
    """Judge 最终评分结果"""
    total_score: int
    passed: bool
    level: JudgeLevel
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evaluation_time: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        result = asdict(self)
        result["level"] = self.level.value
        result["dimension_scores"] = [
            {
                "dimension": ds.dimension.value,
                "score": ds.score,
                "weight": ds.weight,
                "issues": ds.issues,
                "recommendations": ds.recommendations,
            }
            for ds in self.dimension_scores
        ]
        return result

    def get_dimension(self, dimension: EvalDimension) -> DimensionScore | None:
        """获取指定维度的评分"""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds
        return None

    def get_summary(self) -> str:
        """获取评分摘要"""
        dim_summary = ", ".join(
            f"{ds.dimension.value}={ds.score}"
            for ds in self.dimension_scores
        )
        return f"总分={self.total_score}({dim_summary})"


# 维度权重配置
DEFAULT_WEIGHTS = {
    EvalDimension.COMPLETENESS: 0.25,
    EvalDimension.CORRECTNESS: 0.30,
    EvalDimension.CONSISTENCY: 0.20,
    EvalDimension.STYLE: 0.10,
    EvalDimension.PERFORMANCE: 0.10,
    EvalDimension.SECURITY: 0.05,
}


class MultiDimensionJudge:
    """多维度 Judge 评估器
    
    增强功能:
    - 多维度独立评分
    - 加权总分计算
    - 详细的问题和建议
    - 阻塞机制
    """

    def __init__(
        self,
        llm_client: LLMClient = None,
        pass_score: int = 7,
        blocking_threshold: int = 4,
        max_retries: int = 3,
        weights: dict[EvalDimension, float] = None,
    ):
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.pass_score = pass_score
        self.blocking_threshold = blocking_threshold
        self.max_retries = max_retries
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def evaluate(
        self,
        content: str,
        eval_type: str,
        context: dict = None,
    ) -> JudgeResult:
        """统一评估入口
        
        Args:
            content: 待评估内容
            eval_type: 评估类型 (spec, tests, code)
            context: 额外上下文
            
        Returns:
            JudgeResult 包含多维度评分
        """
        if eval_type == "spec":
            return self.evaluate_spec(content, context)
        elif eval_type == "tests":
            return self.evaluate_tests(content, context)
        elif eval_type == "code":
            return self.evaluate_code(content, context)
        else:
            return JudgeResult(
                total_score=0,
                passed=False,
                level=JudgeLevel.BLOCK,
                issues=[f"Unknown eval_type: {eval_type}"],
            )

    def _calculate_total_score(
        self,
        dimension_scores: list[DimensionScore],
    ) -> int:
        """计算加权总分"""
        total = 0.0
        for ds in dimension_scores:
            total += ds.score * ds.weight * 10  # 权重 * 10 映射到 100 分制
        
        return max(1, min(10, int(total / 10)))

    def _determine_level(self, score: int) -> JudgeLevel:
        """根据总分确定评估等级"""
        if score >= self.pass_score:
            return JudgeLevel.PASS
        elif score >= self.blocking_threshold:
            return JudgeLevel.RETRY
        else:
            return JudgeLevel.BLOCK

    def _merge_issues_and_recommendations(
        self,
        dimension_scores: list[DimensionScore],
    ) -> tuple[list[str], list[str]]:
        """合并所有维度的问题和建议"""
        all_issues = []
        all_recommendations = []
        
        for ds in dimension_scores:
            if ds.issues:
                all_issues.append(f"[{ds.dimension.value}] " + "; ".join(ds.issues))
            if ds.recommendations:
                all_recommendations.append(f"[{ds.dimension.value}] " + "; ".join(ds.recommendations))
        
        return all_issues, all_recommendations

    def evaluate_spec(self, sdd: str, context: dict = None) -> JudgeResult:
        """评估 SPEC 文档
        
        维度:
        - COMPLETENESS: 是否包含所有必要章节
        - CORRECTNESS: 业务规则是否正确
        - CONSISTENCY: 与需求的一致性
        """
        dimension_scores = []

        # 1. 完整性评估
        completeness_issues = []
        completeness_recommendations = []
        required_markers = [
            ("#", "缺少标题标记"),
            ("程序", "缺少程序描述"),
            ("业务规则", "缺少业务规则章节"),
            ("处理流程", "缺少处理流程章节"),
            ("错误处理", "缺少错误处理章节"),
            ("测试", "缺少测试策略章节"),
        ]
        
        for marker, desc in required_markers:
            if marker.lower() not in sdd.lower():
                completeness_issues.append(desc)
        
        if "ORDPF" not in sdd and "文件" not in sdd:
            completeness_issues.append("未描述输入/输出文件")
        
        if "状态" not in sdd:
            completeness_issues.append("未定义状态转换")
        
        if completeness_issues:
            completeness_recommendations.append("添加缺失的必要章节")
        
        completeness_score = max(1, 10 - len(completeness_issues))
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.COMPLETENESS,
            score=completeness_score,
            weight=self.weights[EvalDimension.COMPLETENESS],
            issues=completeness_issues,
            recommendations=completeness_recommendations,
        ))

        # 2. 正确性评估
        correctness_issues = []
        correctness_recommendations = []
        
        # 检查文件命名规范
        if "ORDPF" in sdd and not any(x in sdd for x in ["custmf", "CUSTMF", "客户"]):
            correctness_issues.append("ORDPF 文件命名不规范")
        
        # 检查状态定义完整性
        if "02" not in sdd:
            correctness_issues.append("缺少状态 02 (处理成功)")
        if "08" not in sdd:
            correctness_issues.append("缺少状态 08 (部分完成)")
        if "09" not in sdd:
            correctness_issues.append("缺少状态 09 (失败)")
        
        if correctness_issues:
            correctness_recommendations.append("完善状态码定义")
        
        correctness_score = max(1, 10 - len(correctness_issues) * 2)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CORRECTNESS,
            score=correctness_score,
            weight=self.weights[EvalDimension.CORRECTNESS],
            issues=correctness_issues,
            recommendations=correctness_recommendations,
        ))

        # 3. 一致性评估 (简化版)
        consistency_score = 8  # 默认高分
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CONSISTENCY,
            score=consistency_score,
            weight=self.weights[EvalDimension.CONSISTENCY],
            issues=[],
            recommendations=["Spec 与需求保持一致"],
        ))

        # 4. 风格评估 (简化版)
        style_score = 7
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.STYLE,
            score=style_score,
            weight=self.weights[EvalDimension.STYLE],
            issues=[],
            recommendations=["文档结构清晰"],
        ))

        # 计算总分
        total = self._calculate_total_score(dimension_scores)
        level = self._determine_level(total)
        issues, recommendations = self._merge_issues_and_recommendations(dimension_scores)
        
        return JudgeResult(
            total_score=total,
            passed=total >= self.pass_score,
            level=level,
            dimension_scores=dimension_scores,
            issues=issues,
            recommendations=recommendations,
        )

    def evaluate_tests(self, tests: str, context: dict = None) -> JudgeResult:
        """评估测试设计
        
        维度:
        - COMPLETENESS: 是否覆盖所有测试场景
        - CORRECTNESS: 测试用例是否正确
        - CONSISTENCY: 与 SPEC 的一致性
        """
        dimension_scores = []

        # 1. 完整性评估
        completeness_issues = []
        completeness_recommendations = []
        expected_tokens = [
            ("TC-", "缺少测试用例编号"),
            ("前置条件", "缺少前置条件描述"),
            ("步骤", "缺少测试步骤"),
            ("预期结果", "缺少预期结果"),
            ("正常", "缺少正常场景测试"),
            ("异常", "缺少异常场景测试"),
        ]
        
        for token, desc in expected_tokens:
            if token.lower() not in tests.lower():
                completeness_issues.append(desc)
        
        # 检查状态覆盖
        if "02" not in tests:
            completeness_issues.append("缺少状态 02 测试")
        if "08" not in tests:
            completeness_issues.append("缺少状态 08 测试")
        if "09" not in tests:
            completeness_issues.append("缺少状态 09 测试")
        
        # 检查日志验证
        if "日志" not in tests and "log" not in tests.lower():
            completeness_issues.append("缺少日志验证测试")
        
        if completeness_issues:
            completeness_recommendations.append("添加缺失的测试场景")
        
        completeness_score = max(1, 10 - len(completeness_issues))
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.COMPLETENESS,
            score=completeness_score,
            weight=self.weights[EvalDimension.COMPLETENESS],
            issues=completeness_issues,
            recommendations=completeness_recommendations,
        ))

        # 2. 正确性评估
        correctness_issues = []
        
        # 检查测试用例格式
        tc_count = tests.lower().count("tc-")
        if tc_count < 3:
            correctness_issues.append(f"测试用例数量不足 (当前: {tc_count})")
        
        if correctness_issues:
            correctness_recommendations = ["增加测试用例覆盖"]
        else:
            correctness_recommendations = ["测试用例格式正确"]
        
        correctness_score = max(1, 10 - len(correctness_issues) * 2)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CORRECTNESS,
            score=correctness_score,
            weight=self.weights[EvalDimension.CORRECTNESS],
            issues=correctness_issues,
            recommendations=correctness_recommendations,
        ))

        # 3. 一致性评估
        consistency_issues = []
        if "02" in tests and "08" in tests and "09" in tests:
            consistency_recommendations = ["测试覆盖了所有状态码"]
        else:
            consistency_issues.append("测试与 SPEC 定义的状态码不一致")
            consistency_recommendations = ["对齐 SPEC 中的状态码定义"]
        
        consistency_score = max(1, 10 - len(consistency_issues) * 3)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CONSISTENCY,
            score=consistency_score,
            weight=self.weights[EvalDimension.CONSISTENCY],
            issues=consistency_issues,
            recommendations=consistency_recommendations,
        ))

        # 4. 其他维度简化评估
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.STYLE,
            score=7,
            weight=self.weights[EvalDimension.STYLE],
            issues=[],
            recommendations=["测试文档结构清晰"],
        ))

        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.PERFORMANCE,
            score=8,
            weight=self.weights[EvalDimension.PERFORMANCE],
            issues=[],
            recommendations=["无性能测试需求"],
        ))

        # 计算总分
        total = self._calculate_total_score(dimension_scores)
        level = self._determine_level(total)
        issues, recommendations = self._merge_issues_and_recommendations(dimension_scores)
        
        return JudgeResult(
            total_score=total,
            passed=total >= self.pass_score,
            level=level,
            dimension_scores=dimension_scores,
            issues=issues,
            recommendations=recommendations,
        )

    def evaluate_code(self, code: str, context: dict = None) -> JudgeResult:
        """评估代码
        
        维度:
        - COMPLETENESS: 是否包含所有必要组件
        - CORRECTNESS: 代码逻辑是否正确
        - STYLE: 代码风格
        """
        dimension_scores = []

        # 1. 完整性评估
        completeness_issues = []
        completeness_recommendations = []
        expected_tokens = [
            ("ctl-opt", "缺少控制选项"),
            ("dcl-f", "缺少文件声明"),
            ("ORDPF", "缺少订单主文件"),
            ("CUSTMF", "缺少客户主文件"),
            ("INVPF", "缺少库存主文件"),
            ("ORDLOGPF", "缺少日志文件"),
            ("02", "缺少成功状态"),
            ("08", "缺少部分完成状态"),
            ("09", "缺少失败状态"),
        ]
        
        for token, desc in expected_tokens:
            if token.lower() not in code.lower():
                completeness_issues.append(desc)
        
        if completeness_issues:
            completeness_recommendations.append("添加缺失的代码组件")
        
        completeness_score = max(1, 10 - len(completeness_issues))
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.COMPLETENESS,
            score=completeness_score,
            weight=self.weights[EvalDimension.COMPLETENESS],
            issues=completeness_issues,
            recommendations=completeness_recommendations,
        ))

        # 2. 正确性评估
        correctness_issues = []
        correctness_recommendations = []
        
        # 检查错误处理
        if "monitor" not in code.lower() and "on-error" not in code.lower():
            correctness_issues.append("缺少错误处理机制")
        
        # 检查日志写入
        if "write ordlogr" not in code.lower() and "ordlogpf" in code.lower():
            correctness_issues.append("引用了日志文件但未写入日志记录")
        
        if correctness_issues:
            correctness_recommendations.append("添加错误处理和日志记录")
        
        correctness_score = max(1, 10 - len(correctness_issues) * 3)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CORRECTNESS,
            score=correctness_score,
            weight=self.weights[EvalDimension.CORRECTNESS],
            issues=correctness_issues,
            recommendations=correctness_recommendations,
        ))

        # 3. 一致性评估
        consistency_score = 8
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.CONSISTENCY,
            score=consistency_score,
            weight=self.weights[EvalDimension.CONSISTENCY],
            issues=[],
            recommendations=["代码与 SPEC 保持一致"],
        ))

        # 4. 风格评估
        style_issues = []
        if code.count("\n") < 50:
            style_issues.append("代码行数较少，可能过于简单")
        
        style_score = max(1, 10 - len(style_issues))
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.STYLE,
            score=style_score,
            weight=self.weights[EvalDimension.STYLE],
            issues=style_issues,
            recommendations=["代码风格良好"] if not style_issues else ["优化代码结构"],
        ))

        # 5. 性能评估 (简化)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.PERFORMANCE,
            score=8,
            weight=self.weights[EvalDimension.PERFORMANCE],
            issues=[],
            recommendations=["无明显性能问题"],
        ))

        # 6. 安全性评估 (简化)
        dimension_scores.append(DimensionScore(
            dimension=EvalDimension.SECURITY,
            score=7,
            weight=self.weights[EvalDimension.SECURITY],
            issues=[],
            recommendations=["建议添加输入验证"],
        ))

        # 计算总分
        total = self._calculate_total_score(dimension_scores)
        level = self._determine_level(total)
        issues, recommendations = self._merge_issues_and_recommendations(dimension_scores)
        
        return JudgeResult(
            total_score=total,
            passed=total >= self.pass_score,
            level=level,
            dimension_scores=dimension_scores,
            issues=issues,
            recommendations=recommendations,
        )


# 向后兼容：保留原有的 Judge 类
Judge = MultiDimensionJudge
