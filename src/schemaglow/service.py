from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from .diffing import compare_schema_snapshots
from .infer import infer_schema
from .models import (
    BaselineEntry,
    BaselineManifest,
    CompareOptions,
    ComparisonReport,
    DirectoryEntry,
    DirectoryReport,
    SchemaSnapshot,
    Severity,
)

SUPPORTED_SCAN_SUFFIXES = {
    ".avsc",
    ".csv",
    ".json",
    ".jsonl",
    ".parquet",
    ".proto",
    ".yaml",
    ".yml",
}


def inspect_file(path: str | Path, sample_size: int = 10_000) -> SchemaSnapshot:
    return infer_schema(Path(path), sample_size=sample_size)


def snapshot_file(path: str | Path, sample_size: int = 10_000) -> SchemaSnapshot:
    return inspect_file(path, sample_size=sample_size)


def compare_files(
    old_path: str | Path, new_path: str | Path, options: CompareOptions | None = None
) -> ComparisonReport:
    compare_options = options or CompareOptions()
    old_snapshot = infer_schema(Path(old_path), sample_size=compare_options.sample_size)
    new_snapshot = infer_schema(Path(new_path), sample_size=compare_options.sample_size)
    return compare_schema_snapshots(old_snapshot, new_snapshot, compare_options)


def compare_snapshots(
    old_snapshot: SchemaSnapshot,
    new_snapshot: SchemaSnapshot,
    options: CompareOptions | None = None,
) -> ComparisonReport:
    return compare_schema_snapshots(old_snapshot, new_snapshot, options or CompareOptions())


def load_snapshot(path: str | Path) -> SchemaSnapshot:
    snapshot_path = Path(path)
    return SchemaSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))


def save_snapshot(snapshot: SchemaSnapshot, path: str | Path) -> None:
    Path(path).write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


def scan_directories(
    old_root: str | Path,
    new_root: str | Path,
    options: CompareOptions | None = None,
    pattern: str = "*",
) -> DirectoryReport:
    compare_options = options or CompareOptions()
    old_dir = Path(old_root)
    new_dir = Path(new_root)
    old_files = _collect_supported_files(old_dir, pattern=pattern)
    new_files = _collect_supported_files(new_dir, pattern=pattern)
    entries: list[DirectoryEntry] = []

    for relative_path in sorted(old_files.keys() | new_files.keys()):
        old_path = old_files.get(relative_path)
        new_path = new_files.get(relative_path)
        if old_path is None and new_path is not None:
            entries.append(
                DirectoryEntry(
                    relative_path=relative_path,
                    severity=Severity.WARNING,
                    status="added_file",
                    summary=f"new file added: {relative_path}",
                )
            )
            continue
        if old_path is not None and new_path is None:
            entries.append(
                DirectoryEntry(
                    relative_path=relative_path,
                    severity=Severity.BREAKING,
                    status="removed_file",
                    summary=f"file removed: {relative_path}",
                )
            )
            continue
        assert old_path is not None and new_path is not None
        report = compare_files(old_path, new_path, options=compare_options)
        entries.append(
            DirectoryEntry(
                relative_path=relative_path,
                severity=report.overall,
                status="compared",
                summary=f"{relative_path}: {report.overall.value}",
                report=report,
            )
        )

    return DirectoryReport(old_root=str(old_dir), new_root=str(new_dir), entries=entries)


def capture_baseline(
    source_root: str | Path,
    baseline_root: str | Path,
    sample_size: int = 10_000,
    pattern: str = "*",
) -> BaselineManifest:
    source_dir = Path(source_root)
    baseline_dir = Path(baseline_root)
    snapshots_dir = baseline_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    entries: list[BaselineEntry] = []
    for relative_path, file_path in sorted(
        _collect_supported_files(source_dir, pattern=pattern).items()
    ):
        snapshot = infer_schema(file_path, sample_size=sample_size)
        snapshot_path = snapshots_dir / f"{relative_path}.schema.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        save_snapshot(snapshot, snapshot_path)
        entries.append(
            BaselineEntry(
                relative_path=relative_path,
                snapshot_path=str(snapshot_path.relative_to(baseline_dir).as_posix()),
                source_format=snapshot.source_format,
            )
        )

    manifest = BaselineManifest(
        source_root=str(source_dir), sample_size=sample_size, entries=entries
    )
    (baseline_dir / "schemaglow-baseline.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return manifest


def load_baseline_manifest(path: str | Path) -> BaselineManifest:
    manifest_root = Path(path)
    manifest_path = (
        manifest_root / "schemaglow-baseline.json" if manifest_root.is_dir() else manifest_root
    )
    return BaselineManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def check_baseline(
    baseline_root: str | Path,
    candidate_root: str | Path,
    options: CompareOptions | None = None,
    pattern: str = "*",
) -> DirectoryReport:
    compare_options = options or CompareOptions()
    baseline_dir = Path(baseline_root)
    candidate_dir = Path(candidate_root)
    manifest = load_baseline_manifest(baseline_dir)
    candidate_files = _collect_supported_files(candidate_dir, pattern=pattern)
    manifest_entries = {
        entry.relative_path: entry
        for entry in manifest.entries
        if _matches_pattern(entry.relative_path, pattern)
    }
    entries: list[DirectoryEntry] = []

    for relative_path in sorted(manifest_entries):
        entry = manifest_entries[relative_path]
        candidate_path = candidate_files.pop(relative_path, None)
        snapshot_path = baseline_dir / entry.snapshot_path
        if candidate_path is None:
            entries.append(
                DirectoryEntry(
                    relative_path=relative_path,
                    severity=Severity.BREAKING,
                    status="missing_candidate",
                    summary=f"baseline file missing from candidate tree: {relative_path}",
                )
            )
            continue
        baseline_snapshot = load_snapshot(snapshot_path)
        candidate_snapshot = infer_schema(candidate_path, sample_size=compare_options.sample_size)
        report = compare_snapshots(baseline_snapshot, candidate_snapshot, options=compare_options)
        entries.append(
            DirectoryEntry(
                relative_path=relative_path,
                severity=report.overall,
                status="baseline_check",
                summary=f"{relative_path}: {report.overall.value}",
                report=report,
            )
        )

    for relative_path in sorted(candidate_files):
        entries.append(
            DirectoryEntry(
                relative_path=relative_path,
                severity=Severity.WARNING,
                status="unexpected_candidate",
                summary=f"candidate file not present in baseline: {relative_path}",
            )
        )

    return DirectoryReport(
        old_root=str(baseline_dir),
        new_root=str(candidate_dir),
        entries=entries,
    )


def _collect_supported_files(root: Path, pattern: str) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SCAN_SUFFIXES:
            continue
        relative_path = path.relative_to(root).as_posix()
        if not _matches_pattern(relative_path, pattern):
            continue
        files[relative_path] = path
    return files


def _matches_pattern(relative_path: str, pattern: str) -> bool:
    return (
        pattern == "*" or fnmatch(relative_path, pattern) or fnmatch(relative_path, f"**/{pattern}")
    )


__author__ = "gadwant"
