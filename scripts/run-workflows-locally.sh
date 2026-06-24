#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Run GitHub Actions workflows locally with act.

Usage:
  ./scripts/run-workflows-locally.sh [workflow ...]

Examples:
  ./scripts/run-workflows-locally.sh
  ./scripts/run-workflows-locally.sh ci.yml
  ./scripts/run-workflows-locally.sh release.yml

Notes:
  - Requires: act, Docker
  - Uses workflow_dispatch for all runs
  - Release publishing is skipped under act
  - If .secrets.act exists, it is passed to act automatically
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v act >/dev/null 2>&1; then
  echo "Error: act is not installed or not available in PATH." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed or not available in PATH." >&2
  exit 1
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

workflows=("$@")
if [[ ${#workflows[@]} -eq 0 ]]; then
  workflows=("ci.yml" "release.yml")
fi

event_file=$(mktemp)
cleanup() {
  rm -f "$event_file"
}
trap cleanup EXIT

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then PYTHON_BIN="python3"; fi
if command -v python >/dev/null 2>&1; then PYTHON_BIN="python"; fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Error: Python is not installed or not available in PATH." >&2
  exit 1
fi

version=$("$PYTHON_BIN" - <<'PY'
import tomllib
from pathlib import Path
print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)

cat > "$event_file" <<EOF
{
  "ref": "refs/heads/main",
  "ref_type": "branch",
  "ref_name": "main",
  "repository": {
    "full_name": "local/medium-annoyed-api"
  },
  "inputs": {
    "tag": "v${version}"
  }
}
EOF

common_args=(workflow_dispatch --container-architecture linux/amd64 --eventpath "$event_file")

if [[ -f .secrets.act ]]; then
  common_args+=(--secret-file .secrets.act)
fi

for workflow in "${workflows[@]}"; do
  workflow_path=".github/workflows/$workflow"
  if [[ ! -f "$workflow_path" ]]; then
    echo "Error: workflow not found: $workflow_path" >&2
    exit 1
  fi

  echo "Running $workflow_path"
  act "${common_args[@]}" -W "$workflow_path"
done
