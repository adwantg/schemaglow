# Contributing to SchemaGlow

```bash
git clone https://github.com/adwantg/schemaglow.git
cd schemaglow
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Acceptance Gates

```bash
ruff format .
ruff check .
mypy src
pytest
pip-audit
```

## Requirements

1. Keep tests and README examples aligned with the implemented CLI.
2. Do not reduce coverage below 90%.
3. Add tests for every user-visible change.
4. Preserve the local-first, file-format-agnostic workflow.
