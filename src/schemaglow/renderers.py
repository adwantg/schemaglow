from __future__ import annotations

from html import escape
from pathlib import Path
from typing import cast

from jinja2 import Template

from .models import (
    BaselineManifest,
    ComparisonReport,
    DiffEvent,
    DirectoryReport,
    SchemaSnapshot,
)

HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SchemaGlow Report</title>
  <style>
    :root {
      --safe: #116149;
      --warning: #9a6700;
      --breaking: #b42318;
      --ink: #172033;
      --line: #d8deea;
      --paper: #f7f8fb;
    }
    body {
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      margin: 2rem auto;
      max-width: 960px;
      color: var(--ink);
      background: linear-gradient(180deg, #ffffff 0%, var(--paper) 100%);
      padding: 0 1rem 3rem;
    }
    h1, h2 { margin-bottom: 0.5rem; }
    .meta { color: #51607d; }
    .event {
      border: 1px solid var(--line);
      border-left-width: 6px;
      border-radius: 12px;
      background: white;
      padding: 1rem;
      margin: 0 0 1rem;
    }
    .SAFE { border-left-color: var(--safe); }
    .WARNING { border-left-color: var(--warning); }
    .BREAKING { border-left-color: var(--breaking); }
    code {
      background: #eef2f8;
      padding: 0.1rem 0.3rem;
      border-radius: 4px;
    }
  </style>
</head>
<body>
  <h1>SchemaGlow Report</h1>
  <p class="meta">
    <strong>{{ report.overall.value }}</strong>
    for {{ report.old_snapshot.source_path }} -> {{ report.new_snapshot.source_path }}
  </p>
  <p class="meta">
    Counts: safe={{ report.counts["SAFE"] }},
    warning={{ report.counts["WARNING"] }},
    breaking={{ report.counts["BREAKING"] }}
  </p>
  {% for event in report.events %}
  <div class="event {{ event.severity.value }}">
    <strong>{{ event.severity.value }}</strong>
    <p>{{ event.summary }}</p>
    {% if event.old %}
    <p>
      Before: <code>{{ event.old.type_name }}</code>
      {% if event.old.nullable %} nullable{% else %} required{% endif %}
    </p>
    {% endif %}
    {% if event.new %}
    <p>
      After: <code>{{ event.new.type_name }}</code>
      {% if event.new.nullable %} nullable{% else %} required{% endif %}
    </p>
    {% endif %}
  </div>
  {% endfor %}
</body>
</html>
"""
)

DIRECTORY_HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SchemaGlow Scan Report</title>
  <style>
    body {
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      margin: 2rem auto;
      max-width: 1000px;
      color: #172033;
      background: linear-gradient(180deg, #ffffff 0%, #f7f8fb 100%);
      padding: 0 1rem 3rem;
    }
    .entry {
      border: 1px solid #d8deea;
      border-left-width: 6px;
      border-radius: 12px;
      background: white;
      padding: 1rem;
      margin: 0 0 1rem;
    }
    .SAFE { border-left-color: #116149; }
    .WARNING { border-left-color: #9a6700; }
    .BREAKING { border-left-color: #b42318; }
  </style>
</head>
<body>
  <h1>SchemaGlow Scan Report</h1>
  <p>
    <strong>{{ report.overall.value }}</strong>
    for {{ report.old_root }} -> {{ report.new_root }}
  </p>
  {% for entry in report.entries %}
  <div class="entry {{ entry.severity.value }}">
    <strong>{{ entry.severity.value }}</strong>
    <p>{{ entry.summary }}</p>
    {% if entry.report %}
      <p>
        Counts: safe={{ entry.report.counts["SAFE"] }},
        warning={{ entry.report.counts["WARNING"] }},
        breaking={{ entry.report.counts["BREAKING"] }}
      </p>
    {% endif %}
  </div>
  {% endfor %}
</body>
</html>
"""
)


def render_text_report(report: ComparisonReport) -> str:
    lines = [
        "SchemaGlow Report",
        "",
        f"{report.overall.value}",
        f"old: {report.old_snapshot.source_path}",
        f"new: {report.new_snapshot.source_path}",
        (
            "counts: "
            f"SAFE={report.counts['SAFE']} "
            f"WARNING={report.counts['WARNING']} "
            f"BREAKING={report.counts['BREAKING']}"
        ),
    ]
    if report.ignored_fields:
        lines.append(f"ignored: {', '.join(report.ignored_fields)}")
    for event in report.events:
        lines.extend(_format_event_lines(event))
    return "\n".join(lines)


def render_json_report(report: ComparisonReport) -> str:
    try:
        import orjson  # type: ignore[import-not-found]

        payload = cast(
            bytes,
            orjson.dumps(_report_payload(report), option=orjson.OPT_INDENT_2),
        )
        return payload.decode("utf-8")
    except ModuleNotFoundError:
        import json

        return json.dumps(_report_payload(report), indent=2)


def render_markdown_report(report: ComparisonReport) -> str:
    lines = [
        "# SchemaGlow Report",
        "",
        f"**Overall:** `{report.overall.value}`",
        "",
        f"- Old snapshot: `{report.old_snapshot.source_path}`",
        f"- New snapshot: `{report.new_snapshot.source_path}`",
        (
            "- Counts: "
            f"SAFE={report.counts['SAFE']}, "
            f"WARNING={report.counts['WARNING']}, "
            f"BREAKING={report.counts['BREAKING']}"
        ),
        "",
    ]
    if report.ignored_fields:
        ignored_lines = [f"- `{field}`" for field in report.ignored_fields]
        lines.extend(["## Ignored Fields", "", *ignored_lines, ""])
    lines.extend(["## Events", ""])
    for event in report.events:
        lines.append(f"### {event.severity.value}")
        lines.append(f"- Path: `{event.path}`")
        lines.append(f"- Summary: {event.summary}")
        if event.old is not None:
            lines.append(
                "- Before: "
                f"`{event.old.type_name}` / "
                f"{'nullable' if event.old.nullable else 'required'}"
            )
        if event.new is not None:
            lines.append(
                "- After: "
                f"`{event.new.type_name}` / "
                f"{'nullable' if event.new.nullable else 'required'}"
            )
        lines.append("")
    return "\n".join(lines)


def render_html_report(report: ComparisonReport) -> str:
    return HTML_TEMPLATE.render(report=report)


def render_directory_text(report: DirectoryReport) -> str:
    lines = [
        "SchemaGlow Scan Report",
        "",
        f"{report.overall.value}",
        f"old: {report.old_root}",
        f"new: {report.new_root}",
        (
            "counts: "
            f"SAFE={report.counts['SAFE']} "
            f"WARNING={report.counts['WARNING']} "
            f"BREAKING={report.counts['BREAKING']}"
        ),
        "",
    ]
    for entry in report.entries:
        lines.append(f"{entry.severity.value} {entry.relative_path}")
        lines.append(f"- {entry.summary}")
        if entry.report is not None:
            for event in entry.report.events:
                lines.extend(_format_event_lines(event))
        lines.append("")
    return "\n".join(lines).strip()


def render_directory_json(report: DirectoryReport) -> str:
    try:
        import orjson  # type: ignore[import-not-found]

        payload = cast(
            bytes,
            orjson.dumps(_directory_payload(report), option=orjson.OPT_INDENT_2),
        )
        return payload.decode("utf-8")
    except ModuleNotFoundError:
        import json

        return json.dumps(_directory_payload(report), indent=2)


def render_directory_markdown(report: DirectoryReport) -> str:
    lines = [
        "# SchemaGlow Scan Report",
        "",
        f"**Overall:** `{report.overall.value}`",
        "",
        f"- Old root: `{report.old_root}`",
        f"- New root: `{report.new_root}`",
        (
            "- Counts: "
            f"SAFE={report.counts['SAFE']}, "
            f"WARNING={report.counts['WARNING']}, "
            f"BREAKING={report.counts['BREAKING']}"
        ),
        "",
    ]
    for entry in report.entries:
        lines.append(f"## {entry.relative_path}")
        lines.append(f"- Severity: `{entry.severity.value}`")
        lines.append(f"- Summary: {entry.summary}")
        if entry.report is not None:
            for event in entry.report.events:
                lines.append(f"- Event: {event.summary}")
        lines.append("")
    return "\n".join(lines)


def render_directory_html(report: DirectoryReport) -> str:
    return DIRECTORY_HTML_TEMPLATE.render(report=report)


def render_snapshot_text(snapshot: SchemaSnapshot) -> str:
    lines = [
        f"SchemaGlow Inspect: {snapshot.source_path}",
        f"format: {snapshot.source_format}",
        f"root: {snapshot.root_type}",
        f"fields: {len(snapshot.fields)}",
        "",
    ]
    for field in snapshot.fields:
        nullability = "nullable" if field.nullable else "required"
        sample = f" samples={field.sample_values}" if field.sample_values else ""
        lines.append(f"- {field.path}: {field.type_name} ({nullability}){sample}")
    return "\n".join(lines)


def write_report(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def render_baseline_manifest_text(manifest: BaselineManifest, baseline_root: Path) -> str:
    lines = [
        "SchemaGlow Baseline",
        "",
        f"source: {manifest.source_root}",
        f"baseline: {baseline_root}",
        f"files: {len(manifest.entries)}",
        f"sample_size: {manifest.sample_size}",
        "",
    ]
    for entry in manifest.entries:
        lines.append(f"- {entry.relative_path} -> {entry.snapshot_path} ({entry.source_format})")
    return "\n".join(lines)


def _report_payload(report: ComparisonReport) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["overall"] = report.overall.value
    payload["counts"] = report.counts
    return payload


def _directory_payload(report: DirectoryReport) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["overall"] = report.overall.value
    payload["counts"] = report.counts
    for entry_payload, entry in zip(payload["entries"], report.entries, strict=False):
        if isinstance(entry_payload, dict) and entry.report is not None:
            entry_payload["report"] = _report_payload(entry.report)
    return payload


def _format_event_lines(event: DiffEvent) -> list[str]:
    prefix = {
        "SAFE": "+",
        "WARNING": "~",
        "BREAKING": "-",
    }[event.severity.value]
    lines = [f"{event.severity.value}", f"{prefix} {event.summary}"]
    if event.old is not None:
        lines.append(
            "  before: "
            f"{escape(event.old.type_name)} / "
            f"{'nullable' if event.old.nullable else 'required'}"
        )
    if event.new is not None:
        lines.append(
            "  after: "
            f"{escape(event.new.type_name)} / "
            f"{'nullable' if event.new.nullable else 'required'}"
        )
    return lines


__author__ = "gadwant"
