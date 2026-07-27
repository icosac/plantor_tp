"""Main orchestration for TP/profile.py."""

import sys
from pathlib import Path
from typing import Any, Dict, List

from .analysis import summarize
from .config import parse_args
from .io import (
    confirm_force_or_overwrite,
    find_kbs,
    merge_rows_by_kb,
    output_dir_for_kb,
    prepare_output_root,
    read_csv_rows,
    write_runs_csv,
    write_summary_csv,
)
from .plot import (
    generate_normalized_outputs,
    generate_timing_group_outputs,
    read_summary_csv,
    write_latex_table,
)
from .runner import run_planner


def write_plot_outputs(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    output_root: Path,
    table_path: Path,
    normalized_csv: Path,
    normalized_plot_path: Path,
    normalized_tikz_path: Path,
    args: Any,
) -> None:
    """
    Write all table and plot artifacts from aggregate profile rows.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        KB root used to interpret profile paths.
    output_root : Path
        Root where grouped timing outputs are written.
    table_path : Path
        LaTeX table path.
    normalized_csv : Path
        Normalized timing CSV path.
    normalized_plot_path : Path
        Normalized timing plot path.
    normalized_tikz_path : Path
        Normalized timing TikZ path.
    args : Any
        Parsed profile.py arguments.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    write_latex_table(table_path, summaries, kb_root)
    normalized_outputs = generate_normalized_outputs(
        summaries=summaries,
        kb_root=kb_root,
        metric=args.normalized_to_plot_metric,
        normalized_csv=normalized_csv,
        normalized_plot_path=normalized_plot_path,
        tikz_path=normalized_tikz_path,
        write_plot=not args.no_to_normalized_plot,
        write_tikz=not args.no_to_normalized_tikz,
    )
    timing_outputs = generate_timing_group_outputs(
        summaries=summaries,
        kb_root=kb_root,
        output_root=output_root,
        write_plot=not args.no_timing_plots,
        write_tikz=not args.no_timing_tikz,
        write_tables=not args.no_timing_tables,
    )

    print(f"Wrote LaTeX table: {table_path}")
    print(f"Wrote normalized model CSV: {normalized_csv}")
    if normalized_outputs["plot"]:
        for plot_path in normalized_outputs.get("plot_paths", [str(normalized_plot_path)]):
            print(f"Wrote normalized model plot: {plot_path}")
    if normalized_outputs["tikz"]:
        print(f"Wrote normalized model TikZ/PGFPlots: {normalized_tikz_path}")
    for group_name, group_outputs in timing_outputs.items():
        if group_outputs["plot"]:
            for plot_path in group_outputs.get("plot_paths", [group_outputs["plot_path"]]):
                print(f"Wrote {group_name} timing plot: {plot_path}")
        if group_outputs["tikz"]:
            print(f"Wrote {group_name} timing TikZ/PGFPlots: {group_outputs['tikz_path']}")
        if group_outputs["table"]:
            print(f"Wrote {group_name} timing LaTeX table: {group_outputs['table_path']}")


def main() -> int:
    """
    Run the batch profiler.

    Returns
    -------
    int
        Process exit code.
    """
    args = parse_args()
    kb_root = args.kb_root.resolve()
    output_root = args.output_root.resolve()
    table_path = (args.table_path or output_root / "profile_table.tex").resolve()
    runs_csv = (args.runs_csv or output_root / "profile_runs.csv").resolve()
    summary_csv = (args.summary_csv or output_root / "profile_summary.csv").resolve()
    normalized_csv = (
        args.normalized_to_data_csv or output_root / "model_normalized_total_order.csv"
    ).resolve()
    normalized_plot_path = (
        args.normalized_to_plot_path or output_root / "model_normalized_total_order.pdf"
    ).resolve()
    normalized_tikz_path = (
        args.normalized_to_tikz_path or output_root / "model_normalized_total_order_tikz.tex"
    ).resolve()

    if args.only_plot:
        if not summary_csv.is_file():
            print(f"Summary CSV not found: {summary_csv}", file=sys.stderr)
            return 1
        try:
            summaries = read_summary_csv(summary_csv)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        write_plot_outputs(
            summaries=summaries,
            kb_root=kb_root,
            output_root=output_root,
            table_path=table_path,
            normalized_csv=normalized_csv,
            normalized_plot_path=normalized_plot_path,
            normalized_tikz_path=normalized_tikz_path,
            args=args,
        )
        return 0

    kbs = find_kbs(kb_root, args.limit, args.exclude)
    if not kbs:
        exclude_suffix = f" after applying excludes {args.exclude}" if args.exclude else ""
        print(f"No kb_ll.pl files found under {kb_root}{exclude_suffix}", file=sys.stderr)
        return 1

    if not confirm_force_or_overwrite(args, output_root):
        print("Aborted.", file=sys.stderr)
        return 3

    try:
        prepare_output_root(output_root, args.force, overwrite=args.overwrite)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    all_rows: List[Dict[str, Any]] = []
    for kb_index, kb_path in enumerate(kbs, start=1):
        artifact_dir = output_dir_for_kb(kb_path.resolve(), kb_root, output_root)
        print(f"[{kb_index}/{len(kbs)}] Profiling {kb_path}")
        if args.save_logs_viz:
            artifact_row = run_planner(
                args,
                kb_path.resolve(),
                "artifact",
                artifact_dir,
                save_logs=True,
                save_visualizations=True,
            )
            print(
                "  artifact run: "
                f"{artifact_row['status']} "
                f"elapsed={float(artifact_row['elapsed_seconds']):.3f}s"
            )

        if args.runs == 0:
            print("  measured runs skipped (--runs 0)")
            continue

        successive_failures = 0
        for run_index in range(1, args.runs + 1):
            row = run_planner(
                args,
                kb_path.resolve(),
                run_index,
                artifact_dir,
                save_logs=True,
                save_visualizations=False,
            )
            all_rows.append(row)
            print(
                f"  run {run_index:03d}/{args.runs}: "
                f"{row['status']} "
                f"elapsed={float(row['elapsed_seconds']):.3f}s"
            )
            if row["status"] == "ok":
                successive_failures = 0
            else:
                successive_failures += 1
                if args.patience > 0 and successive_failures >= args.patience:
                    print(
                        "  stopping early: "
                        f"{successive_failures} successive non-ok runs "
                        f"(--patience {args.patience})"
                    )
                    break

    output_rows = all_rows
    existing_run_rows: List[Dict[str, Any]] = []
    if args.overwrite:
        existing_run_rows = read_csv_rows(runs_csv)
        if args.runs == 0:
            output_rows = existing_run_rows
        else:
            output_rows = merge_rows_by_kb(
                existing_rows=existing_run_rows,
                new_rows=all_rows,
                replaced_kbs=(kb.resolve() for kb in kbs),
                kb_root=kb_root,
            )

    summaries = summarize(output_rows)
    if args.overwrite and args.runs == 0 and not existing_run_rows:
        summaries = read_csv_rows(summary_csv)
    elif args.overwrite and not existing_run_rows:
        existing_summaries = read_csv_rows(summary_csv)
        if existing_summaries:
            summaries = merge_rows_by_kb(
                existing_rows=existing_summaries,
                new_rows=summaries,
                replaced_kbs=(kb.resolve() for kb in kbs),
                kb_root=kb_root,
            )
    write_runs_csv(runs_csv, output_rows)
    write_summary_csv(summary_csv, summaries)
    write_plot_outputs(
        summaries=summaries,
        kb_root=kb_root,
        output_root=output_root,
        table_path=table_path,
        normalized_csv=normalized_csv,
        normalized_plot_path=normalized_plot_path,
        normalized_tikz_path=normalized_tikz_path,
        args=args,
    )

    print(f"Wrote per-run CSV: {runs_csv}")
    print(f"Wrote summary CSV: {summary_csv}")
    return 0
