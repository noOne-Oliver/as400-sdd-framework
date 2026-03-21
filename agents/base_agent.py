"""Base agent abstractions used by all domain-specific agents."""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.llm_client import LLMClient

builtins.OK = "OK"


@dataclass
class ValidationResult:
    passed: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseAgent(ABC):
    """Common agent behaviour for prompt loading, validation, and retries."""

    def __init__(
        self,
        name: str,
        llm_client: "LLMClient" = None,
        prompt_dir: "Path" = None,
    ):
        self.name = name
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.prompt_dir = Path(prompt_dir) if prompt_dir else None

    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        """Execute the agent and return a structured artifact payload."""

    def validate_output(self, output: dict) -> ValidationResult:
        if not isinstance(output, dict):
            return ValidationResult(False, ["Agent output must be a dictionary."])
        if not output:
            return ValidationResult(False, ["Agent output is empty."])
        return ValidationResult(True, [])

    def retry_with_feedback(self, input_data: dict, feedback: str) -> dict:
        retry_payload = dict(input_data)
        retry_payload["feedback"] = feedback
        return self.execute(retry_payload)

    def _load_prompt(self, prompt_name: str) -> str:
        if not self.prompt_dir:
            return ""
        prompt_path = self.prompt_dir / prompt_name
        if not prompt_path.exists():
            return ""
        return prompt_path.read_text(encoding="utf-8")
