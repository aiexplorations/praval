#!/usr/bin/env bash
# Build twice with a commit-derived epoch and compare artifact hashes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct HEAD)}"
FIRST_DIR="$(mktemp -d)"
SECOND_DIR="$(mktemp -d)"
trap 'rm -rf "$FIRST_DIR" "$SECOND_DIR"' EXIT

python -m build --wheel --outdir "$FIRST_DIR"
python -m build --wheel --outdir "$SECOND_DIR"

if [[ "$(find "$FIRST_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')" != "1" ]] ||
   [[ "$(find "$SECOND_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')" != "1" ]]; then
    echo "Each build must produce exactly one wheel" >&2
    exit 1
fi

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

for second in "$SECOND_DIR"/*; do
    filename="$(basename "$second")"
    if [[ ! -f "$FIRST_DIR/$filename" ]]; then
        echo "Unexpected artifact in second build: $filename" >&2
        exit 1
    fi
done

echo "Reproducible build check passed"
