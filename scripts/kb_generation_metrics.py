#!/usr/bin/env python3
"""Compute aggregate KB-generation metrics used in the paper.

The size metrics are computed from the final corrected Prolog files in
exp/kb_generation. The correction metrics are the manual logical-change counts
reported in Tables hlRes and llRes of the paper.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REPORTED_MODELS = (
    "azure_claude-opus46-multi",
    "azure_claude-sonnet46-multi",
    "azure_gpt52-multi",
    "azure_gpt54-mini-multi",
    "hf_Qwen_Qwen3.6-35B-A3B-multi",
    "hf_meta-llama_Llama-3.3-70B-Instruct-multi",
)

DOMAINS = ("blocks_world", "grippers")
INSTANCES = range(1, 7)

Correction = Optional[Tuple[int, ...]]


# Manual logical-change counts from Table hlRes: (K, I, G, DA_H).
HL_CORRECTIONS: Dict[str, List[List[Correction]]] = {
    "blocks_world": [
        [None, None, None, None, None, None],
        [None, None, None, None, None, (0, 0, 1, 2)],
        [(0, 0, 0, 1), (0, 0, 0, 1), (0, 0, 0, 1), (3, 0, 0, 1), (0, 0, 0, 1), (0, 1, 0, 1)],
        [None, None, None, None, None, None],
        [None, (1, 0, 1, 0), None, None, (1, 0, 0, 0), (1, 1, 1, 0)],
        [None, None, None, None, (0, 0, 1, 0), None],
    ],
    "grippers": [
        [None, None, None, (0, 0, 0, 1), None, None],
        [None, (0, 0, 0, 2), None, (0, 2, 2, 2), None, None],
        [None, None, None, (0, 0, 0, 3), (0, 0, 0, 1), (0, 0, 1, 2)],
        [None, None, (0, 0, 0, 1), (0, 0, 0, 5), (0, 0, 0, 1), (0, 0, 0, 2)],
        [None, (0, 0, 0, 1), (1, 0, 0, 1), (2, 0, 0, 2), (1, 0, 0, 4), (1, 0, 0, 4)],
        [None, (0, 0, 0, 4), None, (0, 1, 1, 8), (0, 0, 0, 2), None],
    ],
}


# Manual logical-change counts from Table llRes: (K, I, G, DA_H, DA_L, M).
LL_CORRECTIONS: Dict[str, List[List[Correction]]] = {
    "blocks_world": [
        [None, None, None, (0,0,0,0,0,1), (1,0,0,0,0,0), (1,0,0,0,0,0)],
        [None, None, None, (0,0,0,0,0,1), (1,0,0,0,0,0), (1,0,0,0,0,2)],
        [(0,0,0,0,1,0), (0,0,0,0,1,0), None, None, (1,0,0,0,1,0), (1,0,0,0,1,0)],
        [None, None, (1,0,0,0,0,0), (0,0,0,0,0,1), (1,0,0,0,0,0), (1,0,0,0,0,0)],
        [None, (1,1,0,0,0,0), None, None, (1,0,0,0,0,0), (1,0,0,0,0,0)],
        [(0,0,0,0,1,0), (0,0,0,0,1,0), (0,0,0,0,1,0), None, (1,0,0,0,1,0), (1,0,0,0,1,0)]
    ],
    "grippers": [
        [(0,0,0,0,0,2), (0,0,1,0,0,2), None, (0,0,0,0,3,0), (0,1,1,0,1,0), (0,1,1,0,3,1)],
        [None, None, None, (0,1,1,0,4,0), (0,1,0,0,3,1), (0,0,0,0,4,1)],
        [(0,0,0,0,0,1), None, None, (0,1,1,0,5,8), (0,1,1,0,4,2), (0,2,2,0,3,5)],
        [None, None, None, (0,1,1,0,2,2), (0,1,0,0,6,1), (0,0,0,0,8,1)],
        [None, (0,0,0,0,2,2), (1,0,0,0,1,2), (0,0,0,0,2,1), (0,1,1,0,6,0), (0,1,1,0,1,3)],
        [None, None, None, (0,0,0,0,0,2), (0,0,0,0,3,0), (0,0,0,0,0,7)],
    ],
}


def active_lines(text: str) -> List[str]:
    """Return non-empty lines after removing full-line and trailing comments."""
    lines: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("%", 1)[0].rstrip()
        if line.strip():
            lines.append(line)
    return lines


def active_text(text: str) -> str:
    return "\n".join(active_lines(text))


def section_text(text: str, start_marker: str, end_marker: Optional[str] = None) -> str:
    lines = text.splitlines()
    start: Optional[int] = None
    start_marker = start_marker.lower()
    end_marker = end_marker.lower() if end_marker else None

    for index, line in enumerate(lines):
        if start_marker in line.lower():
            start = index + 1
            break
    if start is None:
        return ""

    end = len(lines)
    if end_marker:
        for index in range(start, len(lines)):
            if end_marker in lines[index].lower():
                end = index
                break
    return "\n".join(lines[start:end])


def count_static_facts(text: str) -> int:
    kb_section = active_lines(section_text(text, "% kb", "% init"))
    return sum(1 for line in kb_section if line.strip().endswith(".") and not line.strip().startswith(":-"))


def count_state_atoms(text: str, functor: str) -> int:
    match = re.search(
        rf"{functor}\s*\(\s*\[(.*?)\]\s*\)\s*\.",
        active_text(text),
        flags=re.DOTALL,
    )
    if not match:
        return 0
    return len(re.findall(r"(?<![A-Za-z0-9_])(?:neg\()?([a-z][A-Za-z0-9_]*\s*\()", match.group(1)))


def count_schemas(text: str) -> int:
    text = active_text(text)
    return (
        len(re.findall(r"\bhl_d_action\s*\(", text))
        + len(re.findall(r"\bll_d_action\s*\(", text))
        + len(re.findall(r"\bmapping\s*\(", text))
    )


def iter_kb_paths(root: Path) -> Iterable[Tuple[str, str, int, str, Path]]:
    """Yield (domain, level, instance, model, path) for every KB file considered."""
    for domain in DOMAINS:
        for level, file_name in (("HL", "kb_hl.pl"), ("LL", "kb_ll.pl")):
            for instance in INSTANCES:
                for model in REPORTED_MODELS:
                    path = root / "exp" / "kb_generation" / domain / str(instance) / model / "output" / file_name
                    if not path.exists():
                        raise FileNotFoundError(path)
                    yield domain, level, instance, model, path


def print_considered_files(root: Path) -> None:
    for domain, level, instance, model, path in iter_kb_paths(root):
        try:
            display_path = path.relative_to(root)
        except ValueError:
            display_path = path
        print(f"{domain:<12}  {level:<2}  {instance}  {model:<45}  {display_path}")


def file_metrics(path: Path) -> Dict[str, int]:
    text = path.read_text()
    return {
        "lines": len(active_lines(text)),
        "state_facts": count_static_facts(text) + count_state_atoms(text, "init_state") + count_state_atoms(text, "goal_state"),
        "schemas": count_schemas(text),
    }


def correction_summary(domain: str, level: str) -> Tuple[int, int]:
    matrix = HL_CORRECTIONS[domain] if level == "HL" else LL_CORRECTIONS[domain]
    correct = sum(1 for row in matrix for value in row if value is None)
    changes = sum(sum(value) for row in matrix for value in row if value is not None)
    return correct, changes


def correction_summary_for_instance(domain: str, level: str, instance: int) -> Tuple[int, int]:
    matrix = HL_CORRECTIONS[domain] if level == "HL" else LL_CORRECTIONS[domain]
    row = matrix[instance - 1]
    correct = sum(1 for value in row if value is None)
    changes = sum(sum(value) for value in row if value is not None)
    return correct, changes


def mean(values: Iterable[int]) -> float:
    return float(f"{statistics.mean(values):.1f}")


def one_decimal(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def aggregate(root: Path) -> List[Dict[str, object]]:
    detailed: Dict[Tuple[str, str], List[Dict[str, int]]] = {}

    for domain, level, _instance, _model, path in iter_kb_paths(root):
        detailed.setdefault((domain, level), []).append(file_metrics(path))

    rows: List[Dict[str, object]] = []
    for domain in DOMAINS:
        for level in ("HL", "LL"):
            metrics = detailed[(domain, level)]
            correct, changes = correction_summary(domain, level)
            rows.append(
                {
                    "domain": "Blocks World" if domain == "blocks_world" else "Grippers",
                    "level": level,
                    "runs": len(metrics),
                    "correct": correct,
                    "changes": changes,
                    "lines": mean(m["lines"] for m in metrics),
                    "state_facts": mean(m["state_facts"] for m in metrics),
                    "schemas": mean(m["schemas"] for m in metrics),
                    "max_lines": max(m["lines"] for m in metrics),
                }
            )

    for level in ("HL", "LL"):
        metrics = detailed[("blocks_world", level)] + detailed[("grippers", level)]
        correct = sum(correction_summary(domain, level)[0] for domain in DOMAINS)
        changes = sum(correction_summary(domain, level)[1] for domain in DOMAINS)
        rows.append(
            {
                "domain": "All",
                "level": level,
                "runs": len(metrics),
                "correct": correct,
                "changes": changes,
                "lines": mean(m["lines"] for m in metrics),
                "state_facts": mean(m["state_facts"] for m in metrics),
                "schemas": mean(m["schemas"] for m in metrics),
                "max_lines": max(m["lines"] for m in metrics),
            }
        )

    return rows


def metrics_for(root: Path, domain: str, instance: int, level: str) -> List[Dict[str, int]]:
    file_name = "kb_hl.pl" if level == "HL" else "kb_ll.pl"
    rows: List[Dict[str, int]] = []
    for model in REPORTED_MODELS:
        path = root / "exp" / "kb_generation" / domain / str(instance) / model / "output" / file_name
        if not path.exists():
            raise FileNotFoundError(path)
        rows.append(file_metrics(path))
    return rows


def aggregate_by_instance(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for domain in DOMAINS:
        for instance in INSTANCES:
            row: Dict[str, object] = {
                "domain": "Blocks World" if domain == "blocks_world" else "Grippers",
                "instance": instance,
                "runs": len(REPORTED_MODELS),
            }
            for level in ("HL", "LL"):
                metrics = metrics_for(root, domain, instance, level)
                correct, changes = correction_summary_for_instance(domain, level, instance)
                prefix = level.lower()
                row[f"{prefix}_correct"] = correct
                row[f"{prefix}_changes"] = changes
                row[f"{prefix}_lines"] = mean(m["lines"] for m in metrics)
                row[f"{prefix}_state_facts"] = mean(m["state_facts"] for m in metrics)
                row[f"{prefix}_schemas"] = mean(m["schemas"] for m in metrics)
                row[f"{prefix}_max_lines"] = max(m["lines"] for m in metrics)
            rows.append(row)
    return rows


def print_summary_text(rows: Sequence[Dict[str, object]]) -> None:
    print("Domain        Level  Runs  Correct  Changes  Lines  State facts  Schemas  Max lines")
    print("------------  -----  ----  -------  -------  -----  -----------  -------  ---------")
    for row in rows:
        print(
            f"{row['domain']:<12}  {row['level']:<5}  {row['runs']:>4}  {row['correct']:>7}  "
            f"{row['changes']:>7}  {one_decimal(row['lines']):>5}  {one_decimal(row['state_facts']):>11}  "
            f"{one_decimal(row['schemas']):>7}  {row['max_lines']:>9}"
        )


def print_instance_text(rows: Sequence[Dict[str, object]]) -> None:
    print(
        "Domain        Inst  Runs  HL ok  HL chg  HL lines  HL facts  HL sch  "
        "LL ok  LL chg  LL lines  LL facts  LL sch"
    )
    print(
        "------------  ----  ----  -----  ------  --------  --------  ------  "
        "-----  ------  --------  --------  ------"
    )
    for row in rows:
        print(
            f"{row['domain']:<12}  {row['instance']:>4}  {row['runs']:>4}  "
            f"{row['hl_correct']:>5}  {row['hl_changes']:>6}  {one_decimal(row['hl_lines']):>8}  "
            f"{one_decimal(row['hl_state_facts']):>8}  {one_decimal(row['hl_schemas']):>6}  "
            f"{row['ll_correct']:>5}  {row['ll_changes']:>6}  {one_decimal(row['ll_lines']):>8}  "
            f"{one_decimal(row['ll_state_facts']):>8}  {one_decimal(row['ll_schemas']):>6}"
        )


def print_summary_latex(rows: Sequence[Dict[str, object]]) -> None:
    columns = [f"{row['domain']} \\{row['level']}" for row in rows]
    metric_rows = (
        ("Runs", "runs"),
        ("Correct", "correct"),
        ("Changes", "changes"),
        ("Lines", "lines"),
        ("State facts", "state_facts"),
        ("Schemas", "schemas"),
    )

    print(r"\begin{tabular}{l " + " ".join("r" for _ in columns) + "}")
    print(r"\toprule")
    print("Metric & " + " & ".join(columns) + r" \\")
    print(r"\midrule")
    for label, key in metric_rows:
        values = [one_decimal(row[key]) for row in rows]
        print(f"{label} & " + " & ".join(values) + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")


def print_instance_latex(rows: Sequence[Dict[str, object]]) -> None:
    columns = [f"{row['domain']} {row['instance']}" for row in rows]
    metric_rows = (
        ("Runs", "runs"),
        ("HL ok", "hl_correct"),
        ("HL chg", "hl_changes"),
        ("HL lines", "hl_lines"),
        ("HL facts", "hl_state_facts"),
        ("HL sch", "hl_schemas"),
        ("LL ok", "ll_correct"),
        ("LL chg", "ll_changes"),
        ("LL lines", "ll_lines"),
        ("LL facts", "ll_state_facts"),
        ("LL sch", "ll_schemas"),
    )

    print(r"\begin{tabular}{l " + " ".join("r" for _ in columns) + "}")
    print(r"\toprule")
    print("Metric & " + " & ".join(columns) + r" \\")
    print(r"\midrule")
    for label, key in metric_rows:
        values = [one_decimal(row[key]) for row in rows]
        print(f"{label} & " + " & ".join(values) + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")


def print_csv(rows: Sequence[Dict[str, object]]) -> None:
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


def main() -> int:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root, help="Repository root. Defaults to this script's parent repo.")
    parser.add_argument("--format", choices=("text", "latex", "csv", "json"), default="text")
    parser.add_argument("--latex", action="store_true", help="Output in LaTeX tabular format (alias for --format latex).")
    parser.add_argument(
        "--scope",
        choices=("all", "summary", "instances"),
        default="all",
        help="Print aggregate rows, per-instance rows, or both. Defaults to both.",
    )
    args = parser.parse_args()
    if args.latex:
        args.format = "latex"

    # print_considered_files(args.root)
    # print()

    summary_rows = aggregate(args.root)
    instance_rows = aggregate_by_instance(args.root)

    if args.format == "text":
        if args.scope in ("all", "summary"):
            print_summary_text(summary_rows)
        if args.scope == "all":
            print()
        if args.scope in ("all", "instances"):
            print_instance_text(instance_rows)
    elif args.format == "latex":
        if args.scope in ("all", "summary"):
            print_summary_latex(summary_rows)
        if args.scope == "all":
            print()
        if args.scope in ("all", "instances"):
            print_instance_latex(instance_rows)
    elif args.format == "csv":
        if args.scope == "summary":
            print_csv(summary_rows)
        elif args.scope == "instances":
            print_csv(instance_rows)
        else:
            print_csv(
                [{**row, "kind": "summary"} for row in summary_rows]
                + [{**row, "kind": "instance"} for row in instance_rows]
            )
    else:
        if args.scope == "summary":
            print(json.dumps(summary_rows, indent=2))
        elif args.scope == "instances":
            print(json.dumps(instance_rows, indent=2))
        else:
            print(json.dumps({"summary": summary_rows, "instances": instance_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
