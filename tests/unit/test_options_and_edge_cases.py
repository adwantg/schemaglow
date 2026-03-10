from __future__ import annotations

from pathlib import Path

import pytest

from schemaglow.infer import detect_format
from schemaglow.models import CompareOptions, Severity
from schemaglow.service import compare_files, inspect_file


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_ignore_fields_suppresses_matching_paths(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,_loaded_at\n1,2026-03-09\n")
    new_file = _write(tmp_path / "new.csv", "id,_loaded_at\n1,2026-03-10\n")

    report = compare_files(
        old_file, new_file, options=CompareOptions(ignore_fields=r"^_loaded_at$")
    )

    assert report.overall == Severity.SAFE
    assert report.ignored_fields == ["_loaded_at"]
    assert report.events[0].code == "no_change"


def test_strict_numeric_widening_is_warning(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "total\n10\n20\n")
    new_file = _write(tmp_path / "new.csv", "total\n10.5\n20.0\n")

    report = compare_files(old_file, new_file, options=CompareOptions(strict=True))

    assert report.overall == Severity.WARNING
    assert any(
        event.code == "numeric_widening" and event.severity == Severity.WARNING
        for event in report.events
    )


def test_required_to_nullable_becomes_warning(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,status\n1,open\n2,closed\n")
    new_file = _write(tmp_path / "new.csv", "id,status\n1,open\n2,\n")

    report = compare_files(old_file, new_file, options=CompareOptions())

    assert report.overall == Severity.WARNING
    assert any(event.code == "required_to_nullable" for event in report.events)


def test_top_level_json_array_of_objects_flattens_without_array_prefix(tmp_path: Path) -> None:
    source_file = _write(
        tmp_path / "records.json", '[{"user":{"id":1}},{"user":{"id":2,"name":"Bea"}}]'
    )

    snapshot = inspect_file(source_file)

    assert "user.id" in snapshot.field_map
    assert "user.name" in snapshot.field_map
    assert "[]".strip() not in snapshot.field_map


def test_detect_format_rejects_unsupported_extension() -> None:
    with pytest.raises(ValueError, match="Unsupported file format"):
        detect_format(Path("notes.txt"))


def test_sample_shape_change_is_reported_for_string_fields(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id\nUSER_A\nUSER_B\n")
    new_file = _write(tmp_path / "new.csv", "id\nalpha-1\nbeta-2\n")

    report = compare_files(old_file, new_file, options=CompareOptions())

    assert report.overall == Severity.WARNING
    assert any(event.code == "sample_shape_changed" for event in report.events)


def test_nested_field_removal_is_collapsed_to_parent_event(tmp_path: Path) -> None:
    old_file = _write(
        tmp_path / "old.json", '{"user":{"profile":{"id":1,"email":"a@example.com"}}}'
    )
    new_file = _write(tmp_path / "new.json", '{"user":{}}')

    report = compare_files(old_file, new_file, options=CompareOptions())
    removed_paths = {event.path for event in report.events if event.code == "field_removed"}

    assert "user.profile" in removed_paths
    assert "user.profile.id" not in removed_paths


def test_type_change_branches_cover_shape_widening_ambiguous_and_materialized(
    tmp_path: Path,
) -> None:
    old_date = _write(tmp_path / "old_date.csv", "created_at\n2026-03-09\n")
    new_string = _write(tmp_path / "new_string.csv", "created_at\nnot-a-date\n")
    shape_report = compare_files(old_date, new_string, options=CompareOptions())

    old_mixed = _write(
        tmp_path / "old_mixed.jsonl",
        '{"value": 1}\n{"value": "two"}\n',
    )
    new_plain = _write(
        tmp_path / "new_plain.jsonl",
        '{"value": "one"}\n{"value": "two"}\n',
    )
    ambiguous_report = compare_files(old_mixed, new_plain, options=CompareOptions())

    old_null = _write(tmp_path / "old_null.json", '{"status": null}')
    new_value = _write(tmp_path / "new_value.json", '{"status": "open"}')
    materialized_report = compare_files(old_null, new_value, options=CompareOptions())

    old_base = _write(tmp_path / "old_base.csv", "id\n1\n")
    new_required = _write(tmp_path / "new_required.csv", "id,status\n1,open\n")
    added_required_report = compare_files(old_base, new_required, options=CompareOptions())

    assert any(event.code == "shape_widening" for event in shape_report.events)
    assert any(event.code == "ambiguous_type_change" for event in ambiguous_report.events)
    assert any(event.code == "materialized_type" for event in materialized_report.events)
    assert any(event.code == "field_added_required" for event in added_required_report.events)
