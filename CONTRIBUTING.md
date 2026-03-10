# Contributing to SchemaGlow

## Developer Quick Start

```bash
git clone https://github.com/gadwant/schemaglow.git
cd schemaglow

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
pre-commit install
```

## Quality Gates

```bash
ruff format .
ruff check .
mypy src
pytest
pip-audit
```

## Pull Request Requirements

1. Keep tests, docs, and CLI examples aligned with the implemented behavior.
2. Do not reduce coverage below 90%.
3. Add or update tests for every user-visible behavior change.
4. Update `README.md` whenever commands, flags, report formats, or compatibility rules change.
