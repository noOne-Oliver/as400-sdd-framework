from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_cli_generates_artifacts(
    repo_root: Path,
    order_processing_requirement: Path,
    generated_output_dir: Path,
):
    result = subprocess.run(
        [
            sys.executable,
            "run.py",
            "--requirement",
            str(order_processing_requirement),
            "--output-dir",
            str(generated_output_dir),
            "--provider",
            "mock",
            "--model",
            "llama3.1",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"

    expected_files = {
        "analysis.md",
        "sdd.md",
        "tests.md",
        "ORDPRC.rpgle",
        "review.md",
        "execution_report.md",
    }
    assert expected_files.issubset({path.name for path in generated_output_dir.iterdir()})
