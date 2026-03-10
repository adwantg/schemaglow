from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pyarrow.types as pat

from .models import FieldSchema, SchemaSnapshot
from .schema_sources import (
    infer_avro_schema,
    infer_openapi_schema,
    infer_proto_schema,
    is_openapi_document,
)

INTEGER_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?(?:\d+\.\d+|\d+\.\d*|\.\d+)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[tT ][0-2]\d:[0-5]\d"
    r"(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-][0-2]\d:[0-5]\d)?$"
)


@dataclass
class NodeAccumulator:
    observed_count: int = 0
    null_count: int = 0
    kinds: set[str] = field(default_factory=set)
    sample_values: list[str] = field(default_factory=list)
    children: dict[str, NodeAccumulator] = field(default_factory=dict)
    item: NodeAccumulator | None = None
    order: list[str] = field(default_factory=list)

    @property
    def non_null_count(self) -> int:
        return self.observed_count - self.null_count


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        if is_openapi_document(path):
            return "openapi"
        return "json"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".avsc":
        return "avro"
    if suffix == ".proto":
        return "protobuf"
    if suffix in {".yaml", ".yml"} and is_openapi_document(path):
        return "openapi"
    raise ValueError(f"Unsupported file format for {path}")


def infer_schema(path: Path, sample_size: int = 10_000) -> SchemaSnapshot:
    file_format = detect_format(path)
    if file_format == "csv":
        return _infer_csv(path, sample_size)
    if file_format == "json":
        return _infer_json(path, sample_size)
    if file_format == "jsonl":
        return _infer_jsonl(path, sample_size)
    if file_format == "parquet":
        return _infer_parquet(path)
    if file_format == "openapi":
        return infer_openapi_schema(path)
    if file_format == "avro":
        return infer_avro_schema(path)
    if file_format == "protobuf":
        return infer_proto_schema(path)
    raise AssertionError("unreachable")


def _infer_csv(path: Path, sample_size: int) -> SchemaSnapshot:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {path} is missing a header row")
        accumulators = {name: NodeAccumulator() for name in reader.fieldnames}
        row_count = 0
        for row in reader:
            row_count += 1
            for position, column in enumerate(reader.fieldnames):
                value = row.get(column)
                node = accumulators[column]
                node.observed_count += 1
                if value is None or value == "":
                    node.null_count += 1
                    node.kinds.add("null")
                    continue
                node.kinds.add(_infer_scalar_type(value))
                _append_sample(node.sample_values, value)
                if node.order == []:
                    node.order = [str(position)]
            if row_count >= sample_size:
                break
    fields = [
        FieldSchema(
            path=column,
            type_name=_normalize_kinds(node.kinds),
            nullable=node.null_count > 0,
            position=index,
            sample_values=node.sample_values,
        )
        for index, (column, node) in enumerate(accumulators.items())
    ]
    return SchemaSnapshot(
        source_path=str(path),
        source_format="csv",
        root_type="object",
        sample_size=row_count,
        fields=fields,
        metadata={"columns": list(reader.fieldnames), "rows_sampled": row_count},
    )


def _load_json(path: Path) -> Any:
    with path.open("rb") as handle:
        raw = handle.read()
    try:
        import orjson  # type: ignore

        return orjson.loads(raw)
    except ModuleNotFoundError:
        return json.loads(raw.decode("utf-8"))


def _infer_json(path: Path, sample_size: int) -> SchemaSnapshot:
    payload = _load_json(path)
    return _infer_structured_payload(path, "json", payload, sample_size)


def _infer_jsonl(path: Path, sample_size: int) -> SchemaSnapshot:
    rows: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
            if len(rows) >= sample_size:
                break
    return _infer_structured_payload(path, "jsonl", rows, sample_size)


def _infer_structured_payload(
    path: Path, file_format: str, payload: Any, sample_size: int
) -> SchemaSnapshot:
    root = NodeAccumulator()
    top_level = payload
    sampled = 1
    if isinstance(payload, list):
        top_level = payload[:sample_size]
        sampled = len(top_level)
    observe_value(root, top_level)
    if isinstance(top_level, list) and root.item is not None and "object" in root.item.kinds:
        fields = flatten_node(root.item, "", parent_count=max(sampled, 1))
    else:
        parent_count = 1 if not isinstance(top_level, list) else max(sampled, 1)
        fields = flatten_node(root, "", parent_count=parent_count)
    return SchemaSnapshot(
        source_path=str(path),
        source_format=file_format,
        root_type=_normalize_kinds(root.kinds),
        sample_size=sampled,
        fields=fields,
        metadata={"rows_sampled": sampled},
    )


def _infer_parquet(path: Path) -> SchemaSnapshot:
    schema = pq.read_schema(path)
    fields = _flatten_arrow_schema(schema)
    return SchemaSnapshot(
        source_path=str(path),
        source_format="parquet",
        root_type="object",
        sample_size=schema.names.__len__(),
        fields=fields,
        metadata={"columns": list(schema.names)},
    )


def observe_value(node: NodeAccumulator, value: Any) -> None:
    node.observed_count += 1
    if value is None:
        node.null_count += 1
        node.kinds.add("null")
        return

    if isinstance(value, bool):
        node.kinds.add("boolean")
        _append_sample(node.sample_values, str(value).lower())
        return
    if isinstance(value, int) and not isinstance(value, bool):
        node.kinds.add("integer")
        _append_sample(node.sample_values, str(value))
        return
    if isinstance(value, float):
        node.kinds.add("number")
        _append_sample(node.sample_values, str(value))
        return
    if isinstance(value, str):
        node.kinds.add(_infer_scalar_type(value))
        _append_sample(node.sample_values, value)
        return
    if isinstance(value, dict):
        node.kinds.add("object")
        for key, child_value in value.items():
            if key not in node.children:
                node.children[key] = NodeAccumulator()
                node.order.append(key)
            observe_value(node.children[key], child_value)
        return
    if isinstance(value, list):
        node.kinds.add("array")
        if node.item is None:
            node.item = NodeAccumulator()
        for item in value:
            observe_value(node.item, item)
        return

    node.kinds.add("string")
    _append_sample(node.sample_values, str(value))


def flatten_node(node: NodeAccumulator, path: str, parent_count: int) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    non_null_kinds = node.kinds - {"null"}
    effective_type = _normalize_kinds(node.kinds)
    if path:
        nullable = node.null_count > 0 or node.observed_count < parent_count
        fields.append(
            FieldSchema(
                path=path,
                type_name=effective_type,
                nullable=nullable,
                sample_values=node.sample_values,
            )
        )

    if "object" in non_null_kinds:
        for index, key in enumerate(node.order):
            child = node.children[key]
            child_path = key if not path else f"{path}.{key}"
            child_fields = flatten_node(child, child_path, max(node.non_null_count, 1))
            if child_fields:
                child_fields[0].position = index
            fields.extend(child_fields)

    if "array" in non_null_kinds and node.item is not None:
        item_path = f"{path}[]" if path else "[]"
        fields.extend(flatten_node(node.item, item_path, max(node.item.observed_count, 1)))
    return fields


def _flatten_arrow_schema(schema: Any) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    for index, schema_field in enumerate(schema):
        fields.extend(_flatten_arrow_field(schema_field, schema_field.name, position=index))
    return fields


def _flatten_arrow_field(field: Any, path: str, position: int | None = None) -> list[FieldSchema]:
    fields = [
        FieldSchema(
            path=path,
            type_name=_arrow_type_name(field.type),
            nullable=field.nullable,
            position=position,
        )
    ]
    if pat.is_struct(field.type):
        for index, child in enumerate(field.type):
            fields.extend(_flatten_arrow_field(child, f"{path}.{child.name}", position=index))
    elif pat.is_list(field.type) or pat.is_large_list(field.type):
        item_field = field.type.value_field
        fields.extend(_flatten_arrow_field(item_field, f"{path}[]"))
    return fields


def _arrow_type_name(arrow_type: Any) -> str:
    if pat.is_boolean(arrow_type):
        return "boolean"
    if pat.is_integer(arrow_type):
        return "integer"
    if pat.is_floating(arrow_type) or pat.is_decimal(arrow_type):
        return "number"
    if pat.is_date(arrow_type):
        return "date"
    if pat.is_timestamp(arrow_type) or pat.is_time(arrow_type):
        return "datetime"
    if pat.is_string(arrow_type) or pat.is_large_string(arrow_type):
        return "string"
    if pat.is_binary(arrow_type) or pat.is_large_binary(arrow_type):
        return "binary"
    if pat.is_struct(arrow_type):
        return "object"
    if pat.is_list(arrow_type) or pat.is_large_list(arrow_type):
        return "array"
    return "string"


def _infer_scalar_type(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered in {"true", "false"}:
        return "boolean"
    if INTEGER_RE.match(normalized):
        return "integer"
    if FLOAT_RE.match(normalized):
        return "number"
    if DATE_RE.match(normalized):
        return "date"
    if DATETIME_RE.match(normalized):
        return "datetime"
    return "string"


def _normalize_kinds(kinds: Iterable[str]) -> str:
    non_null = {kind for kind in kinds if kind != "null"}
    if not non_null:
        return "null"
    if len(non_null) == 1:
        return next(iter(non_null))
    if non_null <= {"integer", "number"}:
        return "number"
    return "mixed"


def _append_sample(samples: list[str], value: str, limit: int = 3) -> None:
    if value not in samples and len(samples) < limit:
        samples.append(value)


__author__ = "gadwant"
