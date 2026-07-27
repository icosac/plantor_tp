"""Profile output parsing and summary aggregation."""

import re
import statistics
from typing import Any, Dict, Iterable, List

from .plot import TABLE_METRICS


PROLOG_PROFILE_RE = re.compile(
    r"^(?:\[[^\]]+\]\s*)?\[profile\]\s+prolog\.(?P<phase>\S+)\s+"
    r"time\{cpu:(?P<cpu>[-+0-9.eE]+),"
    r"inferences:(?P<inferences>\d+),"
    r"wall:(?P<wall>[-+0-9.eE]+)\}"
)
PYTHON_PROFILE_RE = re.compile(
    r"^(?:\[[^\]]+\]\s*)?\[profile\]\s+python\.(?P<phase>\S+)\s+"
    r"wall_seconds=(?P<wall>[-+0-9.eE]+)"
)


def parse_profiles(output: str) -> Dict[str, float]:
    """
    Extract profile timings from planner.py output.

    Parameters
    ----------
    output : str
        Combined stdout/stderr from planner.py.

    Returns
    -------
    Dict[str, float]
        Flattened timing fields.
    """
    timings: Dict[str, float] = {}
    for line in output.splitlines():
        clean = _strip_ansi(line)
        prolog_match = PROLOG_PROFILE_RE.search(clean)
        if prolog_match:
            phase = prolog_match.group("phase")
            timings[f"prolog.{phase}.wall_seconds"] = float(prolog_match.group("wall"))
            timings[f"prolog.{phase}.cpu_seconds"] = float(prolog_match.group("cpu"))
            timings[f"prolog.{phase}.inferences"] = float(prolog_match.group("inferences"))
            continue

        python_match = PYTHON_PROFILE_RE.search(clean)
        if python_match:
            phase = python_match.group("phase")
            timings[f"python.{phase}.wall_seconds"] = float(python_match.group("wall"))
    return timings


def _strip_ansi(text: str) -> str:
    """
    Remove ANSI color escape codes.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    str
        Text without ANSI escapes.
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def summarize(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aggregate per-run rows by KB.

    Parameters
    ----------
    rows : Iterable[Dict[str, Any]]
        Per-run measurements.

    Returns
    -------
    List[Dict[str, Any]]
        Per-KB aggregate rows.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["kb"]), []).append(row)

    summaries: List[Dict[str, Any]] = []
    for kb, kb_rows in sorted(grouped.items()):
        ok_rows = [row for row in kb_rows if row.get("status") == "ok"]
        summary: Dict[str, Any] = {
            "kb": kb,
            "runs": len(kb_rows),
            "ok": len(ok_rows),
            "timeouts": sum(1 for row in kb_rows if row.get("status") == "timeout"),
            "failed": sum(1 for row in kb_rows if row.get("status") == "failed"),
        }
        for _label, metric in TABLE_METRICS:
            values = [float(row[metric]) for row in ok_rows if metric in row and row[metric] != ""]
            summary[f"{metric}.mean"] = statistics.mean(values) if values else ""
            summary[f"{metric}.std"] = statistics.stdev(values) if len(values) > 1 else (0.0 if values else "")
        summaries.append(summary)
    return summaries
