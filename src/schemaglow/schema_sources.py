from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import FieldSchema, SchemaSnapshot

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
PROTO_FIELD_RE = re.compile(r"(?:(optional|required|repeated)\s+)?([.\w]+)\s+(\w+)\s*=\s*\d+")
PROTO_MAP_RE = re.compile(
    r"(?:(optional|required|repeated)\s+)?map<\s*([^,>]+)\s*,\s*([^>]+)\s*>\s+(\w+)\s*=\s*\d+"
)


def is_openapi_document(path: Path) -> bool:
    try:
        payload = _load_structured_document(path)
    except ValueError:
        return False
    return _looks_like_openapi(payload)


def infer_openapi_schema(path: Path) -> SchemaSnapshot:
    payload = _load_structured_document(path)
    if not _looks_like_openapi(payload):
        raise ValueError(f"{path} does not look like an OpenAPI document")

    resolver = _OpenApiResolver(payload)
    fields: list[FieldSchema] = []

    components = payload.get("components", {}).get("schemas", {})
    for index, (name, schema) in enumerate(components.items()):
        component_fields = _flatten_openapi_schema(
            schema,
            name,
            resolver=resolver,
            required=True,
            ref_chain=(),
        )
        if component_fields:
            component_fields[0].position = index
        fields.extend(component_fields)

    paths = payload.get("paths", {})
    for path_name, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        safe_path = _safe_segment(path_name)
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            prefix = f"paths.{safe_path}.{method.lower()}"
            request_body = operation.get("requestBody", {})
            if isinstance(request_body, dict):
                content = request_body.get("content", {})
                fields.extend(_flatten_openapi_content(content, f"{prefix}.request", resolver))
            responses = operation.get("responses", {})
            if isinstance(responses, dict):
                for status_code, response in responses.items():
                    if not isinstance(response, dict):
                        continue
                    content = response.get("content", {})
                    response_prefix = f"{prefix}.responses.{_safe_segment(str(status_code))}"
                    fields.extend(_flatten_openapi_content(content, response_prefix, resolver))

    return SchemaSnapshot(
        source_path=str(path),
        source_format="openapi",
        root_type="object",
        sample_size=len(fields),
        fields=fields,
        metadata={"schemas": list(components), "paths": len(paths)},
    )


def infer_avro_schema(path: Path) -> SchemaSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    named_types: dict[str, Any] = {}
    _register_avro_types(payload, named_types)
    fields = _flatten_avro_schema(payload, "", named_types=named_types, required=True)
    return SchemaSnapshot(
        source_path=str(path),
        source_format="avro",
        root_type="object",
        sample_size=len(fields),
        fields=fields,
        metadata={"named_types": sorted(named_types)},
    )


def infer_proto_schema(path: Path) -> SchemaSnapshot:
    text = path.read_text(encoding="utf-8")
    messages = _parse_proto(text)
    message_lookup = {message.name: message for message in messages}
    enum_lookup = _collect_proto_enums(messages)
    fields: list[FieldSchema] = []
    for index, message in enumerate(messages):
        message_fields = _flatten_proto_message(
            message,
            path=message.name,
            message_lookup=message_lookup,
            enum_lookup=enum_lookup,
            stack=(),
        )
        if message_fields:
            message_fields[0].position = index
        fields.extend(message_fields)
    return SchemaSnapshot(
        source_path=str(path),
        source_format="protobuf",
        root_type="object",
        sample_size=len(messages),
        fields=fields,
        metadata={"messages": [message.name for message in messages]},
    )


def _load_structured_document(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise ValueError("PyYAML is required for YAML OpenAPI documents") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported structured document: {path}")


def _looks_like_openapi(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return ("openapi" in payload or "swagger" in payload) and (
        "paths" in payload or payload.get("components", {}).get("schemas")
    )


def _flatten_openapi_content(
    content: Any, prefix: str, resolver: _OpenApiResolver
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if not isinstance(content, dict):
        return fields
    for media_type, media_payload in content.items():
        if not isinstance(media_payload, dict) or "schema" not in media_payload:
            continue
        media_prefix = f"{prefix}.{_safe_segment(media_type)}"
        fields.extend(
            _flatten_openapi_schema(
                media_payload["schema"],
                media_prefix,
                resolver=resolver,
                required=True,
                ref_chain=(),
            )
        )
    return fields


def _flatten_openapi_schema(
    schema: Any,
    path: str,
    resolver: _OpenApiResolver,
    required: bool,
    ref_chain: tuple[str, ...],
) -> list[FieldSchema]:
    if not isinstance(schema, dict):
        return [FieldSchema(path=path, type_name="string", nullable=not required)]

    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in ref_chain:
            return [FieldSchema(path=path, type_name="object", nullable=not required)]
        return _flatten_openapi_schema(
            resolver.resolve_ref(ref),
            path,
            resolver=resolver,
            required=required,
            ref_chain=(*ref_chain, ref),
        )

    if "allOf" in schema:
        merged = _merge_openapi_all_of(schema["allOf"], resolver)
        schema = {**schema, **merged}

    nullable = bool(schema.get("nullable")) or not required
    sample_values = [str(value) for value in schema.get("enum", [])[:3]]
    type_name = _openapi_type_name(schema)
    format_hint = schema.get("format")
    fields = [
        FieldSchema(
            path=path,
            type_name=type_name,
            nullable=nullable,
            format_hint=format_hint,
            sample_values=sample_values,
        )
    ]

    if type_name == "object":
        properties = schema.get("properties", {})
        required_children = set(schema.get("required", []))
        if isinstance(properties, dict):
            for index, (child_name, child_schema) in enumerate(properties.items()):
                child_fields = _flatten_openapi_schema(
                    child_schema,
                    f"{path}.{child_name}",
                    resolver=resolver,
                    required=child_name in required_children,
                    ref_chain=ref_chain,
                )
                if child_fields:
                    child_fields[0].position = index
                fields.extend(child_fields)
    elif type_name == "array" and "items" in schema:
        fields.extend(
            _flatten_openapi_schema(
                schema["items"],
                f"{path}[]",
                resolver=resolver,
                required=True,
                ref_chain=ref_chain,
            )
        )
    return fields


def _merge_openapi_all_of(parts: Any, resolver: _OpenApiResolver) -> dict[str, Any]:
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    if not isinstance(parts, list):
        return merged
    for part in parts:
        if not isinstance(part, dict):
            continue
        if "$ref" in part:
            part = resolver.resolve_ref(part["$ref"])
        if "properties" in part and isinstance(part["properties"], dict):
            merged["properties"].update(part["properties"])
        if "required" in part and isinstance(part["required"], list):
            merged["required"].extend(part["required"])
    merged["required"] = sorted(set(merged["required"]))
    return merged


def _openapi_type_name(schema: dict[str, Any]) -> str:
    if "oneOf" in schema or "anyOf" in schema:
        return "mixed"
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = {item for item in schema_type if item != "null"}
        if len(non_null) == 1:
            schema_type = next(iter(non_null))
        else:
            return "mixed"
    mapping = {
        "boolean": "boolean",
        "integer": "integer",
        "number": "number",
        "string": "string",
        "array": "array",
        "object": "object",
    }
    if schema_type in mapping:
        return mapping[schema_type]
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return "string"


def _register_avro_types(schema: Any, named_types: dict[str, Any]) -> None:
    if isinstance(schema, dict):
        schema_type = schema.get("type")
        name = schema.get("name")
        if isinstance(name, str) and schema_type in {"record", "enum", "fixed"}:
            named_types[name] = schema
        if schema_type == "record":
            for field in schema.get("fields", []):
                _register_avro_types(field.get("type"), named_types)
        elif schema_type == "array":
            _register_avro_types(schema.get("items"), named_types)
        elif schema_type == "map":
            _register_avro_types(schema.get("values"), named_types)
    elif isinstance(schema, list):
        for part in schema:
            _register_avro_types(part, named_types)


def _flatten_avro_schema(
    schema: Any, path: str, named_types: dict[str, Any], required: bool
) -> list[FieldSchema]:
    resolved = _resolve_avro_type(schema, named_types)
    nullable = not required
    if isinstance(resolved, list):
        non_null = [part for part in resolved if part != "null"]
        nullable = True
        if len(non_null) == 1:
            return _flatten_avro_schema(non_null[0], path, named_types=named_types, required=False)
        return [FieldSchema(path=path, type_name="mixed", nullable=True)]

    if isinstance(resolved, str):
        return [FieldSchema(path=path, type_name=_avro_primitive_type(resolved), nullable=nullable)]

    if not isinstance(resolved, dict):
        return [FieldSchema(path=path, type_name="string", nullable=nullable)]

    schema_type = resolved.get("type")
    if schema_type == "record":
        fields: list[FieldSchema] = []
        if path:
            fields.append(FieldSchema(path=path, type_name="object", nullable=nullable))
        for index, avro_field in enumerate(resolved.get("fields", [])):
            child_path = avro_field["name"] if not path else f"{path}.{avro_field['name']}"
            child_fields = _flatten_avro_schema(
                avro_field.get("type"),
                child_path,
                named_types=named_types,
                required=True,
            )
            if child_fields:
                child_fields[0].position = index
            fields.extend(child_fields)
        return fields

    if schema_type == "array":
        fields = [FieldSchema(path=path, type_name="array", nullable=nullable)]
        fields.extend(
            _flatten_avro_schema(
                resolved.get("items"), f"{path}[]", named_types=named_types, required=True
            )
        )
        return fields

    if schema_type == "map":
        fields = [FieldSchema(path=path, type_name="object", nullable=nullable)]
        fields.extend(
            _flatten_avro_schema(
                resolved.get("values"),
                f"{path}.value",
                named_types=named_types,
                required=True,
            )
        )
        return fields

    if schema_type == "enum":
        samples = [str(value) for value in resolved.get("symbols", [])[:3]]
        return [
            FieldSchema(
                path=path,
                type_name="string",
                nullable=nullable,
                format_hint="enum",
                sample_values=samples,
            )
        ]

    return [
        FieldSchema(
            path=path,
            type_name=_avro_primitive_type(str(schema_type)),
            nullable=nullable,
        )
    ]


def _resolve_avro_type(schema: Any, named_types: dict[str, Any]) -> Any:
    if isinstance(schema, str) and schema in named_types:
        return named_types[schema]
    if isinstance(schema, dict):
        schema_type = schema.get("type")
        if isinstance(schema_type, str) and schema_type in named_types:
            return named_types[schema_type]
    return schema


def _avro_primitive_type(schema_type: str) -> str:
    mapping = {
        "null": "null",
        "boolean": "boolean",
        "int": "integer",
        "long": "integer",
        "float": "number",
        "double": "number",
        "bytes": "binary",
        "string": "string",
        "record": "object",
        "array": "array",
        "map": "object",
        "fixed": "binary",
        "enum": "string",
    }
    return mapping.get(schema_type, "string")


@dataclass
class _ProtoField:
    label: str | None
    type_name: str
    name: str


@dataclass
class _ProtoEnum:
    name: str
    values: list[str] = field(default_factory=list)


@dataclass
class _ProtoMessage:
    name: str
    fields: list[_ProtoField] = field(default_factory=list)
    messages: list[_ProtoMessage] = field(default_factory=list)
    enums: list[_ProtoEnum] = field(default_factory=list)


def _parse_proto(text: str) -> list[_ProtoMessage]:
    lines = _strip_proto_comments(text)
    messages, _ = _parse_proto_block(lines, 0)
    return messages


def _strip_proto_comments(text: str) -> list[str]:
    without_block_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = []
    for raw_line in without_block_comments.splitlines():
        line = re.sub(r"//.*", "", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def _parse_proto_block(lines: list[str], index: int) -> tuple[list[_ProtoMessage], int]:
    messages: list[_ProtoMessage] = []
    while index < len(lines):
        line = lines[index]
        if line.startswith("}"):
            return messages, index + 1
        if line.startswith("message "):
            match = re.match(r"message\s+(\w+)\s*\{", line)
            if match is None:
                index += 1
                continue
            message_name = match.group(1)
            message, index = _parse_proto_message(lines, index + 1, message_name)
            messages.append(message)
            continue
        index += 1
    return messages, index


def _parse_proto_message(lines: list[str], index: int, name: str) -> tuple[_ProtoMessage, int]:
    message = _ProtoMessage(name=name)
    while index < len(lines):
        line = lines[index]
        if line.startswith("}"):
            return message, index + 1
        if line.startswith("message "):
            nested_name = re.match(r"message\s+(\w+)\s*\{", line)
            if nested_name is not None:
                nested_message, index = _parse_proto_message(lines, index + 1, nested_name.group(1))
                message.messages.append(nested_message)
                continue
        if line.startswith("enum "):
            enum_name = re.match(r"enum\s+(\w+)\s*\{", line)
            if enum_name is not None:
                proto_enum, index = _parse_proto_enum(lines, index + 1, enum_name.group(1))
                message.enums.append(proto_enum)
                continue
        map_match = PROTO_MAP_RE.match(line)
        if map_match is not None:
            label, _, value_type, field_name = map_match.groups()
            message.fields.append(
                _ProtoField(
                    label=label or "repeated", type_name=f"map:{value_type}", name=field_name
                )
            )
            index += 1
            continue
        field_match = PROTO_FIELD_RE.match(line)
        if field_match is not None:
            label, field_type, field_name = field_match.groups()
            message.fields.append(_ProtoField(label=label, type_name=field_type, name=field_name))
        index += 1
    return message, index


def _parse_proto_enum(lines: list[str], index: int, name: str) -> tuple[_ProtoEnum, int]:
    proto_enum = _ProtoEnum(name=name)
    while index < len(lines):
        line = lines[index]
        if line.startswith("}"):
            return proto_enum, index + 1
        enum_value = re.match(r"(\w+)\s*=\s*\d+", line)
        if enum_value is not None:
            proto_enum.values.append(enum_value.group(1))
        index += 1
    return proto_enum, index


def _collect_proto_enums(messages: list[_ProtoMessage]) -> dict[str, list[str]]:
    enum_lookup: dict[str, list[str]] = {}
    for message in messages:
        for proto_enum in message.enums:
            enum_lookup[proto_enum.name] = proto_enum.values
        enum_lookup.update(_collect_proto_enums(message.messages))
    return enum_lookup


def _flatten_proto_message(
    message: _ProtoMessage,
    path: str,
    message_lookup: dict[str, _ProtoMessage],
    enum_lookup: dict[str, list[str]],
    stack: tuple[str, ...],
) -> list[FieldSchema]:
    fields = [FieldSchema(path=path, type_name="object", nullable=False)]
    nested_lookup = {
        **message_lookup,
        **{nested.name: nested for nested in message.messages},
    }
    for index, proto_field in enumerate(message.fields):
        field_path = f"{path}.{proto_field.name}"
        fields.extend(
            _flatten_proto_field(
                proto_field,
                field_path=field_path,
                position=index,
                message_lookup=nested_lookup,
                enum_lookup=enum_lookup,
                stack=(*stack, path),
            )
        )
    for nested in message.messages:
        message_lookup[nested.name] = nested
    return fields


def _flatten_proto_field(
    proto_field: _ProtoField,
    field_path: str,
    position: int,
    message_lookup: dict[str, _ProtoMessage],
    enum_lookup: dict[str, list[str]],
    stack: tuple[str, ...],
) -> list[FieldSchema]:
    nullable = proto_field.label != "required"
    field_type = proto_field.type_name

    if field_type.startswith("map:"):
        value_type = field_type.split(":", maxsplit=1)[1]
        fields = [
            FieldSchema(path=field_path, type_name="object", nullable=True, position=position)
        ]
        fields.extend(
            _flatten_proto_scalar_or_message(
                value_type,
                f"{field_path}.value",
                nullable=False,
                position=None,
                message_lookup=message_lookup,
                enum_lookup=enum_lookup,
                stack=stack,
            )
        )
        return fields

    if proto_field.label == "repeated":
        fields = [FieldSchema(path=field_path, type_name="array", nullable=True, position=position)]
        fields.extend(
            _flatten_proto_scalar_or_message(
                field_type,
                f"{field_path}[]",
                nullable=False,
                position=None,
                message_lookup=message_lookup,
                enum_lookup=enum_lookup,
                stack=stack,
            )
        )
        return fields

    return _flatten_proto_scalar_or_message(
        field_type,
        field_path,
        nullable=nullable,
        position=position,
        message_lookup=message_lookup,
        enum_lookup=enum_lookup,
        stack=stack,
    )


def _flatten_proto_scalar_or_message(
    field_type: str,
    field_path: str,
    nullable: bool,
    position: int | None,
    message_lookup: dict[str, _ProtoMessage],
    enum_lookup: dict[str, list[str]],
    stack: tuple[str, ...],
) -> list[FieldSchema]:
    normalized = _proto_scalar_type(field_type)
    if normalized is not None:
        return [
            FieldSchema(
                path=field_path,
                type_name=normalized,
                nullable=nullable,
                position=position,
            )
        ]
    if field_type in enum_lookup:
        return [
            FieldSchema(
                path=field_path,
                type_name="string",
                nullable=nullable,
                position=position,
                format_hint="enum",
                sample_values=enum_lookup[field_type][:3],
            )
        ]
    if field_type in message_lookup:
        message = message_lookup[field_type]
        if any(ancestor.split(".")[-1] == message.name for ancestor in stack):
            return [
                FieldSchema(
                    path=field_path,
                    type_name="object",
                    nullable=nullable,
                    position=position,
                )
            ]
        fields = [
            FieldSchema(path=field_path, type_name="object", nullable=nullable, position=position)
        ]
        for index, proto_field in enumerate(message.fields):
            child_path = f"{field_path}.{proto_field.name}"
            fields.extend(
                _flatten_proto_field(
                    proto_field,
                    field_path=child_path,
                    position=index,
                    message_lookup=message_lookup,
                    enum_lookup=enum_lookup,
                    stack=(*stack, field_path),
                )
            )
        return fields
    return [FieldSchema(path=field_path, type_name="string", nullable=nullable, position=position)]


def _proto_scalar_type(field_type: str) -> str | None:
    mapping = {
        "bool": "boolean",
        "bytes": "binary",
        "double": "number",
        "fixed32": "integer",
        "fixed64": "integer",
        "float": "number",
        "int32": "integer",
        "int64": "integer",
        "sfixed32": "integer",
        "sfixed64": "integer",
        "sint32": "integer",
        "sint64": "integer",
        "string": "string",
        "uint32": "integer",
        "uint64": "integer",
    }
    return mapping.get(field_type)


def _safe_segment(value: str) -> str:
    sanitized = value.strip("/")
    sanitized = sanitized.replace("/", ".")
    sanitized = re.sub(r"[^A-Za-z0-9_.{}-]+", "_", sanitized)
    return sanitized or "root"


class _OpenApiResolver:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def resolve_ref(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"Only local OpenAPI refs are supported: {ref}")
        current: Any = self.payload
        for segment in ref[2:].split("/"):
            current = current[segment]
        if not isinstance(current, dict):
            raise ValueError(f"OpenAPI ref {ref} did not resolve to an object")
        return current


__author__ = "gadwant"
