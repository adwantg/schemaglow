# Testing SchemaGlow

This file gives you a repeatable way to test every shipped feature with committed sample files.

## 1. Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional quality checks:

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

## 2. Sample File Layout

Downloaded originals live in:

- `tests/fixtures/downloaded/seattle-weather.csv`
- `tests/fixtures/downloaded/miserables.json`
- `tests/fixtures/downloaded/example.jsonl`
- `tests/fixtures/downloaded/alltypes_plain.parquet`
- `tests/fixtures/downloaded/petstore.yaml`
- `tests/fixtures/downloaded/user.avsc`
- `tests/fixtures/downloaded/addressbook.proto`

Manual baseline/candidate pairs for feature testing live in:

- `tests/fixtures/manual/`

The original download URLs are listed in `tests/fixtures/downloaded/SOURCES.md`.

## 3. Inspect Every Supported Input Type

Run these commands one by one:

```bash
schemaglow inspect tests/fixtures/downloaded/seattle-weather.csv
schemaglow inspect tests/fixtures/downloaded/miserables.json
schemaglow inspect tests/fixtures/downloaded/example.jsonl
schemaglow inspect tests/fixtures/downloaded/alltypes_plain.parquet
schemaglow inspect tests/fixtures/downloaded/petstore.yaml
schemaglow inspect tests/fixtures/downloaded/user.avsc
schemaglow inspect tests/fixtures/downloaded/addressbook.proto
```

What to check:

- each command exits successfully
- `source_format` matches the file type
- field paths are present for nested structures such as `nodes[].name`, `Pet.name`, and `Person.email`

If you want machine-readable output:

```bash
schemaglow inspect tests/fixtures/downloaded/petstore.yaml --format json
```

## 4. Diff Each Supported Format

### CSV

```bash
schemaglow diff \
  tests/fixtures/manual/csv/weather-baseline.csv \
  tests/fixtures/manual/csv/weather-candidate.csv
```

Expected result: `SAFE`, with an added optional `station` field.

### JSON

```bash
schemaglow diff \
  tests/fixtures/manual/json/miserables-baseline.json \
  tests/fixtures/manual/json/miserables-candidate.json
```

Expected result: `BREAKING`, with `metadata.version` changing from integer to string.

### JSONL

```bash
schemaglow diff \
  tests/fixtures/manual/jsonl/search-baseline.jsonl \
  tests/fixtures/manual/jsonl/search-candidate.jsonl
```

Expected result: `BREAKING`, with `result.sequenceNumber` changing from integer to string.

### Parquet

```bash
schemaglow diff \
  tests/fixtures/manual/parquet/alltypes-baseline.parquet \
  tests/fixtures/manual/parquet/alltypes-candidate.parquet
```

Expected result: `SAFE`, with an added optional `campaign_id` field.

### OpenAPI

```bash
schemaglow diff \
  tests/fixtures/manual/openapi/petstore-baseline.yaml \
  tests/fixtures/manual/openapi/petstore-candidate.yaml
```

Expected result: `BREAKING`, with `Pet.name` changing from string to integer.

### Avro

```bash
schemaglow diff \
  tests/fixtures/manual/avro/user-baseline.avsc \
  tests/fixtures/manual/avro/user-candidate.avsc
```

Expected result: `BREAKING`, with `favorite_number` changing from integer to string.

### Protobuf

```bash
schemaglow diff \
  tests/fixtures/manual/proto/addressbook-baseline.proto \
  tests/fixtures/manual/proto/addressbook-candidate.proto
```

Expected result: `BREAKING`, with `Person.email` changing from string to integer.

## 5. Report Export

JSON report:

```bash
schemaglow diff \
  tests/fixtures/manual/parquet/alltypes-baseline.parquet \
  tests/fixtures/manual/parquet/alltypes-candidate.parquet \
  --format json
```

Markdown report:

```bash
schemaglow diff \
  tests/fixtures/manual/openapi/petstore-baseline.yaml \
  tests/fixtures/manual/openapi/petstore-candidate.yaml \
  --report markdown \
  --report-path /tmp/schemaglow-openapi-report.md
```

HTML report:

```bash
schemaglow diff \
  tests/fixtures/manual/proto/addressbook-baseline.proto \
  tests/fixtures/manual/proto/addressbook-candidate.proto \
  --report html \
  --report-path /tmp/schemaglow-proto-report.html
```

What to check:

- JSON output parses cleanly
- Markdown file is created at `/tmp/schemaglow-openapi-report.md`
- HTML file is created at `/tmp/schemaglow-proto-report.html`

## 6. Snapshot and Compare

Create two snapshots:

```bash
schemaglow snapshot tests/fixtures/manual/csv/weather-baseline.csv -o /tmp/weather-old.schema.json
schemaglow snapshot tests/fixtures/manual/csv/weather-candidate.csv -o /tmp/weather-new.schema.json
```

Compare the saved snapshots:

```bash
schemaglow compare /tmp/weather-old.schema.json /tmp/weather-new.schema.json
schemaglow compare /tmp/weather-old.schema.json /tmp/weather-new.schema.json --format json
```

Expected result: the same `station` change reported by direct file diff.

## 7. Scan Two Directory Trees

```bash
schemaglow scan tests/fixtures/manual/scan/old tests/fixtures/manual/scan/new
schemaglow scan tests/fixtures/manual/scan/old tests/fixtures/manual/scan/new --format json
schemaglow scan \
  tests/fixtures/manual/scan/old \
  tests/fixtures/manual/scan/new \
  --report markdown \
  --report-path /tmp/schemaglow-scan.md
```

Expected result:

- overall severity is `BREAKING`
- `weather.csv` is compared
- `petstore.yaml` is compared
- `addressbook.proto` is reported as an added file

## 8. Baseline Capture and Baseline Check

Capture a baseline:

```bash
rm -rf /tmp/schemaglow-baseline
schemaglow baseline capture tests/fixtures/manual/scan/old -o /tmp/schemaglow-baseline
```

Check a candidate tree against the baseline:

```bash
schemaglow baseline check /tmp/schemaglow-baseline tests/fixtures/manual/scan/new
schemaglow baseline check /tmp/schemaglow-baseline tests/fixtures/manual/scan/new --format json
```

Expected result:

- baseline manifest is written under `/tmp/schemaglow-baseline`
- overall severity is `BREAKING`
- `addressbook.proto` is reported as an unexpected candidate file

## 9. Ignore Fields

Without ignore rules:

```bash
schemaglow diff \
  tests/fixtures/manual/options/ignore-old.jsonl \
  tests/fixtures/manual/options/ignore-new.jsonl
```

You should see `_loaded_at` added.

With ignore rules:

```bash
schemaglow diff \
  tests/fixtures/manual/options/ignore-old.jsonl \
  tests/fixtures/manual/options/ignore-new.jsonl \
  --ignore-fields '^_loaded_at$'
```

Expected result: `SAFE`, with the ignored field listed and no schema change after filtering.

## 10. Strict Numeric Widening

Default behavior:

```bash
schemaglow diff \
  tests/fixtures/manual/options/strict-old.csv \
  tests/fixtures/manual/options/strict-new.csv
```

Expected result: `SAFE`, because `integer -> number` widening is allowed by default.

Strict behavior:

```bash
schemaglow diff \
  tests/fixtures/manual/options/strict-old.csv \
  tests/fixtures/manual/options/strict-new.csv \
  --strict
```

Expected result: `WARNING`, for the same `integer -> number` change.

## 11. Rename Heuristics

Without rename heuristics:

```bash
schemaglow diff \
  tests/fixtures/manual/options/rename-old.csv \
  tests/fixtures/manual/options/rename-new.csv
```

You should see a removal and an addition.

With rename heuristics:

```bash
schemaglow diff \
  tests/fixtures/manual/options/rename-old.csv \
  tests/fixtures/manual/options/rename-new.csv \
  --rename-heuristics
```

Expected result: `WARNING`, with `possible rename: customer_id -> customerid`.

## 12. Automated Sample-Fixture Coverage

If you want to run only the committed sample-fixture tests:

```bash
pytest tests/integration/test_sample_fixtures.py
```

This covers:

- inspection of all downloaded sample formats
- diffing of all committed baseline/candidate fixture pairs
- strict mode, ignore rules, and rename heuristics
- scan and baseline workflows
