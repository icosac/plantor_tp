#!/usr/bin/env python3

"""
Run the Prolog planner, build partial-order/STN structures, and emit summaries and visualizations.
"""

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from utility.logger import logger

from planner_support import (
    build_prolog_goal,
    parse_args,
    parse_duration_constraints,
    parse_durative_actions_links,
    run_po_visualizer,
    run_prolog,
    summarize_stn,
    summarize_stn_optimization,
)
from src.partial_order import PartialOrderPlan
from src.stn import SimpleTemporalNetwork


def _record_profile(
    label: str,
    started_at: float,
    python_timings: List[Dict[str, Any]],
    emit: bool,
) -> float:
    """
    Record elapsed wall-clock time for one Python pipeline phase.

    Parameters
    ----------
    label : str
        Profile phase name.
    started_at : float
        Value returned by time.perf_counter() at phase start.
    python_timings : List[Dict[str, Any]]
        Mutable timing collection for the final recap.
    emit : bool
        Whether to also log the individual profile line immediately.

    Returns
    -------
    float
        Elapsed wall-clock seconds.
    """
    elapsed_s = time.perf_counter() - started_at
    python_timings.append({"phase": label, "wall_seconds": elapsed_s})
    if emit:
        logger.info(f"[profile] python.{label} wall_seconds={elapsed_s:.6f}")
    return elapsed_s


def _parse_prolog_profiles(planner_log: str) -> List[Dict[str, Any]]:
    """
    Parse profile lines emitted by Prolog call_time/2 wrappers.

    Parameters
    ----------
    planner_log : str
        Raw planner output.

    Returns
    -------
    List[Dict[str, Any]]
        Parsed Prolog timing rows.
    """
    profile_re = re.compile(
        r"^\[profile\]\s+prolog\.(?P<phase>\S+)\s+"
        r"time\{cpu:(?P<cpu>[-+0-9.eE]+),"
        r"inferences:(?P<inferences>\d+),"
        r"wall:(?P<wall>[-+0-9.eE]+)\}"
    )
    rows: List[Dict[str, Any]] = []
    for line in planner_log.splitlines():
        match = profile_re.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "phase": match.group("phase"),
                "cpu_seconds": float(match.group("cpu")),
                "wall_seconds": float(match.group("wall")),
                "inferences": int(match.group("inferences")),
            }
        )
    return rows


def _save_bt_visualization(
    bt_xml_path: Path,
    output_path: Path,
    repository_root: Path,
) -> Dict[str, str]:
    """
    Save a Cytoscape HTML visualization for a generated behavior-tree XML file.

    Parameters
    ----------
    bt_xml_path : Path
        Path to an MP/BT XML file.
    output_path : Path
        Requested visualization output path.
    repository_root : Path
        Repository root, used to locate MP/BT.

    Returns
    -------
    Dict[str, str]
        Mapping from generated artifact kind to file path.
    """
    bt_module_dir = (repository_root / "MP" / "BT").resolve()
    if str(bt_module_dir) not in sys.path:
        sys.path.insert(0, str(bt_module_dir))

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = output_path.suffix.lower()
    if suffix == ".html":
        from bt_visualization import export_bt_cytoscape_html

        export_bt_cytoscape_html(
            xml_path=str(bt_xml_path),
            output_path=str(output_path),
            title=output_path.stem or "Behavior Tree",
        )
        return {suffix.lstrip("."): str(output_path)}

    raise ValueError(
        "Unsupported BT visualization suffix "
        f"{output_path.suffix!r}. Use .html."
    )


def _log_profile_recap(python_timings: List[Dict[str, Any]], planner_log: str) -> None:
    """
    Print a compact profile recap from Python and Prolog timing records.

    Parameters
    ----------
    python_timings : List[Dict[str, Any]]
        Timing rows recorded in the Python runner.
    planner_log : str
        Raw planner output containing optional Prolog timing rows.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    prolog_timings = _parse_prolog_profiles(planner_log)
    logger.info("===========================TIMINGS RECAP===========================")
    if prolog_timings:
        logger.info("Prolog phases:")
        for row in prolog_timings:
            logger.info(
                "  - "
                f"{row['phase']}: wall={row['wall_seconds']:.6f}s, "
                f"cpu={row['cpu_seconds']:.6f}s, "
                f"inferences={row['inferences']}"
            )
    else:
        logger.info("Prolog phases: no profile rows captured.")

    if python_timings:
        logger.info("Python phases:")
        for row in python_timings:
            logger.info(f"  - {row['phase']}: wall={row['wall_seconds']:.6f}s")
    else:
        logger.info("Python phases: no profile rows captured.")
    logger.info("===================================================================")


def main() -> int:
    """
    Run planner execution, parsing, visualization, and optional STN optimization.

    Returns
    -------
    int
        Numeric result produced by this function.
    """
    args = parse_args()
    if args.save_log is not None:
        save_log_path = args.save_log.resolve()
        save_log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.change_output_dir_file(str(save_log_path.parent), save_log_path.name)
        logger.info(f"Saving full planner log to: {save_log_path}")

    planner_log = ""
    python_timings: List[Dict[str, Any]] = []
    pipeline_started_at = time.perf_counter()

    def profile(label: str, started_at: float) -> float:
        return _record_profile(
            label=label,
            started_at=started_at,
            python_timings=python_timings,
            emit=args.profile,
        )

    def finish(exit_code: int) -> int:
        profile("total_pipeline", pipeline_started_at)
        if args.profile:
            _log_profile_recap(python_timings, planner_log)
        return exit_code

    root_dir = Path(__file__).resolve().parent
    kb_file = args.kb.resolve()
    src_dir = args.src_dir.resolve()
    po_viz_script = (root_dir / "prolog_planner" / "tools" / "po_viz.py").resolve()
    from_prolog_log_path: Optional[Path] = (
        args.from_prolog_log.resolve()
        if args.from_prolog_log is not None
        else None
    )

    # Validate required on-disk inputs. In replay mode the Prolog output is
    # already available, so KB/source files are not needed.
    if from_prolog_log_path is None:
        if not kb_file.is_file():
            logger.error(f"KB file not found: {kb_file}")
            return finish(2)
        for required in ["bfs_planner.pl", "mappings.pl", "enablers.pl"]:
            required_path = src_dir / required
            if not required_path.is_file():
                logger.error(f"Missing required Prolog source: {required_path}")
                return finish(2)
    elif not from_prolog_log_path.is_file():
        logger.error(f"Prolog log file not found: {from_prolog_log_path}")
        return finish(2)
    if not args.no_po_html and not po_viz_script.is_file():
        logger.error(f"PO visualizer not found: {po_viz_script}")
        return finish(2)

    inner_timeout_s = None if args.timeout == -1 else args.timeout
    if from_prolog_log_path is not None:
        logger.info("=================REPLAYING PROLOG PLANNER LOG=================")
        log_read_started_at = time.perf_counter()
        planner_log = from_prolog_log_path.read_text(encoding="utf-8").strip()
        profile("prolog_log_replay", log_read_started_at)
        logger.info(f"Loaded Prolog planner log from: {from_prolog_log_path}")
    else:
        logger.info("==============RUNNING PROLOG PLANNER WITH CONFIGURATION==============")
        goal = build_prolog_goal(
            kb_file=kb_file,
            src_dir=src_dir,
            max_depth=args.max_depth,
            enable_graph_debug=args.enable_graph_debug,
            profile=args.profile,
        )

        try:
            prolog_started_at = time.perf_counter()
            result = run_prolog(
                swipl=args.swipl,
                goal=goal,
                timeout_s=inner_timeout_s,
                stack_limit=args.stack_limit,
            )
        except FileNotFoundError:
            profile("prolog_subprocess", prolog_started_at)
            logger.error(f"Could not execute '{args.swipl}'.")
            return finish(2)
        except subprocess.TimeoutExpired:
            profile("prolog_subprocess", prolog_started_at)
            logger.error(f"Planner timed out after {args.timeout}s.")
            return finish(124)
        profile("prolog_subprocess", prolog_started_at)

        # Keep a single merged log so parsers can reason over all emitted sections.
        planner_log = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()

    log_file_path: Optional[Path] = None
    temp_log_path: Optional[Path] = None
    if args.save_prolog_log is not None:
        save_prolog_log_started_at = time.perf_counter()
        save_path = args.save_prolog_log.resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(planner_log + ("\n" if planner_log else ""), encoding="utf-8")
        logger.info(f"Saved Prolog planner log to: {save_path}")
        profile("save_prolog_planner_log", save_prolog_log_started_at)
        log_file_path = save_path
    elif from_prolog_log_path is not None:
        log_file_path = from_prolog_log_path

    if from_prolog_log_path is None and result.returncode != 0:
        logger.error(f"SWI-Prolog exited with code {result.returncode}.")
        if planner_log:
            logger.error(planner_log)
        return finish(result.returncode)

    plan_found = "[planner] Plan found" in planner_log
    logger.info(f"Plan found: {plan_found}")
    if not plan_found:
        logger.warning("No plan found in Prolog output.")
        if planner_log:
            logger.info(planner_log)
        return finish(1)

    logger.info("Full planner log:\n" + planner_log)

    logger.info("=================GENERATING PARTIAL ORDER STRUCTURE=================")

    try:
        po_parse_started_at = time.perf_counter()
        if args.optimize_objective == "none":
            logger.info(
                "Optimization objective is 'none'; building a total-order "
                "low-level sequence and ignoring enabler edges for STN construction."
            )
            po_plan = PartialOrderPlan.from_low_level_sequence(planner_log)
        else:
            po_plan = PartialOrderPlan.from_prolog(
                planner_log,
                include_assumptions=not args.no_assumptions,
                include_causal=not args.no_causal,
            )
        profile("partial_order_construction", po_parse_started_at)
    except (RuntimeError, ValueError) as exc:
        profile("partial_order_construction", po_parse_started_at)
        logger.error(f"Failed to parse partial order from Prolog output: {exc}")
        if planner_log:
            logger.error(planner_log)
        return finish(3)
    
    po_plan.summarize()
    
    if not args.no_po_html:
        # The visualizer works from a file path; emit a temp log if user did not request one.
        if log_file_path is None:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".txt",
                prefix="tp_planner_log_",
                delete=False,
            ) as tmp_handle:
                tmp_handle.write(planner_log + ("\n" if planner_log else ""))
                temp_log_path = Path(tmp_handle.name).resolve()
            log_file_path = temp_log_path

        po_html_path = args.po_html.resolve()
        po_html_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            po_viz_started_at = time.perf_counter()
            viz_result = run_po_visualizer(
                python_exec=sys.executable,
                po_viz_script=po_viz_script,
                planner_log_path=log_file_path,
                output_html_path=po_html_path,
                timeout_s=inner_timeout_s,
                labels=args.po_labels,
                reason_filter=args.po_reason_filter,
                no_ll=args.po_no_ll,
            )
            profile("partial_order_html_generation", po_viz_started_at)
        except subprocess.TimeoutExpired:
            profile("partial_order_html_generation", po_viz_started_at)
            logger.error(f"PO visualization timed out after {args.timeout}s.")
            return finish(4)
        finally:
            if temp_log_path is not None and temp_log_path.exists():
                temp_log_path.unlink(missing_ok=True)

        if viz_result.returncode != 0:
            logger.error(f"PO visualizer exited with code {viz_result.returncode}.")
            viz_log = ((viz_result.stdout or "") + "\n" + (viz_result.stderr or "")).strip()
            if viz_log:
                logger.error(viz_log)
            return finish(4)
        viz_log = ((viz_result.stdout or "") + "\n" + (viz_result.stderr or "")).strip()
        if viz_log:
            logger.info(viz_log)
        logger.info(f"PO HTML visualization written to: {po_html_path}")

    po_consistency_started_at = time.perf_counter()
    po_is_consistent = po_plan.check_consistency()
    profile("partial_order_consistency_check", po_consistency_started_at)
    if not po_is_consistent:
        logger.error("Parsed partial order plan is inconsistent (e.g., cyclic).")
        return finish(3)


    if not args.no_stn:
        logger.info("======================BUILDING STN STRUCTURE======================")

        # Build an STN from the partial-order plan, then enrich it with parsed duration bounds.
        stn_generation_started_at = time.perf_counter()
        stn = SimpleTemporalNetwork()
        stn.from_partial_order(
            po_plan,
            default_min=args.stn_default_min,
            default_max=args.stn_default_max,
        )
        profile("stn_generation", stn_generation_started_at)

        duration_parse_started_at = time.perf_counter()
        duration_constraints = parse_duration_constraints(planner_log)
        profile("duration_constraint_parsing", duration_parse_started_at)
        logger.info(f"Parsed duration constraints: {len(duration_constraints)}")
        link_parse_started_at = time.perf_counter()
        linked_actions = parse_durative_actions_links(planner_log)
        profile("durative_link_parsing", link_parse_started_at)
        logger.info(f"Parsed durative action links: {len(linked_actions)}")
        
        if duration_constraints and linked_actions:
            add_constraints_started_at = time.perf_counter()
            stn.add_time_constraints({"durations": duration_constraints, "linked_actions": linked_actions})
            profile("stn_time_constraint_application", add_constraints_started_at)
        else:
            logger.warning("No duration constraints found; using default STN bounds.")
        
        summarize_stn(stn)

        if args.optimize_report_latex is not None:
            report_path = args.optimize_report_latex.resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                report_started_at = time.perf_counter()
                report_info = stn.export_optimization_report_latex(
                    path=str(report_path),
                    objective=args.optimize_objective,
                    anchor_node="INIT",
                    enforce_precedence_for_unweighted=not args.optimize_no_precedence,
                    integer_time=args.optimize_integer_time,
                    non_negative_time=not args.optimize_allow_negative_time,
                    solver_name=args.optimize_solver,
                )
                profile("stn_optimization_latex_report", report_started_at)
            except Exception as exc:
                profile("stn_optimization_latex_report", report_started_at)
                logger.error(f"Could not write optimization LaTeX report: {exc}")
                return finish(6)
            logger.info(
                "STN optimization LaTeX report written to: "
                f"{report_info.get('path')} "
                f"(weighted={report_info.get('weighted_constraints')}, "
                f"precedence={report_info.get('precedence_constraints')})"
            )

        if args.optimize_stn:
            logger.info("=====================OPTIMIZING STN STRUCTURE=====================")
            if not args.no_stn_html:
                stn_html_path = args.stn_html.resolve()
                stn_html_path.parent.mkdir(parents=True, exist_ok=True)
                html_node_limit = None if args.stn_html_max_nodes <= 0 else args.stn_html_max_nodes
                stn_html_started_at = time.perf_counter()
                stn.to_cytoscape_html(
                    str(stn_html_path),
                    title="Simple Temporal Network",
                    max_nodes=html_node_limit,
                )
                profile("stn_html_generation", stn_html_started_at)
                logger.info(f"STN HTML visualization written to: {stn_html_path}")

            infeasibility_report_path = (
                args.optimize_infeasibility_report.resolve()
                if args.optimize_infeasibility_report is not None
                else None
            )
            if infeasibility_report_path is not None:
                infeasibility_report_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                stn_optimization_started_at = time.perf_counter()
                optimization_result = stn.optimize_time_assignments(
                    objective=args.optimize_objective,
                    anchor_nodes=("INIT", "END"),
                    enforce_precedence_for_unweighted=not args.optimize_no_precedence,
                    precedence_min_gap=args.optimize_precedence_gap,
                    integer_time=args.optimize_integer_time,
                    solver_name=args.optimize_solver,
                    infeasibility_report_path=(
                        str(infeasibility_report_path) if infeasibility_report_path is not None else None
                    ),
                )
                profile("stn_optimization", stn_optimization_started_at)
            except Exception as exc:
                profile("stn_optimization", stn_optimization_started_at)
                logger.error(f"ERROR: STN optimization failed: {exc.with_traceback(exc.__traceback__)}")  
                return finish(5)
            
            summarize_stn_optimization(
                optimization_result,
                sample_actions=max(args.optimize_sample_actions, 0),
            )

            if not args.no_opt_stn_html:
                # Export a dedicated HTML view using solved timestamps.
                opt_stn_html_path = args.opt_stn_html.resolve()
                opt_stn_html_path.parent.mkdir(parents=True, exist_ok=True)

                opt_stn_html_started_at = time.perf_counter()
                stn.to_optimized_timeline_html(
                    str(opt_stn_html_path),
                    title="Optimized Simple Temporal Network",
                )
                profile("optimized_stn_html_generation", opt_stn_html_started_at)
                logger.info(
                    "Optimized STN HTML visualization written to: "
                    f"{opt_stn_html_path}"
                )

                if not args.no_opt_stn_graph_html:
                    opt_stn_graph_html_path = (
                        args.opt_stn_graph_html.resolve()
                        if args.opt_stn_graph_html is not None
                        else opt_stn_html_path.with_name(f"{opt_stn_html_path.stem}_execution_graph.html")
                    )
                    opt_stn_graph_html_path.parent.mkdir(parents=True, exist_ok=True)
                    opt_stn_graph_html_started_at = time.perf_counter()
                    html_node_limit = None if args.stn_html_max_nodes <= 0 else args.stn_html_max_nodes
                    stn.to_timepoint_graph_html(
                        str(opt_stn_graph_html_path),
                        title="Optimized STN Execution Graph",
                        max_nodes=html_node_limit,
                        time_assignments=optimization_result.get("times"),
                    )
                    profile("optimized_stn_graph_html_generation", opt_stn_graph_html_started_at)
                    logger.info(
                        "Optimized STN execution graph HTML written to: "
                        f"{opt_stn_graph_html_path}"
                    )

            if args.bt_xml is not None or args.bt_save_viz is not None:
                bt_temp_dir = None
                try:
                    if args.bt_xml is not None:
                        bt_xml_path = args.bt_xml.resolve()
                        bt_xml_path.parent.mkdir(parents=True, exist_ok=True)
                    else:
                        bt_temp_dir = tempfile.TemporaryDirectory(prefix="plantor_bt_")
                        bt_xml_path = Path(bt_temp_dir.name) / "optimized_bt.xml"

                    bt_xml_started_at = time.perf_counter()
                    stn.to_xml_bt(
                        filename=str(bt_xml_path),
                        robot_ids=args.bt_robot_ids,
                    )
                    profile("bt_xml_generation", bt_xml_started_at)
                    if args.bt_xml is not None:
                        logger.info(f"Optimized STN behavior-tree XML written to: {bt_xml_path}")

                    if args.bt_save_viz is not None:
                        bt_viz_path = args.bt_save_viz.resolve()
                        bt_viz_started_at = time.perf_counter()
                        try:
                            bt_viz_outputs = _save_bt_visualization(
                                bt_xml_path=bt_xml_path,
                                output_path=bt_viz_path,
                                repository_root=root_dir.parent,
                            )
                        except Exception as exc:
                            profile("bt_visualization_generation", bt_viz_started_at)
                            logger.error(f"ERROR: BT visualization generation failed: {exc}")
                            return finish(7)
                        profile("bt_visualization_generation", bt_viz_started_at)
                        logger.info(
                            "Optimized STN behavior-tree visualization written to: "
                            f"{bt_viz_outputs}"
                        )
                finally:
                    if bt_temp_dir is not None:
                        bt_temp_dir.cleanup()

        

    return finish(0)


if __name__ == "__main__":
    raise SystemExit(main())
