"""Model Router for Agent-Based Model Selection.

Harness Engineering 理念:
- Multi-Agent: 不同agent需要不同能力的模型
- Declarative Pipeline: 模型选择通过配置声明

成本优化:
- 简单任务(路由/分类/diff分析) → 小模型
- 复杂任务(推理/合成/总结) → 大模型
- 可节省60-70%成本

参考 Kunal Gangalani 的 Multi-Agent Production Guide (2026)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from core.task_classifier import TaskComplexity, TaskType

logger = logging.getLogger("as400_sdd_framework")


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str
    max_tokens: int
    cost_per_1k_tokens: float  # USD
    capabilities: list[str] = field(default_factory=list)
    recommended_for: list[str] = field(default_factory=list)


class ModelRouter:
    """模型路由器 - 根据任务类型选择最佳模型

    设计原则:
    1. 简单任务用小模型 (省钱)
    2. 复杂任务用大模型 (保质量)
    3. 支持模型降级 (Fallback)
    """

    # 预定义模型配置
    MODELS = {
        "mock-small": ModelConfig(
            name="mock-small",
            provider="mock",
            max_tokens=500,
            cost_per_1k_tokens=0.0,
            capabilities=["routing", "classification", "simple_diff"],
            recommended_for=["code_review_simple", "routing"],
        ),
        "mock-medium": ModelConfig(
            name="mock-medium",
            provider="mock",
            max_tokens=2000,
            cost_per_1k_tokens=0.0,
            capabilities=["generation", "analysis", "summary"],
            recommended_for=["test_design", "spec_analysis"],
        ),
        "mock-large": ModelConfig(
            name="mock-large",
            provider="mock",
            max_tokens=8000,
            cost_per_1k_tokens=0.0,
            capabilities=["complex_reasoning", "synthesis", "creative"],
            recommended_for=["code_generation", "requirements_analysis", "complex_review"],
        ),
        # 可扩展: 添加真实模型配置
        # "gpt-4o": ModelConfig(
        #     name="gpt-4o",
        #     provider="openai",
        #     max_tokens=128000,
        #     cost_per_1k_tokens=0.015,
        #     capabilities=["complex_reasoning", "synthesis", "creative"],
        #     recommended_for=["code_generation", "requirements_analysis"],
        # ),
        # "gpt-4o-mini": ModelConfig(
        #     name="gpt-4o-mini",
        #     provider="openai",
        #     max_tokens=128000,
        #     cost_per_1k_tokens=0.00015,
        #     capabilities=["routing", "classification", "simple_diff"],
        #     recommended_for=["code_review_simple", "routing"],
        # ),
    }

    # Agent到模型映射
    AGENT_MODEL_MAP = {
        "ra_agent": "mock-large",      # 需求分析 - 复杂
        "sd_agent": "mock-large",      # 规格设计 - 复杂
        "td_agent": "mock-medium",     # 测试设计 - 中等
        "cg_agent": "mock-large",      # 代码生成 - 复杂
        "cr_agent": "mock-medium",     # 代码审查 - 中等
        "te_agent": "mock-small",       # 测试执行 - 简单
    }

    def __init__(self):
        self._routing_history: list[dict] = []
        self._cost_savings = {
            "total_routed": 0,
            "small_model_uses": 0,
            "estimated_savings": 0.0,
        }

    def get_model_for_agent(
        self,
        agent_name: str,
        task_complexity: Optional[TaskComplexity] = None,
    ) -> ModelConfig:
        """获取Agent推荐的模型

        Args:
            agent_name: Agent名称
            task_complexity: 任务复杂度覆盖

        Returns:
            ModelConfig 模型配置
        """
        # 1. 检查Agent特定映射
        model_name = self.AGENT_MODEL_MAP.get(agent_name)

        if model_name:
            model_config = self.MODELS.get(model_name)
            if model_config:
                self._record_routing(agent_name, model_name, "agent_map")
                return model_config

        # 2. 基于复杂度选择
        if task_complexity:
            model_name = self._get_model_by_complexity(task_complexity)
            model_config = self.MODELS.get(model_name)
            if model_config:
                self._record_routing(agent_name, model_name, "complexity")
                return model_config

        # 3. 默认配置
        default = self.MODELS["mock-medium"]
        self._record_routing(agent_name, default.name, "default")
        return default

    def _get_model_by_complexity(self, complexity: TaskComplexity) -> str:
        """根据复杂度选择模型"""
        mapping = {
            TaskComplexity.SIMPLE: "mock-small",
            TaskComplexity.MEDIUM: "mock-medium",
            TaskComplexity.COMPLEX: "mock-large",
        }
        return mapping.get(complexity, "mock-medium")

    def get_model_for_task(
        self,
        task_type: TaskType,
        task_name: str,
    ) -> ModelConfig:
        """根据任务类型选择模型

        Args:
            task_type: 任务类型
            task_name: 任务名称

        Returns:
            ModelConfig 模型配置
        """
        # 并行任务可用小模型
        if task_type == TaskType.PARALLEL:
            model_name = "mock-small"
        # 顺序任务需要大模型
        elif task_type == TaskType.SEQUENTIAL:
            model_name = "mock-large"
        # 混合任务用中模型
        else:
            model_name = "mock-medium"

        model_config = self.MODELS.get(model_name, self.MODELS["mock-medium"])
        self._record_routing(task_name, model_name, "task_type")
        return model_config

    def estimate_cost(
        self,
        agent_name: str,
        estimated_tokens: int,
        use_small_model: bool = False,
    ) -> dict:
        """估算任务成本

        Args:
            agent_name: Agent名称
            estimated_tokens: 预估token数
            use_small_model: 是否使用小模型

        Returns:
            dict 成本估算
        """
        # 正常情况用大模型
        large_model = self.MODELS["mock-large"]
        large_cost = (estimated_tokens / 1000) * large_model.cost_per_1k_tokens

        # 使用小模型节省
        small_model = self.MODELS["mock-small"]
        small_cost = (estimated_tokens / 1000) * small_model.cost_per_1k_tokens

        savings = large_cost - small_cost
        savings_percent = (savings / large_cost * 100) if large_cost > 0 else 0

        return {
            "agent": agent_name,
            "estimated_tokens": estimated_tokens,
            "large_model_cost": large_cost,
            "small_model_cost": small_cost,
            "savings": savings,
            "savings_percent": savings_percent,
            "recommended": "small" if use_small_model else "large",
        }

    def get_routing_stats(self) -> dict:
        """获取路由统计"""
        return {
            "total_routes": len(self._routing_history),
            "cost_savings": self._cost_savings,
            "model_usage": self._count_model_usage(),
            "recent_routes": self._routing_history[-10:],
        }

    def _count_model_usage(self) -> dict:
        """统计模型使用次数"""
        usage = {}
        for route in self._routing_history:
            model = route.get("model_name", "unknown")
            usage[model] = usage.get(model, 0) + 1
        return usage

    def _record_routing(
        self,
        agent_or_task: str,
        model_name: str,
        reason: str,
    ) -> None:
        """记录路由历史"""
        import time
        self._routing_history.append({
            "agent_or_task": agent_or_task,
            "model_name": model_name,
            "reason": reason,
            "timestamp": time.time(),
        })


# 全局路由器
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """获取全局模型路由器"""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
