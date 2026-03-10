from __future__ import annotations

from pathlib import Path

from schemaglow.models import CompareOptions, Severity
from schemaglow.service import compare_files, inspect_file


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_csv_diff_detects_numeric_widening_and_order_change(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "id,total\n1,10\n2,20\n")
    new_file = _write(tmp_path / "new.csv", "total,id\n10.5,1\n20.0,2\n")

    report = compare_files(old_file, new_file, options=CompareOptions())

    assert report.overall == Severity.SAFE
    assert any(event.code == "numeric_widening" for event in report.events)
    assert any(event.code == "column_order_changed" for event in report.events)


def test_jsonl_diff_detects_breaking_nullability_and_nested_expansion(tmp_path: Path) -> None:
    old_file = _write(
        tmp_path / "old.jsonl",
        "\n".join(
            [
                '{"user":{"id":1,"name":"Ada"}}',
                '{"user":{"id":2}}',
            ]
        )
        + "\n",
    )
    new_file = _write(
        tmp_path / "new.jsonl",
        "\n".join(
            [
                '{"user":{"id":1,"name":"Ada","email":"ada@example.com"}}',
                '{"user":{"id":2,"name":"Bea","email":"bea@example.com"}}',
            ]
        )
        + "\n",
    )

    report = compare_files(old_file, new_file, options=CompareOptions())

    assert any(
        event.code == "nullable_to_required" and event.path == "user.name"
        for event in report.events
    )
    assert any(
        event.code == "nested_shape_expanded" and event.path == "user.email"
        for event in report.events
    )
    assert report.overall == Severity.BREAKING


def test_rename_heuristics_flags_likely_field_rename(tmp_path: Path) -> None:
    old_file = _write(tmp_path / "old.csv", "user_name\nada\nbea\n")
    new_file = _write(tmp_path / "new.csv", "username\nada\nbea\n")

    report = compare_files(old_file, new_file, options=CompareOptions(rename_heuristics=True))

    rename_events = [event for event in report.events if event.code == "possible_rename"]
    assert len(rename_events) == 1
    assert rename_events[0].summary == "possible rename: user_name -> username"


def test_inspect_file_infers_nested_json_fields(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sample.json",
        '{"order":{"id":1,"created_at":"2026-03-09T12:00:00Z"},"tags":["a","b"]}',
    )

    snapshot = inspect_file(path)
    field_map = snapshot.field_map

    assert field_map["order"].type_name == "object"
    assert field_map["order.created_at"].type_name == "datetime"
    assert field_map["tags"].type_name == "array"
    assert field_map["tags[]"].type_name == "string"


def test_openapi_avro_and_proto_are_supported(tmp_path: Path) -> None:
    openapi_file = _write(
        tmp_path / "openapi.yaml",
        """
openapi: 3.1.0
info:
  title: Demo
  version: "1.0"
paths: {}
components:
  schemas:
    User:
      type: object
      required: [id]
      properties:
        id:
          type: integer
        email:
          type: string
          format: email
""".strip()
        + "\n",
    )
    avro_file = _write(
        tmp_path / "user.avsc",
        """
{
  "type": "record",
  "name": "User",
  "fields": [
    {"name": "id", "type": "long"},
    {"name": "nickname", "type": ["null", "string"]}
  ]
}
""".strip()
        + "\n",
    )
    proto_file = _write(
        tmp_path / "user.proto",
        """
syntax = "proto3";

message User {
  string id = 1;
  repeated string tags = 2;
}
""".strip()
        + "\n",
    )

    openapi_snapshot = inspect_file(openapi_file)
    avro_snapshot = inspect_file(avro_file)
    proto_snapshot = inspect_file(proto_file)

    assert openapi_snapshot.source_format == "openapi"
    assert openapi_snapshot.field_map["User.email"].format_hint == "email"
    assert avro_snapshot.source_format == "avro"
    assert avro_snapshot.field_map["nickname"].nullable is True
    assert proto_snapshot.source_format == "protobuf"
    assert proto_snapshot.field_map["User.tags"].type_name == "array"
    assert proto_snapshot.field_map["User.tags[]"].type_name == "string"
