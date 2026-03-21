"""Pipeline orchestrator for the AS400 SDD auto-development framework."""

from __future__ import annotations

import builtins
import json
import logging
from pathlib import Path
from typing import Callable

import yaml

from agents.cg_agent import CGAgent
from agents.cr_agent import CRAgent
from agents.ra_agent import RAAgent
from agents.sd_agent import SDAgent
from agents.td_agent import TDAgent
from agents.te_agent import TEAgent
from core.exceptions import HumanInterventionRequired, PipelineFailedError
from core.judge import Judge, JudgeResult
from core.knowledge_graph import KnowledgeGraph
from core.llm_client import LLMClient
from core.state_machine import PipelineState, StateMachine

builtins.OK = "OK"


class Orchestrator:
    """Coordinates the end-to-end AS400 SDD pipeline with retries and judging."""

    def __init__(
        self,
        config_dir: "Path" = "config",
        provider: str = None,
        model: str = None,
        base_url: str = None,
        max_retries: int = 3,
        logger: "logging.Logger" = None,
    ):
        self.config_dir = Path(config_dir)
        self.pipeline_config = self._load_yaml("pipeline.yaml")
        self.agent_config = self._load_yaml("agents.yaml")
        self.validation_config = self._load_yaml("validation.yaml")

        provider_name = provider or self.pipeline_config.get("llm", {}).get("provider", "mock")
        model_name = model or self.pipeline_config.get("llm", {}).get("model", "llama3.1")
        base_url_value = (
            base_url
            or self.pipeline_config.get("llm", {}).get("base_url", "http://localhost:11434")
        )

        self.max_retries = max_retries
        self.llm_client = LLMClient(provider=provider_name, model=model_name, base_url=base_url_value)
        self.judge = Judge(self.llm_client, pass_score=self.validation_config.get("judge", {}).get("pass_score", 7))
        self.knowledge_graph = KnowledgeGraph("knowledge")
        self.state_machine = StateMachine()
        self.logger = logger or self._build_logger()

        self.ra_agent = RAAgent(self.llm_client)
        self.sd_agent = SDAgent(self.llm_client)
        self.td_agent = TDAgent(self.llm_client)
        self.cg_agent = CGAgent(self.llm_client)
        self.cr_agent = CRAgent(self.llm_client)
        self.te_agent = TEAgent(self.llm_client)

    def run(
        self,
        requirement_path: str | Path,
        output_dir: "Path" = None,
        allow_human_intervention: bool = False,
    ) -> dict:
        requirement_file = Path(requirement_path)
        target_dir = Path(output_dir) if output_dir else requirement_file.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("Pipeline started for requirement: %s", requirement_file)
        self.state_machine = StateMachine()

        try:
            requirement_text = requirement_file.read_text(encoding="utf-8")
            analysis = self.transition_requirements(
                requirement_text=requirement_text,
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )
            sdd_result = self.transition_spec_design(
                analysis=analysis,
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )
            tests_result = self.transition_test_design(
                analysis=analysis,
                sdd=sdd_result["sdd"],
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )
            code_result = self.transition_code_generation(
                analysis=analysis,
                sdd=sdd_result["sdd"],
                tests=tests_result["tests"],
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )
            review_result = self.transition_code_review(
                program_name=analysis["program_name"],
                analysis=analysis,
                sdd=sdd_result["sdd"],
                tests=tests_result["tests"],
                code=code_result["code"],
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )
            execution_result = self.transition_test_execution(
                program_name=analysis["program_name"],
                tests=tests_result["tests"],
                code=review_result["reviewed_code"],
                output_dir=target_dir,
                allow_human_intervention=allow_human_intervention,
            )

            self.state_machine.transition_to(
                PipelineState.COMPLETED,
                {"message": "Pipeline completed successfully"},
            )
            self.logger.info("Pipeline completed successfully")
            return {
                "status": "completed",
                "state": self.state_machine.snapshot(),
                "artifacts": {
                    "analysis": analysis["analysis_markdown"],
                    "sdd": sdd_result["sdd"],
                    "tests": tests_result["tests"],
                    "code": review_result["reviewed_code"],
                    "review_report": review_result["review_report"],
                    "execution_report": execution_result["execution_report"],
                },
            }
        except HumanInterventionRequired as exc:
            self.logger.warning("Pipeline paused for human intervention: %s", exc.reason)
            return {
                "status": "waiting_human",
                "state": self.state_machine.snapshot(),
                "phase": exc.phase,
                "reason": exc.reason,
                "context": exc.context,
            }
        except Exception as exc:
            self.state_machine.transition_to(
                PipelineState.FAILED,
                {"message": str(exc)},
            )
            self.logger.exception("Pipeline failed")
            return {
                "status": "failed",
                "state": self.state_machine.snapshot(),
                "error": str(exc),
            }

    def transition_requirements(
        self,
        requirement_text: str,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.REQUIREMENTS)
        return self._run_agent_with_judge(
            state=PipelineState.REQUIREMENTS,
            agent_runner=lambda payload: self.ra_agent.execute(payload),
            validator=lambda output: self.ra_agent.validate_output(output),
            judge_runner=lambda output: self.judge.evaluate_spec(output["analysis_markdown"]),
            input_data={
                "requirement_text": requirement_text,
                "knowledge_context": self.knowledge_graph.build_context(requirement_text),
            },
            artifact_key="analysis_markdown",
            artifact_path=output_dir / "analysis.md",
            allow_human_intervention=allow_human_intervention,
        )

    def transition_spec_design(
        self,
        analysis: dict,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.SPEC_DESIGN)
        return self._run_agent_with_judge(
            state=PipelineState.SPEC_DESIGN,
            agent_runner=lambda payload: self.sd_agent.execute(payload),
            validator=lambda output: self.sd_agent.validate_output(output),
            judge_runner=lambda output: self.judge.evaluate_spec(output["sdd"]),
            input_data={"analysis": analysis},
            artifact_key="sdd",
            artifact_path=output_dir / "sdd.md",
            allow_human_intervention=allow_human_intervention,
        )

    def transition_test_design(
        self,
        analysis: dict,
        sdd: str,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.TEST_DESIGN)
        return self._run_agent_with_judge(
            state=PipelineState.TEST_DESIGN,
            agent_runner=lambda payload: self.td_agent.execute(payload),
            validator=lambda output: self.td_agent.validate_output(output),
            judge_runner=lambda output: self.judge.evaluate_tests(output["tests"]),
            input_data={"analysis": analysis, "sdd": sdd},
            artifact_key="tests",
            artifact_path=output_dir / "tests.md",
            allow_human_intervention=allow_human_intervention,
        )

    def transition_code_generation(
        self,
        analysis: dict,
        sdd: str,
        tests: str,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.CODE_GENERATION)
        return self._run_agent_with_judge(
            state=PipelineState.CODE_GENERATION,
            agent_runner=lambda payload: self.cg_agent.execute(payload),
            validator=lambda output: self.cg_agent.validate_output(output),
            judge_runner=lambda output: self.judge.evaluate_code(output["code"]),
            input_data={"analysis": analysis, "sdd": sdd, "tests": tests},
            artifact_key="code",
            artifact_path=output_dir / f"{analysis['program_name']}.rpgle",
            allow_human_intervention=allow_human_intervention,
        )

    def transition_code_review(
        self,
        program_name: str,
        analysis: dict,
        sdd: str,
        tests: str,
        code: str,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.CODE_REVIEW)
        input_data = {
            "program_name": program_name,
            "code": code,
        }
        feedback = ""

        for attempt in range(1, self.max_retries + 1):
            review_output = self.cr_agent.execute(input_data)
            review_validation = self.cr_agent.validate_output(review_output)
            if not review_validation.passed:
                feedback = "; ".join(review_validation.issues)
                continue

            judge_result = self.judge.evaluate_code(review_output["reviewed_code"])
            review_output["judge_result"] = judge_result.to_dict()
            self._write_artifact(output_dir / "review.md", review_output["review_report"])

            if judge_result.passed:
                self.logger.info("Code review passed on attempt %s", attempt)
                return review_output

            feedback = self._format_feedback("code review", judge_result)
            if attempt == self.max_retries:
                self._handle_human_intervention(
                    allow_human_intervention,
                    PipelineState.CODE_REVIEW,
                    feedback,
                    {"program_name": program_name},
                )
                raise PipelineFailedError(feedback)

            regenerated = self.cg_agent.retry_with_feedback(
                {
                    "analysis": analysis,
                    "sdd": sdd,
                    "tests": tests,
                },
                feedback,
            )
            input_data["code"] = regenerated["code"]

        raise PipelineFailedError("Code review failed unexpectedly.")

    def transition_test_execution(
        self,
        program_name: str,
        tests: str,
        code: str,
        output_dir: Path,
        allow_human_intervention: bool,
    ) -> dict:
        self.state_machine.transition_to(PipelineState.TEST_EXECUTION)
        input_data = {"program_name": program_name, "tests": tests, "code": code}
        output = self.te_agent.execute(input_data)
        validation = self.te_agent.validate_output(output)
        if not validation.passed:
            raise PipelineFailedError("; ".join(validation.issues))
        self._write_artifact(output_dir / "execution_report.md", output["execution_report"])
        score = 8 if output.get("passed") else 4
        output["judge_result"] = {"score": score, "passed": score >= 7, "issues": [], "recommendations": ["Test execution completed"]}
        return output

    def _run_agent_with_judge(
        self,
        state: PipelineState,
        agent_runner: Callable[[dict], dict],
        validator: Callable[[dict], object],
        judge_runner: Callable[[dict], JudgeResult],
        input_data: dict,
        artifact_key: str,
        artifact_path: Path,
        allow_human_intervention: bool,
    ) -> dict:
        feedback = ""
        last_error = "Unknown failure"

        for attempt in range(1, self.max_retries + 1):
            self.logger.info("State=%s attempt=%s", state.value, attempt)
            execution_input = dict(input_data)
            if feedback:
                execution_input["feedback"] = feedback

            output = agent_runner(execution_input)
            validation = validator(output)
            if not validation.passed:
                last_error = "; ".join(validation.issues)
                feedback = last_error
                self.logger.warning("%s validation failed: %s", state.value, last_error)
                continue

            artifact = output[artifact_key]
            self._write_artifact(artifact_path, artifact)
            judge_result = judge_runner(output)
            output["judge_result"] = judge_result.to_dict()

            if judge_result.passed:
                self.logger.info("%s passed judge with score=%s", state.value, judge_result.score)
                return output

            last_error = self._format_feedback(state.value, judge_result)
            feedback = last_error
            self.logger.warning("%s judge failed: %s", state.value, last_error)

        self._handle_human_intervention(
            allow_human_intervention,
            state,
            last_error,
            {"artifact_path": str(artifact_path)},
        )
        raise PipelineFailedError(last_error)

    def _handle_human_intervention(
        self,
        allow_human_intervention: bool,
        state: PipelineState,
        reason: str,
        context: "dict" = None,
    ) -> None:
        if not allow_human_intervention:
            return
        self.state_machine.transition_to(
            PipelineState.WAITING_HUMAN,
            {"phase": state.value, "reason": reason},
        )
        raise HumanInterventionRequired(state.value, reason, context)

    def _write_artifact(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    @staticmethod
    def _format_feedback(phase: str, judge_result: JudgeResult) -> str:
        issues = ", ".join(judge_result.issues) or "no issues"
        recommendations = ", ".join(judge_result.recommendations) or "no recommendations"
        return (
            f"{phase} failed judge evaluation with score {judge_result.score}: "
            f"issues={issues}; recommendations={recommendations}"
        )

    @staticmethod
    def _build_logger() -> logging.Logger:
        logger = logging.getLogger("as400_sdd_framework")
        if logger.handlers:
            return logger
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    def dump_state(self) -> str:
        return json.dumps(self.state_machine.snapshot(), ensure_ascii=False, indent=2)
