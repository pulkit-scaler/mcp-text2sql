#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# smoke_test.sh — Quick sanity check for the MCP Text2SQL demo
# ──────────────────────────────────────────────────────────────
# Usage:  bash scripts/smoke_test.sh
# Exit 0 = all checks passed, non-zero = something failed
# ──────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}  ✅ $1${NC}"; }
fail() { echo -e "${RED}  ❌ $1${NC}"; exit 1; }

echo "═══════════════════════════════════════════════"
echo "  MCP Text2SQL Demo — Smoke Test"
echo "═══════════════════════════════════════════════"

# 1. Check uv is installed
echo ""
echo "1. Checking uv installation..."
command -v uv >/dev/null 2>&1 && pass "uv found: $(uv --version)" || fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"

# 2. Check Python version
echo "2. Checking Python version..."
PYTHON_VERSION=$(uv run python --version 2>&1)
pass "Python: $PYTHON_VERSION"

# 3. Check dependencies installed
echo "3. Checking dependencies..."
uv run python -c "import mcp; import openai; import dotenv; import pydantic" 2>/dev/null && pass "All dependencies importable" || fail "Missing dependencies. Run: uv sync"

# 4. Check database exists
echo "4. Checking sample database..."
if [ -f "data/sample.db" ]; then
    pass "data/sample.db exists"
else
    echo "   Database not found. Creating..."
    uv run python scripts/setup_db.py
    pass "Database created"
fi

# 5. Check .env exists
echo "5. Checking .env file..."
if [ -f ".env" ]; then
    pass ".env file exists"
else
    echo -e "${RED}  ⚠️  .env not found. Copy .env.example to .env and add your OPENAI_API_KEY${NC}"
    echo "     cp .env.example .env"
fi

# 6. Run pytest (tool unit tests — no API key needed)
echo "6. Running unit tests..."
uv run python -m pytest tests/test_tools.py -v --tb=short 2>&1 | tail -5
pass "Unit tests completed"

echo ""
echo "═══════════════════════════════════════════════"
echo -e "${GREEN}  All smoke checks passed!${NC}"
echo "═══════════════════════════════════════════════"
