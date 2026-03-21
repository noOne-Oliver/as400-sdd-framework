"""Unified config loader — reads config/sdd_config.yaml as the single source of truth."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class SDDConfig:
    """Thin wrapper around the sdd_config.yaml document."""

    def __init__(self, config_path: str | Path = "config/sdd_config.yaml"):
        self.path = Path(config_path)
        self._raw: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path}")
        self._raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    def llm_provider(self) -> str:
        return self._raw.get("llm", {}).get("provider", "mock")

    def llm_model(self) -> str:
        return self._raw.get("llm", {}).get("model", "llama3.1")

    def llm_base_url(self) -> Optional[str]:
        return self._raw.get("llm", {}).get("base_url")

    def llm_max_retries(self) -> int:
        return self._raw.get("llm", {}).get("max_retries", 3)

    def pipeline_stages(self) -> list:
        return self._raw.get("pipeline", {}).get("stages", [])

    def manual_approval_points(self) -> list:
        return self._raw.get("pipeline", {}).get("manual_approval_points", [])

    def pipeline_max_retries(self) -> int:
        return self._raw.get("pipeline", {}).get("max_retries", 3)

    def validation_rules(self) -> Dict[str, str]:
        return self._raw.get("validation", {})

    def knowledge_dir(self) -> str:
        return self._raw.get("knowledge", {}).get("knowledge_dir", "knowledge")

    def knowledge_memory_path(self) -> str:
        return self._raw.get("knowledge", {}).get("memory_path", "knowledge/.kg_memory.json")

    def session_output_dir(self) -> str:
        return self._raw.get("session", {}).get("output_dir", "outputs")

    def session_save_session_context(self) -> bool:
        return self._raw.get("session", {}).get("save_session_context", True)

    def session_save_files_plan(self) -> bool:
        return self._raw.get("session", {}).get("save_files_plan", True)

    def tools_enabled(self) -> list:
        return self._raw.get("tools", {}).get("enabled", [])

    def tool_config(self, tool_name: str) -> Dict[str, Any]:
        return self._raw.get("tools", {}).get(tool_name, {})

    def agent_config(self, agent_name: str) -> Dict[str, Any]:
        return self._raw.get("agents", {}).get(agent_name, {})
