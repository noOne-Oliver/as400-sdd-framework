"""Observability module for Agent Metrics Collection.

Harness Engineering 理念:
- Multi-Agent: 多Agent协作需要可观测性
- LLM-as-Judge: 每个agent执行都需要评分验证

追踪指标:
- 成功率 (success rate)
- 延迟 (p50/p95/p99)
- Token消耗
- 错误率与失败模式
- 重试率
- 每请求成本
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("as400_sdd_framework")


class MetricType(str, Enum):
    """指标类型"""
    LATENCY = "latency"
    TOKEN_USAGE = "token_usage"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    RETRY_RATE = "retry_rate"
    COST = "cost"


@dataclass
class AgentMetric:
    """单个Agent指标"""
    agent_name: str
    phase: str
    timestamp: str
    latency_ms: float
    token_used: int
    success: bool
    error: Optional[str] = None
    retry_count: int = 0
    model: str = "mock"
    score: Optional[float] = None  # Judge评分


@dataclass
class PipelineMetric:
    """流水线级指标"""
    pipeline_id: str
    start_time: str
    end_time: Optional[str] = None
    total_duration_ms: Optional[float] = None
    phases: list[str] = field(default_factory=list)
    total_tokens: int = 0
    overall_success: bool = False
    cost_estimate: float = 0.0


class MetricsCollector:
    """指标收集器

    功能:
    1. 收集每个agent的执行指标
    2. 计算聚合统计 (p50/p95/p99)
    3. 持久化到文件
    4. 生成监控告警
    """

    def __init__(self, pipeline_id: Optional[str] = None):
        self.pipeline_id = pipeline_id or f"pipeline_{int(time.time())}"
        self._agent_metrics: list[AgentMetric] = []
        self._phase_metrics: dict[str, list[AgentMetric]] = defaultdict(list)
        self._start_time = time.time()
        self._enabled = True

    def record_agent_execution(
        self,
        agent_name: str,
        phase: str,
        latency_ms: float,
        token_used: int,
        success: bool,
        error: Optional[str] = None,
        retry_count: int = 0,
        model: str = "mock",
        score: Optional[float] = None,
    ) -> None:
        """记录单个agent执行"""
        if not self._enabled:
            return

        metric = AgentMetric(
            agent_name=agent_name,
            phase=phase,
            timestamp=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            token_used=token_used,
            success=success,
            error=error,
            retry_count=retry_count,
            model=model,
            score=score,
        )

        self._agent_metrics.append(metric)
        self._phase_metrics[phase].append(metric)

        logger.debug(
            f"Recorded metric: agent={agent_name}, phase={phase}, "
            f"latency={latency_ms:.2f}ms, success={success}"
        )

    def get_agent_stats(self, agent_name: str) -> dict:
        """获取指定agent的统计信息"""
        metrics = [m for m in self._agent_metrics if m.agent_name == agent_name]

        if not metrics:
            return {"agent": agent_name, "count": 0}

        latencies = [m.latency_ms for m in metrics]
        token_used = [m.token_used for m in metrics]
        scores = [m.score for m in metrics if m.score is not None]
        success_count = sum(1 for m in metrics if m.success)
        retry_total = sum(m.retry_count for m in metrics)

        return {
            "agent": agent_name,
            "count": len(metrics),
            "success_rate": success_count / len(metrics) if metrics else 0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p50_latency_ms": self._percentile(latencies, 50),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "total_tokens": sum(token_used),
            "avg_score": sum(scores) / len(scores) if scores else None,
            "total_retries": retry_total,
            "error_rate": 1 - (success_count / len(metrics)) if metrics else 0,
        }

    def get_phase_stats(self, phase: str) -> dict:
        """获取指定阶段的统计信息"""
        metrics = self._phase_metrics.get(phase, [])

        if not metrics:
            return {"phase": phase, "count": 0}

        latencies = [m.latency_ms for m in metrics]
        success_count = sum(1 for m in metrics if m.success)

        return {
            "phase": phase,
            "count": len(metrics),
            "success_rate": success_count / len(metrics),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p50_latency_ms": self._percentile(latencies, 50),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
        }

    def get_pipeline_stats(self) -> dict:
        """获取流水线级统计信息"""
        total_duration = time.time() - self._start_time
        total_tokens = sum(m.token_used for m in self._agent_metrics)
        success_count = sum(1 for m in self._agent_metrics if m.success)

        # 估算成本 (基于token)
        # Mock模式: $0.00, 真实模式假设 $0.002/1K tokens
        cost_estimate = (total_tokens / 1000) * 0.002

        agent_stats = {}
        for agent_name in set(m.agent_name for m in self._agent_metrics):
            agent_stats[agent_name] = self.get_agent_stats(agent_name)

        return {
            "pipeline_id": self.pipeline_id,
            "total_duration_ms": total_duration * 1000,
            "total_agents": len(set(m.agent_name for m in self._agent_metrics)),
            "total_executions": len(self._agent_metrics),
            "overall_success_rate": success_count / len(self._agent_metrics) if self._agent_metrics else 0,
            "total_tokens": total_tokens,
            "cost_estimate_usd": cost_estimate,
            "agent_stats": agent_stats,
            "start_time": datetime.fromtimestamp(self._start_time, tz=timezone.utc).isoformat(),
        }

    def check_anomalies(self) -> list[dict]:
        """检查异常并返回告警列表"""
        alerts = []

        for agent_name in set(m.agent_name for m in self._agent_metrics):
            stats = self.get_agent_stats(agent_name)

            # 检查延迟异常 (> 5s)
            if stats.get("p95_latency_ms", 0) > 5000:
                alerts.append({
                    "type": "high_latency",
                    "agent": agent_name,
                    "p95_latency_ms": stats["p95_latency_ms"],
                    "threshold_ms": 5000,
                })

            # 检查成功率低 (< 80%)
            if stats.get("success_rate", 1.0) < 0.8:
                alerts.append({
                    "type": "low_success_rate",
                    "agent": agent_name,
                    "success_rate": stats["success_rate"],
                    "threshold": 0.8,
                })

            # 检查错误率高 (> 20%)
            if stats.get("error_rate", 0) > 0.2:
                alerts.append({
                    "type": "high_error_rate",
                    "agent": agent_name,
                    "error_rate": stats["error_rate"],
                    "threshold": 0.2,
                })

        return alerts

    def save_metrics(self, output_dir: Path) -> Path:
        """保存指标到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metrics_file = output_dir / f"metrics_{self.pipeline_id}.json"

        data = {
            "pipeline_stats": self.get_pipeline_stats(),
            "agent_metrics": [
                asdict(m) for m in self._agent_metrics
            ],
            "phase_metrics": {
                phase: [asdict(m) for m in metrics]
                for phase, metrics in self._phase_metrics.items()
            },
            "anomaly_alerts": self.check_anomalies(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        metrics_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        logger.info(f"Saved metrics to {metrics_file}")
        return metrics_file

    @staticmethod
    def _percentile(values: list, percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def reset(self) -> None:
        """重置指标"""
        self._agent_metrics.clear()
        self._phase_metrics.clear()
        self._start_time = time.time()
        logger.info("Metrics reset")

    def disable(self) -> None:
        """禁用指标收集"""
        self._enabled = False

    def enable(self) -> None:
        """启用指标收集"""
        self._enabled = True


# 全局指标收集器
_collector: Optional[MetricsCollector] = None


def get_metrics_collector(pipeline_id: Optional[str] = None) -> MetricsCollector:
    """获取全局指标收集器"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector(pipeline_id)
    return _collector
