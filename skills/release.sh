#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Usage: ./release.sh <version>}"

echo "=== SchemaGlow Release v${VERSION} ==="
ruff format --check .
ruff check .
mypy src
pytest -v
pip-audit
python -m build
python -m twine check dist/*
