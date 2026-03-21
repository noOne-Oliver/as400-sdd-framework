"""Tests for parallel execution and StageDriver."""

from __future__ import annotations

import pytest

from core.stage_driver import StageSpec


class TestStageSpec:
    def test_stage_spec_parses_basic_config(self):
        config = {
            "name": "REQUIREMENTS",
            "agent": "ra_agent",
            "input_keys": ["requirement_text"],
            "output_key": "analysis",
            "judge": "evaluate_spec",
            "artifact": "analysis.md",
        }
        spec = StageSpec(config)
        assert spec.name == "REQUIREMENTS"
        assert spec.agent_name == "ra_agent"
        assert spec.input_keys == ["requirement_text"]
        assert spec.output_key == "analysis"
        assert spec.judge_method == "evaluate_spec"

    def test_stage_spec_resolve_artifact_with_program_name(self):
        config = {"name": "CG", "agent": "cg_agent", "artifact": "{program_name}.rpgle"}
        spec = StageSpec(config)
        path = spec.resolve_artifact({"program_name": "ORDPRC"})
        assert path.name == "ORDPRC.rpgle"

    def test_stage_spec_resolve_artifact_no_placeholder(self):
        config = {"name": "TEST", "agent": "te_agent", "artifact": "execution_report.md"}
        spec = StageSpec(config)
        path = spec.resolve_artifact({})
        assert path.name == "execution_report.md"

    def test_stage_spec_defaults(self):
        spec = StageSpec({})
        assert spec.name == ""
        assert spec.agent_name == ""
        assert spec.input_keys == []
        assert spec.output_key == ""
        assert spec.judge_method == ""
        assert spec.artifact == ""


class TestParallelExecution:
    def test_orchestrator_parallel_td_cg_method_exists(self):
        """Verify _run_parallel_td_and_cg is defined on Orchestrator."""
        from core.orchestrator import Orchestrator
        assert hasattr(Orchestrator, "_run_parallel_td_and_cg")
        assert callable(getattr(Orchestrator, "_run_parallel_td_and_cg"))

    def test_orchestrator_parallel_td_cg_signature(self):
        """Verify the method has the expected parameters."""
        from core.orchestrator import Orchestrator
        import inspect
        sig = inspect.signature(Orchestrator._run_parallel_td_and_cg)
        params = list(sig.parameters.keys())
        assert "analysis" in params
        assert "sdd" in params
        assert "output_dir" in params
        assert "allow_human_intervention" in params

    def test_raw_transition_methods_exist(self):
        """Verify transition_test_design_raw and transition_code_generation_raw exist."""
        from core.orchestrator import Orchestrator
        assert hasattr(Orchestrator, "transition_test_design_raw")
        assert hasattr(Orchestrator, "transition_code_generation_raw")
