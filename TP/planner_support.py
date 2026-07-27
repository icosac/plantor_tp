"""Argument definitions and helper utilities for TP planner execution."""

import argparse
import math
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from utility.logger import logger

from src.partial_order import PartialOrderPlan
from src.stn import SimpleTemporalNetwork


def _prolog_quote(path: Path) -> str:
    """
    Escape a filesystem path so it is safe in a Prolog atom literal.

    Parameters
    ----------
    path : Path
        Filesystem path used by this operation.

    Returns
    -------
    str
        String result produced by this function.
    """
    return str(path).replace("\\", "/").replace("'", "\\'")


def _prolog_profile_line(label: str, time_var: str) -> str:
    """
    Build a Prolog format/2 goal that emits one machine-readable profile line.

    Parameters
    ----------
    label : str
        Profile phase name.
    time_var : str
        Prolog variable containing a call_time/2 result.

    Returns
    -------
    str
        Prolog goal fragment.
    """
    return f"format('[profile] prolog.{label} ~w\\n', [{time_var}])"


def build_prolog_goal(
    kb_file: Path,
    src_dir: Path,
    max_depth: int,
    enable_graph_debug: bool,
    profile: bool = False,
) -> str:
    """
    Build the full SWI-Prolog goal string that runs the planner pipeline.

    Parameters
    ----------
    kb_file : Path
        Path to the Prolog knowledge-base file to consult.
    src_dir : Path
        Directory containing Prolog source files used during execution.
    max_depth : int
        Maximum planner search depth. Use -1 for unbounded search.
    enable_graph_debug : bool
        Whether to enable graph-debug traces in planner output.
    profile : bool, optional
        Whether to emit extra machine-readable Prolog timing lines.

    Returns
    -------
    str
        String result produced by this function.
    """
    bfs_planner = src_dir / "bfs_planner.pl"
    mappings = src_dir / "mappings.pl"
    enablers = src_dir / "enablers.pl"

    # Bootstrap the Prolog runtime and consult all required source files.
    goal_parts = [
        "style_check(-singleton)",
        "style_check(-discontiguous)",
        "set_prolog_flag(verbose, silent)",
        f"['{_prolog_quote(kb_file)}']",
        f"['{_prolog_quote(bfs_planner)}']",
        f"['{_prolog_quote(mappings)}']",
        f"['{_prolog_quote(enablers)}']",
    ]
    if enable_graph_debug:
        goal_parts.append("enable_graph_debug")

    total_order_profile = (
        _prolog_profile_line("total_order_planning", "TimePlan")
        if profile
        else "true"
    )
    mapping_goal = (
        "call_time(apply_mappings(Init, Plan, LL_Plan), TimeMapping), "
        f"{_prolog_profile_line('low_level_mapping', 'TimeMapping')}"
        if profile
        else "apply_mappings(Init, Plan, LL_Plan)"
    )
    enabler_goal = (
        "call_time(extract_enablers(LL_Plan, Enablers), TimeEnablers), "
        f"{_prolog_profile_line('enabler_extraction', 'TimeEnablers')}"
        if profile
        else "extract_enablers(LL_Plan, Enablers)"
    )
    start_end_goal = (
        "call_time(extract_start_end_links(LL_Plan, StartEndLinks), TimeStartEndLinks), "
        f"{_prolog_profile_line('start_end_link_extraction', 'TimeStartEndLinks')}"
        if profile
        else "extract_start_end_links(LL_Plan, StartEndLinks)"
    )
    start_end_print_goal = (
        "call_time(print_start_end_links(LL_Plan, StartEndLinks), TimeStartEndPrinting), "
        f"{_prolog_profile_line('start_end_link_printing', 'TimeStartEndPrinting')}"
        if profile
        else "print_start_end_links(LL_Plan, StartEndLinks)"
    )
    plan_enablers_print_goal = (
        "call_time(print_plan_with_enablers(LL_Plan, Enablers), TimePlanEnablersPrinting), "
        f"{_prolog_profile_line('plan_with_enablers_printing', 'TimePlanEnablersPrinting')}"
        if profile
        else "print_plan_with_enablers(LL_Plan, Enablers)"
    )
    duration_print_goal = (
        "call_time(print_plan_durations(LL_Plan), TimeDurationPrinting), "
        f"{_prolog_profile_line('duration_constraint_printing', 'TimeDurationPrinting')}"
        if profile
        else "print_plan_durations(LL_Plan)"
    )

    # Execute planning and emit structured sections that the Python side parses later.
    goal_parts.extend(
        [
            "format('[planner] Starting BFS planner\\n')",
            f"call_time(bfs_planner({max_depth}, Plan), TimePlan)",
            total_order_profile,
            (
                "(Plan \\= [] -> "
                "(format('[planner] Plan found in ~w\\n', [TimePlan]), "
                "print_list(Plan, true), "
                "init_state(Init), "
                f"{mapping_goal}, "
                "format('[planner] LL Plan:'), "
                "print_list(LL_Plan, true), "
                f"{enabler_goal}, "
                "format('[planner] Enablers:'), "
                "print_list(Enablers, true), "
                f"{start_end_goal}, "
                "format('[planner] Start/end link terms:'), "
                "print_list(StartEndLinks, true), "
                f"{start_end_print_goal}, "
                f"{plan_enablers_print_goal}, "
                f"{duration_print_goal}); "
                "format('[planner] No plan found\\n'))"
            ),
        ]
    )
    return ", ".join(goal_parts)


def parse_durative_actions_links(prolog_output: str) -> Dict[str, str]:
    """
    Extract start/end link information for durative actions from planner output.

    Parameters
    ----------
    prolog_output : str
        Raw planner output text produced by Prolog.

    Returns
    -------
    Dict[str, str]
        Dictionary containing structured results from this function.
    """
    links: Dict[str, str] = {}
    collecting = False
    line_pattern = re.compile(r"^\s*start_end_link\((\d+)\s*-\s*(.*)\s*,\s*(\d+)\s*-\s*(.*)\s*\)$")

    for line in prolog_output.splitlines():
        # Start collecting only after the dedicated marker appears.
        if line.startswith("[planner] Start/end link terms:"):
            collecting = True
            continue

        if not collecting:
            continue

        # Stop when another `[planner] ...` section starts.
        if line.startswith("["):
            break

        stripped = line.strip()
        if not stripped:
            continue

        match = line_pattern.match(line)
        if not match:
            logger.warning(f"Line does not match expected format for durative action links: '{line}'")
            continue

        start_id = int(match.group(1))
        start_name = match.group(2).strip()
        end_id = int(match.group(3))
        end_name = match.group(4).strip()
        links[f"{start_id}-{start_name}"] = f"{end_id}-{end_name}"

    logger.info("===================================================================")
    logger.info(f"Extracted {len(links)} durative action links from planner output.")
    for key, value in links.items():
        logger.info(f"  - {key}: {value}")
    logger.info("===================================================================")

    return links


def _parse_duration_number(token: str) -> Optional[float]:
    """
    Parse numeric duration tokens including Prolog-style infinity values.

    Parameters
    ----------
    token : str
        Single token value being parsed or validated.

    Returns
    -------
    Optional[float]
        Result returned by `_parse_duration_number`.
    """
    value = (token or "").strip().lower()
    if not value:
        return None
    if value in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    if value in {"-inf", "-infinity"}:
        return float("-inf")
    try:
        return float(value)
    except ValueError:
        return None


def parse_duration_constraints(prolog_output: str) -> Dict[str, Dict[str, float]]:
    """
    Extract duration bounds from planner textual output.

    Parameters
    ----------
    prolog_output : str
        Raw planner output text produced by Prolog.

    Returns
    -------
    Dict[str, Dict[str, float]]
        Dictionary containing structured results from this function.
    """
    constraints: Dict[str, Dict[str, float]] = {}
    collecting = False
    line_pattern = re.compile(r"^\s*(\d+)\s*-\s*(.*?)\s*=>\s*\[(.*?),(.*?)\]\s*$")

    for line in prolog_output.splitlines():
        # Start collecting only after the dedicated marker appears.
        if line.startswith("[planner] Duration constraints:"):
            collecting = True
            continue

        if not collecting:
            continue

        # Stop when another `[planner] ...` section starts.
        if line.startswith("["):
            break

        stripped = line.strip()
        if not stripped:
            if constraints:
                break
            continue

        match = line_pattern.match(line)
        if not match:
            continue

        step_id = int(match.group(1))
        step = match.group(2).strip()
        min_duration = _parse_duration_number(match.group(3))
        max_duration = _parse_duration_number(match.group(4))
        # Keep malformed bounds non-fatal; warn and continue parsing remaining entries.
        if min_duration is None or max_duration is None:
            logger.warning(f"Could not parse duration bounds for {step_id}-{step}")
            continue
        if (math.isinf(min_duration) and min_duration > 0) or (math.isinf(max_duration) and max_duration < 0):
            logger.warning(f"Invalid infinite duration bounds for {step_id}-{step}")
            continue
        if min_duration > max_duration:
            logger.warning(f"Duration bounds are inconsistent for {step_id}-{step}")
            continue

        constraints[f"{step_id}-{step}"] = {"min": min_duration, "max": max_duration}

    return constraints


def run_prolog(
    swipl: str,
    goal: str,
    timeout_s: Optional[int],
    stack_limit: str = "10G",
) -> subprocess.CompletedProcess:
    """
    Invoke SWI-Prolog with the generated planner goal.

    Parameters
    ----------
    swipl : str
        SWI-Prolog executable path or command name.
    goal : str
        Prolog goal string passed to the SWI-Prolog process.
    timeout_s : Optional[int]
        Maximum time allowed for the operation in seconds, or None for no timeout.
    stack_limit : str, optional
        SWI-Prolog stack limit passed through --stack_limit.

    Returns
    -------
    subprocess.CompletedProcess
        Result returned by `run_prolog`.
    """
    # Use a large stack because large planning instances can recurse deeply.
    cmd = [
        swipl,
        f"--stack_limit={stack_limit}",
        "-q",
        "-g",
        goal,
        "-t",
        "halt",
    ]
    logger.info(f"Running: {shlex.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
    )






def run_po_visualizer(
    python_exec: str,
    po_viz_script: Path,
    planner_log_path: Path,
    output_html_path: Path,
    timeout_s: Optional[int],
    labels: str = "short",
    reason_filter: str = "all",
    no_ll: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run the PO visualizer script to generate an interactive HTML graph.

    Parameters
    ----------
    python_exec : str
        Python interpreter used to launch subprocess tools.
    po_viz_script : Path
        Path to the partial-order visualization script.
    planner_log_path : Path
        Path to the planner log file consumed by the visualizer.
    output_html_path : Path
        Path where the generated HTML visualization is written.
    timeout_s : int
        Maximum time allowed for the operation, in seconds.
    labels : str, optional
        Node-label style used by the visualizer.
    reason_filter : str, optional
        Comma-separated reason kinds to keep in the visualization.
    no_ll : bool, optional
        Whether low-level actions should be hidden from output.

    Returns
    -------
    subprocess.CompletedProcess
        Result returned by `run_po_visualizer`.
    """
    cmd = [
        python_exec,
        str(po_viz_script),
        str(planner_log_path),
        "--output",
        str(output_html_path),
        "--labels",
        labels,
        "--reason-filter",
        reason_filter,
    ]
    if no_ll:
        cmd.append("--no-ll")

    logger.info(f"Generating PO HTML: {shlex.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
    )


def summarize_stn(stn: SimpleTemporalNetwork) -> None:
    """
    Print core statistics for the generated Simple Temporal Network.

    Parameters
    ----------
    stn : SimpleTemporalNetwork
        Simple Temporal Network instance to inspect or render.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    ordering_edges = sum(1 for _, _, data in stn.edges(data=True) if data.get("type") == "ordering")
    causal_edges = sum(1 for _, _, data in stn.edges(data=True) if data.get("type") == "causal_link")
    weighted_edges = sum(1 for _, _, data in stn.edges(data=True) if "weight" in data)

    logger.info("STN generated successfully. Summary:")
    logger.info(f"  STN nodes: {stn.number_of_nodes()}")
    logger.info(f"  STN edges: {stn.number_of_edges()}")
    logger.info(f"  STN ordering edges: {ordering_edges}")
    logger.info(f"  STN causal-link edges: {causal_edges}")
    logger.info(f"  STN weighted edges: {weighted_edges}")
    logger.info(f"  STN duration consistency: {stn.check_consistency_durations()}")


def summarize_stn_optimization(solution: Dict[str, Any], sample_actions: int) -> None:
    """
    Print optimization status and a sample of solved action intervals.

    Parameters
    ----------
    solution : Dict[str, Any]
        Optimization result dictionary produced by the STN solver.
    sample_actions : int
        Number of actions to include in summary output.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    logger.info("STN optimization completed. Summary:")
    logger.info(f"  Solver: {solution.get('solver')}")
    logger.info(f"  Status: {solution.get('status')}")
    logger.info(f"  Objective value: {solution.get('objective')}")
    logger.info(f"  Anchor node: {solution.get('anchor_node')}")
    logger.info(f"  Weighted constraints: {solution.get('weighted_constraints')}")
    logger.info(f"  Precedence constraints: {solution.get('precedence_constraints')}")
    if isinstance(solution.get("precedence_min_gap"), (int, float)):
        logger.info(f"  Precedence minimum gap: {solution.get('precedence_min_gap')}")

    scheduled_actions = solution.get("scheduled_actions", [])
    if isinstance(scheduled_actions, list) and scheduled_actions:
        logger.info(f"  Optimized action schedule ({len(scheduled_actions)} actions):")
        for action in scheduled_actions:
            label = action.get("display_name") or action.get("action") or "action"
            start = action.get("start")
            end = action.get("end")
            duration = action.get("duration")
            if (
                isinstance(start, (int, float))
                and isinstance(end, (int, float))
                and isinstance(duration, (int, float))
            ):
                logger.info(
                    f"  - {label}: start={start:.6g}, end={end:.6g}, duration={duration:.6g}"
                )
            else:
                logger.info(f"  - {label}: {action}")

    actions = solution.get("actions", {})
    if not isinstance(actions, dict) or sample_actions <= 0:
        return

    # Sort by start time so the sample is easy to read as a chronological timeline.
    sortable_actions = []
    for action_name, values in actions.items():
        if not isinstance(values, dict):
            continue
        start_time = values.get("start")
        if isinstance(start_time, (int, float)):
            sortable_actions.append((action_name, values))
    sortable_actions.sort(key=lambda item: item[1].get("start", float("inf")))

    if not sortable_actions:
        return

    shown = sortable_actions[:sample_actions]
    logger.info(f"Sample optimized STN timepoint intervals ({len(shown)}):")
    for action_name, values in shown:
        start = values.get("start")
        end = values.get("end")
        duration = values.get("duration")
        logger.info(
            f"  - {action_name}: start={start:.6g}, end={end:.6g}, duration={duration:.6g}"
            if isinstance(start, (int, float)) and isinstance(end, (int, float)) and isinstance(duration, (int, float))
            else f"  - {action_name}: {values}"
        )


def parse_args() -> argparse.Namespace:
    """
    Define and parse command-line options for planner execution.

    Returns
    -------
    argparse.Namespace
        Result returned by `parse_args`.
    """
    root_dir = Path(__file__).resolve().parent
    default_kb = root_dir / "kb" / "crane.pl"
    default_src = root_dir / "prolog_planner" / "src"
    default_po_html = root_dir / "prolog_planner" / "po_graph_from_tp_planner.html"
    default_stn_html = root_dir / "prolog_planner" / "stn_graph_from_tp_planner.html"
    default_opt_stn_html = root_dir / "prolog_planner" / "opt_stn.html"
    default_bt_xml = root_dir / "prolog_planner" / "optimized_bt.xml"
    default_infeasibility_report = root_dir / "prolog_planner" / "stn_infeasibility_report.txt"

    parser = argparse.ArgumentParser(
        description=(
            "Run the Prolog planner and load the resulting partial-order information "
            "into a Python PartialOrderPlan object."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--kb",
        type=Path,
        default=default_kb,
        help=f"Path to the Prolog KB file (default: {default_kb}).",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=default_src,
        help=f"Path to Prolog source directory containing bfs_planner/mappings/enablers (default: {default_src}).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum BFS depth; use -1 for unbounded search (default: 10).",
    )
    parser.add_argument(
        "--swipl",
        default="swipl",
        help="SWI-Prolog executable (default: swipl).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Planner timeout in seconds; use -1 for no timeout (default: 180).",
    )
    parser.add_argument(
        "--stack-limit",
        default="10G",
        help="SWI-Prolog stack limit passed as --stack_limit.",
    )
    parser.add_argument(
        "--save-log",
        type=Path,
        default=None,
        help="Optional file path to save the full Python planner log.",
    )
    parser.add_argument(
        "--save-prolog-log",
        type=Path,
        default=None,
        help="Optional file path to save raw Prolog planner stdout/stderr.",
    )
    parser.add_argument(
        "--from-prolog-log",
        type=Path,
        default=None,
        help=(
            "Replay planner output from a Prolog log file instead of invoking SWI-Prolog. "
            "The file must contain the same full output that SWI-Prolog would emit."
        ),
    )
    parser.add_argument(
        "--po-html",
        type=Path,
        default=default_po_html,
        help=f"Output HTML path for PO visualization (default: {default_po_html}).",
    )
    parser.add_argument(
        "--no-po-html",
        action="store_true",
        help="Disable PO HTML generation step.",
    )
    parser.add_argument(
        "--po-labels",
        choices=["id", "short", "full"],
        default="short",
        help="Node label style for PO visualization (default: short).",
    )
    parser.add_argument(
        "--po-reason-filter",
        default="all",
        help="Comma-separated enabler reason kinds to keep in PO visualization (default: all).",
    )
    parser.add_argument(
        "--po-no-ll",
        action="store_true",
        help="Hide low-level action nodes in PO visualization.",
    )
    parser.add_argument(
        "--no-stn",
        action="store_true",
        help="Disable conversion from PartialOrderPlan to STN.",
    )
    parser.add_argument(
        "--stn-default-min",
        type=float,
        default=1e-3,
        help="Default minimum duration used in STN conversion (default: 1e-3).",
    )
    parser.add_argument(
        "--stn-default-max",
        type=float,
        default=float("inf"),
        help="Default maximum duration used in STN conversion (default: inf).",
    )
    parser.add_argument(
        "--stn-html",
        type=Path,
        default=default_stn_html,
        help=f"Output HTML path for STN visualization (default: {default_stn_html}).",
    )
    parser.add_argument(
        "--stn-html-max-nodes",
        type=int,
        default=0,
        help="Maximum number of STN nodes shown in HTML (default: 0, meaning all nodes).",
    )
    parser.add_argument(
        "--no-stn-html",
        action="store_true",
        help="Disable STN HTML generation.",
    )
    parser.add_argument(
        "--optimize-stn",
        action="store_true",
        help="Optimize STN time assignments via OR-Tools linear solver.",
    )
    parser.add_argument(
        "--optimize-objective",
        choices=["makespan", "end_time", "none"],
        default="makespan",
        help="Objective for STN optimization (default: makespan).",
    )
    parser.add_argument(
        "--optimize-integer-time",
        action="store_true",
        help="Use integer time variables (MILP) instead of continuous variables.",
    )
    parser.add_argument(
        "--optimize-allow-negative-time",
        action="store_true",
        help="Allow negative time values in optimization (default: disabled).",
    )
    parser.add_argument(
        "--optimize-no-precedence",
        action="store_true",
        help="Do not convert unweighted ordering/causal edges into precedence constraints.",
    )
    parser.add_argument(
        "--optimize-precedence-gap",
        type=float,
        default=1e-3,
        help="Minimum delay enforced on precedence constraints (default: 1e-3).",
    )
    parser.add_argument(
        "--optimize-solver",
        default=None,
        help="Optional OR-Tools backend name (e.g., GLOP, CBC_MIXED_INTEGER_PROGRAMMING).",
    )
    parser.add_argument(
        "--optimize-sample-actions",
        type=int,
        default=10,
        help="How many optimized actions to print (default: 10).",
    )
    parser.add_argument(
        "--optimize-report-latex",
        type=Path,
        default=None,
        help="Optional output path for a LaTeX report of the optimization model constraints.",
    )
    parser.add_argument(
        "--opt-stn-html",
        type=Path,
        default=default_opt_stn_html,
        help=f"Output HTML path for optimized STN visualization (default: {default_opt_stn_html}).",
    )
    parser.add_argument(
        "--opt-stn-graph-html",
        type=Path,
        default=None,
        help=(
            "Output HTML path for the optimized STN execution graph. "
            "When omitted, a sibling of --opt-stn-html named '<stem>_execution_graph.html' is written."
        ),
    )
    parser.add_argument(
        "--no-opt-stn-html",
        action="store_true",
        help="Disable optimized STN HTML generation after optimization.",
    )
    parser.add_argument(
        "--no-opt-stn-graph-html",
        action="store_true",
        help="Disable the optimized STN execution graph HTML generation.",
    )
    parser.add_argument(
        "--bt-xml",
        type=Path,
        default=None,
        help=(
            "Optional output XML path for an MP/BT behavior tree extracted from the optimized STN "
            f"(suggested default path: {default_bt_xml})."
        ),
    )
    parser.add_argument(
        "--bt-robot-ids",
        default=None,
        help="Optional list or comma-separated string of robot IDs.",
    )
    parser.add_argument(
        "--bt-save-viz",
        type=Path,
        default=None,
        help=(
            "Optional output path for a Cytoscape behavior-tree HTML visualization. "
            "Supported suffixes: .html."
        ),
    )
    parser.add_argument(
        "--optimize-infeasibility-report",
        type=Path,
        default=default_infeasibility_report,
        help=(
            "Path for the STN infeasibility diagnostics report written when optimization fails "
            f"(default: {default_infeasibility_report})."
        ),
    )
    parser.add_argument(
        "--no-assumptions",
        action="store_true",
        help="Exclude assumption(...) enabler edges from the loaded PartialOrderPlan.",
    )
    parser.add_argument(
        "--no-causal",
        action="store_true",
        help="Exclude causal(...) enabler edges from the loaded PartialOrderPlan.",
    )
    parser.add_argument(
        "--enable-graph-debug",
        action="store_true",
        help="Enable Prolog graph debug trace while running planner.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Emit Prolog/Python timing lines and print a timings recap at the end.",
    )
    args = parser.parse_args()
    if args.max_depth < -1:
        parser.error("--max-depth must be -1 for unbounded search or a non-negative integer.")
    if args.timeout < -1 or args.timeout == 0:
        parser.error("--timeout must be -1 for no timeout or a positive integer.")
    return args
