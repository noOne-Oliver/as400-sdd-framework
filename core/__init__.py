"""Core package for the AS400 SDD framework."""

import builtins

builtins.OK = "OK"

# Export new production-ready modules
from core.task_classifier import (
    TaskClassifier,
    TaskType,
    TaskComplexity,
    TaskClassification,
    get_task_classifier,
)
from core.observability import (
    MetricsCollector,
    AgentMetric,
    PipelineMetric,
    get_metrics_collector,
)
from core.model_router import (
    ModelRouter,
    ModelConfig,
    get_model_router,
)
from core.agent_fallback import (
    AgentFallbackHandler,
    FallbackStrategy,
    TokenBudget,
    CircuitBreakerState,
    get_fallback_handler,
)
