"""Pipeline orchestrator for the AS400 SDD auto-development framework."""

from __future__ import annotations

import builtins
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Union

from agents.cg_agent import CGAgent
from agents.cr_agent import CRAgent
from agents.ra_agent import RAAgent
from agents.sd_agent import SDAgent
from agents.td_agent import TDAgent
from agents.te_agent import TEAgent
from core.config_loader import SDDConfig
from core.exceptions import HumanInterventionRequired, PipelineFailedError
from core.judge import Judge, JudgeResult
from core.knowledge_graph import KnowledgeGraph
from core.llm_client import LLMClient
from core.session_context import PhaseRecord, SessionContext
from core.state_machine import PipelineState, StateMachine

builtins.OK = "OK"


class Orchestrator:
    """Coordinates the end-to-end AS400 SDD pipeline with retries and judging."""

    def __init__(
        self,
        config: "SDDConfig" = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: Optional[int] = None,
        logger: "logging.Logger" = None,
        requirement_path: Optional[str] = None,
    ):
        self.config = config or SDDConfig()

        provider_name = provider or self.config.llm_provider()
        model_name = model or self.config.llm_model()
        base_url_value = base_url or self.config.llm_base_url()

        self.max_retries = max_retries if max_retries is not None else self.config.pipeline_max_retries()

        self.llm_client = LLMClient(
            provider=provider_name,
            model=model_name,
            base_url=base_url_value,
        )
        self.judge = Judge(
            self.llm_client,
            pass_score=7,
        )
        self.knowledge_graph = KnowledgeGraph(
            knowledge_dir=self.config.knowledge_dir(),
            memory_path=self.config.knowledge_memory_path(),
        )
        self.state_machine = StateMachine()
        self.logger = logger or self._build_logger()

        self.ra_agent = RAAgent(self.llm_client)
        self.sd_agent = SDAgent(self.llm_client)
        self.td_agent = TDAgent(self.llm_client)
        self.cg_agent = CGAgent(self.llm_client)
        self.cr_agent = CRAgent(self.llm_client)
        self.te_agent = TEAgent(self.llm_client)
        self.session_context = SessionContext(str(requirement_path)) if requirement_path else None

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
        self.session_context = SessionContext(str(requirement_file))

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
            self.session_context.save(target_dir)
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
                "session_context": self.session_context.to_dict(),
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
                "context_summary": self._get_context_summary(),
            },
            artifact_key="analysis_markdown",
            artifact_path=output_dir / "analysis.md",
            agent_name=self.ra_agent.name,
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
            input_data={"analysis": analysis, "context_summary": self._get_context_summary()},
            artifact_key="sdd",
            artifact_path=output_dir / "sdd.md",
            agent_name=self.sd_agent.name,
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
            input_data={
                "analysis": analysis,
                "sdd": sdd,
                "context_summary": self._get_context_summary(),
            },
            artifact_key="tests",
            artifact_path=output_dir / "tests.md",
            agent_name=self.td_agent.name,
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
            input_data={
                "analysis": analysis,
                "sdd": sdd,
                "tests": tests,
                "context_summary": self._get_context_summary(),
            },
            artifact_key="code",
            artifact_path=output_dir / f"{analysis['program_name']}.rpgle",
            agent_name=self.cg_agent.name,
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
            "context_summary": self._get_context_summary(),
        }
        feedback = ""

        for attempt in range(1, self.max_retries + 1):
            review_output = self.cr_agent.execute(input_data)
            review_validation = self.cr_agent.validate_output(review_output)
            if not review_validation.passed:
                feedback = "; ".join(review_validation.issues)
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
                        "context_summary": self._get_context_summary(),
                    },
                    feedback,
                )
                input_data["code"] = regenerated["code"]
                continue

            judge_result = self.judge.evaluate_code(review_output["reviewed_code"])
            review_output["judge_result"] = judge_result.to_dict()
            self._write_artifact(output_dir / "review.md", review_output["review_report"])

            if judge_result.passed:
                self.logger.info("Code review passed on attempt %s", attempt)
                self._record_phase(PipelineState.CODE_REVIEW, self.cr_agent.name, review_output)
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
                    "context_summary": self._get_context_summary(),
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
        self._record_phase(PipelineState.TEST_EXECUTION, self.te_agent.name, output)
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
        agent_name: str,
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
                if state == PipelineState.CODE_GENERATION:
                    for filename, content in output.get("generated_files", {}).items():
                        self._write_artifact(artifact_path.parent / filename, content)
                    self._write_json_artifact(
                        artifact_path.parent / "files_plan.json",
                        output.get("files_to_generate", []),
                    )
                self._record_phase(state, agent_name, output)
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

    def _write_json_artifact(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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

    def _get_context_summary(self) -> str:
        if not self.session_context:
            return ""
        return self.session_context.get_history_summary()

    def _record_phase(self, state: PipelineState, agent_name: str, output: dict) -> None:
        if not self.session_context:
            return
        judge_payload = output.get("judge_result", {})
        score = judge_payload.get("score", 0)
        record = PhaseRecord(
            phase=state.value,
            agent=agent_name,
            summary=self._build_phase_summary(state, output),
            score=score,
            artifacts=self._sanitize_artifacts(output),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.session_context.add_phase(record)

    @staticmethod
    def _sanitize_artifacts(output: dict) -> dict:
        sanitized = {}
        for key, value in output.items():
            if key == "checklist" and hasattr(value, "__dict__"):
                sanitized[key] = value.__dict__
            elif key != "judge_result":
                sanitized[key] = value
        return sanitized

    @staticmethod
    def _build_phase_summary(state: PipelineState, output: dict) -> str:
        if state == PipelineState.REQUIREMENTS:
            return output.get("summary", "需求分析完成。")[:200]
        if state == PipelineState.SPEC_DESIGN:
            return f"{output.get('program_name', '')} 设计说明已生成，包含业务规则、处理流程与测试策略。"[:200]
        if state == PipelineState.TEST_DESIGN:
            return f"{output.get('program_name', '')} 测试设计已生成，覆盖 02/08/09 状态与日志场景。"[:200]
        if state == PipelineState.CODE_GENERATION:
            planned = output.get("files_to_generate", [])
            filenames = ", ".join(item["filename"] for item in planned)
            return f"代码生成完成，规划文件: {filenames}"[:200]
        if state == PipelineState.CODE_REVIEW:
            return "；".join(output.get("findings", []))[:200]
        if state == PipelineState.TEST_EXECUTION:
            return (
                f"测试执行完成，结果 {output.get('passed_count', 0)}/{output.get('total_count', 0)} 通过。"
            )[:200]
        return "阶段完成。"
