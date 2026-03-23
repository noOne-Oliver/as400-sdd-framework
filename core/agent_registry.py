"""Agent Registry with Dynamic Routing for Multi-Agent Collaboration.

Harness Engineering 理念:
- Multi-Agent: 多个专用 Agent 协作完成复杂任务
- 动态路由: 根据上下文自动选择最合适的 Agent
- Tool Registry: 工具注册表，支持扩展
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("as400_sdd_framework")


class AgentCapability(str, Enum):
    """Agent 能力枚举"""
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    SPEC_DESIGN = "spec_design"
    TEST_DESIGN = "test_design"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TEST_EXECUTION = "test_execution"
    GENERAL = "general"


@dataclass
class AgentMetadata:
    """Agent 元数据"""
    name: str
    capabilities: list[AgentCapability]
    model_preference: str = "default"
    priority: int = 1
    description: str = ""
    max_retries: int = 3


class DynamicRouter:
    """动态路由选择器
    
    根据上下文信息自动选择最合适的 Agent
    """

    def __init__(self, registry: "AgentRegistry"):
        self.registry = registry
        self.routing_history: list[dict] = []

    def route(self, task_type: str, context: dict) -> Optional[str]:
        """根据任务类型和上下文路由到最佳 Agent
        
        Args:
            task_type: 任务类型 (如 "requirements", "spec", "tests", "code")
            context: 上下文字典
            
        Returns:
            Agent 名称或 None
        """
        # 任务类型到能力映射
        capability_map = {
            "requirements": AgentCapability.REQUIREMENTS_ANALYSIS,
            "spec": AgentCapability.SPEC_DESIGN,
            "tests": AgentCapability.TEST_DESIGN,
            "code_generation": AgentCapability.CODE_GENERATION,
            "code_review": AgentCapability.CODE_REVIEW,
            "test_execution": AgentCapability.TEST_EXECUTION,
        }
        
        target_capability = capability_map.get(task_type, AgentCapability.GENERAL)
        
        # 查找匹配度最高的 Agent
        candidates = []
        for agent_name, metadata in self.registry._metadata.items():
            if target_capability in metadata.capabilities:
                # 计算匹配分数
                score = self._calculate_match_score(metadata, context)
                candidates.append((agent_name, score, metadata))
        
        if not candidates:
            logger.warning(f"No agent found for task_type={task_type}")
            return None
        
        # 按分数排序，选择最高分
        candidates.sort(key=lambda x: (x[1], x[2].priority), reverse=True)
        selected = candidates[0][0]
        
        # 记录路由历史
        self.routing_history.append({
            "task_type": task_type,
            "selected_agent": selected,
            "score": candidates[0][1],
            "timestamp": datetime.now().isoformat(),
            "context_keys": list(context.keys())[:5],  # 只记录部分上下文
        })
        
        logger.info(f"Routed task_type={task_type} to agent={selected} (score={candidates[0][1]})")
        return selected

    def _calculate_match_score(self, metadata: AgentMetadata, context: dict) -> float:
        """计算 Agent 与任务的匹配分数
        
        基于以下因素:
        - 能力匹配度
        - 优先级
        - 上下文适配
        """
        base_score = 10.0
        
        # 优先级加成
        priority_bonus = metadata.priority * 0.1
        
        # 上下文适配检查
        context_score = 0.0
        context_summary = context.get("context_summary", "")
        if context_summary:
            # 检查是否有相关上下文
            context_score = 1.0 if len(context_summary) > 50 else 0.5
        
        return base_score + priority_bonus + context_score

    def get_routing_stats(self) -> dict:
        """获取路由统计信息"""
        if not self.routing_history:
            return {"total_routes": 0}
        
        agent_counts = {}
        for record in self.routing_history:
            agent = record["selected_agent"]
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        return {
            "total_routes": len(self.routing_history),
            "agent_usage": agent_counts,
            "recent_routes": self.routing_history[-10:],
        }


class AgentRegistry:
    """Agent 注册表
    
    支持:
    - 静态注册: 预定义的 Agent
    - 动态注册: 运行时添加新 Agent
    - 动态路由: 根据上下文选择最佳 Agent
    - 能力查询: 查询具有特定能力的 Agent
    """

    def __init__(self):
        self._agents: dict[str, Any] = {}
        self._metadata: dict[str, AgentMetadata] = {}
        self._routers: dict[str, DynamicRouter] = {}
        self._initialized = False
        self._plugins: list[dict] = []  # 插件扩展
        self._logger = logger

    def register(
        self,
        name: str,
        agent: Any,
        capabilities: list[AgentCapability],
        priority: int = 1,
        description: str = "",
    ) -> None:
        """注册一个 Agent
        
        Args:
            name: Agent 名称
            agent: Agent 实例
            capabilities: Agent 能力列表
            priority: 优先级 (1-10, 越高越优先)
            description: 描述
        """
        if name in self._agents:
            self._logger.warning(f"Agent {name} already registered, overwriting")
        
        metadata = AgentMetadata(
            name=name,
            capabilities=capabilities,
            priority=priority,
            description=description,
        )
        
        self._agents[name] = agent
        self._metadata[name] = metadata
        self._routers[name] = DynamicRouter(self)
        
        self._logger.info(f"Registered agent: {name} with capabilities: {[c.value for c in capabilities]}")

    def register_plugin(self, plugin_config: dict) -> None:
        """注册插件扩展
        
        Plugin 配置格式:
        {
            "name": "plugin_name",
            "capabilities": ["capability1", "capability2"],
            "handler": callable,
            "config": {...}
        }
        """
        self._plugins.append(plugin_config)
        self._logger.info(f"Registered plugin: {plugin_config.get('name')}")

    def get(self, name: str) -> Optional[Any]:
        """获取指定名称的 Agent"""
        return self._agents.get(name)

    def get_by_capability(self, capability: AgentCapability) -> list[tuple[str, AgentMetadata]]:
        """获取具有特定能力的 Agent 列表"""
        results = []
        for name, metadata in self._metadata.items():
            if capability in metadata.capabilities:
                results.append((name, metadata))
        return sorted(results, key=lambda x: x[1].priority, reverse=True)

    def get_router(self, name: str) -> Optional[DynamicRouter]:
        """获取 Agent 的动态路由器"""
        return self._routers.get(name)

    def route(self, task_type: str, context: dict) -> Optional[str]:
        """动态路由到最佳 Agent
        
        使用加权轮询 + 能力匹配 + 上下文感知
        """
        # 任务类型到能力映射
        capability_map = {
            "requirements": AgentCapability.REQUIREMENTS_ANALYSIS,
            "spec": AgentCapability.SPEC_DESIGN,
            "tests": AgentCapability.TEST_DESIGN,
            "code_generation": AgentCapability.CODE_GENERATION,
            "code_review": AgentCapability.CODE_REVIEW,
            "test_execution": AgentCapability.TEST_EXECUTION,
        }
        
        target_capability = capability_map.get(task_type, AgentCapability.GENERAL)
        
        # 获取具有该能力的 Agent
        candidates = self.get_by_capability(target_capability)
        
        if not candidates:
            self._logger.warning(f"No agent found for capability: {target_capability}")
            return None
        
        # 使用第一个（优先级最高）
        selected_name = candidates[0][0]
        
        self._logger.info(f"Routed task_type={task_type} to agent={selected_name}")
        return selected_name

    def list_agents(self) -> list[dict]:
        """列出所有注册的 Agent"""
        return [
            {
                "name": name,
                "capabilities": [c.value for c in metadata.capabilities],
                "priority": metadata.priority,
                "description": metadata.description,
            }
            for name, metadata in self._metadata.items()
        ]

    def get_stats(self) -> dict:
        """获取注册表统计信息"""
        capability_counts = {}
        for metadata in self._metadata.values():
            for cap in metadata.capabilities:
                capability_counts[cap.value] = capability_counts.get(cap.value, 0) + 1
        
        return {
            "total_agents": len(self._agents),
            "capabilities": capability_counts,
            "plugins": len(self._plugins),
            "routers": {name: router.get_routing_stats() for name, router in self._routers.items()},
        }

    def save_state(self, path: Path) -> None:
        """保存注册表状态到文件"""
        state = {
            "agents": list(self._agents.keys()),
            "metadata": {
                name: {
                    "capabilities": [c.value for c in m.capabilities],
                    "priority": m.priority,
                    "description": m.description,
                }
                for name, m in self._metadata.items()
            },
            "plugins": [p.get("name") for p in self._plugins],
            "timestamp": datetime.now().isoformat(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        self._logger.info(f"Saved registry state to {path}")


# 全局单例
_global_registry: Optional[AgentRegistry] = None


def get_global_registry() -> AgentRegistry:
    """获取全局 Agent 注册表单例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def register_global_agent(
    name: str,
    agent: Any,
    capabilities: list[AgentCapability],
    priority: int = 1,
    description: str = "",
) -> None:
    """注册全局 Agent"""
    registry = get_global_registry()
    registry.register(name, agent, capabilities, priority, description)
