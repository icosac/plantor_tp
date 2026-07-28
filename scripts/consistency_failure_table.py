#!/usr/bin/env python3
"""Recreate the consistency-failure count table from KB-generation logs.

The script is read-only: it scans exp/kb_generation/**/log.log, extracts the
actual failed repair-iteration blocks, and builds a hierarchy from explicit
"Failed checks" lines:

- [consistency_checks] Failed checks: [...] gives the failed checker families.
- [family] Failed checks: [...] gives the failed checks inside that family.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utility.logger import logger


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
NEXT_LOG_RECORD_RE = r"\n\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} "
FAILED_CHECKS_RE = re.compile(r"\[([^\]]+)\]\s*Failed checks:\s*\[([^\]]*)\]")
LAYERS = ("HL", "LL")


@dataclass
class FamilyStats:
    appearances: int = 0
    children: Counter[str] = field(default_factory=Counter)


FamilyCounts = Dict[str, Dict[str, FamilyStats]]


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def failed_attempt_blocks(text: str, layer: str) -> Iterable[str]:
    pattern = re.compile(
        rf"\[{layer}\] Consistency check failed \(attempt \d+/\d+\) for reason:\s*\n"
        rf"(.*?)(?={NEXT_LOG_RECORD_RE}|\Z)",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(text):
        yield match.group(1)


def parse_failed_checks_payload(payload: str) -> List[str]:
    return [check.strip() for check in payload.split(",") if check.strip()]


def failed_checks_line(line: str) -> tuple[str, List[str]] | None:
    match = FAILED_CHECKS_RE.match(line.strip())
    if not match:
        return None

    family, checks = match.groups()
    return family, parse_failed_checks_payload(checks)


def count_block(block: str, family_counts: Dict[str, FamilyStats]) -> None:
    failed_families: List[str] = []
    child_checks: Dict[str, Counter[str]] = defaultdict(Counter)

    for line in block.splitlines():
        parsed = failed_checks_line(line)
        if not parsed:
            continue

        family, checks = parsed
        if family == "consistency_checks":
            failed_families.extend(checks)
        else:
            child_checks[family].update(checks)

    for family in failed_families:
        family_counts[family].appearances += 1

    for family, checks in child_checks.items():
        family_counts[family].children.update(checks)
        if family not in failed_families:
            logger.debug("Found child checks for %s without a top-level family count", family)


def collect_family_counts(root: Path) -> FamilyCounts:
    counts: FamilyCounts = {layer: defaultdict(FamilyStats) for layer in LAYERS}
    log_paths = sorted(root.glob("**/log.log"))
    logger.debug("Found %d log files under %s", len(log_paths), root)

    for log_path in log_paths:
        text = strip_ansi(log_path.read_text(errors="replace"))
        for layer in LAYERS:
            blocks = list(failed_attempt_blocks(text, layer))
            if blocks:
                logger.debug("Found %d %s failed attempts in %s", len(blocks), layer, log_path)
            for block in blocks:
                count_block(block, counts[layer])

    for layer in LAYERS:
        logger.debug(
            "Collected %s family counts: %s",
            layer,
            {
                family: {"appearances": stats.appearances, "children": dict(stats.children)}
                for family, stats in counts[layer].items()
            },
        )
    return counts


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def layer_label(layer: str) -> str:
    return "High-Level" if layer == "HL" else "Low-level"


def sorted_families(family_counts: Dict[str, FamilyStats]) -> List[tuple[str, FamilyStats]]:
    return sorted(
        family_counts.items(),
        key=lambda item: (-item[1].appearances, item[0]),
    )


def layer_row_count(family_counts: Dict[str, FamilyStats]) -> int:
    total = 0
    for _family, stats in sorted_families(family_counts):
        total += 1
        total += len(stats.children)
    return total


def layer_prefix(layer: str, remaining_rows: int, first: bool) -> str:
    if first:
        return rf"        \multirow{{{remaining_rows}}}{{*}}{{\rotatebox[origin=c]{{90}}{{{layer_label(layer)}}}}}"
    return "       "


def write_latex(counts: FamilyCounts, out: TextIO) -> None:
    logger.debug("Writing hierarchy as LaTeX")
    print(r"\begin{table*}[t]", file=out)
    print(r"    \centering", file=out)
    print(r"    \caption{Failed consistency checks during the repair loop.}", file=out)
    print(r"    \label{tab:consistencyFailures}", file=out)
    print(r"    \footnotesize", file=out)
    print(r"    \begin{tabular}{clc}", file=out)
    print(r"        \toprule", file=out)
    print(r"        Layer & Failed check & Appearances \\", file=out)
    print(r"        \midrule", file=out)

    for layer_index, layer in enumerate(LAYERS):
        if layer_index:
            print(r"        \midrule", file=out)

        remaining_rows = layer_row_count(counts[layer])
        first_layer_row = True
        for family, stats in sorted_families(counts[layer]):
            prefix = layer_prefix(layer, remaining_rows, first_layer_row)
            first_layer_row = False

            if stats.children:
                family_label = rf"\textbf{{{latex_escape(family)}}} ({stats.appearances})"
                print(rf"{prefix} & \multicolumn{{2}}{{l}}{{{family_label}}} \\", file=out)
                for child, appearances in stats.children.most_common():
                    print(rf"        & \quad {latex_escape(child)} & {appearances} \\", file=out)
            else:
                print(rf"{prefix} & {latex_escape(family)} & {stats.appearances} \\", file=out)

    print(r"        \bottomrule", file=out)
    print(r"    \end{tabular}", file=out)
    print(r"\end{table*}", file=out)


def write_csv(counts: FamilyCounts, out: TextIO) -> None:
    logger.debug("Writing hierarchy as CSV")
    writer = csv.writer(out)
    writer.writerow(["layer", "row_type", "family", "failed_check", "appearances"])
    for layer in LAYERS:
        for family, stats in sorted_families(counts[layer]):
            writer.writerow([layer, "family", family, "", stats.appearances])
            for child, appearances in stats.children.most_common():
                writer.writerow([layer, "check", family, child, appearances])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count failed consistency-check families and children in exp/kb_generation logs."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("exp/kb_generation"),
        help="KB-generation experiment directory. Default: exp/kb_generation",
    )
    parser.add_argument(
        "--format",
        choices=("latex", "csv"),
        default="latex",
        help="Output format. Default: latex",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging. Default logging level is info.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.debug:
        logger.set_debug()
    else:
        logger.set_info()

    logger.debug("Arguments: %s", args)
    if not args.root.exists():
        print(f"error: root does not exist: {args.root}", file=sys.stderr)
        return 2

    counts = collect_family_counts(args.root)
    if args.format == "csv":
        write_csv(counts, sys.stdout)
    else:
        write_latex(counts, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
