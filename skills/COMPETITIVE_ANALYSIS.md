# SchemaGlow Competitive Analysis

## Landscape

| Tier | Description | Players |
| ---- | ----------- | ------- |
| General validation platforms | Full data-quality systems | Great Expectations, OpenMetadata |
| File utilities | Inspection and format tooling | qsv, parquet-tools |
| Schema diff tools | Schema-oriented comparison | json-schema-diff, DBDiff |

## Competitor Notes

### Great Expectations

- Strength: strong validation and expectation management.
- Weakness: heavier workflow than a lightweight two-file diff CLI.

### OpenMetadata

- Strength: metadata platform with checks and drift monitoring.
- Weakness: not local-first and not optimized for quick repository review.

### json-schema-diff

- Strength: explicit schema diff for JSON schema assets.
- Weakness: narrower scope and less suited to raw data files.

### parquet-tools

- Strength: good utility layer for Parquet inspection.
- Weakness: does not explain compatibility impact for humans.

## Differentiators

1. Format-agnostic file workflow instead of one-format tooling.
2. Human-first compatibility output instead of raw structural diff.
3. Local-first CLI that fits pull request and CI review.

## Positioning Statement

> SchemaGlow is a git-friendly schema diff tool that tells humans whether a data-file change is safe, risky, or breaking.

## Product Risks

- Type inference can overgeneralize when the sample is too small.
- Rename heuristics should remain clearly marked as uncertain behavior.
- The README and CLI help must stay synchronized because the workflow is command-driven.
