# Project Requirements

This file is the concrete project brief derived from `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow/requirement.txt`.

## 1. Project Identity

| Field | Value |
| ----- | ----- |
| Project Name | `SchemaGlow` |
| PyPI Package Name | `schemaglow` |
| One-Liner Description | Human-friendly schema diff for CSV, JSON, JSONL, and Parquet. |
| GitHub URL | `https://github.com/adwantg/schemaglow` |
| Author Name | `Goutam Adwant` |
| Author Email | `workwithgoutam@gmail.com` |
| License | MIT |

## 2. Problem & Solution

### Pain Point

Existing tools validate, inspect, or diff schemas, but very few explain file-level schema drift in a way that is immediately useful in pull request review, CI, or human approval workflows.

### Solution

Build a local-first Python CLI that infers normalized schemas from CSV, JSON, JSONL, Parquet, OpenAPI, Avro, and protobuf sources, compares two file versions or snapshot files, scans directories, checks committed baselines, classifies the impact as `SAFE`, `WARNING`, or `BREAKING`, and renders results as terminal text, JSON, Markdown, or HTML.

### EB1A Argument

SchemaGlow is positioned as a format-agnostic compatibility explainer instead of a validation platform. The novelty is the combination of file-first schema inference, compatibility semantics, and human-readable impact reporting for developer review workflows.

### Adoption Strategy

Keep the tool lightweight, local, and easy to drop into existing repositories. The main wedge is faster pull request review for data files, reducing time spent on manual schema inspection and custom scripts.

## 3. Technical Stack

| Component | Choice | Notes |
| --------- | ------ | ----- |
| Runtime | Python `3.11+` | Matches packaging and type-checking target |
| Build System | `hatchling` | PEP 621 metadata |
| CLI Framework | `typer` + `rich` | User-facing command surface and terminal output |
| Core Dependencies | `pydantic`, `pyarrow`, `jinja2` | Models, Parquet support, HTML reports |
| Quality Tools | `ruff`, `mypy`, `pytest`, `pip-audit`, `pre-commit` | Required quality gate set |

## 4. Repository Layout

```text
schemaglow/
├── src/
│   └── schemaglow/
│       ├── __init__.py
│       ├── cli.py
│       ├── service.py
│       ├── infer.py
│       ├── diffing.py
│       ├── renderers.py
│       └── models.py
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/
│   ├── ci.yml
│   └── pypi_publish.yml
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── CITATION.cff
└── release.sh
```

## 5. Feature Roadmap

### v1.0 - Core

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | File and snapshot comparison | Compare files directly and compare saved schema snapshots. |
| 2 | Human-readable severity classification | Explain changes with `SAFE`, `WARNING`, and `BREAKING` labels. |
| 3 | JSON, Markdown, and HTML report export | Emit review-friendly and machine-readable reports. |

### v1.1 - Hardening

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | GitHub Action and pre-commit packaging | Ship CI automation and local quality hooks. |
| 2 | Better nested diff and ignore-field workflows | Improve nested drift reporting and field filtering. |
| 3 | Improved rename heuristics and sample-based ambiguity handling | Flag likely renames and handle uncertain sample-driven inference better. |

### v2.0 - Ecosystem

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | OpenAPI, Avro, and protobuf support | Add those schema formats to the comparison engine. |
| 2 | Directory-wide drift scans | Detect schema drift across whole datasets or repositories. |
| 3 | Baseline contract files committed to repositories | Compare current files against committed repository snapshots. |

## 6. Competitive Landscape

### Direct Competitors

| Competitor | What They Do | Their Weakness |
| ---------- | ------------ | -------------- |
| Great Expectations | Data validation and expectation management | Heavyweight for quick two-file schema review |
| OpenMetadata | Metadata and drift monitoring platform | Requires platform adoption, not a lightweight CLI |
| json-schema-diff | JSON schema comparison | Narrow format focus and less file-first |
| parquet-tools | Utility workflows for Parquet | Not positioned as a compatibility explainer |

### Positioning Statement

> SchemaGlow is a git-friendly schema diff tool that tells humans whether a data-file change is safe, risky, or breaking.

## 7. Non-Negotiables

1. Keep the tool local-first with no server or metadata platform dependency.
2. Support CSV, JSON, JSONL, and Parquet in one consistent CLI workflow.
3. Enforce `ruff`, `mypy`, `pytest`, and strict type checking in CI.
4. Reject PRs that reduce test coverage below 90%.

## 8. Testing Requirements

1. Cover CSV, JSON, JSONL, and Parquet inference paths.
2. Verify `SAFE`, `WARNING`, and `BREAKING` classifications with automated tests.
3. Ensure all CLI commands produce expected output formats.
4. Cover the primary file diff and snapshot comparison workflow end to end.

## 9. CLI Commands

| Command | Description | Example |
| ------- | ----------- | ------- |
| `schemaglow diff` | Compare two source files | `schemaglow diff old.parquet new.parquet --report markdown --report-path report.md` |
| `schemaglow inspect` | Infer and print a schema snapshot | `schemaglow inspect data.json --format json` |
| `schemaglow snapshot` | Save a schema snapshot to JSON | `schemaglow snapshot data.jsonl -o baseline.schema.json` |
| `schemaglow compare` | Compare two saved snapshots | `schemaglow compare old.schema.json new.schema.json --format json` |
| `schemaglow scan` | Compare two directory trees recursively | `schemaglow scan old/ new/ --format json` |
| `schemaglow baseline capture` | Capture baseline contract snapshots | `schemaglow baseline capture data/ -o .schemaglow-baseline` |
| `schemaglow baseline check` | Compare a candidate tree against a baseline | `schemaglow baseline check .schemaglow-baseline data/ --format json` |

## 10. Keywords / Classifiers

Keywords: `schema-diff`, `parquet`, `jsonl`, `csv`, `cli`

PyPI Classifiers:

- `Development Status :: 3 - Alpha`
- `Intended Audience :: Developers`
- `License :: OSI Approved :: MIT License`
- `Programming Language :: Python :: 3`
- `Programming Language :: Python :: 3.11`
- `Programming Language :: Python :: 3.12`
