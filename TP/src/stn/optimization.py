"""STN optimization model construction and solving helpers."""

from typing import Any, Dict, Optional, Tuple

import sys
from pathlib import Path
import re

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.logger import logger

try:
    from .utilities import SNAP_RE
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from stn.utilities import SNAP_RE

class STNOptimizationMixin:
    """Optimization helpers mixed into SimpleTemporalNetwork."""

    def optimize_time_assignments(
            self,
            objective: str = "makespan",
            anchor_nodes: Optional[Tuple[str, str]] = ("INIT", "END"),
            enforce_precedence_for_unweighted: bool = True,
            precedence_min_gap: float = 1e-3,
            integer_time: bool = False,
            solver_name: Optional[str] = None,
            infeasibility_report_path: Optional[str] = None,
            snap_re : str = SNAP_RE,
        ) -> Dict[str, Any]:
        """
        Optimize STN time assignments with OR-Tools linear/MIP backends.

        Parameters
        ----------
        objective : str, optional
            Optimization objective mode (`makespan`, `end_time`, `none`).
            `none` is used by the planner's low-level-sequence mode; the STN
            topology is already fixed, so timestamps are optimized by minimizing
            the end anchor.
        anchor_nodes : Optional[Tuple[str, str]], optional
            Nodes (A, B) fixed at time zero and at end time, respectively (with fallback resolution).
        enforce_precedence_for_unweighted : bool, optional
            Whether ordering/causal edges are converted into precedence constraints.
        precedence_min_gap : float, optional
            Minimum delay enforced for precedence constraints (`t_to >= t_from + gap`).
        integer_time : bool, optional
            Solve with integer decision variables instead of continuous variables.
        solver_name : Optional[str]
            Explicit OR-Tools backend name (for example `GLOP`, `CBC_MIXED_INTEGER_PROGRAMMING`).
        infeasibility_report_path : Optional[str]
            Optional path for writing an infeasibility diagnostic report when solve fails.

        Returns
        -------
        Dict[str, Any]
            Structured optimization result including assignments and schedule extraction.
        """
        try:
            from ortools.linear_solver import pywraplp
        except ImportError as exc:
            raise ImportError(
                "OR-Tools is required for STN optimization. Install it with: pip install ortools"
            ) from exc

        if self.number_of_nodes() == 0:
            raise ValueError("Cannot optimize an empty STN.")

        # Find anchor nodes
        if not (anchor_nodes and len(anchor_nodes) == 2 and anchor_nodes[0] != anchor_nodes[1]):
            raise ValueError("anchor_nodes must be a tuple of two node different identifiers (for start and end anchors).")
        
        start_anchor = self._resolve_anchor_node(anchor_nodes[0])
        end_anchor = self._resolve_anchor_node(anchor_nodes[1])
        logger.debug(f"Found anchors: requested='{anchor_nodes[0]}', effective='{start_anchor}'")
        logger.debug(f"Found anchors: requested='{anchor_nodes[1]}', effective='{end_anchor}'")

        # Add delay between precedence-linked events if requested
        precedence_min_gap = float(precedence_min_gap)
        if precedence_min_gap < 0.0:
            raise ValueError("precedence_min_gap must be >= 0.")

        # Instantiate solver
        if solver_name is None:
            solver_name = "CBC_MIXED_INTEGER_PROGRAMMING" if integer_time else "GLOP"
            logger.info(f"No solver_name provided, defaulting to '{solver_name}' based on integer_time={integer_time}.")
        solver = pywraplp.Solver.CreateSolver(solver_name)
        if solver is None:
            raise ValueError(f"Could not create OR-Tools solver backend '{solver_name}'.")

        # Instantiate time variables for each node, with appropriate bounds.
        lb = 0.0
        ub = solver.infinity()
        logger.debug(f"Time variable bounds set to: [{lb}, {ub}].")
        time_vars = {}
        for idx, node in enumerate(self.nodes()):
            var_name = f"t_{idx}"
            if integer_time:
                time_vars[node] = solver.IntVar(lb, ub, var_name)
            else:
                time_vars[node] = solver.NumVar(lb, ub, var_name)

        logger.debug(f"Created {len(time_vars)} time variables.")
        logger.debug("Adding constraints...")

        # Fix start anchor to 0.
        solver.Add(time_vars[start_anchor] == 0.0)

        weighted_edges = []
        precedence_edges = []

        # Add constraints based on edges
        for from_node, to_node, data in self.edges(data=True):
            if "type" not in data:
                raise ValueError(f"Edge ({from_node} -> {to_node}) is missing required 'type' attribute.")
            
            if data.get("type") in ("ordering", "causal_link") and enforce_precedence_for_unweighted:
                # Enforce strict precedence with minimum gap if requested.
                solver.Add(time_vars[to_node] >= time_vars[from_node] + precedence_min_gap)
                precedence_edges.append({"from": from_node, "to": to_node, "type": data.get("type")})

            elif data.get("type") == "mock":
                if from_node == to_node:
                    logger.error(f"Mock edge from node '{from_node}' to itself is not allowed.")
                elif (from_node == start_anchor and to_node == end_anchor) or (from_node == end_anchor and to_node == start_anchor):
                    logger.error(f"Mock edge cannot directly connect the start anchor '{start_anchor}' and end anchor '{end_anchor}'.")
                if from_node == start_anchor:
                    # Enforce any node must come after the start anchor.
                    solver.Add(time_vars[to_node] >= time_vars[from_node] + precedence_min_gap)
                    precedence_edges.append({"from": from_node, "to": to_node, "type": data.get("type")})
                elif to_node == end_anchor:
                    # Enforce any node must come before the end anchor.
                    solver.Add(time_vars[from_node] <= time_vars[to_node] - precedence_min_gap)
                    precedence_edges.append({"from": from_node, "to": to_node, "type": data.get("type")})

            elif data.get("type") == "duration":
                weight = data.get("weight")
                if weight == 0:
                    logger.warning(f"Duration edge from '{from_node}' to '{to_node}' has zero weight, skipping constraint.")
                elif weight > 0:
                    # This is the upper bound on the duration of the action.
                    solver.Add(time_vars[to_node] - time_vars[from_node] <= weight)
                    weighted_edges.append({"from": from_node, "to": to_node, "weight": weight, "type": data.get("type")})
                    logger.debug(f"Added upper bound constraint: t_{to_node} - t_{from_node} <= {weight}")
                elif weight < 0:
                    # This is the lower bound on the duration of the action.
                    solver.Add(time_vars[from_node] - time_vars[to_node] >= -weight)
                    weighted_edges.append({"from": from_node, "to": to_node, "weight": weight, "type": data.get("type")})
                    logger.debug(f"Added lower bound constraint: t_{from_node} - t_{to_node} >= {-weight}")

        # Set objective
        objective_expr = solver.Objective()
        if objective in {"end_time", "none"}:
            objective_expr.SetCoefficient(time_vars[end_anchor], 1.0)
            objective_expr.SetMinimization()
        elif objective == "makespan":
            logger.error("The 'makespan' objective is not yet implemented. Please use 'end_time'.")
            raise NotImplementedError("The 'makespan' objective is not yet implemented. Please use 'end_time'.")
        else:
            raise ValueError("objective must be one of: 'makespan', 'end_time', 'none'.")
        
        # Set-up the solver
        logger.debug(f"Solving optimization problem with objective='{objective}', anchor_nodes={anchor_nodes}, enforce_precedence_for_unweighted={enforce_precedence_for_unweighted}, precedence_min_gap={precedence_min_gap}, integer_time={integer_time}, solver_name='{solver_name}'...")
        status = solver.Solve()
        status_names = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
            pywraplp.Solver.ABNORMAL: "ABNORMAL",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
        }
        status_name = status_names.get(status, str(status))
        logger.info(f"Solver finished with status: {status_name}.")

        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            report_note = ""
            if infeasibility_report_path:
                try:
                    report_info = self.export_infeasibility_report(
                        path=infeasibility_report_path,
                        status_name=status_name,
                        objective=objective,
                        requested_anchor=anchor_nodes[0],
                        effective_anchor=start_anchor,
                        weighted_edges=weighted_edges,
                        precedence_edges=precedence_edges,
                        non_negative_time=True,
                        precedence_min_gap=precedence_min_gap,
                        end_must_be_latest=("END" in self.nodes()),
                        integer_time=integer_time,
                        solver_name=solver_name,
                    )
                    self.to_cytoscape_html(f"infeasible_graph.html")
                    core_note = ""
                    if report_info.get("unsat_core_available"):
                        core_note = (
                            f" - Unsat core: {report_info.get('unsat_core_size')} "
                            f"constraint(s) [{report_info.get('unsat_core_kind')}]"
                        )
                    report_note = (
                        f" Infeasibility report written to: {report_info.get('path')}"
                        f"{core_note}  -  HTML graph: infeasible_graph.html"
                    )
                except Exception as report_exc:
                    report_note = f" Failed to write infeasibility report: {report_exc}"
            raise ValueError(f"STN optimization failed with status: {status_name}.{report_note}")

        primary_objective_value = float(objective_expr.Value())
        primary_end_time = float(time_vars[end_anchor].solution_value())
        secondary_objective_value = None

        # Lexicographic tie-breaker: after minimizing END, keep that makespan
        # fixed and pull executable timepoints as early as possible. Without
        # this, LP solvers may return any equally optimal vertex, including
        # schedules where independent root branches start arbitrarily late.
        if objective in {"end_time", "none"}:
            solver.Add(time_vars[end_anchor] <= primary_end_time + 1.0e-9)
            solver.Add(time_vars[end_anchor] >= primary_end_time - 1.0e-9)
            objective_expr.Clear()

            secondary_terms = []
            snap_pattern_for_secondary = re.compile(snap_re)
            for node in self.nodes():
                if node in {start_anchor, end_anchor}:
                    continue
                node_label = str(node)
                match = snap_pattern_for_secondary.match(node_label)
                if match and match.group("type").lower() == "start":
                    secondary_terms.append(node)

            if not secondary_terms:
                secondary_terms = [
                    node
                    for node in self.nodes()
                    if node not in {start_anchor, end_anchor}
                ]

            for node in secondary_terms:
                objective_expr.SetCoefficient(time_vars[node], 1.0)
            objective_expr.SetMinimization()

            secondary_status = solver.Solve()
            secondary_status_name = status_names.get(secondary_status, str(secondary_status))
            logger.info(
                "Secondary STN optimization finished with status: "
                f"{secondary_status_name}."
            )
            if secondary_status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
                raise ValueError(
                    "Secondary STN optimization failed with status: "
                    f"{secondary_status_name}."
                )
            status = secondary_status
            status_name = secondary_status_name
            secondary_objective_value = float(objective_expr.Value())

        assignments = {str(node): float(time_vars[node].solution_value()) for node in self.nodes()}
        for node_name, time_value in assignments.items():
            if node_name in self.nodes():
                self.nodes[node_name]["optimized_time"] = time_value

        snap_pattern = re.compile(snap_re)
        scheduled_actions = []
        scheduled_action_records = []

        # Get timestamp for all actions and save them in the graph for later use in visualization and reporting.
        actions_in_assignment = [(node, timestamp) for node, timestamp in assignments.items()]
        for i in range(len(actions_in_assignment)):
            node, timestamp = actions_in_assignment[i]
            if node in ["INIT", "END"]:
                continue

            match = snap_pattern.match(node)
            if match and match["type"] == "start":
                action_name = match["action_name"]

                # Look for the corresponding end action
                for j in range(i + 1, len(actions_in_assignment)):
                    end_node, end_timestamp = actions_in_assignment[j]
                    end_match = snap_pattern.match(end_node)
                    if end_match and end_match["type"] == "end" and end_match["action_name"] == action_name:
                        scheduled_actions.append((action_name, timestamp, end_timestamp, node, end_node))
                        scheduled_action_records.append(
                            {
                                "action": action_name,
                                "display_name": action_name,
                                "start": float(timestamp),
                                "end": float(end_timestamp),
                                "duration": float(end_timestamp - timestamp),
                                "start_node": node,
                                "end_node": end_node,
                            }
                        )
                        break
        
        self.graph["optimized_assignments"] = assignments
        self.graph["scheduled_actions"] = scheduled_actions
        actions_by_node = {
            str(record["start_node"]): record
            for record in scheduled_action_records
        }

        return {
            "status": status_name,
            "objective": primary_objective_value,
            "primary_objective": primary_objective_value,
            "secondary_objective": secondary_objective_value,
            "solver": solver_name,
            "anchor_node": str(start_anchor),
            "start_anchor_node": str(start_anchor),
            "end_anchor_node": str(end_anchor),
            "weighted_constraints": len(weighted_edges),
            "precedence_constraints": len(precedence_edges),
            "precedence_min_gap": precedence_min_gap,
            "times": assignments,
            "timepoints": actions_in_assignment,
            "actions": actions_by_node,
            "scheduled_actions": scheduled_action_records,
        }
