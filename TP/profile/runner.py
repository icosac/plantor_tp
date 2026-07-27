"""Subprocess execution helpers for profile runs."""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis import parse_profiles


def subprocess_timeout(timeout_s: int) -> Optional[int]:
    """
    Convert CLI timeout values to subprocess.run-compatible values.

    Parameters
    ----------
    timeout_s : int
        Timeout in seconds, or -1 to disable the timeout.

    Returns
    -------
    Optional[int]
        Timeout in seconds, or None for no timeout.
    """
    return None if timeout_s == -1 else timeout_s


def run_artifact_label(run_label: Any) -> str:
    """
    Convert a run label into a stable filename component.

    Parameters
    ----------
    run_label : Any
        Run label written to CSV output.

    Returns
    -------
    str
        Filename-safe run label.
    """
    if isinstance(run_label, int):
        return f"{run_label:03d}"
    return str(run_label)


def planner_command(
    args: argparse.Namespace,
    kb_path: Path,
    artifact_dir: Path,
    run_label: Any,
    save_logs: bool,
    save_visualizations: bool,
) -> List[str]:
    """
    Build the planner.py subprocess command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed profile.py arguments.
    kb_path : Path
        KB file to profile.
    artifact_dir : Path
        Per-KB output directory.
    run_label : Any
        Run label used to name per-run artifacts.
    save_logs : bool
        Whether to save planner and subprocess logs for this run.
    save_visualizations : bool
        Whether to save PO/STN visualizations for this run.

    Returns
    -------
    List[str]
        Subprocess command.
    """
    cmd = [
        sys.executable,
        str(args.planner),
        "--kb",
        str(kb_path),
        "--max-depth",
        str(args.max_depth),
        "--timeout",
        str(args.timeout),
        "--stack-limit",
        str(args.stack_limit),
        "--optimize-stn",
        "--optimize-objective",
        "end_time",
        "--profile",
    ]
    if getattr(args, "enable_graph_debug", False):
        cmd.append("--enable-graph-debug")

    if save_logs or save_visualizations:
        artifact_dir.mkdir(parents=True, exist_ok=True)

    file_label = run_artifact_label(run_label)

    if save_logs:
        if not save_visualizations:
            cmd.extend(
                [
                    "--save-log",
                    str(artifact_dir / f"run_{file_label}_full.log"),
                    "--save-prolog-log",
                    str(artifact_dir / f"run_{file_label}_planner.log"),
                    "--bt-xml",
                    str(artifact_dir / f"run_{file_label}_bt.xml"),
                ]
            )
        else:
            cmd.extend(
                [
                    "--save-log",
                    str(artifact_dir / f"full_log.log"),
                    "--save-prolog-log",
                    str(artifact_dir / f"planner_log.log"),
                    "--bt-xml",
                    str(artifact_dir / f"bt.xml"),
                ]
            )


    if save_visualizations:
        cmd.extend(
            [
                "--po-html",
                str(artifact_dir / "partial_order.html"),
                "--stn-html",
                str(artifact_dir / "stn.html"),
                "--opt-stn-html",
                str(artifact_dir / "optimized_stn.html"),
                "--bt-save-viz",
                str(artifact_dir / "bt_viz.html"),
            ]
        )
    else:
        cmd.extend(["--no-po-html", "--no-stn-html", "--no-opt-stn-html"])
    return cmd


def run_planner(
    args: argparse.Namespace,
    kb_path: Path,
    run_label: Any,
    artifact_dir: Path,
    save_logs: bool,
    save_visualizations: bool,
) -> Dict[str, Any]:
    """
    Run planner.py once and parse timings.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed profile.py arguments.
    kb_path : Path
        KB file to profile.
    run_label : Any
        Run label written to CSV output.
    artifact_dir : Path
        Per-KB artifact directory.
    save_logs : bool
        Whether to save planner and subprocess logs for this run.
    save_visualizations : bool
        Whether to save PO/STN visualizations for this run.

    Returns
    -------
    Dict[str, Any]
        Per-run result row.
    """
    cmd = planner_command(
        args=args,
        kb_path=kb_path,
        artifact_dir=artifact_dir,
        run_label=run_label,
        save_logs=save_logs,
        save_visualizations=save_visualizations,
    )
    started_at = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True,
            text=True,
            check=False,
            timeout=subprocess_timeout(args.process_timeout),
        )
        elapsed_s = time.perf_counter() - started_at
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if save_logs:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / f"run_{run_artifact_label(run_label)}_stdout_stderr.txt").write_text(
                output, encoding="utf-8"
            )

        status = "ok"
        if result.returncode == 124:
            status = "timeout"
        elif result.returncode != 0:
            status = "failed"

        row: Dict[str, Any] = {
            "kb": str(kb_path),
            "run": run_label,
            "status": status,
            "returncode": result.returncode,
            "elapsed_seconds": elapsed_s,
            "artifact_dir": str(artifact_dir),
        }
        row.update(parse_profiles(output))
        return row
    except subprocess.TimeoutExpired as exc:
        elapsed_s = time.perf_counter() - started_at
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + "\n"
        output += (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        if save_logs:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / f"run_{run_artifact_label(run_label)}_stdout_stderr.txt").write_text(
                output, encoding="utf-8"
            )
        return {
            "kb": str(kb_path),
            "run": run_label,
            "status": "timeout",
            "returncode": "process-timeout",
            "elapsed_seconds": elapsed_s,
            "artifact_dir": str(artifact_dir),
        }
