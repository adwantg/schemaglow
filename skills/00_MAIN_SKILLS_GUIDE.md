# SchemaGlow Architecture Guide

## Purpose

This guide summarizes how SchemaGlow is organized and how changes should flow through the repository.

## Product Scope

SchemaGlow compares data files, schema artifacts, saved schema snapshots, directory trees, and baseline contracts, then explains whether the change is safe, risky, or breaking.

Key capabilities:

1. Infer normalized schemas from CSV, JSON, JSONL, Parquet, OpenAPI, Avro, and protobuf.
2. Compare files, snapshots, directory scans, and baseline contracts with compatibility-aware rules.
3. Render text, JSON, Markdown, and HTML reports for local review and CI.

## Stack

- Runtime: Python 3.11+
- CLI: `typer` and `rich`
- Models: `pydantic`
- Parquet support: `pyarrow`
- OpenAPI YAML support: `pyyaml`
- HTML reports: `jinja2`
- Quality: `ruff`, `mypy`, `pytest`, `pip-audit`, `pre-commit`

## Repository Layout

```text
schemaglow/
├── src/schemaglow/
│   ├── cli.py
│   ├── service.py
│   ├── infer.py
│   ├── schema_sources.py
│   ├── diffing.py
│   ├── renderers.py
│   └── models.py
├── tests/unit/
├── tests/integration/
├── README.md
├── pyproject.toml
└── .github/workflows/
```

## Module Responsibilities

- `cli.py`: command definitions and option parsing
- `service.py`: orchestration between inference, snapshots, scans, and baselines
- `infer.py`: format detection and schema inference entrypoint
- `schema_sources.py`: OpenAPI, Avro, and protobuf schema normalization
- `diffing.py`: compatibility classification rules
- `renderers.py`: single-file and directory report outputs
- `models.py`: snapshot and report contracts

## Engineering Workflow

1. Start from the user-facing behavior.
2. Update inference or diff rules in `src/schemaglow/`.
3. Add unit coverage for the rule or parser change.
4. Add or update CLI integration coverage when the command surface changes.
5. Update `README.md` examples and the relevant skill docs.

## Testing Requirements

1. Cover all supported file formats, including OpenAPI, Avro, and protobuf.
2. Verify `SAFE`, `WARNING`, and `BREAKING` outputs directly.
3. Cover snapshot and baseline save/load flows.
4. Exercise at least one CLI round-trip for `diff`, `inspect`, `snapshot`, `compare`, `scan`, and `baseline`.
