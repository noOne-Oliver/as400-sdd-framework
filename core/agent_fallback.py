"""Agent Fallback & Token Budget Control.

Harness Engineering 理念:
- Multi-Agent: Agent失败时需要fallback机制
- Context Preservation: Token budget控制防止上下文丢失

功能:
1. Agent Fallback - 每个agent失败时降级到默认行为
2. Token Budget - 每个agent设置max token防止 runaway
3. Circuit Breaker - 连续失败时断开防止雪崩
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("as400_sdd_framework")


class FallbackStrategy(str, Enum):
    """降级策略"""
    RETURN_DEFAULT = "return_default"      # 返回默认值
    USE_PREVIOUS = "use_previous"          # 使用上一次结果
    SKIP_STAGE = "skip_stage"              # 跳过该阶段
    RETRY_SIMPLER = "retry_simpler"        # 用简化方式重试
    ESCALATE = "escalate"                  # 升级处理


@dataclass
class TokenBudget:
    """Token预算配置"""
    max_tokens: int = 4000
    warning_threshold: float = 0.8  # 80%时警告
    critical_threshold: float = 0.95  # 95%时强制中断
    estimated_overhead: int = 500  # 预留上下文开销


@dataclass
class CircuitBreakerState:
    """断路器状态"""
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    is_open: bool = False
    recovery_timeout: float = 60.0  # 60秒后尝试恢复


@dataclass
class FallbackConfig:
    """Fallback配置"""
    enabled: bool = True
    strategy: FallbackStrategy = FallbackStrategy.RETURN_DEFAULT
    default_output: Optional[dict] = None
    max_retries: int = 2
    retry_delay: float = 1.0  # 秒


class AgentFallbackHandler:
    """Agent降级处理器

    设计原则:
    1. 每个agent有独立的fallback策略
    2. 降级时保留尽可能多的有效输出
    3. 记录降级事件供后续分析
    """

    # Agent默认fallback配置
    DEFAULT_CONFIGS = {
        "ra_agent": FallbackConfig(
            strategy=FallbackStrategy.RETURN_DEFAULT,
            default_output={
                "program_name": "UNKNOWN",
                "summary": "需求分析降级输出",
                "analysis_markdown": "# 需求分析\n\n(降级模式)",
            },
        ),
        "sd_agent": FallbackConfig(
            strategy=FallbackStrategy.RETURN_DEFAULT,
            default_output={
                "program_name": "UNKNOWN",
                "sdd": "# 设计说明\n\n(降级模式)",
            },
        ),
        "td_agent": FallbackConfig(
            strategy=FallbackStrategy.SKIP_STAGE,
            default_output={
                "program_name": "UNKNOWN",
                "tests": "# 测试用例\n\n(降级模式: 跳过)",
            },
        ),
        "cg_agent": FallbackConfig(
            strategy=FallbackStrategy.USE_PREVIOUS,
            default_output={
                "program_name": "UNKNOWN",
                "code": "**NONE**",
            },
        ),
        "cr_agent": FallbackConfig(
            strategy=FallbackStrategy.RETURN_DEFAULT,
            default_output={
                "reviewed_code": "**NONE**",
                "review_report": "代码审查降级输出",
                "findings": ["审查降级: 无"],
            },
        ),
        "te_agent": FallbackConfig(
            strategy=FallbackStrategy.RETURN_DEFAULT,
            default_output={
                "passed": False,
                "execution_report": "测试执行降级输出",
                "passed_count": 0,
                "total_count": 0,
            },
        ),
    }

    def __init__(self):
        self._configs: dict[str, FallbackConfig] = {}
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._fallback_history: list[dict] = []
        self._token_budgets: dict[str, TokenBudget] = {}

        # 初始化默认配置
        for agent, config in self.DEFAULT_CONFIGS.items():
            self._configs[agent] = config
            self._circuit_breakers[agent] = CircuitBreakerState()
            self._token_budgets[agent] = TokenBudget()

    def get_fallback_config(self, agent_name: str) -> FallbackConfig:
        """获取Agent的fallback配置"""
        return self._configs.get(agent_name, FallbackConfig())

    def set_fallback_config(self, agent_name: str, config: FallbackConfig) -> None:
        """设置Agent的fallback配置"""
        self._configs[agent_name] = config
        logger.info(f"Set fallback config for {agent_name}: strategy={config.strategy}")

    def set_token_budget(self, agent_name: str, budget: TokenBudget) -> None:
        """设置Agent的token预算"""
        self._token_budgets[agent_name] = budget
        logger.info(
            f"Set token budget for {agent_name}: "
            f"max={budget.max_tokens}, warning={budget.warning_threshold}"
        )

    def get_token_budget(self, agent_name: str) -> TokenBudget:
        """获取Agent的token预算"""
        return self._token_budgets.get(agent_name, TokenBudget())

    def check_token_limit(
        self,
        agent_name: str,
        current_tokens: int,
    ) -> tuple[bool, str]:
        """检查token是否超限

        Returns:
            (是否通过, 状态消息)
        """
        budget = self.get_token_budget(agent_name)
        usage_ratio = current_tokens / budget.max_tokens

        if usage_ratio >= budget.critical_threshold:
            return False, f"CRITICAL: Token使用 {usage_ratio*100:.1f}% 超过临界值"

        if usage_ratio >= budget.warning_threshold:
            return True, f"WARNING: Token使用 {usage_ratio*100:.1f}% 接近上限"

        return True, f"OK: Token使用 {usage_ratio*100:.1f}%"

    def check_circuit_breaker(self, agent_name: str) -> bool:
        """检查断路器状态

        Returns:
            True=可以调用, False=断路器断开
        """
        state = self._circuit_breakers.get(agent_name, CircuitBreakerState())

        if not state.is_open:
            return True

        # 检查是否超时可以恢复
        if state.last_failure_time:
            elapsed = time.time() - state.last_failure_time
            if elapsed > state.recovery_timeout:
                # 尝试恢复
                state.is_open = False
                state.failure_count = 0
                logger.info(f"Circuit breaker recovery for {agent_name}")
                return True

        return False

    def record_failure(
        self,
        agent_name: str,
        error: str,
        failure_threshold: int = 3,
    ) -> None:
        """记录失败事件"""
        if agent_name not in self._circuit_breakers:
            self._circuit_breakers[agent_name] = CircuitBreakerState()

        state = self._circuit_breakers[agent_name]
        state.failure_count += 1
        state.last_failure_time = time.time()

        if state.failure_count >= failure_threshold:
            state.is_open = True
            logger.warning(
                f"Circuit breaker OPEN for {agent_name} "
                f"(failures={state.failure_count})"
            )

        self._fallback_history.append({
            "agent": agent_name,
            "error": error,
            "failure_count": state.failure_count,
            "timestamp": time.time(),
        })

    def record_success(self, agent_name: str) -> None:
        """记录成功事件 (重置断路器)"""
        if agent_name in self._circuit_breakers:
            state = self._circuit_breakers[agent_name]
            if state.failure_count > 0:
                logger.info(
                    f"Circuit breaker reset for {agent_name} "
                    f"(was {state.failure_count} failures)"
                )
            state.failure_count = 0
            state.is_open = False

    def execute_with_fallback(
        self,
        agent_name: str,
        primary_func: Callable[[], dict],
        context: Optional[dict] = None,
    ) -> dict:
        """执行带fallback的agent调用

        Args:
            agent_name: Agent名称
            primary_func: 主要执行函数
            context: 上下文字典

        Returns:
            dict 执行结果
        """
        # 检查断路器
        if not self.check_circuit_breaker(agent_name):
            logger.warning(f"Circuit breaker open, using fallback for {agent_name}")
            return self._execute_fallback(agent_name, context)

        # 检查token预算
        budget = self.get_token_budget(agent_name)
        estimated_tokens = budget.estimated_overhead
        within_limit, msg = self.check_token_limit(agent_name, estimated_tokens)
        if not within_limit:
            logger.warning(f"Token limit exceeded for {agent_name}: {msg}")
            return self._execute_fallback(agent_name, context)

        try:
            result = primary_func()
            self.record_success(agent_name)
            return result
        except Exception as exc:
            logger.error(f"Agent {agent_name} failed: {exc}")
            self.record_failure(agent_name, str(exc))
            return self._execute_fallback(agent_name, context, error=str(exc))

    def _execute_fallback(
        self,
        agent_name: str,
        context: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> dict:
        """执行fallback策略"""
        config = self.get_fallback_config(agent_name)

        if not config.enabled:
            logger.error(f"Fallback disabled for {agent_name}, re-raising")
            raise RuntimeError(f"Agent {agent_name} failed without fallback: {error}")

        strategy = config.strategy

        if strategy == FallbackStrategy.RETURN_DEFAULT:
            logger.info(f"Fallback: RETURN_DEFAULT for {agent_name}")
            return config.default_output or {}

        elif strategy == FallbackStrategy.USE_PREVIOUS:
            logger.info(f"Fallback: USE_PREVIOUS for {agent_name}")
            # 从context获取上一次结果
            if context and "previous_output" in context:
                return context["previous_output"]
            return config.default_output or {}

        elif strategy == FallbackStrategy.SKIP_STAGE:
            logger.info(f"Fallback: SKIP_STAGE for {agent_name}")
            return {
                "skipped": True,
                "agent": agent_name,
                "reason": "fallback_skip",
            }

        elif strategy == FallbackStrategy.RETRY_SIMPLER:
            logger.info(f"Fallback: RETRY_SIMPLER for {agent_name}")
            # 重试时简化输入
            if context:
                simplified = self._simplify_context(context)
                return {"retry_simplified": simplified}
            return config.default_output or {}

        else:
            return config.default_output or {}

    def _simplify_context(self, context: dict) -> dict:
        """简化context用于重试"""
        # 只保留关键字段
        keys_to_keep = ["program_name", "requirement_text"]
        return {k: v for k, v in context.items() if k in keys_to_keep}

    def get_fallback_stats(self) -> dict:
        """获取fallback统计"""
        return {
            "total_fallbacks": len(self._fallback_history),
            "recent_fallbacks": self._fallback_history[-10:],
            "circuit_breakers": {
                agent: {
                    "is_open": state.is_open,
                    "failure_count": state.failure_count,
                }
                for agent, state in self._circuit_breakers.items()
            },
            "configs": {
                agent: {
                    "strategy": config.strategy.value,
                    "enabled": config.enabled,
                }
                for agent, config in self._configs.items()
            },
        }


# 全局处理器
_handler: Optional[AgentFallbackHandler] = None


def get_fallback_handler() -> AgentFallbackHandler:
    """获取全局fallback处理器"""
    global _handler
    if _handler is None:
        _handler = AgentFallbackHandler()
    return _handler
