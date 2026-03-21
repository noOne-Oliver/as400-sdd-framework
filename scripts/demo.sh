#!/usr/bin/env bash
set -euo pipefail

REQ_PATH=${1:-"examples/order_processing/requirement.txt"}
OUT_DIR=${2:-"examples/order_processing"}

python3 - <<PY
from core.orchestrator import Orchestrator

orchestrator = Orchestrator(provider="mock")
result = orchestrator.run("${REQ_PATH}", output_dir="${OUT_DIR}")
print("Demo status:", result.get("status"))
print("Artifacts:")
for key, value in result.get("artifacts", {}).items():
    print(f"- {key}: {len(value)} chars")
PY
