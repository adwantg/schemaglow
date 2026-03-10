from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import (
    CompareOptions,
    ComparisonReport,
    DiffEvent,
    FieldSchema,
    SchemaSnapshot,
    Severity,
)


def compare_schema_snapshots(
    old_snapshot: SchemaSnapshot, new_snapshot: SchemaSnapshot, options: CompareOptions
) -> ComparisonReport:
    old_fields, ignored = _filter_fields(old_snapshot.fields, options.ignore_fields)
    new_fields, ignored_new = _filter_fields(new_snapshot.fields, options.ignore_fields)
    ignored.extend(ignored_new)
    old_map = {field.path: field for field in old_fields}
    new_map = {field.path: field for field in new_fields}
    old_paths = set(old_map)
    new_paths = set(new_map)
    common_paths = old_paths & new_paths
    removed = set(old_paths - new_paths)
    added = set(new_paths - old_paths)
    events: list[DiffEvent] = []

    removed = _collapse_nested_paths(removed)
    added = _collapse_nested_paths(added)

    if options.rename_heuristics:
        rename_events, removed, added = _detect_possible_renames(removed, added, old_map, new_map)
        events.extend(rename_events)

    for path in sorted(common_paths):
        old_field = old_map[path]
        new_field = new_map[path]
        events.extend(_compare_common_field(path, old_field, new_field, options.strict))

    for path in sorted(removed):
        events.append(
            DiffEvent(
                severity=Severity.BREAKING,
                code="field_removed",
                path=path,
                summary=f"removed field: {path}",
                old=old_map[path],
            )
        )

    for path in sorted(added):
        new_field = new_map[path]
        severity, code, summary = _classify_added_field(path, new_field)
        events.append(
            DiffEvent(
                severity=severity,
                code=code,
                path=path,
                summary=summary,
                new=new_field,
            )
        )

    if not options.ignore_order:
        order_event = _detect_order_change(old_fields, new_fields)
        if order_event is not None:
            events.append(order_event)

    if not events:
        events.append(
            DiffEvent(
                severity=Severity.SAFE,
                code="no_change",
                path="*",
                summary="no schema changes detected",
            )
        )

    return ComparisonReport(
        old_snapshot=old_snapshot.model_copy(update={"fields": old_fields}),
        new_snapshot=new_snapshot.model_copy(update={"fields": new_fields}),
        events=sorted(events, key=_event_sort_key),
        ignored_fields=sorted(set(ignored)),
    )


def _filter_fields(
    fields: list[FieldSchema], pattern: str | None
) -> tuple[list[FieldSchema], list[str]]:
    if pattern is None:
        return fields, []
    regex = re.compile(pattern)
    kept: list[FieldSchema] = []
    ignored: list[str] = []
    for field in fields:
        if regex.search(field.path) or _has_ignored_ancestor(field.path, ignored):
            ignored.append(field.path)
            continue
        kept.append(field)
    return kept, ignored


def _compare_common_field(
    path: str, old_field: FieldSchema, new_field: FieldSchema, strict: bool
) -> list[DiffEvent]:
    events: list[DiffEvent] = []
    if old_field.type_name != new_field.type_name:
        severity, code = _classify_type_change(old_field.type_name, new_field.type_name, strict)
        events.append(
            DiffEvent(
                severity=severity,
                code=code,
                path=path,
                summary=f"type changed: {path} ({old_field.type_name} -> {new_field.type_name})",
                old=old_field,
                new=new_field,
            )
        )
    if old_field.nullable and not new_field.nullable:
        events.append(
            DiffEvent(
                severity=Severity.BREAKING,
                code="nullable_to_required",
                path=path,
                summary=f"nullability changed: {path} (nullable -> required)",
                old=old_field,
                new=new_field,
            )
        )
    elif not old_field.nullable and new_field.nullable:
        events.append(
            DiffEvent(
                severity=Severity.WARNING,
                code="required_to_nullable",
                path=path,
                summary=f"nullability changed: {path} (required -> nullable)",
                old=old_field,
                new=new_field,
            )
        )
    shape_change = _detect_sample_shape_change(path, old_field, new_field)
    if shape_change is not None:
        events.append(shape_change)
    return events


def _classify_type_change(old_type: str, new_type: str, strict: bool) -> tuple[Severity, str]:
    if old_type == "integer" and new_type == "number":
        return (
            (Severity.WARNING, "numeric_widening")
            if strict
            else (Severity.SAFE, "numeric_widening")
        )
    if old_type in {"date", "datetime"} and new_type == "string":
        return Severity.WARNING, "shape_widening"
    if old_type == "mixed" or new_type == "mixed":
        return Severity.WARNING, "ambiguous_type_change"
    if old_type == new_type:
        return Severity.SAFE, "no_change"
    if old_type == "null":
        return Severity.SAFE, "materialized_type"
    return Severity.BREAKING, "incompatible_type_change"


def _classify_added_field(path: str, field: FieldSchema) -> tuple[Severity, str, str]:
    nested = "." in path or "[]" in path
    if nested:
        return Severity.WARNING, "nested_shape_expanded", f"nested object shape expanded: {path}"
    if field.nullable:
        return (
            Severity.SAFE,
            "field_added_optional",
            f"added optional field: {path} ({field.type_name})",
        )
    return (
        Severity.WARNING,
        "field_added_required",
        f"added required field: {path} ({field.type_name})",
    )


def _detect_possible_renames(
    removed: set[str],
    added: set[str],
    old_map: dict[str, FieldSchema],
    new_map: dict[str, FieldSchema],
) -> tuple[list[DiffEvent], set[str], set[str]]:
    events: list[DiffEvent] = []
    matched_removed: set[str] = set()
    matched_added: set[str] = set()
    for removed_path in sorted(removed):
        old_parent = removed_path.rpartition(".")[0]
        best_match: str | None = None
        best_score = 0.0
        for added_path in sorted(added):
            if added_path in matched_added:
                continue
            if added_path.rpartition(".")[0] != old_parent:
                continue
            if old_map[removed_path].type_name != new_map[added_path].type_name:
                continue
            if old_map[removed_path].nullable != new_map[added_path].nullable:
                continue
            score = SequenceMatcher(
                None, removed_path.split(".")[-1], added_path.split(".")[-1]
            ).ratio()
            sample_overlap = _sample_overlap_score(
                old_map[removed_path].sample_values,
                new_map[added_path].sample_values,
            )
            score = (score * 0.8) + (sample_overlap * 0.2)
            if score > best_score:
                best_match = added_path
                best_score = score
        if best_match is not None and best_score >= 0.72:
            matched_removed.add(removed_path)
            matched_added.add(best_match)
            events.append(
                DiffEvent(
                    severity=Severity.WARNING,
                    code="possible_rename",
                    path=removed_path,
                    summary=f"possible rename: {removed_path} -> {best_match}",
                    old=old_map[removed_path],
                    new=new_map[best_match],
                )
            )
    return events, removed - matched_removed, added - matched_added


def _detect_order_change(
    old_fields: list[FieldSchema], new_fields: list[FieldSchema]
) -> DiffEvent | None:
    old_order = [
        field.path for field in old_fields if "." not in field.path and "[]" not in field.path
    ]
    new_order = [
        field.path for field in new_fields if "." not in field.path and "[]" not in field.path
    ]
    if old_order and old_order != new_order and set(old_order) == set(new_order):
        return DiffEvent(
            severity=Severity.SAFE,
            code="column_order_changed",
            path="*",
            summary="column order changed only",
        )
    return None


def _event_sort_key(event: DiffEvent) -> tuple[int, str, str]:
    rank = {
        Severity.BREAKING: 0,
        Severity.WARNING: 1,
        Severity.SAFE: 2,
    }[event.severity]
    return rank, event.path, event.code


def _collapse_nested_paths(paths: set[str]) -> set[str]:
    collapsed: set[str] = set()
    for path in sorted(paths, key=lambda item: (item.count("."), item.count("[]"), item)):
        if any(_is_descendant(path, ancestor) for ancestor in collapsed):
            continue
        collapsed.add(path)
    return collapsed


def _has_ignored_ancestor(path: str, ignored: list[str]) -> bool:
    return any(_is_descendant(path, ancestor) for ancestor in ignored)


def _is_descendant(path: str, ancestor: str) -> bool:
    return path.startswith(f"{ancestor}.") or path.startswith(f"{ancestor}[]")


def _detect_sample_shape_change(
    path: str, old_field: FieldSchema, new_field: FieldSchema
) -> DiffEvent | None:
    if old_field.type_name != "string" or new_field.type_name != "string":
        return None
    old_shape = _sample_shape(old_field.sample_values)
    new_shape = _sample_shape(new_field.sample_values)
    if old_shape in {"unknown", "mixed"} or new_shape in {"unknown", "mixed"}:
        return None
    if old_shape == new_shape:
        return None
    return DiffEvent(
        severity=Severity.WARNING,
        code="sample_shape_changed",
        path=path,
        summary=f"sample shape changed: {path} ({old_shape} -> {new_shape})",
        old=old_field,
        new=new_field,
    )


def _sample_shape(values: list[str]) -> str:
    if not values:
        return "unknown"
    shapes = {_classify_sample_value(value) for value in values}
    if len(shapes) == 1:
        return next(iter(shapes))
    return "mixed"


def _classify_sample_value(value: str) -> str:
    stripped = value.strip()
    if re.fullmatch(r"-?\d+", stripped):
        return "integer-like"
    if re.fullmatch(r"-?(?:\d+\.\d+|\d+\.\d*|\.\d+)", stripped):
        return "number-like"
    if re.fullmatch(r"[0-9a-fA-F-]{36}", stripped):
        return "uuid-like"
    if re.fullmatch(r"[A-Z0-9_]+", stripped):
        return "enum-like"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", stripped):
        return "identifier-like"
    if " " in stripped:
        return "free-text"
    return "string-like"


def _sample_overlap_score(old_samples: list[str], new_samples: list[str]) -> float:
    if not old_samples or not new_samples:
        return 0.0
    old_set = set(old_samples)
    new_set = set(new_samples)
    return len(old_set & new_set) / max(len(old_set | new_set), 1)


__author__ = "gadwant"
