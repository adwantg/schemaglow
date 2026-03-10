# SchemaGlow

Human-friendly schema diff for CSV, JSON, JSONL, Parquet, OpenAPI, Avro, and protobuf.

SchemaGlow compares data files, schema artifacts, directory trees, and saved contract snapshots. It tells you what changed, whether it is safe, and what might break. It is built for pull request review, CI checks, repository-wide drift scans, and baseline contract validation when raw git diffs are not enough.

## Why

Most nearby tools validate data contracts, inspect file structure, or diff technical schemas in a format-specific way. SchemaGlow focuses on a narrower workflow:

- compare two file versions quickly
- explain changes in plain language
- classify impact as `SAFE`, `WARNING`, or `BREAKING`
- export machine-readable and review-friendly reports

## Features

- Compare `CSV`, `JSON`, `JSONL`, `Parquet`, `OpenAPI`, `Avro`, and `protobuf` sources with one CLI.
- Infer normalized schema snapshots from both raw data files and schema-definition files.
- Classify compatibility changes as `SAFE`, `WARNING`, or `BREAKING`.
- Export diff output as terminal text, JSON, Markdown, or HTML.
- Save schema snapshots and compare them later without re-reading source files.
- Scan two directory trees recursively and aggregate drift into one report.
- Capture baseline contract files and check candidate trees against committed baselines.
- Detect optional nested expansions, removals, type changes, nullability changes, sample-shape ambiguity, and column-order-only changes.
- Support ignore rules, strict numeric widening, and rename heuristics with sample overlap.

## Installation

```bash
pip install schemaglow
```

For local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI

### `schemaglow diff`

Compare two files directly.

```bash
schemaglow diff old.parquet new.parquet
schemaglow diff baseline.jsonl candidate.jsonl --format json
schemaglow diff old.openapi.yaml new.openapi.yaml
schemaglow diff old.avsc new.avsc
schemaglow diff old.proto new.proto --report html --report-path proto-report.html
schemaglow diff old.csv new.csv --report markdown --report-path schema-report.md
schemaglow diff old.csv new.csv --ignore-fields '(^_loaded_at$|^metadata\.)'
schemaglow diff old.csv new.csv --strict --rename-heuristics
```

Example text output:

```text
SchemaGlow Report

BREAKING
old: old.csv
new: new.csv
counts: SAFE=1 WARNING=0 BREAKING=1
BREAKING
- removed field: order_total
SAFE
+ column order changed only
```

### `schemaglow inspect`

Infer a snapshot from one file and print its normalized field model.

```bash
schemaglow inspect data.json
schemaglow inspect data.parquet --format json
schemaglow inspect openapi.yaml --format json
schemaglow inspect schema.proto
```

### `schemaglow snapshot`

Persist an inferred snapshot to JSON for later comparison.

```bash
schemaglow snapshot data.jsonl -o snapshots/baseline.schema.json
schemaglow snapshot schema.avsc -o snapshots/avro.schema.json
```

### `schemaglow compare`

Compare two saved schema snapshots.

```bash
schemaglow compare old.schema.json new.schema.json
schemaglow compare old.schema.json new.schema.json --format json
```

### `schemaglow scan`

Compare two directory trees recursively and aggregate the results.

```bash
schemaglow scan datasets/baseline datasets/candidate
schemaglow scan specs/old specs/new --format json
schemaglow scan repo-old repo-new --pattern '*.proto' --report markdown --report-path scan.md
```

### `schemaglow baseline capture`

Capture a repository-local contract baseline made of saved snapshots.

```bash
schemaglow baseline capture data/ -o .schemaglow-baseline
schemaglow baseline capture specs/ -o contracts/api --pattern '*.yaml'
```

### `schemaglow baseline check`

Compare a candidate tree against committed baseline contract files.

```bash
schemaglow baseline check .schemaglow-baseline data/
schemaglow baseline check contracts/api specs/ --format json
```

## Supported Inputs

| Format | Typical suffixes | Notes |
| ---- | ---- | ---- |
| CSV | `.csv` | Header-driven field discovery with scalar inference |
| JSON | `.json` | Raw object or array data; OpenAPI JSON is auto-detected |
| JSONL | `.jsonl` | One JSON object per line |
| Parquet | `.parquet` | Schema extracted with PyArrow |
| OpenAPI | `.yaml`, `.yml`, `.json` | Local refs, component schemas, request/response schemas |
| Avro | `.avsc` | Records, arrays, maps, enums, unions |
| Protobuf | `.proto` | Messages, enums, repeated fields, and maps |

## Compatibility Rules

`SAFE`

- new nullable or optional top-level field
- column order changed only
- numeric widening from `integer` to `number` unless `--strict` is enabled
- no schema change

`WARNING`

- new required top-level field
- nested object shape expanded
- required to nullable change
- ambiguous or mixed-type widening
- sample shape changed while remaining string-typed
- likely rename detected with `--rename-heuristics`

`BREAKING`

- field removed
- nullable to required change
- incompatible type change such as `string -> integer`

## Architecture

The package uses a small pipeline that mirrors the product brief.

```text
src/schemaglow/
├── cli.py         # Typer command surface
├── service.py     # File and snapshot orchestration
├── infer.py       # Format detection and schema inference
├── schema_sources.py # OpenAPI, Avro, and protobuf parsers
├── diffing.py     # Compatibility rules and event generation
├── renderers.py   # Text, JSON, Markdown, and HTML output
└── models.py      # Pydantic models for snapshots and reports
```

Processing flow:

1. Detect the input format from suffix and schema-document heuristics.
2. Infer a normalized field map with type, nullability, order, and sample hints.
3. Compare old and new field sets against compatibility rules.
4. Aggregate file-level results for scans and baseline checks when needed.
5. Render the result for humans or CI consumers.

## Tools Used

| Tool | Purpose |
| ---- | ------- |
| `Python 3.11+` | Runtime and packaging baseline |
| `Typer` | CLI commands and help output |
| `Rich` | Terminal rendering |
| `Pydantic` | Snapshot and report models |
| `PyArrow` | Parquet schema reading and test fixture creation |
| `PyYAML` | OpenAPI YAML parsing |
| `Jinja2` | HTML report templating |
| `pytest` + `pytest-cov` | Unit and integration tests with coverage |
| `mypy` | Strict type checking |
| `ruff` | Linting and formatting |
| `pip-audit` | Dependency vulnerability checks |

## Testing and Verification

Local verification commands:

```bash
ruff format --check .
ruff check .
mypy src
pytest
pip-audit
```

Manual end-to-end commands using committed sample files are documented in `TESTING.md`.

The automated test suite covers:

- CSV inference and numeric widening behavior
- JSON and JSONL nested shape, nullability, and sample-shape changes
- OpenAPI, Avro, and protobuf schema parsing
- nested diff collapsing and rename heuristics
- snapshot and baseline round-trips
- CLI integration for `inspect`, `snapshot`, `compare`, `diff`, `scan`, and `baseline`
- Parquet and directory report generation

## Roadmap Status

`v1.0`

- file and snapshot comparison
- human-readable severity classification
- JSON, Markdown, and HTML report export

`v1.1`

- GitHub Action and pre-commit packaging
- better nested diff and ignore-field workflows
- improved rename heuristics and sample-based ambiguity handling

`v2.0`

- OpenAPI, Avro, and protobuf support
- directory-wide drift scans
- baseline contract files committed to repositories

## Repository Standards

- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [SECURITY.md](./SECURITY.md)
- [LICENSE](./LICENSE)
- [CITATION.cff](./CITATION.cff)
