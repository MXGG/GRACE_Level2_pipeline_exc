#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

make_dir() {
  mkdir -p "$1"
}

copy_tree_safe() {
  local src="$1"
  local dst="$2"

  if [[ ! -e "$src" ]]; then
    echo "WARN: skip missing source: $src" >&2
    return 0
  fi

  if [[ -e "$dst" && "$FORCE" != "1" ]]; then
    echo "Skip existing destination: $dst  (use --force to overwrite files)"
    return 0
  fi

  mkdir -p "$(dirname "$dst")"
  echo "Copy $src -> $dst"
  if [[ "$FORCE" == "1" ]]; then
    rm -rf "$dst"
  fi
  cp -R "$src" "$dst"
}

for dir in \
  configs/schema \
  src/python \
  src/matlab \
  packaging/windows/python/pyinstaller \
  packaging/windows/matlab \
  packaging/windows/installer \
  packaging/linux/python \
  packaging/linux/matlab \
  packaging/hpc \
  outputs/local \
  outputs/remote \
  outputs/figures \
  outputs/logs \
  examples/quickstart-python \
  examples/quickstart-matlab \
  examples/caspian-leakage \
  examples/basin-timeseries \
  archive/legacy \
  archive/deprecated \
  docs/runtime \
  docs/data \
  docs/release \
  docs/algorithms; do
  make_dir "$dir"
done

copy_tree_safe "python" "src/python"
copy_tree_safe "matlab" "src/matlab"
copy_tree_safe "installer" "packaging/windows/installer/legacy-installer"
copy_tree_safe "output" "outputs/legacy-output"

if [[ -f "grace-l2.iss" ]]; then
  cp -f "grace-l2.iss" "packaging/windows/installer/grace-l2.iss"
fi

if [[ -f "hpc.ps1" ]]; then
  cp -f "hpc.ps1" "packaging/hpc/hpc-root-wrapper.legacy.ps1"
fi

echo "Staged repository layout without deleting legacy paths."
echo "Next: update commands to use configs/, src/python/, src/matlab/, packaging/, and outputs/."
