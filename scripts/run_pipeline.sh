#!/usr/bin/env bash
set -euo pipefail

REQ_PATH=${1:-"examples/order_processing/requirement.txt"}
OUT_DIR=${2:-"examples/order_processing"}

python3 - <<PY
import sys
from core.orchestrator import Orchestrator

orchestrator = Orchestrator()
result = orchestrator.run("${REQ_PATH}", output_dir="${OUT_DIR}")
print("Pipeline status:", result.get("status"))
print("State:", result.get("state", {}).get("current_state"))
PY
