"""Session context primitives for passing execution history across agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class PhaseRecord:
    phase: str
    agent: str
    summary: str
    score: int
    artifacts: dict
    timestamp: str


class SessionContext:
    """Collects per-phase execution summaries and artifacts for the current run."""

    def __init__(self, requirement_path: str):
        self.requirement_path = requirement_path
        self.created_at = self._now()
        self.phases: list[PhaseRecord] = []

    def add_phase(self, record: PhaseRecord) -> None:
        self.phases.append(record)

    def get_history_summary(self) -> str:
        if not self.phases:
            return "暂无已完成阶段。"
        lines = [
            f"[{record.phase}] {record.agent} score={record.score}: {record.summary}"
            for record in self.phases
        ]
        return "\n".join(lines)

    def get_last_artifact(self, key: str) -> str:
        for record in reversed(self.phases):
            value = record.artifacts.get(key)
            if isinstance(value, str):
                return value
        return ""

    def to_dict(self) -> dict:
        return {
            "requirement_path": self.requirement_path,
            "created_at": self.created_at,
            "phases": [asdict(record) for record in self.phases],
        }

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "session_context.json").write_text(
            self._to_json(),
            encoding="utf-8",
        )

    def _to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
