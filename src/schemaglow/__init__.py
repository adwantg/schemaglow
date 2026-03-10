"""SchemaGlow package."""

from .service import (
    capture_baseline,
    check_baseline,
    compare_files,
    compare_snapshots,
    inspect_file,
    scan_directories,
    snapshot_file,
)

__all__ = [
    "capture_baseline",
    "check_baseline",
    "compare_files",
    "compare_snapshots",
    "inspect_file",
    "scan_directories",
    "snapshot_file",
]

__author__ = "gadwant"
__version__ = "1.0.0"
