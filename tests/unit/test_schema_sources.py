from __future__ import annotations

from pathlib import Path

import pytest

from schemaglow.schema_sources import infer_openapi_schema, is_openapi_document
from schemaglow.service import inspect_file


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_is_openapi_document_handles_supported_and_unsupported_inputs(tmp_path: Path) -> None:
    openapi_json = _write(
        tmp_path / "openapi.json",
        '{"openapi":"3.1.0","info":{"title":"Demo","version":"1.0"},"paths":{}}',
    )
    plain_json = _write(tmp_path / "plain.json", '{"value": 1}')

    assert is_openapi_document(openapi_json) is True
    assert is_openapi_document(plain_json) is False
    assert is_openapi_document(tmp_path / "notes.txt") is False


def test_openapi_paths_refs_allof_and_arrays_are_flattened(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "openapi.yaml",
        """
openapi: 3.1.0
info:
  title: Demo
  version: "1.0"
paths:
  /users:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExtendedUser'
      responses:
        "200":
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/BaseUser'
components:
  schemas:
    BaseUser:
      type: object
      required: [id]
      properties:
        id:
          type: integer
        email:
          type: string
          format: email
    ExtendedUser:
      allOf:
        - $ref: '#/components/schemas/BaseUser'
        - type: object
          properties:
            role:
              type: string
              enum: [ADMIN, MEMBER]
""".strip()
        + "\n",
    )

    snapshot = inspect_file(path)

    assert snapshot.source_format == "openapi"
    assert snapshot.field_map["BaseUser.email"].format_hint == "email"
    assert snapshot.field_map["ExtendedUser.role"].sample_values == ["ADMIN", "MEMBER"]
    assert (
        snapshot.field_map["paths.users.post.request.application.json.role"].type_name == "string"
    )
    assert (
        snapshot.field_map["paths.users.post.responses.200.application.json"].type_name == "array"
    )
    assert (
        snapshot.field_map["paths.users.post.responses.200.application.json[].email"].format_hint
        == "email"
    )


def test_infer_openapi_rejects_non_openapi_documents(tmp_path: Path) -> None:
    path = _write(tmp_path / "plain.yaml", "name: demo\n")

    with pytest.raises(ValueError, match="does not look like an OpenAPI document"):
        infer_openapi_schema(path)


def test_avro_named_types_arrays_maps_and_unions_are_flattened(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "schema.avsc",
        """
{
  "type": "record",
  "name": "User",
  "fields": [
    {"name": "profile", "type": {"type": "record", "name": "Profile", "fields": [
      {"name": "age", "type": "int"}
    ]}},
    {"name": "profile_copy", "type": "Profile"},
    {"name": "tags", "type": {"type": "array", "items": "string"}},
    {"name": "attributes", "type": {"type": "map", "values": "long"}},
    {"name": "status", "type": {"type": "enum", "name": "Status", "symbols": ["OPEN", "CLOSED"]}},
    {"name": "variant", "type": ["null", "int", "string"]}
  ]
}
""".strip()
        + "\n",
    )

    snapshot = inspect_file(path)

    assert snapshot.source_format == "avro"
    assert snapshot.field_map["profile.age"].type_name == "integer"
    assert snapshot.field_map["profile_copy.age"].type_name == "integer"
    assert snapshot.field_map["tags"].type_name == "array"
    assert snapshot.field_map["tags[]"].type_name == "string"
    assert snapshot.field_map["attributes.value"].type_name == "integer"
    assert snapshot.field_map["status"].sample_values == ["OPEN", "CLOSED"]
    assert snapshot.field_map["variant"].type_name == "mixed"
    assert snapshot.field_map["variant"].nullable is True


def test_proto_nested_messages_enums_maps_and_self_reference_are_flattened(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "schema.proto",
        """
syntax = "proto3";

message Node {
  Node child = 1;
}

message User {
  enum Role {
    ROLE_UNSPECIFIED = 0;
    ADMIN = 1;
  }

  message Address {
    string city = 1;
  }

  Role role = 1;
  map<string, int64> scores = 2;
  repeated Address addresses = 3;
  optional string nickname = 4;
}

message Wrapper {
  User user = 1;
}
""".strip()
        + "\n",
    )

    snapshot = inspect_file(path)

    assert snapshot.source_format == "protobuf"
    assert snapshot.field_map["Node.child"].type_name == "object"
    assert "Node.child.child" not in snapshot.field_map
    assert snapshot.field_map["User.role"].sample_values == ["ROLE_UNSPECIFIED", "ADMIN"]
    assert snapshot.field_map["User.scores.value"].type_name == "integer"
    assert snapshot.field_map["User.addresses"].type_name == "array"
    assert snapshot.field_map["User.addresses[].city"].type_name == "string"
    assert snapshot.field_map["Wrapper.user.nickname"].nullable is True
