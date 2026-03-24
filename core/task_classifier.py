"""Task Classifier for Multi-Agent Routing Decision.

Google Scaling Principles (2026):
- Parallelizable tasks: Multi-agent improves by 81%
- Sequential tasks: Multi-agent degrades by 39-70%
- Decision rule: Task splittable + single-agent success < 45% → use multi-agent

Harness Engineering 理念:
- LLM-as-Judge: 任务分类需要经过评估验证
- Declarative Pipeline: 声明式任务类型定义
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("as400_sdd_framework")


class TaskType(str, Enum):
    """任务类型枚举"""
    PARALLEL = "parallel"           # 可并行拆分
    SEQUENTIAL = "sequential"       # 顺序依赖
    MIXED = "mixed"                 # 混合类型
    UNKNOWN = "unknown"             # 未知


class TaskComplexity(str, Enum):
    """任务复杂度枚举"""
    SIMPLE = "simple"              # 简单任务 (路由到小模型)
    MEDIUM = "medium"              # 中等复杂度
    COMPLEX = "complex"            # 复杂任务 (路由到大模型)


@dataclass
class TaskClassification:
    """任务分类结果"""
    task_type: TaskType
    complexity: TaskComplexity
    use_multi_agent: bool
    recommended_model: str
    reason: str
    confidence: float = 0.8  # 置信度 0-1
    metadata: dict = field(default_factory=dict)


@dataclass
class TaskMetrics:
    """任务执行指标"""
    task_id: str
    task_type: TaskType
    agent_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    token_used: int = 0
    success: bool = False
    error: Optional[str] = None
    retry_count: int = 0


class TaskClassifier:
    """任务分类器 - 根据任务特征决定多agent策略

    分类依据:
    1. 任务可并行性 (parallel/sequential)
    2. 任务复杂度 (simple/medium/complex)
    3. 单agent成功率预测

    Google研究结论:
    - 顺序任务不应盲目使用多agent
    - 并行任务从多agent获益最大
    """

    # 任务类型特征映射
    TASK_PATTERNS = {
        "requirements_analysis": {
            "type": TaskType.SEQUENTIAL,
            "complexity": TaskComplexity.MEDIUM,
            "reason": "需求分析需要完整上下文，无法并行"
        },
        "spec_design": {
            "type": TaskType.SEQUENTIAL,
            "complexity": TaskComplexity.COMPLEX,
            "reason": "规格设计依赖需求分析结果"
        },
        "test_design": {
            "type": TaskType.SEQUENTIAL,
            "complexity": TaskComplexity.MEDIUM,
            "reason": "测试设计依赖规格说明"
        },
        "code_generation": {
            "type": TaskType.PARALLEL,
            "complexity": TaskComplexity.COMPLEX,
            "reason": "代码生成可按文件/模块并行"
        },
        "code_review": {
            "type": TaskType.PARALLEL,
            "complexity": TaskComplexity.MEDIUM,
            "reason": "代码审查可并行检查多个维度"
        },
        "test_execution": {
            "type": TaskType.PARALLEL,
            "complexity": TaskComplexity.SIMPLE,
            "reason": "测试执行可并行运行多个用例"
        },
    }

    # 模型推荐配置
    MODEL_CONFIG = {
        TaskComplexity.SIMPLE: {"provider": "mock", "model": "small", "max_tokens": 500},
        TaskComplexity.MEDIUM: {"provider": "mock", "model": "medium", "max_tokens": 2000},
        TaskComplexity.COMPLEX: {"provider": "mock", "model": "large", "max_tokens": 8000},
    }

    def __init__(self):
        self._history: list[TaskClassification] = []

    def classify(self, task_name: str, context: Optional[dict] = None) -> TaskClassification:
        """对任务进行分类

        Args:
            task_name: 任务名称 (如 "code_generation", "requirements_analysis")
            context: 上下文字典，包含任务详情

        Returns:
            TaskClassification 分类结果
        """
        context = context or {}

        # 查找预定义模式
        pattern = self.TASK_PATTERNS.get(task_name)

        if pattern:
            task_type = pattern["type"]
            complexity = pattern["complexity"]
            reason = pattern["reason"]
        else:
            # 动态推断
            task_type, complexity, reason = self._infer_task特征(task_name, context)

        # 计算是否使用多agent
        use_multi_agent = self._should_use_multi_agent(task_type, context)

        # 推荐模型
        recommended_model = self._get_recommended_model(complexity, task_type)

        classification = TaskClassification(
            task_type=task_type,
            complexity=complexity,
            use_multi_agent=use_multi_agent,
            recommended_model=recommended_model,
            reason=reason,
            metadata={
                "task_name": task_name,
                "has_context": bool(context),
                "context_keys": list(context.keys())[:5] if context else []
            }
        )

        self._history.append(classification)
        logger.info(
            f"Task classified: {task_name} → type={task_type.value}, "
            f"complexity={complexity.value}, multi_agent={use_multi_agent}"
        )

        return classification

    def _infer_task特征(self, task_name: str, context: dict) -> tuple:
        """推断任务特征"""
        # 默认值
        task_type = TaskType.UNKNOWN
        complexity = TaskComplexity.MEDIUM
        reason = "默认分类"

        # 基于任务名称关键词推断
        name_lower = task_name.lower()

        if any(kw in name_lower for kw in ["parallel", "batch", "multiple", "split"]):
            task_type = TaskType.PARALLEL
            reason = "任务名包含并行关键词"
        elif any(kw in name_lower for kw in ["sequential", "chain", "dependency"]):
            task_type = TaskType.SEQUENTIAL
            reason = "任务名包含顺序关键词"
        elif any(kw in name_lower for kw in ["simple", "basic", "generate"]):
            complexity = TaskComplexity.SIMPLE
            reason = "任务名包含简单任务关键词"
        elif any(kw in name_lower for kw in ["complex", "advanced", "analyze"]):
            complexity = TaskComplexity.COMPLEX
            reason = "任务名包含复杂任务关键词"

        return task_type, complexity, reason

    def _should_use_multi_agent(self, task_type: TaskType, context: dict) -> bool:
        """根据任务类型决定是否使用多agent

        Google研究结论:
        - 并行任务: 多agent提升81%
        - 顺序任务: 多agent降低39-70%

        决策规则:
        1. 顺序任务 → 单agent
        2. 并行任务 + 可拆分 → 多agent
        3. 混合任务 → 按实际情况判断
        """
        if task_type == TaskType.SEQUENTIAL:
            return False

        if task_type == TaskType.PARALLEL:
            # 检查是否可拆分
            if context.get("splittable", True):
                return True
            return False

        # MIXED或UNKNOWN，默认单agent（保守策略）
        return False

    def _get_recommended_model(self, complexity: TaskComplexity, task_type: TaskType) -> str:
        """获取推荐的模型配置"""
        config = self.MODEL_CONFIG.get(complexity, self.MODEL_CONFIG[TaskComplexity.MEDIUM])
        return f"{config['provider']}:{config['model']}"

    def get_classification_stats(self) -> dict:
        """获取分类统计"""
        if not self._history:
            return {"total": 0}

        type_counts = {}
        multi_agent_count = 0

        for c in self._history:
            type_counts[c.task_type.value] = type_counts.get(c.task_type.value, 0) + 1
            if c.use_multi_agent:
                multi_agent_count += 1

        return {
            "total": len(self._history),
            "type_distribution": type_counts,
            "multi_agent_rate": multi_agent_count / len(self._history),
            "recent": [
                {
                    "task_type": c.task_type.value,
                    "use_multi_agent": c.use_multi_agent,
                    "complexity": c.complexity.value,
                }
                for c in self._history[-10:]
            ]
        }


# 全局单例
_classifier: Optional[TaskClassifier] = None


def get_task_classifier() -> TaskClassifier:
    """获取全局任务分类器"""
    global _classifier
    if _classifier is None:
        _classifier = TaskClassifier()
    return _classifier
