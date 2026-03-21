"""State management primitives for the AS400 SDD framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PipelineState(str, Enum):
    IDLE = "IDLE"
    REQUIREMENTS = "REQUIREMENTS"
    SPEC_DESIGN = "SPEC_DESIGN"
    TEST_DESIGN = "TEST_DESIGN"
    CODE_GENERATION = "CODE_GENERATION"
    CODE_REVIEW = "CODE_REVIEW"
    TEST_EXECUTION = "TEST_EXECUTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_HUMAN = "WAITING_HUMAN"


@dataclass
class StateSnapshot:
    state: PipelineState
    timestamp: str
    details: dict = field(default_factory=dict)


class StateMachine:
    """Tracks pipeline transitions and keeps a minimal execution history."""

    _allowed_transitions = {
        PipelineState.IDLE: {
            PipelineState.REQUIREMENTS,
            PipelineState.FAILED,
        },
        PipelineState.REQUIREMENTS: {
            PipelineState.SPEC_DESIGN,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.SPEC_DESIGN: {
            PipelineState.TEST_DESIGN,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.TEST_DESIGN: {
            PipelineState.CODE_GENERATION,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.CODE_GENERATION: {
            PipelineState.CODE_REVIEW,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.CODE_REVIEW: {
            PipelineState.TEST_EXECUTION,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.TEST_EXECUTION: {
            PipelineState.COMPLETED,
            PipelineState.WAITING_HUMAN,
            PipelineState.FAILED,
        },
        PipelineState.WAITING_HUMAN: {
            PipelineState.REQUIREMENTS,
            PipelineState.SPEC_DESIGN,
            PipelineState.TEST_DESIGN,
            PipelineState.CODE_GENERATION,
            PipelineState.CODE_REVIEW,
            PipelineState.TEST_EXECUTION,
            PipelineState.FAILED,
            PipelineState.COMPLETED,
        },
        PipelineState.COMPLETED: set(),
        PipelineState.FAILED: set(),
    }

    def __init__(self, initial_state: PipelineState = PipelineState.IDLE):
        self.current_state = initial_state
        self.history: list[StateSnapshot] = [
            StateSnapshot(
                state=initial_state,
                timestamp=self._now(),
                details={"message": "pipeline initialized"},
            )
        ]

    def transition_to(
        self, new_state: PipelineState, details: "dict" = None
    ) -> None:
        if new_state == self.current_state:
            return

        allowed = self._allowed_transitions.get(self.current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition from {self.current_state} to {new_state}"
            )

        self.current_state = new_state
        self.history.append(
            StateSnapshot(
                state=new_state,
                timestamp=self._now(),
                details=details or {},
            )
        )

    def snapshot(self) -> dict:
        return {
            "current_state": self.current_state.value,
            "history": [
                {
                    "state": item.state.value,
                    "timestamp": item.timestamp,
                    "details": item.details,
                }
                for item in self.history
            ],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
