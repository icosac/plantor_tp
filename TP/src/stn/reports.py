"""STN infeasibility report and utilities."""

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx


class STNReportsMixin:
    """Reporting helpers mixed into SimpleTemporalNetwork."""

    @staticmethod
    def _latex_escape(text: str) -> str:
        """
        Escape LaTeX-sensitive characters.

        Parameters
        ----------
        text : str
            Input text to escape for LaTeX rendering.

        Returns
        -------
        str
            Escaped LaTeX-safe string.
        """
        mapping = {
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
        return "".join(mapping.get(ch, ch) for ch in str(text))

    @staticmethod
    def _format_bound(value: float) -> str:
        """
        Format finite and infinite numeric bounds for reporting.

        Parameters
        ----------
        value : float
            Numeric value to format.

        Returns
        -------
        str
            Human-readable finite/infinite bound string.
        """
        if math.isinf(value):
            return r"\infty" if value > 0 else r"-\infty"
        return f"{value:g}"

    def export_infeasibility_report(
            self,
            path: str,
            status_name: str,
            objective: str,
            requested_anchor: Optional[str],
            effective_anchor: str,
            weighted_edges: List[Dict[str, Any]],
            precedence_edges: List[Dict[str, Any]],
            non_negative_time: bool,
            precedence_min_gap: float,
            end_must_be_latest: bool,
            integer_time: bool,
            solver_name: Optional[str],
            max_constraints: int = 500,
        ) -> Dict[str, Any]:
        """
        Export a plain-text diagnostics report for failed STN optimization.

        Parameters
        ----------
        path : str
            Output path for the report file.
        status_name : str
            Solver status label.
        objective : str
            Objective mode used for optimization.
        requested_anchor : Optional[str]
            Anchor requested by caller.
        effective_anchor : str
            Resolved anchor actually used.
        weighted_edges : List[Dict[str, Any]]
            Weighted optimization constraints.
        precedence_edges : List[Dict[str, Any]]
            Precedence constraints.
        non_negative_time : bool
            Whether non-negative bounds were active.
        precedence_min_gap : float
            Minimum precedence delay used in optimization constraints.
        end_must_be_latest : bool
            Whether END is constrained as an upper bound for all other nodes.
        integer_time : bool
            Whether integer variable mode was active.
        solver_name : Optional[str]
            Solver backend name.
        max_constraints : int, optional
            Maximum number of constraints listed in sample section.

        Returns
        -------
        Dict[str, Any]
            Metadata about the generated report.
        """
        if not path:
            raise ValueError("Report path must be a non-empty string.")

        report_path = Path(path).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)

        analysis = self.check_optimization_consistency(
            anchor_node=effective_anchor,
            enforce_precedence_for_unweighted=True,
            non_negative_time=non_negative_time,
            precedence_min_gap=precedence_min_gap,
            enforce_end_as_latest=end_must_be_latest,
        )
        negative_cycle = analysis.get("negative_cycle")
        direct_contradictions = analysis.get("direct_pair_contradictions", [])
        unsat_core = analysis.get("unsat_core", {})
        if not isinstance(unsat_core, dict):
            unsat_core = {}

        zero_node = "__ANCHOR_ZERO__"
        constraints = self._build_analysis_constraints(
            weighted_edges=weighted_edges,
            precedence_edges=precedence_edges,
            effective_anchor=effective_anchor,
            non_negative_time=non_negative_time,
            precedence_min_gap=precedence_min_gap,
            enforce_end_as_latest=end_must_be_latest,
            zero_node=zero_node,
        )

        weakly_connected = nx.is_weakly_connected(self) if self.number_of_nodes() > 0 else False
        disconnected_components: List[List[str]] = []
        if self.number_of_nodes() > 0 and not weakly_connected:
            disconnected_components = [
                sorted(str(node) for node in component)
                for component in nx.weakly_connected_components(self)
            ]

        def node_label(node_name: str) -> str:
            return "ZERO(0)" if node_name == zero_node else str(node_name)

        def constraint_expr(row: Dict[str, Any]) -> str:
            frm = node_label(str(row["from"]))
            to = node_label(str(row["to"]))
            weight = float(row["weight"])
            bound = self._format_bound(weight)
            if str(row.get("origin")) == "weighted" and weight < 0:
                # Surface the intuitive lower-bound interpretation for negative edges.
                return (
                    f"t({frm}) - t({to}) >= {self._format_bound(-weight)} "
                    f"(equiv. t({to}) - t({frm}) <= {bound})"
                )
            return f"t({to}) - t({frm}) <= {bound}"

        lines: List[str] = []
        lines.append("STN Infeasibility Diagnostic Report")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"Solver status: {status_name}")
        lines.append(f"Solver backend: {solver_name}")
        lines.append(f"Objective: {objective}")
        lines.append(f"Integer time: {integer_time}")
        lines.append(f"Non-negative time: {non_negative_time}")
        lines.append(f"Precedence minimum gap: {precedence_min_gap}")
        lines.append(f"End constrained as latest: {end_must_be_latest}")
        lines.append(f"Requested anchor: {requested_anchor}")
        lines.append(f"Effective anchor: {effective_anchor}")
        if requested_anchor is not None and str(requested_anchor) != str(effective_anchor):
            lines.append(
                "Anchor fallback was used because the requested anchor was not present in the STN nodes."
            )
        lines.append("")
        lines.append("Model Summary")
        lines.append("-" * 80)
        lines.append(f"Nodes: {self.number_of_nodes()}")
        lines.append(f"Edges: {self.number_of_edges()}")
        lines.append(f"Weighted constraints: {len(weighted_edges)}")
        lines.append(f"Precedence constraints: {len(precedence_edges)}")
        lines.append(f"Derived diagnostic constraints (including bounds/anchor): {len(constraints)}")
        lines.append(f"Weakly connected STN graph: {weakly_connected}")

        core_available = bool(unsat_core.get("available"))
        core_kind = str(unsat_core.get("kind", "n/a"))
        core_size = int(unsat_core.get("constraint_count", 0) or 0)
        if core_available:
            lines.append(f"Diagnostic unsat core: available ({core_kind})")
            lines.append(f"Diagnostic unsat core size: {core_size}")
            core_ids = unsat_core.get("constraint_ids", [])
            if isinstance(core_ids, list) and core_ids:
                preview = ", ".join(str(core_id) for core_id in core_ids[:20])
                suffix = "" if len(core_ids) <= 20 else ", ..."
                lines.append(f"Diagnostic unsat core constraint IDs: {preview}{suffix}")
        else:
            lines.append(
                "Diagnostic unsat core: unavailable ({})".format(
                    unsat_core.get("reason", "not_available")
                )
            )

        if disconnected_components:
            lines.append(f"Disconnected components: {len(disconnected_components)}")
            for idx, component in enumerate(disconnected_components, start=1):
                preview = ", ".join(component[:15])
                suffix = "" if len(component) <= 15 else ", ..."
                lines.append(f"  component {idx} ({len(component)} nodes): {preview}{suffix}")

        lines.append("")
        lines.append("Direct Pair Contradictions (u->v and v->u with sum < 0)")
        lines.append("-" * 80)
        if direct_contradictions:
            for row in direct_contradictions:
                lines.append(
                    "  {} <-> {} : uv={}, vu={}, sum={}".format(
                        node_label(row["u"]),
                        node_label(row["v"]),
                        self._format_bound(float(row["bound_uv"])),
                        self._format_bound(float(row["bound_vu"])),
                        self._format_bound(float(row["sum"])),
                    )
                )
        else:
            lines.append("  none")

        lines.append("")
        lines.append("Negative Cycle Diagnostic")
        lines.append("-" * 80)
        if negative_cycle:
            lines.append(
                "Detected a negative cycle with total weight {}.".format(
                    self._format_bound(float(negative_cycle["cycle_weight"]))
                )
            )
            cycle_nodes = " -> ".join(node_label(node) for node in negative_cycle["cycle_nodes"])
            lines.append(f"Cycle nodes: {cycle_nodes}")
            lines.append("Cycle edges and tightest constraints:")
            for edge in negative_cycle["cycle_edges"]:
                lines.append(
                    "  {} -> {} | w={} | id={} | type={} | origin={}".format(
                        node_label(edge["from"]),
                        node_label(edge["to"]),
                        self._format_bound(float(edge["tightest_weight"])),
                        edge["tightest_constraint_id"],
                        edge["tightest_constraint_type"],
                        edge["tightest_constraint_origin"],
                    )
                )
                for candidate in edge.get("candidate_constraints", [])[:5]:
                    lines.append(
                        "    candidate id={} type={} origin={} expr={}".format(
                            candidate.get("id"),
                            candidate.get("type"),
                            candidate.get("origin"),
                            constraint_expr(candidate),
                        )
                    )
        else:
            lines.append(
                "No negative cycle detected in the reduced diagnostic graph. "
                "Infeasibility may be caused by a combination of bounds not captured in a simple cycle."
            )

        lines.append("")
        lines.append("Unsat Core (Diagnostic)")
        lines.append("-" * 80)
        if core_available:
            lines.append(f"Kind: {core_kind}")
            if unsat_core.get("cycle_weight") is not None:
                lines.append(
                    "Cycle weight: {}".format(
                        self._format_bound(float(unsat_core.get("cycle_weight", 0.0)))
                    )
                )
            cycle_nodes = unsat_core.get("cycle_nodes", [])
            if isinstance(cycle_nodes, list) and cycle_nodes:
                lines.append(
                    "Cycle nodes: {}".format(
                        " -> ".join(node_label(str(node)) for node in cycle_nodes)
                    )
                )
            pair = unsat_core.get("pair")
            if isinstance(pair, dict) and pair:
                lines.append(
                    "Contradictory pair: {} <-> {} (sum={})".format(
                        node_label(str(pair.get("u"))),
                        node_label(str(pair.get("v"))),
                        self._format_bound(float(pair.get("sum", 0.0))),
                    )
                )
            lines.append("Core constraints:")
            for row in unsat_core.get("constraints", []):
                lines.append(
                    "  [id={}] {} | type={} | origin={}".format(
                        row.get("id"),
                        constraint_expr(row),
                        row.get("type"),
                        row.get("origin"),
                    )
                )
        else:
            lines.append("  none")

        lines.append("")
        lines.append("Constraint Sample")
        lines.append("-" * 80)
        lines.append(
            "Showing up to {} constraints in diagnostic form: t(v) - t(u) <= w".format(
                max_constraints
            )
        )
        for idx, row in enumerate(constraints[:max_constraints], start=1):
            lines.append(
                "  [{:04d}] {} | type={} | origin={}".format(
                    idx,
                    constraint_expr(row),
                    row["type"],
                    row["origin"],
                )
            )
        if len(constraints) > max_constraints:
            lines.append(f"  ... truncated {len(constraints) - max_constraints} additional constraints")

        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

        return {
            "path": str(report_path),
            "status": status_name,
            "negative_cycle_detected": bool(negative_cycle),
            "direct_pair_contradictions": len(direct_contradictions),
            "constraint_count": len(constraints),
            "precedence_min_gap": precedence_min_gap,
            "end_must_be_latest": bool(end_must_be_latest),
            "unsat_core_available": core_available,
            "unsat_core_size": core_size,
            "unsat_core_kind": core_kind if core_available else None,
        }

    