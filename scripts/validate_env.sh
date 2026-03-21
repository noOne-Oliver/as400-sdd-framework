#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import sys
try:
    import yaml, requests
    print("✅ dependencies ok")
except Exception as exc:
    print("❌ dependency error", exc)
    sys.exit(1)
PY
