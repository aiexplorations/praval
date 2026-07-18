#!/usr/bin/env bash
# Stage a verified exact-wheel documentation artifact in a praval-ai checkout.

set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 <documentation-artifact-dir> <praval-ai-checkout>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$SCRIPT_DIR/stage_docs_artifact.py" \
  --artifact "$1" \
  --website "$2"
