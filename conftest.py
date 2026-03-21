"""Shared pytest fixtures for the AS400 SDD framework test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""

    return PROJECT_ROOT


@pytest.fixture
def order_processing_requirement(repo_root: Path) -> Path:
    """Return the sample requirement used by CLI integration tests."""

    return repo_root / "examples" / "order_processing" / "requirement.txt"


@pytest.fixture
def generated_output_dir(tmp_path: Path) -> Path:
    """Provide an isolated output directory for generated artifacts."""

    return tmp_path / "generated-artifacts"
