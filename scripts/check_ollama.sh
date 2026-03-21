#!/bin/bash
# Check if Ollama is available and the configured model is loaded.

set -e

MODEL="${1:-llama3.1}"
BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "=== Ollama Environment Check ==="
echo "Model: $MODEL"
echo "Base URL: $BASE_URL"

# Check if Ollama CLI is installed
if ! command -v ollama &>/dev/null; then
    echo "❌ Ollama CLI not found in PATH"
    echo "Install: https://github.com/ollama/ollama"
    exit 1
fi
echo "✓ Ollama CLI found: $(ollama --version)"

# Check if Ollama server is running
if ! curl -s --max-time 5 "$BASE_URL/api/tags" > /dev/null 2>&1; then
    echo "❌ Ollama server not reachable at $BASE_URL"
    echo "Start it with: ollama serve"
    exit 1
fi
echo "✓ Ollama server is running"

# List available models
echo ""
echo "=== Available Models ==="
curl -s "$BASE_URL/api/tags" | python3 -c "
import json, sys
data = json.load(sys.stdin)
models = data.get('models', [])
if not models:
    print('  (none loaded)')
for m in models:
    name = m.get('name', '?')
    size = m.get('size', 0)
    size_gb = size / (1024**3) if size else 0
    print(f'  {name}  ({size_gb:.1f} GB)')
"

# Check if target model is loaded
echo ""
echo "=== Model '$MODEL' Check ==="
if curl -s "$BASE_URL/api/tags" | python3 -c "
import json, sys
data = json.load(sys.stdin)
models = data.get('models', [])
found = any('$MODEL' in m.get('name', '') for m in models)
sys.exit(0 if found else 1)
" 2>/dev/null; then
    echo "✓ Model '$MODEL' is loaded and ready"
    exit 0
else
    echo "⚠ Model '$MODEL' is NOT loaded"
    echo "  Run: ollama pull $MODEL"
    echo "  Or:  ollama run $MODEL"
    exit 1
fi
