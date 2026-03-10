# SchemaGlow

Human-friendly schema diff for CSV, JSON, JSONL, Parquet, OpenAPI, Avro, and protobuf.

This skill-side README mirrors the product-facing repository summary so the AI workflow and the package surface stay aligned.

## Core Features

- compare raw files, saved snapshots, directory trees, and baseline contracts
- classify compatibility as `SAFE`, `WARNING`, or `BREAKING`
- render terminal, JSON, Markdown, and HTML output
- support ignore patterns, strict numeric widening, sample-shape warnings, and rename heuristics

## Commands

```bash
schemaglow diff old.parquet new.parquet
schemaglow inspect data.json --format json
schemaglow snapshot data.jsonl -o baseline.schema.json
schemaglow compare old.schema.json new.schema.json --format json
schemaglow scan baseline_dir candidate_dir --format json
schemaglow baseline capture data -o .schemaglow-baseline
schemaglow baseline check .schemaglow-baseline data --format json
```

## Architecture

- `cli.py` exposes commands
- `infer.py` normalizes file schemas
- `schema_sources.py` parses OpenAPI, Avro, and protobuf schemas
- `diffing.py` applies compatibility rules
- `service.py` orchestrates snapshots, scans, and baselines
- `renderers.py` emits report formats
- `tests/` verifies both logic and command behavior

## Tools Used

- `typer`
- `rich`
- `pydantic`
- `pyarrow`
- `pyyaml`
- `jinja2`
- `pytest`
- `mypy`
- `ruff`
