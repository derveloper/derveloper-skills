#!/usr/bin/env bash
# Validate GEPA installation and API key configuration
set -euo pipefail

echo "=== GEPA Setup Validation ==="

# Check gepa installation
if python3 -c "import gepa; print(f'gepa {gepa.__version__}')" 2>/dev/null; then
    echo "[OK] gepa installed"
else
    echo "[FAIL] gepa not installed. Run: pip install gepa"
    exit 1
fi

# Check optional deps
for pkg in dspy litellm; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "[OK] $pkg available"
    else
        echo "[WARN] $pkg not installed (optional)"
    fi
done

# Check API keys
for var in OPENAI_API_KEY ANTHROPIC_API_KEY; do
    if [ -n "${!var:-}" ]; then
        echo "[OK] $var set"
    else
        echo "[INFO] $var not set"
    fi
done

echo "=== Done ==="
