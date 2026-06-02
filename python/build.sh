#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-build"
VENV_PY="$VENV_DIR/bin/python"
DIST="$REPO_ROOT/dist"
WORK="$SCRIPT_DIR/build"

echo "========================================"
echo "GRACE Pipeline Build Script"
echo "========================================"
echo

PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "ERROR: Python >= 3.9 was not found"
        exit 1
    fi
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 9):
    raise SystemExit("ERROR: Python >= 3.9 is required")
print(f"Using Python {sys.version.split()[0]} -> {sys.executable}")
PY

if [ ! -x "$VENV_PY" ]; then
    rm -rf "$VENV_DIR"
    echo "Creating build virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "Installing build dependencies..."
"$VENV_PY" -m pip install --upgrade pip setuptools wheel
"$VENV_PY" -m pip install -e ".[build]"

echo
echo "Building executable..."
"$VENV_PY" -m PyInstaller grace_pipeline.spec --clean --noconfirm --distpath "$DIST" --workpath "$WORK"

if [ -f "$DIST/grace-pipeline" ]; then
    echo
    echo "========================================"
    echo "Build successful!"
    echo "Executable: $DIST/grace-pipeline"
    echo "Build venv: $VENV_DIR"
    echo "========================================"
else
    echo
    echo "ERROR: Build failed"
    exit 1
fi
