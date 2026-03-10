from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .models import CompareOptions
from .renderers import (
    render_baseline_manifest_text,
    render_directory_html,
    render_directory_json,
    render_directory_markdown,
    render_directory_text,
    render_html_report,
    render_json_report,
    render_markdown_report,
    render_snapshot_text,
    render_text_report,
    write_report,
)
from .service import (
    capture_baseline,
    check_baseline,
    compare_files,
    compare_snapshots,
    inspect_file,
    load_baseline_manifest,
    load_snapshot,
    save_snapshot,
    scan_directories,
    snapshot_file,
)

app = typer.Typer(help="Human-friendly schema diff for CSV, JSON, JSONL, and Parquet.")
baseline_app = typer.Typer(help="Capture and check baseline contract snapshots.")
app.add_typer(baseline_app, name="baseline")
console = Console(soft_wrap=True, force_terminal=False, color_system=None)


def _emit_report(report_content: str, report_path: Path | None) -> None:
    if report_path is None:
        console.print(report_content)
        return
    write_report(report_path, report_content)
    console.print(f"report written to {report_path}")


def _emit_comparison_output(format: str, comparison: object) -> None:
    if format == "json":
        if hasattr(comparison, "entries"):
            console.print(render_directory_json(comparison))  # type: ignore[arg-type]
        else:
            console.print(render_json_report(comparison))  # type: ignore[arg-type]
        return
    if hasattr(comparison, "entries"):
        console.print(render_directory_text(comparison))  # type: ignore[arg-type]
        return
    console.print(render_text_report(comparison))  # type: ignore[arg-type]


def _emit_comparison_report(
    report: str | None, report_path: Path | None, comparison: object
) -> None:
    if report == "markdown":
        content = (
            render_directory_markdown(comparison)  # type: ignore[arg-type]
            if hasattr(comparison, "entries")
            else render_markdown_report(comparison)  # type: ignore[arg-type]
        )
        _emit_report(content, report_path)
    elif report == "html":
        content = (
            render_directory_html(comparison)  # type: ignore[arg-type]
            if hasattr(comparison, "entries")
            else render_html_report(comparison)  # type: ignore[arg-type]
        )
        _emit_report(content, report_path)
    elif report is not None:
        raise typer.BadParameter("report must be one of: markdown, html")


@app.command()
def diff(
    old_file: Path = typer.Argument(..., help="Baseline data file path."),
    new_file: Path = typer.Argument(..., help="Candidate data file path."),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    report: str | None = typer.Option(
        None, "--report", help="Optional report format: markdown or html."
    ),
    report_path: Path | None = typer.Option(
        None, "--report-path", help="Write the generated report to a file."
    ),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
    ignore_order: bool = typer.Option(
        False, "--ignore-order", help="Suppress column order change events."
    ),
    ignore_fields: str | None = typer.Option(
        None, "--ignore-fields", help="Regex for field paths to ignore."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat numeric widening as warning instead of safe."
    ),
    rename_heuristics: bool = typer.Option(
        False, "--rename-heuristics", help="Detect likely field renames."
    ),
) -> None:
    options = CompareOptions(
        sample_size=sample,
        ignore_order=ignore_order,
        ignore_fields=ignore_fields,
        strict=strict,
        rename_heuristics=rename_heuristics,
    )
    comparison = compare_files(old_file, new_file, options=options)
    _emit_comparison_output(format, comparison)
    _emit_comparison_report(report, report_path, comparison)


@app.command()
def inspect(
    file: Path = typer.Argument(..., help="Data file to inspect."),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
) -> None:
    snapshot = inspect_file(file, sample_size=sample)
    if format == "json":
        console.print(snapshot.model_dump_json(indent=2))
    else:
        console.print(render_snapshot_text(snapshot))


@app.command()
def snapshot(
    file: Path = typer.Argument(..., help="Data file to snapshot."),
    output: Path = typer.Option(..., "-o", "--output", help="Snapshot JSON path."),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
) -> None:
    schema_snapshot = snapshot_file(file, sample_size=sample)
    save_snapshot(schema_snapshot, output)
    console.print(f"snapshot written to {output}")


@app.command()
def compare(
    old_schema: Path = typer.Argument(..., help="Baseline schema snapshot JSON."),
    new_schema: Path = typer.Argument(..., help="Candidate schema snapshot JSON."),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    ignore_order: bool = typer.Option(
        False, "--ignore-order", help="Suppress column order change events."
    ),
    ignore_fields: str | None = typer.Option(
        None, "--ignore-fields", help="Regex for field paths to ignore."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat numeric widening as warning instead of safe."
    ),
    rename_heuristics: bool = typer.Option(
        False, "--rename-heuristics", help="Detect likely field renames."
    ),
) -> None:
    options = CompareOptions(
        ignore_order=ignore_order,
        ignore_fields=ignore_fields,
        strict=strict,
        rename_heuristics=rename_heuristics,
    )
    comparison = compare_snapshots(
        load_snapshot(old_schema), load_snapshot(new_schema), options=options
    )
    _emit_comparison_output(format, comparison)


@app.command()
def scan(
    old_root: Path = typer.Argument(..., help="Baseline directory path."),
    new_root: Path = typer.Argument(..., help="Candidate directory path."),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    report: str | None = typer.Option(
        None, "--report", help="Optional report format: markdown or html."
    ),
    report_path: Path | None = typer.Option(
        None, "--report-path", help="Write the generated report to a file."
    ),
    pattern: str = typer.Option(
        "*", "--pattern", help="Glob pattern for files to include in the scan."
    ),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
    ignore_order: bool = typer.Option(
        False, "--ignore-order", help="Suppress column order change events."
    ),
    ignore_fields: str | None = typer.Option(
        None, "--ignore-fields", help="Regex for field paths to ignore."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat numeric widening as warning instead of safe."
    ),
    rename_heuristics: bool = typer.Option(
        False, "--rename-heuristics", help="Detect likely field renames."
    ),
) -> None:
    options = CompareOptions(
        sample_size=sample,
        ignore_order=ignore_order,
        ignore_fields=ignore_fields,
        strict=strict,
        rename_heuristics=rename_heuristics,
    )
    report_data = scan_directories(old_root, new_root, options=options, pattern=pattern)
    _emit_comparison_output(format, report_data)
    _emit_comparison_report(report, report_path, report_data)


@baseline_app.command("capture")
def baseline_capture(
    source_root: Path = typer.Argument(..., help="Directory to snapshot into a baseline."),
    output: Path = typer.Option(..., "-o", "--output", help="Baseline directory."),
    pattern: str = typer.Option(
        "*", "--pattern", help="Glob pattern for files to include in the baseline."
    ),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
) -> None:
    manifest = capture_baseline(source_root, output, sample_size=sample, pattern=pattern)
    console.print(render_baseline_manifest_text(manifest, output))


@baseline_app.command("check")
def baseline_check(
    baseline_root: Path = typer.Argument(
        ..., help="Baseline directory containing manifest and snapshots."
    ),
    candidate_root: Path = typer.Argument(..., help="Candidate directory to validate."),
    format: str = typer.Option("text", "--format", help="Output format: text or json."),
    report: str | None = typer.Option(
        None, "--report", help="Optional report format: markdown or html."
    ),
    report_path: Path | None = typer.Option(
        None, "--report-path", help="Write the generated report to a file."
    ),
    pattern: str = typer.Option(
        "*", "--pattern", help="Glob pattern for files to include in the check."
    ),
    sample: int = typer.Option(10_000, "--sample", help="Maximum rows/items to inspect."),
    ignore_order: bool = typer.Option(
        False, "--ignore-order", help="Suppress column order change events."
    ),
    ignore_fields: str | None = typer.Option(
        None, "--ignore-fields", help="Regex for field paths to ignore."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat numeric widening as warning instead of safe."
    ),
    rename_heuristics: bool = typer.Option(
        False, "--rename-heuristics", help="Detect likely field renames."
    ),
) -> None:
    load_baseline_manifest(baseline_root)
    options = CompareOptions(
        sample_size=sample,
        ignore_order=ignore_order,
        ignore_fields=ignore_fields,
        strict=strict,
        rename_heuristics=rename_heuristics,
    )
    report_data = check_baseline(
        baseline_root,
        candidate_root,
        options=options,
        pattern=pattern,
    )
    _emit_comparison_output(format, report_data)
    _emit_comparison_report(report, report_path, report_data)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()

__author__ = "gadwant"
