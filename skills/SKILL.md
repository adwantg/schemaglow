---
name: "schemaglow"
description: "Project skill for developing the SchemaGlow repository. Use when working on the Python package, CLI commands, schema inference, compatibility rules, reports, packaging, tests, or documentation for CSV, JSON, JSONL, and Parquet schema diff workflows."
---

# SchemaGlow Skill

Use this skill when editing `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow`.

## Project Context

- Pain point: developers can inspect or validate schemas, but they still lack a simple CLI that explains schema drift impact for humans in PR and CI review.
- Solution: infer file schemas, compare them, classify change severity, and render review-friendly output across single files, scans, and baselines.
- Positioning: a git-friendly schema diff tool that tells humans whether a data-file change is safe, risky, or breaking.

## Working Rules

1. Keep CSV, JSON, JSONL, Parquet, OpenAPI, Avro, and protobuf support aligned across commands, docs, and tests.
2. Treat `SAFE`, `WARNING`, and `BREAKING` classifications as the core product behavior.
3. Update `README.md` whenever commands, flags, compatibility rules, or report outputs change.
4. Keep the repo local-first; do not introduce service dependencies or metadata-platform assumptions.
5. Maintain `ruff`, `mypy`, `pytest`, and 90% coverage requirements.

## Primary References

- `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow/skills/REQUIREMENTS.md`
- `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow/skills/00_MAIN_SKILLS_GUIDE.md`
- `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow/skills/FEATURES.md`
- `/Users/goutamadwant/Documents/OpenSource/PythonProjects/schemaglow/skills/COMPETITIVE_ANALYSIS.md`

## Repository Files Covered by This Skill

- `README.md`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/`
- `src/schemaglow/` package modules
- `tests/` unit and integration coverage
- `CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff`, `release.sh`

## Delivery Checklist

1. Keep CLI help, README examples, and tests synchronized.
2. Add tests for every user-visible compatibility rule change.
3. Prefer simple, deterministic inference and diff rules over speculative behavior.
4. Preserve human-readable output and machine-readable export paths together.
5. Keep `scan` and `baseline` flows consistent with single-file comparison semantics.
