"""Tests for core/config_loader.py and config/sdd_config.yaml."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from core.config_loader import SDDConfig


@pytest.fixture
def sample_config_file(tmp_path):
    config = {
        "name": "test-framework",
        "version": "1.0",
        "llm": {
            "provider": "ollama",
            "model": "qwen2.5",
            "base_url": "http://localhost:11434",
            "max_retries": 5,
        },
        "pipeline": {
            "stages": ["REQUIREMENTS", "SPEC_DESIGN"],
            "manual_approval_points": ["REQUIREMENTS"],
            "max_retries": 4,
        },
        "validation": {
            "spec_rules_path": "validation/spec_rules.yaml",
            "code_rules_path": "validation/code_rules.yaml",
        },
        "knowledge": {
            "knowledge_dir": "kb",
            "memory_path": "kb/.kg_memory.json",
        },
        "session": {
            "output_dir": "outputs",
            "save_session_context": True,
            "save_files_plan": False,
        },
        "tools": {
            "enabled": ["shell"],
            "shell": {"allowed_commands": ["python3"]},
        },
        "agents": {
            "ra_agent": {"name": "ra_agent", "description": "RA agent"},
        },
    }
    path = tmp_path / "sdd_config.yaml"
    path.write_text(yaml.dump(config), encoding="utf-8")
    return path


def test_sdd_config_loads_yaml(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.get("name") == "test-framework"


def test_sdd_config_llm_settings(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.llm_provider() == "ollama"
    assert cfg.llm_model() == "qwen2.5"
    assert cfg.llm_base_url() == "http://localhost:11434"
    assert cfg.llm_max_retries() == 5


def test_sdd_config_pipeline_stages(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.pipeline_stages() == ["REQUIREMENTS", "SPEC_DESIGN"]


def test_sdd_config_manual_approval_points(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.manual_approval_points() == ["REQUIREMENTS"]


def test_sdd_config_pipeline_max_retries(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.pipeline_max_retries() == 4


def test_sdd_config_validation_rules(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    rules = cfg.validation_rules()
    assert "spec_rules_path" in rules
    assert rules["spec_rules_path"] == "validation/spec_rules.yaml"


def test_sdd_config_knowledge_dir(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.knowledge_dir() == "kb"


def test_sdd_config_knowledge_memory_path(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.knowledge_memory_path() == "kb/.kg_memory.json"


def test_sdd_config_session_settings(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.session_output_dir() == "outputs"
    assert cfg.session_save_session_context() is True
    assert cfg.session_save_files_plan() is False


def test_sdd_config_tools_enabled(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    assert cfg.tools_enabled() == ["shell"]


def test_sdd_config_tool_config(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    shell_cfg = cfg.tool_config("shell")
    assert shell_cfg["allowed_commands"] == ["python3"]


def test_sdd_config_agent_config(sample_config_file):
    cfg = SDDConfig(str(sample_config_file))
    ra_cfg = cfg.agent_config("ra_agent")
    assert ra_cfg["name"] == "ra_agent"


def test_sdd_config_file_not_found():
    import pytest
    with pytest.raises(OSError):
        SDDConfig("nonexistent.yaml")


def test_sdd_config_defaults_for_missing_keys(tmp_path):
    """Missing optional keys should return sensible defaults."""
    path = tmp_path / "minimal.yaml"
    path.write_text(yaml.dump({"name": "min"}), encoding="utf-8")
    cfg = SDDConfig(str(path))
    assert cfg.llm_provider() == "mock"  # default
    assert cfg.pipeline_stages() == []     # empty list default
    assert cfg.llm_base_url() is None
    assert cfg.knowledge_dir() == "knowledge"
