"""Filesystem and CSV helpers for profile runs."""

import argparse
import csv
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .plot import kb_label


def find_kbs(kb_root: Path, limit: int, exclude_patterns: List[str]) -> List[Path]:
    """
    Find generated low-level KB files.

    Parameters
    ----------
    kb_root : Path
        Root directory to search.
    limit : int
        Maximum number of KBs to return. Zero means no limit.
    exclude_patterns : List[str]
        Regexes matched against each path relative to kb_root.

    Returns
    -------
    List[Path]
        Sorted KB paths.
    """
    exclude_res = [re.compile(pattern) for pattern in exclude_patterns]
    kbs = []
    for kb_path in sorted(kb_root.rglob("kb_ll.pl")):
        relative_path = kb_path.relative_to(kb_root).as_posix()
        if any(pattern.search(relative_path) for pattern in exclude_res):
            continue
        kbs.append(kb_path)
    if limit > 0:
        return kbs[:limit]
    return kbs


def output_dir_for_kb(kb_path: Path, kb_root: Path, output_root: Path) -> Path:
    """
    Map a KB path under exp/kb_generation into a mirrored exp/planner path.

    Parameters
    ----------
    kb_path : Path
        Path to kb_ll.pl.
    kb_root : Path
        Source KB root.
    output_root : Path
        Destination root.

    Returns
    -------
    Path
        Output directory for this KB.
    """
    return output_root / kb_path.parent.relative_to(kb_root)


def prepare_output_root(output_root: Path, force: bool, overwrite: bool = False) -> None:
    """
    Ensure the output root is clean before running.

    Parameters
    ----------
    output_root : Path
        Directory where profiling outputs will be written.
    force : bool
        Whether to delete and recreate a non-empty output root.
    overwrite : bool, optional
        Whether to allow writing into a non-empty output root without deleting it.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    if output_root.exists() and not output_root.is_dir():
        raise RuntimeError(f"Output root exists and is not a directory: {output_root}")

    if output_root.exists() and any(output_root.iterdir()):
        if overwrite:
            output_root.mkdir(parents=True, exist_ok=True)
            return
        if not force:
            raise RuntimeError(
                f"Output root is not empty: {output_root}. "
                "Pass --force to delete and recreate it, or --overwrite to update existing CSV entries."
            )
        shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)


def confirm_force_or_overwrite(args: argparse.Namespace, output_root: Path) -> bool:
    """
    Ask for confirmation before running with --force or --overwrite.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed profile.py arguments.
    output_root : Path
        Resolved output root affected by force/overwrite behavior.

    Returns
    -------
    bool
        True when execution should continue.
    """
    if args.sure or not (args.force or args.overwrite):
        return True

    action = "--force will delete and recreate" if args.force else "--overwrite will update"
    prompt = f"{action} output data under {output_root}. Continue? [y/N] "
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def write_runs_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    """
    Write per-run rows to CSV.

    Parameters
    ----------
    path : Path
        Output CSV path.
    rows : List[Dict[str, Any]]
        Per-run rows.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = ["kb", "run", "status", "returncode", "elapsed_seconds", "artifact_dir"]
    fieldnames = preferred + [field for field in fieldnames if field not in preferred]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    """
    Read CSV rows if the file exists.

    Parameters
    ----------
    path : Path
        CSV path.

    Returns
    -------
    List[Dict[str, Any]]
        Rows from the CSV, or an empty list when the file is absent.
    """
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def kb_row_key(row: Dict[str, Any], kb_root: Path) -> str:
    """
    Build a stable key for a run or summary row.

    Parameters
    ----------
    row : Dict[str, Any]
        CSV row containing a kb field.
    kb_root : Path
        KB root used to normalize paths.

    Returns
    -------
    str
        Stable KB key.
    """
    return kb_label(Path(str(row["kb"])), kb_root)


def merge_rows_by_kb(
    existing_rows: List[Dict[str, Any]],
    new_rows: List[Dict[str, Any]],
    replaced_kbs: Iterable[Path],
    kb_root: Path,
) -> List[Dict[str, Any]]:
    """
    Replace rows for selected KBs while preserving all other rows.

    Parameters
    ----------
    existing_rows : List[Dict[str, Any]]
        Previously written CSV rows.
    new_rows : List[Dict[str, Any]]
        Rows produced by the current run.
    replaced_kbs : Iterable[Path]
        KBs processed by the current run.
    kb_root : Path
        KB root used to normalize paths.

    Returns
    -------
    List[Dict[str, Any]]
        Merged rows.
    """
    replaced_keys = {kb_label(kb, kb_root) for kb in replaced_kbs}
    kept_rows = [row for row in existing_rows if kb_row_key(row, kb_root) not in replaced_keys]
    return kept_rows + new_rows


def write_summary_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    """
    Write aggregate rows to CSV.

    Parameters
    ----------
    path : Path
        Output CSV path.
    rows : List[Dict[str, Any]]
        Aggregate rows.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = ["kb", "runs", "ok", "timeouts", "failed"]
    fieldnames = preferred + [field for field in fieldnames if field not in preferred]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
