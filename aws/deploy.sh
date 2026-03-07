#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ThreadPilot – Lambda Deployment Packager
# Usage: bash aws/deploy.sh
#
# Produces: threadpilot-lambda.zip  (ready to upload to the Lambda console)
#
# ZIP structure (Handler = aws.lambda_handler.lambda_handler):
#   aws/
#     __init__.py
#     lambda_handler.py
#   daily_digest/          ← copied from src/daily_digest/
#     __init__.py
#     config.py
#     …
#   (all pip packages)     ← installed from aws/requirements-lambda.txt
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGE_DIR="$PROJECT_ROOT/package"
ZIP_NAME="threadpilot-lambda.zip"
ZIP_PATH="$PROJECT_ROOT/$ZIP_NAME"
PYTHON="${PYTHON_BIN:-python3}"   # override with PYTHON_BIN env var if needed

echo "=== ThreadPilot Lambda Packager ==="
echo "Project root : $PROJECT_ROOT"
echo "Package dir  : $PACKAGE_DIR"
echo "Output zip   : $ZIP_PATH"
echo

# ── 1. Clean previous build ───────────────────────────────────────────────────
echo "[1/5] Cleaning previous build..."
rm -rf "$PACKAGE_DIR"
rm -f  "$ZIP_PATH"
mkdir -p "$PACKAGE_DIR"

# ── 2. Install pip dependencies ───────────────────────────────────────────────
echo "[2/5] Installing dependencies into package/..."
$PYTHON -m pip install \
    --target "$PACKAGE_DIR" \
    --requirement "$SCRIPT_DIR/requirements-lambda.txt" \
    --quiet

# ── 3. Copy application source ────────────────────────────────────────────────
echo "[3/5] Copying application source..."

# daily_digest package (must live at root of zip so imports resolve)
cp -r "$PROJECT_ROOT/src/daily_digest" "$PACKAGE_DIR/daily_digest"

# aws package (contains lambda_handler.py)
mkdir -p "$PACKAGE_DIR/aws"
cp "$SCRIPT_DIR/__init__.py"      "$PACKAGE_DIR/aws/__init__.py"
cp "$SCRIPT_DIR/lambda_handler.py" "$PACKAGE_DIR/aws/lambda_handler.py"

# ── 4. Strip tests / caches to keep zip small ─────────────────────────────────
echo "[4/5] Pruning unnecessary files..."
find "$PACKAGE_DIR" -type d -name "__pycache__"  -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "tests"        -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "*.dist-info"  -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.pyc"                -delete   2>/dev/null || true

# ── 5. Zip the package ────────────────────────────────────────────────────────
echo "[5/5] Creating $ZIP_NAME..."
cd "$PACKAGE_DIR"
zip -r "$ZIP_PATH" . --quiet

ZIP_MB=$(du -sh "$ZIP_PATH" | cut -f1)
echo
echo "✅ Done!  $ZIP_PATH  ($ZIP_MB)"
echo
echo "─────────────────────────────────────────────────────────────────────"
echo "Upload this zip to Lambda, then set:"
echo "  Handler  →  aws.lambda_handler.lambda_handler"
echo "  Runtime  →  Python 3.12"
echo "  Timeout  →  900 s"
echo "  Memory   →  1024 MB"
echo
echo "Environment variables to add in Lambda → Configuration → Environment:"
echo "  SLACK_BOT_TOKEN        xoxb-..."
echo "  SLACK_SIGNING_SECRET   ..."
echo "  BEDROCK_MODEL_ID       amazon.nova-micro-v1:0"
echo "  BEDROCK_REGION         ap-south-1  (or your region)"
echo "  LLM_PROVIDER           bedrock"
echo "  CHANNEL_MECHANICAL     C..."
echo "  CHANNEL_ELECTRICAL     C..."
echo "  CHANNEL_SOFTWARE       C..."
echo "  CHANNEL_DIGEST         C..."
echo "  LEADERSHIP_USERS       U...  (comma-separated)"
echo "─────────────────────────────────────────────────────────────────────"
