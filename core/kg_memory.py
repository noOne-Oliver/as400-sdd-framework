"""Cross-run knowledge memory for KnowledgeGraph — persists learned facts across sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class KGMemory:
    """Stores and retrieves learned knowledge per program/requirement name."""

    def __init__(self, storage_path: str | Path = "knowledge/.kg_memory.json"):
        self.storage_path = Path(storage_path)
        self._cache: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                self._cache = json.loads(self.storage_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _persist(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_context(self, requirement_name: str, kg_state: dict) -> None:
        """Remember KG search results and extracted facts from a pipeline run."""
        self._cache[requirement_name] = {
            "matched_documents": kg_state.get("matched_documents", []),
            "facts": kg_state.get("facts", []),
            "status_codes": kg_state.get("status_codes", []),
            "program_name": kg_state.get("program_name", ""),
        }
        self._persist()

    def load_context(self, requirement_name: str) -> Optional[dict]:
        """Retrieve previously learned knowledge for this requirement, or None."""
        return self._cache.get(requirement_name)

    def get_learned_facts(self, requirement_name: str) -> list[str]:
        """Return flattened list of fact strings remembered from past runs."""
        ctx = self.load_context(requirement_name)
        if not ctx:
            return []
        return ctx.get("facts", [])

    def has_memory(self, requirement_name: str) -> bool:
        return requirement_name in self._cache

    def clear(self, requirement_name: str = None) -> None:
        if requirement_name:
            self._cache.pop(requirement_name, None)
        else:
            self._cache.clear()
        self._persist()
