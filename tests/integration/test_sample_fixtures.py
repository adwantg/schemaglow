from __future__ import annotations

import shutil
from pathlib import Path

from schemaglow.models import CompareOptions, Severity
from schemaglow.service import (
    capture_baseline,
    check_baseline,
    compare_files,
    inspect_file,
    scan_directories,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DOWNLOADED = FIXTURES / "downloaded"
MANUAL = FIXTURES / "manual"


def test_downloaded_samples_cover_every_supported_input_type() -> None:
    expected = {
        "seattle-weather.csv": ("csv", "date"),
        "miserables.json": ("json", "nodes[].name"),
        "example.jsonl": ("jsonl", "result.sequenceNumber"),
        "alltypes_plain.parquet": ("parquet", "id"),
        "petstore.yaml": ("openapi", "Pet.name"),
        "user.avsc": ("avro", "name"),
        "addressbook.proto": ("protobuf", "Person.email"),
    }

    for filename, (source_format, expected_path) in expected.items():
        snapshot = inspect_file(DOWNLOADED / filename)

        assert snapshot.source_format == source_format
        assert expected_path in snapshot.field_map


def test_manual_fixture_pairs_exercise_each_supported_diff_path() -> None:
    cases = [
        (
            MANUAL / "csv/weather-baseline.csv",
            MANUAL / "csv/weather-candidate.csv",
            Severity.SAFE,
            "field_added_optional",
            "station",
        ),
        (
            MANUAL / "json/miserables-baseline.json",
            MANUAL / "json/miserables-candidate.json",
            Severity.BREAKING,
            "incompatible_type_change",
            "metadata.version",
        ),
        (
            MANUAL / "jsonl/search-baseline.jsonl",
            MANUAL / "jsonl/search-candidate.jsonl",
            Severity.BREAKING,
            "incompatible_type_change",
            "result.sequenceNumber",
        ),
        (
            MANUAL / "parquet/alltypes-baseline.parquet",
            MANUAL / "parquet/alltypes-candidate.parquet",
            Severity.SAFE,
            "field_added_optional",
            "campaign_id",
        ),
        (
            MANUAL / "openapi/petstore-baseline.yaml",
            MANUAL / "openapi/petstore-candidate.yaml",
            Severity.BREAKING,
            "incompatible_type_change",
            "Pet.name",
        ),
        (
            MANUAL / "avro/user-baseline.avsc",
            MANUAL / "avro/user-candidate.avsc",
            Severity.BREAKING,
            "incompatible_type_change",
            "favorite_number",
        ),
        (
            MANUAL / "proto/addressbook-baseline.proto",
            MANUAL / "proto/addressbook-candidate.proto",
            Severity.BREAKING,
            "incompatible_type_change",
            "Person.email",
        ),
    ]

    for old_path, new_path, severity, code, event_path in cases:
        report = compare_files(old_path, new_path, CompareOptions())

        assert report.overall == severity
        assert any(event.code == code and event.path == event_path for event in report.events)


def test_manual_option_fixtures_cover_strict_ignore_and_rename_modes() -> None:
    default_report = compare_files(
        MANUAL / "options/strict-old.csv",
        MANUAL / "options/strict-new.csv",
        CompareOptions(),
    )
    strict_report = compare_files(
        MANUAL / "options/strict-old.csv",
        MANUAL / "options/strict-new.csv",
        CompareOptions(strict=True),
    )
    rename_report = compare_files(
        MANUAL / "options/rename-old.csv",
        MANUAL / "options/rename-new.csv",
        CompareOptions(rename_heuristics=True),
    )
    ignore_report = compare_files(
        MANUAL / "options/ignore-old.jsonl",
        MANUAL / "options/ignore-new.jsonl",
        CompareOptions(ignore_fields=r"^_loaded_at$"),
    )

    assert default_report.overall == Severity.SAFE
    assert strict_report.overall == Severity.WARNING
    assert any(event.code == "possible_rename" for event in rename_report.events)
    assert ignore_report.overall == Severity.SAFE
    assert ignore_report.ignored_fields == ["_loaded_at"]


def test_manual_scan_and_baseline_workflows_use_committed_fixtures(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    baseline_root = tmp_path / ".schemaglow-baseline"
    shutil.copytree(MANUAL / "scan/old", old_root)
    shutil.copytree(MANUAL / "scan/new", new_root)

    scan_report = scan_directories(old_root, new_root, CompareOptions())
    manifest = capture_baseline(old_root, baseline_root)
    baseline_report = check_baseline(baseline_root, new_root, CompareOptions())

    assert scan_report.overall == Severity.BREAKING
    assert any(entry.status == "added_file" for entry in scan_report.entries)
    assert manifest.entries
    assert baseline_report.overall == Severity.BREAKING
    assert any(entry.status == "unexpected_candidate" for entry in baseline_report.entries)
