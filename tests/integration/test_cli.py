from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from typer.testing import CliRunner

from schemaglow.cli import app

runner = CliRunner()


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_diff_command_outputs_json_and_writes_html_report_for_parquet(tmp_path: Path) -> None:
    old_file = tmp_path / "old.parquet"
    new_file = tmp_path / "new.parquet"
    report_path = tmp_path / "report.html"

    pq.write_table(pa.table({"id": [1, 2]}), old_file)
    pq.write_table(pa.table({"id": [1, 2], "campaign_id": ["a", None]}), new_file)

    result = runner.invoke(
        app,
        [
            "diff",
            str(old_file),
            str(new_file),
            "--format",
            "json",
            "--report",
            "html",
            "--report-path",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout.split("report written to", maxsplit=1)[0].strip())
    assert payload["overall"] == "SAFE"
    assert any(event["code"] == "field_added_optional" for event in payload["events"])
    assert report_path.exists()
    assert "<html" in report_path.read_text(encoding="utf-8").lower()


def test_inspect_snapshot_and_compare_roundtrip(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,total\n1,10\n2,20\n")
    new_file = _write(tmp_path / "new.csv", "id,total,status\n1,10,open\n2,20,\n")
    old_snapshot = tmp_path / "old.schema.json"
    new_snapshot = tmp_path / "new.schema.json"

    inspect_result = runner.invoke(app, ["inspect", str(old_file)])
    assert inspect_result.exit_code == 0
    assert "SchemaGlow Inspect" in inspect_result.stdout
    assert "- id: integer (required)" in inspect_result.stdout

    snapshot_old_result = runner.invoke(app, ["snapshot", str(old_file), "-o", str(old_snapshot)])
    snapshot_new_result = runner.invoke(app, ["snapshot", str(new_file), "-o", str(new_snapshot)])
    assert snapshot_old_result.exit_code == 0
    assert snapshot_new_result.exit_code == 0
    assert old_snapshot.exists()
    assert new_snapshot.exists()

    compare_result = runner.invoke(
        app, ["compare", str(old_snapshot), str(new_snapshot), "--format", "json"]
    )
    assert compare_result.exit_code == 0
    payload = json.loads(compare_result.stdout)
    assert payload["overall"] == "SAFE"
    assert any(event["path"] == "status" for event in payload["events"])


def test_diff_markdown_stdout_and_inspect_json_output(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.json", '{"order":{"id":1,"total":10}}')
    new_file = _write(tmp_path / "new.json", '{"order":{"id":1,"total":10,"status":"open"}}')

    diff_result = runner.invoke(
        app,
        [
            "diff",
            str(old_file),
            str(new_file),
            "--report",
            "markdown",
        ],
    )
    inspect_result = runner.invoke(app, ["inspect", str(new_file), "--format", "json"])

    assert diff_result.exit_code == 0
    assert "SchemaGlow Report" in diff_result.stdout
    assert "# SchemaGlow Report" in diff_result.stdout
    assert inspect_result.exit_code == 0
    payload = json.loads(inspect_result.stdout)
    assert payload["source_format"] == "json"
    assert any(field["path"] == "order.status" for field in payload["fields"])


def test_compare_text_output_and_invalid_report_value(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,total\n1,10\n")
    new_file = _write(tmp_path / "new.csv", "id,total\n1,10.5\n")
    old_snapshot = tmp_path / "old.schema.json"
    new_snapshot = tmp_path / "new.schema.json"

    runner.invoke(app, ["snapshot", str(old_file), "-o", str(old_snapshot)])
    runner.invoke(app, ["snapshot", str(new_file), "-o", str(new_snapshot)])

    compare_result = runner.invoke(app, ["compare", str(old_snapshot), str(new_snapshot)])
    invalid_report = runner.invoke(app, ["diff", str(old_file), str(new_file), "--report", "xml"])

    assert compare_result.exit_code == 0
    assert "SchemaGlow Report" in compare_result.stdout
    assert invalid_report.exit_code != 0


def test_scan_command_and_baseline_commands(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    baseline_dir = tmp_path / ".schemaglow-baseline"
    old_dir.mkdir()
    new_dir.mkdir()

    _write(old_dir / "orders.csv", "id,total\n1,10\n")
    _write(new_dir / "orders.csv", "id,total,status\n1,10,\n")
    _write(
        new_dir / "openapi.yaml",
        "openapi: 3.1.0\ninfo:\n  title: Demo\n  version: '1.0'\npaths: {}\n",
    )

    scan_result = runner.invoke(app, ["scan", str(old_dir), str(new_dir), "--format", "json"])
    capture_result = runner.invoke(
        app, ["baseline", "capture", str(old_dir), "-o", str(baseline_dir)]
    )
    check_result = runner.invoke(
        app,
        ["baseline", "check", str(baseline_dir), str(new_dir), "--format", "json"],
    )

    assert scan_result.exit_code == 0
    scan_payload = json.loads(scan_result.stdout)
    assert scan_payload["overall"] == "WARNING"
    assert any(entry["status"] == "added_file" for entry in scan_payload["entries"])

    assert capture_result.exit_code == 0
    assert "SchemaGlow Baseline" in capture_result.stdout
    assert (baseline_dir / "schemaglow-baseline.json").exists()

    assert check_result.exit_code == 0
    check_payload = json.loads(check_result.stdout)
    assert any(entry["status"] == "unexpected_candidate" for entry in check_payload["entries"])
