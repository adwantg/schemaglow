from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BREAKING = "BREAKING"


class FieldSchema(BaseModel):
    path: str
    type_name: str
    nullable: bool = False
    format_hint: str | None = None
    position: int | None = None
    sample_values: list[str] = Field(default_factory=list)


class SchemaSnapshot(BaseModel):
    source_path: str | None = None
    source_format: str
    root_type: str
    sample_size: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fields: list[FieldSchema]
    metadata: dict[str, str | int | bool | list[str]] = Field(default_factory=dict)

    @property
    def field_map(self) -> dict[str, FieldSchema]:
        return {field.path: field for field in self.fields}


class DiffEvent(BaseModel):
    severity: Severity
    code: str
    path: str
    summary: str
    old: FieldSchema | None = None
    new: FieldSchema | None = None


class ComparisonReport(BaseModel):
    old_snapshot: SchemaSnapshot
    new_snapshot: SchemaSnapshot
    events: list[DiffEvent]
    ignored_fields: list[str] = Field(default_factory=list)

    @property
    def overall(self) -> Severity:
        if any(event.severity == Severity.BREAKING for event in self.events):
            return Severity.BREAKING
        if any(event.severity == Severity.WARNING for event in self.events):
            return Severity.WARNING
        return Severity.SAFE

    @property
    def counts(self) -> dict[str, int]:
        counts = {severity.value: 0 for severity in Severity}
        for event in self.events:
            counts[event.severity.value] += 1
        return counts


class DirectoryEntry(BaseModel):
    relative_path: str
    severity: Severity
    status: str
    summary: str
    report: ComparisonReport | None = None


class DirectoryReport(BaseModel):
    old_root: str
    new_root: str
    entries: list[DirectoryEntry]

    @property
    def overall(self) -> Severity:
        if any(entry.severity == Severity.BREAKING for entry in self.entries):
            return Severity.BREAKING
        if any(entry.severity == Severity.WARNING for entry in self.entries):
            return Severity.WARNING
        return Severity.SAFE

    @property
    def counts(self) -> dict[str, int]:
        counts = {severity.value: 0 for severity in Severity}
        for entry in self.entries:
            counts[entry.severity.value] += 1
        return counts


class BaselineEntry(BaseModel):
    relative_path: str
    snapshot_path: str
    source_format: str


class BaselineManifest(BaseModel):
    source_root: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sample_size: int
    entries: list[BaselineEntry]


class CompareOptions(BaseModel):
    sample_size: int = 10_000
    ignore_order: bool = False
    ignore_fields: str | None = None
    strict: bool = False
    rename_heuristics: bool = False


__author__ = "gadwant"
