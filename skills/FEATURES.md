# SchemaGlow Feature Roadmap

## v1.0 - Core

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | File and snapshot comparison | Compare raw files directly and compare saved schema snapshots. |
| 2 | Human-readable severity classification | Explain changes with `SAFE`, `WARNING`, and `BREAKING` labels. |
| 3 | JSON, Markdown, and HTML report export | Emit review-friendly and machine-readable reports. |

## v1.1 - Hardening

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | GitHub Action and pre-commit packaging | Ship repository automation for CI and local quality gates. |
| 2 | Better nested diff and ignore-field workflows | Improve nested drift reporting and field suppression controls. |
| 3 | Improved rename heuristics and sample-based ambiguity handling | Detect likely renames and better surface uncertain type changes. |

## v2.0 - Ecosystem

| # | Feature | Description |
| - | ------- | ----------- |
| 1 | OpenAPI, Avro, and protobuf support | Add those schema formats to the comparison engine. |
| 2 | Directory-wide drift scans | Compare larger collections of files in one run. |
| 3 | Baseline contract files committed to repositories | Commit schema baselines directly to repositories. |

## Supported Data Types in v1.0

| Type | Example | Handling |
| ---- | ------- | -------- |
| CSV scalar fields | `order_total` | Header-driven field discovery with scalar inference |
| JSON objects | `user.email` | Nested object flattening |
| JSON arrays | `items[].sku` | Array item flattening |
| JSONL records | one object per line | Record-set merge across lines |
| Parquet fields | `campaign_id` | Direct schema extraction through PyArrow |
