"""Custom exceptions for the AS400 SDD framework."""


class FrameworkError(Exception):
    """Base exception for framework-level failures."""


class ValidationError(FrameworkError):
    """Raised when an artifact fails structural validation."""


class LLMError(FrameworkError):
    """Raised when an LLM provider call fails."""


class PipelineFailedError(FrameworkError):
    """Raised when the orchestrator cannot recover from a failure."""


from typing import Optional, Dict


class HumanInterventionRequired(FrameworkError):
    """Raised when the pipeline pauses for a human decision."""

    def __init__(self, phase: str, reason: str, context: Optional[Dict] = None):
        super().__init__(reason)
        self.phase = phase
        self.reason = reason
        self.context = context or {}
