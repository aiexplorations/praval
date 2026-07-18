#!/usr/bin/env bash
# Build twice with a commit-derived epoch and compare artifact hashes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct HEAD)}"
FIRST_DIR="$(mktemp -d)"
SECOND_DIR="$(mktemp -d)"
trap 'rm -rf "$FIRST_DIR" "$SECOND_DIR"' EXIT

python -m build --outdir "$FIRST_DIR"
python -m build --outdir "$SECOND_DIR"
python scripts/normalize_sdist.py "$FIRST_DIR"/praval-*.tar.gz
python scripts/normalize_sdist.py "$SECOND_DIR"/praval-*.tar.gz

for first in "$FIRST_DIR"/*; do
    filename="$(basename "$first")"
    second="$SECOND_DIR/$filename"
    if [[ ! -f "$second" ]]; then
        echo "Missing artifact in second build: $filename" >&2
        exit 1
    fi
    if ! cmp --silent "$first" "$second"; then
        echo "Non-reproducible artifact: $filename" >&2
        shasum -a 256 "$first" "$second" >&2
        exit 1
    fi
done

echo "Reproducible build check passed"
