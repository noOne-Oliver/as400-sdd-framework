"""Declarative stage driver — runs pipeline stages defined in sdd_config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.judge import Judge
from core.llm_client import LLMClient


class StageSpec:
    """Parsed definition of a single pipeline stage from sdd_config.yaml."""

    def __init__(self, stage_config: Dict[str, Any]):
        self.name: str = stage_config.get("name", "")
        self.agent_name: str = stage_config.get("agent", "")
        self.input_keys: List[str] = stage_config.get("input_keys", [])
        self.output_key: str = stage_config.get("output_key", "")
        self.judge_method: str = stage_config.get("judge", "")
        self.artifact: str = stage_config.get("artifact", "")
        self.retry_with_feedback: bool = stage_config.get("retry_with_feedback", True)

    def resolve_artifact(self, context: Dict[str, Any]) -> Path:
        """Expand {program_name} etc. in artifact path using current context."""
        path_str = self.artifact
        for key, val in context.items():
            path_str = path_str.replace(f"{{{key}}}", str(val))
        return Path(path_str)


class StageDriver:
    """Runs a single stage given its spec and the current pipeline context.

    The orchestrator holds ``context`` (a mutable dict) that accumulates
    outputs from all completed stages.  Each driver call reads the keys it
    needs from ``context`` and writes its own output back under
    ``output_key``.
    """

    def __init__(
        self,
        stage_spec: "StageSpec",
        agent_registry: Dict[str, object],
        judge: "Judge",
        logger,  # logging.Logger
    ):
        self.spec = stage_spec
        self.agents = agent_registry
        self.judge = judge
        self.logger = logger

    def input_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the keys this stage needs from the shared context."""
        data: Dict[str, Any] = {}
        for key in self.spec.input_keys:
            data[key] = context.get(key)
        return data

    def run(
        self,
        context: Dict[str, Any],
        output_dir: Path,
        allow_human_intervention: bool = False,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute the stage: run agent → validate → judge → return output dict."""
        agent = self.agents.get(self.spec.agent_name)
        if agent is None:
            raise ValueError(f"Agent '{self.spec.agent_name}' not found in registry")

        payload = self.input_data(context)
        feedback = ""
        last_error = ""

        for attempt in range(1, max_retries + 1):
            self.logger.info(
                "%s attempt=%d", self.spec.name, attempt
            )

            if feedback and self.spec.retry_with_feedback:
                output = agent.retry_with_feedback(payload, feedback)
            else:
                output = agent.execute(payload)

            validation = agent.validate_output(output)
            if not validation.passed:
                last_error = "; ".join(validation.issues)
                self.logger.warning(
                    "%s validation failed [%d]: %s",
                    self.spec.name, attempt, last_error
                )
                feedback = f"Validation failed: {last_error}"
                continue

            judge_output = self._run_judge(output)
            if judge_output is not None:
                judge_passed = judge_output.get("passed", False)
                score = judge_output.get("score", 0)
                if not judge_passed:
                    last_error = judge_output.get("issues", "")
                    self.logger.warning(
                        "%s judge failed [%d] score=%s: %s",
                        self.spec.name, attempt, score, last_error
                    )
                    feedback = f"Judge feedback: {last_error}"
                    continue

            self.logger.info(
                "%s passed (score=%s)",
                self.spec.name,
                judge_output.get("score") if judge_output else "N/A",
            )
            result = output
            if judge_output:
                result["judge_result"] = judge_output
            context[self.spec.output_key] = result
            return result

        raise RuntimeError(
            f"Stage '{self.spec.name}' failed after {max_retries} attempts: {last_error}"
        )

    def _run_judge(self, output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatch to the appropriate judge method, or None if no judge needed."""
        method_name = self.spec.judge_method
        if not method_name:
            return None
        judge_fn = getattr(self.judge, method_name, None)
        if judge_fn is None:
            return None
        judged = judge_fn(output.get(self.spec.output_key, ""))
        return {
            "passed": judged.passed,
            "score": judged.score,
            "issues": judged.issues,
            "recommendations": getattr(judged, "recommendations", []),
        }
