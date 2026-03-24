"""Tests for production-ready enhancements: TaskClassifier, Observability, ModelRouter, Fallback."""

import pytest
from core.task_classifier import TaskClassifier, TaskType, TaskComplexity, get_task_classifier
from core.observability import MetricsCollector, get_metrics_collector
from core.model_router import ModelRouter, get_model_router, ModelConfig
from core.agent_fallback import AgentFallbackHandler, FallbackStrategy, TokenBudget, get_fallback_handler


class TestTaskClassifier:
    """Tests for TaskClassifier."""

    def test_classify_parallel_task(self):
        """Test that parallel tasks are correctly classified."""
        classifier = TaskClassifier()

        result = classifier.classify("code_generation")

        assert result.task_type == TaskType.PARALLEL
        assert result.complexity == TaskComplexity.COMPLEX
        assert result.use_multi_agent is True

    def test_classify_sequential_task(self):
        """Test that sequential tasks are correctly classified."""
        classifier = TaskClassifier()

        result = classifier.classify("requirements_analysis")

        assert result.task_type == TaskType.SEQUENTIAL
        assert result.use_multi_agent is False

    def test_get_classification_stats(self):
        """Test classification statistics."""
        classifier = TaskClassifier()
        classifier.classify("code_generation")
        classifier.classify("requirements_analysis")

        stats = classifier.get_classification_stats()

        assert stats["total"] == 2
        assert "type_distribution" in stats

    def test_singleton(self):
        """Test that get_task_classifier returns same instance."""
        c1 = get_task_classifier()
        c2 = get_task_classifier()
        assert c1 is c2


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_record_and_get_stats(self):
        """Test recording metrics and retrieving stats."""
        collector = MetricsCollector(pipeline_id="test_pipeline")

        collector.record_agent_execution(
            agent_name="ra_agent",
            phase="REQUIREMENTS",
            latency_ms=1500.0,
            token_used=500,
            success=True,
        )

        stats = collector.get_agent_stats("ra_agent")
        assert stats["count"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["avg_latency_ms"] == 1500.0

    def test_percentile_calculation(self):
        """Test percentile calculations."""
        collector = MetricsCollector()

        # Record multiple executions
        for i in [100, 200, 300, 400, 500]:
            collector.record_agent_execution(
                agent_name="cg_agent",
                phase="CODE_GENERATION",
                latency_ms=float(i),
                token_used=100,
                success=True,
            )

        stats = collector.get_agent_stats("cg_agent")
        assert stats["p50_latency_ms"] == 300.0
        assert stats["p95_latency_ms"] == 500.0

    def test_anomaly_detection(self):
        """Test anomaly detection for high latency."""
        collector = MetricsCollector()

        # Record high latency executions
        for _ in range(3):
            collector.record_agent_execution(
                agent_name="slow_agent",
                phase="TEST",
                latency_ms=6000.0,  # > 5000ms threshold
                token_used=100,
                success=True,
            )

        alerts = collector.check_anomalies()
        assert len(alerts) > 0
        assert alerts[0]["type"] == "high_latency"

    def test_save_metrics(self, tmp_path):
        """Test saving metrics to file."""
        collector = MetricsCollector(pipeline_id="test_save")
        collector.record_agent_execution(
            agent_name="ra_agent",
            phase="REQUIREMENTS",
            latency_ms=1000.0,
            token_used=200,
            success=True,
        )

        output_file = collector.save_metrics(tmp_path)
        assert output_file.exists()


class TestModelRouter:
    """Tests for ModelRouter."""

    def test_get_model_for_agent(self):
        """Test model selection for different agents."""
        router = ModelRouter()

        # Complex agent should get large model
        model = router.get_model_for_agent("cg_agent")
        assert "large" in model.name

        # Simple agent should get small model
        model = router.get_model_for_agent("te_agent")
        assert "small" in model.name

    def test_estimate_cost(self):
        """Test cost estimation."""
        router = ModelRouter()

        estimate = router.estimate_cost("cg_agent", estimated_tokens=1000)
        assert "large_model_cost" in estimate
        assert "small_model_cost" in estimate
        assert estimate["savings"] >= 0

    def test_routing_stats(self):
        """Test routing statistics."""
        router = ModelRouter()
        router.get_model_for_agent("cg_agent")
        router.get_model_for_agent("te_agent")

        stats = router.get_routing_stats()
        assert stats["total_routes"] == 2
        assert "model_usage" in stats


class TestAgentFallbackHandler:
    """Tests for AgentFallbackHandler."""

    def test_fallback_config(self):
        """Test fallback configuration."""
        handler = AgentFallbackHandler()

        config = handler.get_fallback_config("ra_agent")
        assert config.enabled is True
        assert config.strategy == FallbackStrategy.RETURN_DEFAULT

    def test_token_budget(self):
        """Test token budget management."""
        handler = AgentFallbackHandler()
        budget = TokenBudget(max_tokens=4000)

        handler.set_token_budget("test_agent", budget)
        retrieved = handler.get_token_budget("test_agent")

        assert retrieved.max_tokens == 4000

    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        handler = AgentFallbackHandler()

        # Should be closed initially
        assert handler.check_circuit_breaker("test_agent") is True

        # Record failures
        handler.record_failure("test_agent", "error1")
        handler.record_failure("test_agent", "error2")
        handler.record_failure("test_agent", "error3")

        # Should be open after 3 failures
        assert handler.check_circuit_breaker("test_agent") is False

    def test_record_success(self):
        """Test success resets circuit breaker."""
        handler = AgentFallbackHandler()

        handler.record_failure("test_agent", "error1")
        handler.record_success("test_agent")

        # Should be closed after success
        assert handler.check_circuit_breaker("test_agent") is True

    def test_execute_with_fallback(self):
        """Test execute_with_fallback."""
        handler = AgentFallbackHandler()

        def primary():
            return {"success": True}

        result = handler.execute_with_fallback("ra_agent", primary)
        assert result["success"] is True

    def test_execute_with_fallback_on_failure(self):
        """Test fallback on primary failure."""
        handler = AgentFallbackHandler()

        def primary_fail():
            raise RuntimeError("Primary failed")

        result = handler.execute_with_fallback("ra_agent", primary_fail)
        # Should return default fallback output
        assert "program_name" in result or "summary" in result

    def test_token_limit_check(self):
        """Test token limit checking."""
        handler = AgentFallbackHandler()
        budget = TokenBudget(max_tokens=1000, warning_threshold=0.8, critical_threshold=0.95)

        handler.set_token_budget("test_agent", budget)

        # Within limit
        ok, msg = handler.check_token_limit("test_agent", 500)
        assert ok is True

        # Warning threshold
        ok, msg = handler.check_token_limit("test_agent", 850)
        assert "WARNING" in msg

        # Critical threshold
        ok, msg = handler.check_token_limit("test_agent", 960)
        assert ok is False
        assert "CRITICAL" in msg
