#!/usr/bin/env bash
# Author: gadwant
# Release script for schemaglow
# Usage: ./release.sh <version> [--no-upload] [--no-git] [--skip-quality]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
  cat <<USAGE
Usage: ./release.sh <version> [--no-upload] [--no-git] [--skip-quality]

Examples:
  ./release.sh 1.0.0
  ./release.sh 1.0.0 --no-upload
  ./release.sh 1.0.0 --no-git
  ./release.sh 1.0.0 --skip-quality --no-upload
USAGE
}

if [[ $# -lt 1 ]]; then
  echo -e "${RED}Error: Version number required${NC}"
  usage
  exit 1
fi

VERSION="$1"
shift

SKIP_UPLOAD=false
SKIP_GIT=false
SKIP_QUALITY=false

for arg in "$@"; do
  case "$arg" in
    --no-upload)
      SKIP_UPLOAD=true
      ;;
    --no-git)
      SKIP_GIT=true
      ;;
    --skip-quality)
      SKIP_QUALITY=true
      ;;
    *)
      echo -e "${RED}Error: Unknown option: $arg${NC}"
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo -e "${RED}Error: Invalid version format. Use X.Y.Z (example: 1.0.0)${NC}"
  exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  schemaglow Release Script v$VERSION${NC}"
echo -e "${BLUE}========================================${NC}"

if [[ -d ".venv" && -f ".venv/bin/activate" ]]; then
  echo -e "${YELLOW}[1/10] Activating virtual environment...${NC}"
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo -e "${YELLOW}[1/10] No local .venv found; using current Python environment...${NC}"
fi

if [[ "$SKIP_QUALITY" == false ]]; then
  echo -e "${YELLOW}[2/10] Running quality checks...${NC}"

  if command -v ruff >/dev/null 2>&1; then
    ruff check .
    ruff format --check .
  else
    echo -e "${YELLOW}ruff not found; skipping lint/format checks${NC}"
  fi

  if command -v mypy >/dev/null 2>&1; then
    mypy src
  else
    echo -e "${YELLOW}mypy not found; skipping type checks${NC}"
  fi

  if python - <<'PY'
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("pytest_cov") is not None else 1)
PY
  then
    python -m pytest -q
  else
    echo -e "${YELLOW}pytest-cov not found; installing for coverage-enabled test run...${NC}"
    if python -m pip install --upgrade pytest-cov >/dev/null 2>&1; then
      python -m pytest -q
    else
      echo -e "${YELLOW}Could not install pytest-cov; running tests without global addopts.${NC}"
      python -m pytest -q -o addopts=''
    fi
  fi

  if command -v pip-audit >/dev/null 2>&1; then
    pip-audit
  else
    echo -e "${YELLOW}pip-audit not found; skipping dependency audit${NC}"
  fi

  echo -e "${GREEN}✓ Quality checks passed${NC}"
else
  echo -e "${YELLOW}[2/10] Skipping quality checks (--skip-quality flag)${NC}"
fi


echo -e "${YELLOW}[3/10] Updating version metadata...${NC}"
python - <<PY
from pathlib import Path
import re

version = "${VERSION}"

def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Expected one match for {pattern!r} in {path}")
    path.write_text(updated, encoding="utf-8")

replace_once(Path("pyproject.toml"), r'^version\s*=\s*"[^"]+"$', f'version = "{version}"')
replace_once(Path("src/schemaglow/__init__.py"), r'^__version__\s*=\s*"[^"]+"$', f'__version__ = "{version}"')
PY

echo -e "${GREEN}✓ Updated pyproject.toml and src/schemaglow/__init__.py${NC}"

echo -e "${YELLOW}[4/10] Updating CITATION metadata (if present)...${NC}"
TODAY="$(date +%Y-%m-%d)"
if [[ -f "CITATION.cff" ]]; then
  python - <<PY
from pathlib import Path
import re

version = "${VERSION}"
today = "${TODAY}"
path = Path("CITATION.cff")
text = path.read_text(encoding="utf-8")
text, count_version = re.subn(r'^version:\s*"[^"]+"$', f'version: "{version}"', text, count=1, flags=re.MULTILINE)
text, count_date = re.subn(r'^date-released:\s*"[^"]+"$', f'date-released: "{today}"', text, count=1, flags=re.MULTILINE)
if count_version == 1 and count_date == 1:
    path.write_text(text, encoding="utf-8")
    print("Updated CITATION.cff")
else:
    print("CITATION.cff found, but version/date fields not updated (missing expected keys)")
PY
else
  echo -e "${YELLOW}CITATION.cff not found; skipping${NC}"
fi

echo -e "${YELLOW}[5/10] Ensuring packaging tools are available...${NC}"
python - <<'PY'
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "build", "twine", "pkginfo"])
PY

echo -e "${YELLOW}[6/10] Cleaning previous build artifacts...${NC}"
rm -rf dist build *.egg-info src/*.egg-info

echo -e "${YELLOW}[7/10] Building distribution artifacts...${NC}"
python -m build

echo -e "${YELLOW}[8/10] Verifying artifacts with twine...${NC}"
TWINE_CHECK_LOG="$(mktemp)"
set +e
python -m twine check dist/* >"${TWINE_CHECK_LOG}" 2>&1
TWINE_STATUS=$?
set -e
if [[ ${TWINE_STATUS} -ne 0 ]]; then
  cat "${TWINE_CHECK_LOG}"
  if grep -qi "license-file" "${TWINE_CHECK_LOG}"; then
    echo -e "${RED}Detected unsupported 'license-file' metadata in built artifacts.${NC}"
    echo -e "${RED}Set Hatch build target core-metadata-version to 2.3, then rebuild.${NC}"
  fi
  rm -f "${TWINE_CHECK_LOG}"
  echo -e "${RED}twine check failed${NC}"
  exit ${TWINE_STATUS}
fi
cat "${TWINE_CHECK_LOG}"
rm -f "${TWINE_CHECK_LOG}"

echo -e "${YELLOW}[9/10] Upload step...${NC}"
if [[ "$SKIP_UPLOAD" == false ]]; then
  echo -e "${BLUE}Uploading to PyPI via twine...${NC}"
  python -m twine upload dist/*
  echo -e "${GREEN}✓ Uploaded to PyPI${NC}"
else
  echo -e "${YELLOW}Skipped upload (--no-upload flag)${NC}"
fi

echo -e "${YELLOW}[10/10] Git tagging step...${NC}"
if [[ "$SKIP_GIT" == true ]]; then
  echo -e "${YELLOW}Skipped git operations (--no-git flag)${NC}"
elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add pyproject.toml src/schemaglow/__init__.py
  if [[ -f "CITATION.cff" ]]; then
    git add CITATION.cff
  fi

  if ! git diff --cached --quiet; then
    git commit -m "Release v$VERSION"
  else
    echo -e "${YELLOW}No version metadata changes to commit${NC}"
  fi

  if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo -e "${YELLOW}Tag v$VERSION already exists locally${NC}"
  else
    git tag -a "v$VERSION" -m "v$VERSION"
    echo -e "${GREEN}✓ Created git tag v$VERSION${NC}"
  fi

  echo -e "${BLUE}Next push commands:${NC}"
  echo "  git push origin main"
  echo "  git push origin v$VERSION"
else
  echo -e "${YELLOW}Not a git repository; skipping git operations${NC}"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Release v$VERSION completed${NC}"
echo -e "${GREEN}========================================${NC}"
