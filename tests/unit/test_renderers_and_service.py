from __future__ import annotations

import json
from pathlib import Path

from schemaglow.models import CompareOptions, Severity
from schemaglow.renderers import (
    render_baseline_manifest_text,
    render_directory_html,
    render_directory_json,
    render_directory_markdown,
    render_directory_text,
    render_html_report,
    render_json_report,
    render_markdown_report,
    render_snapshot_text,
    render_text_report,
    write_report,
)
from schemaglow.service import (
    capture_baseline,
    check_baseline,
    compare_files,
    compare_snapshots,
    load_snapshot,
    save_snapshot,
    scan_directories,
    snapshot_file,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_renderers_emit_all_supported_report_formats(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,total\n1,10\n2,20\n")
    new_file = _write(tmp_path / "new.csv", "id,total,status\n1,10,open\n2,20,\n")

    report = compare_files(old_file, new_file, options=CompareOptions())

    text_output = render_text_report(report)
    json_output = render_json_report(report)
    markdown_output = render_markdown_report(report)
    html_output = render_html_report(report)

    assert "SchemaGlow Report" in text_output
    assert "added optional field: status (string)" in text_output
    assert json.loads(json_output)["overall"] == Severity.SAFE.value
    assert "# SchemaGlow Report" in markdown_output
    assert "added optional field: status (string)" in markdown_output
    assert "<html" in html_output.lower()
    assert "campaign_id" not in html_output


def test_snapshot_save_load_and_compare_roundtrip(tmp_path: Path) -> None:
    source_file = _write(tmp_path / "source.json", '{"order":{"id":1,"total":12.5}}')
    snapshot_path = tmp_path / "snapshot.json"

    snapshot = snapshot_file(source_file)
    save_snapshot(snapshot, snapshot_path)
    loaded_snapshot = load_snapshot(snapshot_path)
    comparison = compare_snapshots(snapshot, loaded_snapshot)

    assert loaded_snapshot.source_format == "json"
    assert loaded_snapshot.field_map["order.total"].type_name == "number"
    assert comparison.overall == Severity.SAFE
    assert comparison.events[0].code == "no_change"


def test_render_snapshot_text_and_write_report(tmp_path: Path) -> None:
    source_file = _write(tmp_path / "records.jsonl", '{"user":{"id":1}}\n{"user":{"id":2}}\n')
    report_path = tmp_path / "inspect.txt"

    snapshot = snapshot_file(source_file)
    inspect_output = render_snapshot_text(snapshot)
    write_report(report_path, inspect_output)

    assert "SchemaGlow Inspect" in inspect_output
    assert "- user.id: integer (required)" in inspect_output
    assert report_path.read_text(encoding="utf-8") == inspect_output


def test_renderers_include_ignored_fields_and_before_after_details(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,_loaded_at\n1,2026-03-09\n")
    new_file = _write(tmp_path / "new.csv", "id,_loaded_at\none,2026-03-10\n")

    report = compare_files(
        old_file, new_file, options=CompareOptions(ignore_fields=r"^_loaded_at$")
    )

    text_output = render_text_report(report)
    markdown_output = render_markdown_report(report)

    assert "ignored: _loaded_at" in text_output
    assert "before: integer / required" in text_output
    assert "## Ignored Fields" in markdown_output
    assert "- Before: `integer` / required" in markdown_output


def test_scan_directories_and_baseline_check(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    baseline_dir = tmp_path / "baseline"
    old_dir.mkdir()
    new_dir.mkdir()

    _write(old_dir / "orders.csv", "id,total\n1,10\n")
    _write(new_dir / "orders.csv", "id,total,status\n1,10,\n")
    _write(new_dir / "extra.json", '{"id": 1}')

    scan_report = scan_directories(old_dir, new_dir, options=CompareOptions())
    manifest = capture_baseline(old_dir, baseline_dir)
    baseline_report = check_baseline(baseline_dir, new_dir, options=CompareOptions())

    assert manifest.entries[0].relative_path == "orders.csv"
    assert scan_report.overall == Severity.WARNING
    assert any(entry.status == "added_file" for entry in scan_report.entries)
    assert baseline_report.overall == Severity.WARNING
    assert any(entry.status == "unexpected_candidate" for entry in baseline_report.entries)


def test_directory_renderers_and_baseline_manifest_text(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    baseline_dir = tmp_path / "baseline"
    old_dir.mkdir()
    new_dir.mkdir()

    _write(old_dir / "orders.csv", "id,total\n1,10\n")
    _write(new_dir / "orders.csv", "id,total\n1,10.5\n")

    scan_report = scan_directories(old_dir, new_dir, options=CompareOptions(strict=True))
    manifest = capture_baseline(old_dir, baseline_dir)

    text_output = render_directory_text(scan_report)
    json_output = render_directory_json(scan_report)
    markdown_output = render_directory_markdown(scan_report)
    html_output = render_directory_html(scan_report)
    manifest_output = render_baseline_manifest_text(manifest, baseline_dir)

    assert "SchemaGlow Scan Report" in text_output
    assert '"overall": "WARNING"' in json_output
    assert "# SchemaGlow Scan Report" in markdown_output
    assert "<html" in html_output.lower()
    assert "SchemaGlow Baseline" in manifest_output
    assert "orders.csv" in manifest_output
