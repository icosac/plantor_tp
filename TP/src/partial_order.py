"""
Define the partial-order plan graph model and parsing helpers for planner output.
"""

#! I'm not sure if a graph representing a partial order must be weakly connected. If there are two flows that do not intersect, this is a correct PO no? 

import sys
from pathlib import Path

import networkx as nx

import re

from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from utility.logger import logger

class PartialOrderPlan(nx.MultiDiGraph):
    """
    A graph representing a partial order plan.
    
    References:
    UCPOP [Panberthy and Weld, 1992]
    [Bercher and Olz, 2020]
    [Kambhampati and Nau, 1994]
    """

    def __init__(self):    
        """
        Handle init.

        Returns
        -------
        Any
            Result returned by `__init__`.
        """
        super(PartialOrderPlan, self).__init__()

    @classmethod
    def from_prolog(
        cls,
        prolog_output: str,
        include_assumptions: bool = True,
        include_causal: bool = True,
    ) -> "PartialOrderPlan":
        """
        Build a PartialOrderPlan from Prolog planner output.

        Parameters
        ----------
        prolog_output : str
            Raw planner output text produced by Prolog. See REAMDE.md for expected format.
        include_assumptions : bool, optional
            Whether assumption-based links are included while parsing.
        include_causal : bool, optional
            Whether causal links are included while parsing.

        Returns
        -------
        "PartialOrderPlan"
            Result returned by `from_prolog`.
        """
        if not isinstance(prolog_output, str):
            raise TypeError("prolog_output must be a string.")

        pop = cls()
        parsed_plan_rows = cls._parse_plan_actions_with_enablers(prolog_output)
        
        # Add all nodes first (from explicit plan block when available) so edge insertion is straightforward.
        for row in parsed_plan_rows:
            node_name = cls._node_name(row["step_id"], row["step"])
            pop.add_action_node(
                node_name,
                parameters=cls._node_parameters(row["step_id"], row["step"]),
            )
        
        # Add mock "INIT" and "END" nodes if not already present, to ensure the graph is connected and has a clear start and end.
        if "INIT" not in pop.nodes:
            pop.add_action_node("INIT", parameters={"phase": "start"})
        if "END" not in pop.nodes:
            pop.add_action_node("END", parameters={"phase": "end"})

        # Add causal and assumption edges from explicit plan block when available.
        enablers_info = cls._parse_enabler_terms(prolog_output)
        for enabler in enablers_info:
            if not include_assumptions and enabler["reason_kind"] == "assumption":
                continue
            if not include_causal and enabler["reason_kind"] == "causal":
                continue

            from_node = cls._node_name(enabler["source_id"], enabler["source_step"])
            to_node = cls._node_name(enabler["target_id"], enabler["target_step"])

            if enabler["reason_kind"] == "causal":
                # For causal links we preserve literals so downstream visualization can show why the edge exists.
                literals = enabler["reason_raw"] if enabler["reason_raw"] else [""] #! This was once reason_literals, maybe this is wrong.
                # pop.add_casual_link_edge(
                #     from_node,
                #     to_node,
                #     preconditions=literals,
                #     effects=[""], 
                # )
                pop.add_typed_edge(
                    from_node,
                    to_node,
                    edge_type="causal_link",
                    preconditions=literals, 
                    effects=[""] 
                )
            else:
                if from_node not in pop.nodes:
                    pop.add_action_node(from_node)
                if to_node not in pop.nodes:
                    pop.add_action_node(to_node)
                pop.add_typed_edge(from_node, to_node, "ordering")

        # Add mock edges from "INIT" to all start nodes and from all end nodes to "END" to ensure connectivity.
        for node, data in pop.nodes(data=True):
            if node != "INIT" and node != "END":
                pop.add_typed_edge("INIT", node, "mock")
                pop.add_typed_edge(node, "END", "mock")

        if len(pop.nodes) == 0:
            raise ValueError(
                "No partial-order information found. Expected enabler(...) terms "
                "or '[enablers] Plan actions with enablers' block."
            )

        return pop

    @classmethod
    def from_low_level_sequence(cls, prolog_output: str) -> "PartialOrderPlan":
        """
        Build a total-order plan from the extracted low-level snap-step sequence.

        This ignores enabler edges entirely and preserves the order printed in
        the low-level plan block. The resulting graph contains only INIT, END,
        low-level start/end steps, and consecutive ordering edges.
        """
        if not isinstance(prolog_output, str):
            raise TypeError("prolog_output must be a string.")

        parsed_plan_rows = cls._parse_plan_actions_with_enablers(prolog_output)
        low_level_rows = []
        for row in parsed_plan_rows:
            phase, action_term = cls._parse_phase_and_action(row["step"])
            if phase in {"start", "end"} and action_term.startswith("ll_"):
                low_level_rows.append(row)

        if not low_level_rows:
            raise ValueError(
                "No low-level snap steps found in the extracted plan. "
                "Expected rows such as 'N - start(ll_...)' in the enabler plan block."
            )

        pop = cls()
        pop.add_action_node("INIT", parameters={"phase": "start"})
        for row in low_level_rows:
            node_name = cls._node_name(row["step_id"], row["step"])
            pop.add_action_node(
                node_name,
                parameters=cls._node_parameters(row["step_id"], row["step"]),
            )
        pop.add_action_node("END", parameters={"phase": "end"})

        ordered_nodes = [
            cls._node_name(row["step_id"], row["step"])
            for row in low_level_rows
        ]
        pop.add_typed_edge("INIT", ordered_nodes[0], "ordering")
        for previous_node, next_node in zip(ordered_nodes, ordered_nodes[1:]):
            pop.add_typed_edge(previous_node, next_node, "ordering")
        pop.add_typed_edge(ordered_nodes[-1], "END", "ordering")

        return pop

    @staticmethod
    def _node_name(step_id: int, step: str) -> str:
        """
        How nodes are named.

        Parameters
        ----------
        step_id : int
            Numeric plan step identifier.
        step : str
            Plan step term string (for example `start(...)` or `end(...)`).

        Returns
        -------
        str
            String result produced by this function.
        """
        return f"{step_id}-{step}"

    @staticmethod
    def _node_parameters(step_id: int, step: str) -> Dict[str, Any]:
        """
        Handle node parameters.

        Parameters
        ----------
        step_id : int
            Numeric plan step identifier.
        step : str
            Plan step term string (for example `start(...)` or `end(...)`).

        Returns
        -------
        Dict[str, Any]
            Dictionary containing structured results from this function.
        """
        phase, action_term = PartialOrderPlan._parse_phase_and_action(step)
        return {
            "step_id": step_id,
            "step": step,
            "phase": phase,
            "action_term": action_term,
        }

    @staticmethod
    def _parse_phase_and_action(step: str) -> Tuple[str, str]:
        """
        Handle parse phase and action.

        Parameters
        ----------
        step : str
            Plan step term string (for example `start(...)` or `end(...)`).

        Returns
        -------
        Tuple[str, str]
            Tuple containing structured results from this function.
        """
        step_clean = step.strip()
        match = re.match(r"^\s*(start|end)\((.*)\)\s*$", step_clean)
        if not match:
            return "other", step_clean
        return match.group(1), match.group(2).strip()


    @staticmethod
    def _parse_enabler_terms(
        prolog_output: str,
        start_collecting_re: str = r"^\s*\[planner\]\s*Enablers:",
        end_collecting_re: str = r"^\s*\[",
        enabler_re: str = r"^\s*enabler\((?P<step_id1>\d+)-(?P<action1_type>end|start)\((?P<action1_name>.*)\),(?P<step_id2>\d+)-(?P<action2_type>end|start)\((?P<action2_name>.*)\),(?P<reason_type>causal|assumption)\((?P<reason>.*)\)\)\s*$",
        stop_on_empty_line: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Handle parse enabler terms.

        Parameters
        ----------
        prolog_output : str
            Raw planner output text produced by Prolog.
        start_collecting_re : str, optional
            Regular expression pattern used to identify the line that marks the beginning of the enabler terms block.
        end_collecting_re : str, optional
            Regular expression pattern used to identify the line that marks the end of the enabler terms block
        enabler_re : str, optional
            Regular expression pattern used to identify and parse enabler(...) terms in the Prolog output. It should contain the following named groups: step_id1, action1_type, action1_name, step_id2, action2_type, action2_name, reason_type, reason.
        stop_on_empty_line : bool, optional
            Whether to stop collecting lines when an empty line is encountered (after having started collection).
            
        Returns
        -------
        List[Dict[str, Any]]
            Dictionary containing structured results from this function.
        """

        parsed: List[Dict[str, Any]] = []
        start_collecting_pattern = re.compile(start_collecting_re)
        end_collecting_pattern = re.compile(end_collecting_re)
        enabler_pattern = re.compile(enabler_re)

        collecting = False

        for line in prolog_output.splitlines():
            if start_collecting_pattern.match(line):
                collecting = True
            elif end_collecting_pattern.match(line) and collecting:
                break
                
            if not collecting:
                continue

            if stop_on_empty_line and not line.strip() and parsed:
                break

            enabler_match = enabler_pattern.match(line)
            if not enabler_match:
                continue

            source_id    = int(enabler_match.group("step_id1"))
            action1_type = enabler_match.group("action1_type")
            action1_name = enabler_match.group("action1_name").strip()
            target_id    = int(enabler_match.group("step_id2"))
            action2_type = enabler_match.group("action2_type")
            action2_name = enabler_match.group("action2_name").strip()
            reason_type  = enabler_match.group("reason_type").strip()
            reason_text  = enabler_match.group("reason").strip()


            parsed.append(
                {
                    "source_id": source_id,
                    "source_step": f"{action1_type}({action1_name})",
                    "target_id": target_id,
                    "target_step": f"{action2_type}({action2_name})",
                    "reason_kind": reason_type,
                    "reason_raw": reason_text,
                }
            )
        return parsed

    @staticmethod
    def _parse_plan_actions_with_enablers(
        prolog_output: str,
        start_collecting_re: str = r"^\[enablers\] Plan actions with enablers",
        end_collecting_re: str = r"^\s*\[",
        line_re: str = r"^\s*(?P<step_id>\d+)\s*-\s*(?P<action_name>.*?)\s*<=\s*\[(?P<enablers>.*?)\]\s*$",
        stop_on_empty_line: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Handle parse plan actions with enablers.

        Parameters
        ----------
        prolog_output : str
            Raw planner output text produced by Prolog.
        start_collecting_re : str, optional
            Regular expression pattern used to identify the line that marks the beginning of the plan block with enabler information.
        end_collecting_re : str, optional
            Regular expression pattern used to identify the line that marks the end of the plan block with enabler information.
        line_re : str, optional
            Regular expression pattern used to parse lines in the plan block with enabler information. It should get: the step id of the action, the name of the action and the list of incoming enabler step ids.
        stop_on_empty_line : bool, optional
            Whether to stop collecting lines when an empty line is encountered (after having started collection).
        Returns
        -------
        List[Dict[str, Any]]
            Dictionary containing structured results from this function.
        """
        rows: List[Dict[str, Any]] = []
        collecting = False
        line_pattern = re.compile(line_re)
        start_collecting_pattern = re.compile(start_collecting_re)
        end_collecting_pattern = re.compile(end_collecting_re)

        for line in prolog_output.splitlines():
            start_match = start_collecting_pattern.match(line)
            if start_match:
                collecting = True
                continue

            if not collecting:
                continue
            
            end_match = end_collecting_pattern.match(line)
            if end_match:
                break

            if stop_on_empty_line and not line.strip() and rows:
                break
            
            match = line_pattern.match(line)
            if not match:
                continue

            step_id = int(match.group("step_id"))
            action = match.group("action_name").strip()
            enablers_raw = match.group("enablers").strip()
            enablers: List[int] = []
            if enablers_raw:
                for token in enablers_raw.split(","):
                    token_clean = token.strip()
                    if not token_clean:
                        continue
                    try:
                        enablers.append(int(token_clean))
                    except ValueError:
                        continue

            rows.append(
                {
                    "step_id": step_id,
                    "step": action,
                    "enablers": sorted(enablers),
                }
            )

        rows.sort(key=lambda row: row["step_id"])
        return rows


    def add_action_node(
        self,
        action_name: str,
        parameters: dict = None
    ) -> bool:
        """
        Add an action node to the partial order plan.

        Parameters
        ----------
        action_name : str
            Action identifier or Prolog action term name.
        parameters : dict, optional
            Optional metadata dictionary stored with the action node.

        Returns
        -------
        bool
            Boolean result indicating whether the check/operation succeeded.
        """
        if not self.has_node(action_name):              
            self.add_node(action_name, parameters = parameters)
            return True
        return False
    

    def add_typed_edge(
        self,
        from_action: str,
        to_action: str,
        edge_type: str,
        **edge_attributes: Any
    ) -> None:
        """
        Add an edge of a specific type between two action nodes.

        Parameters
        ----------
        from_action : str
            Source action node for the edge being created.
        to_action : str
            Target action node for the edge being created.
        edge_type : str
            Type of the edge being created. C
        **edge_attributes : Any
            Additional attributes for the edge.

        Returns
        -------
        None
            This function performs side effects and returns nothing.

        Raises
        ------
        ValueError
            If `edge_type` is not one of 'mock', 'ordering' or 'causal_link'.
        ValueError            
            If `from_action` or `to_action` are not found in the graph nodes.
        """
        assert from_action is not None, "from_action cannot be None"
        assert to_action is not None, "to_action cannot be None"
        assert edge_type is not None and edge_type in ["mock", "ordering", "causal_link"], "edge_type must be one of 'mock', 'ordering' or 'causal_link'"

        if from_action not in self.nodes:
            raise ValueError(f"from_action '{from_action}' not found in the graph nodes.")
        if to_action not in self.nodes:
            raise ValueError(f"to_action '{to_action}' not found in the graph nodes.")

        if edge_type == "causal_link":
            if "preconditions" not in edge_attributes:
                edge_attributes["preconditions"] = [""]
            elif isinstance(edge_attributes["preconditions"], str):
                edge_attributes["preconditions"] = [edge_attributes["preconditions"]]

            if "effects" not in edge_attributes:
                edge_attributes["effects"] = [""]
            elif isinstance(edge_attributes["effects"], str):
                edge_attributes["effects"] = [edge_attributes["effects"]]
        
        self.add_edge(from_action, to_action, type=edge_type, **edge_attributes)


    def check_consistency(self) -> bool:
        """
        Check the consistency of the partial order plan. A POP is correct and solvable iff:.

        Returns
        -------
        bool
            Boolean result indicating whether the check/operation succeeded.
        """
        if not self._no_ordering_edges_cycle():
            return False
        if not nx.is_weakly_connected(self):
            logger.error("The graph is not weakly connected. The partial order plan is inconsistent.")
            return False
        if not self._exist_path_from_start_to_end():
            return False
        return True
    

    def _exist_path_from_start_to_end(self) -> bool:
        """
        Check that there is a path from the initial action (start) to the goal action (end).

        Returns
        -------
        bool
            Boolean result indicating whether the check/operation succeeded.
        """
        start_node = "INIT"
        end_node = "END"

        if nx.has_path(self, start_node, end_node):
            return True

        logger.error(f"No path from {start_node} to {end_node}. The partial order plan is inconsistent.")
        return False


    def _no_ordering_edges_cycle(self) -> bool:
        """
        Check that there are no cycles in the ordering edges, i.e., the graph is a DAG.

        Returns
        -------
        bool
            Boolean result indicating whether the check/operation succeeded.
        """
        ordering_graph = nx.DiGraph()
        for u, v, data in self.edges(data=True):
            if data["type"] == "ordering":
                ordering_graph.add_edge(u, v)

        if not nx.is_directed_acyclic_graph(ordering_graph):
            logger.error("Cycle detected in ordering edges. The partial order plan is inconsistent.")
            # Print the cycle for debugging purposes
            try:
                cycle = nx.find_cycle(ordering_graph, orientation="original")
                logger.error("Cycle found in ordering edges:")
                for u, v, _ in cycle:
                    logger.error(f"{u} -> {v}")
            except nx.NetworkXNoCycle:
                logger.error("No cycle found, but the graph is not a DAG. This should not happen.")
            return False
        else:
            return True


    def draw(self, path: str, show_edges : str = "both") -> None:
        """
        Draw the partial order plan to a file.

        Parameters
        ----------
        path : str
            Filesystem path used by this operation.
        show_edges : str, optional
            Whether to display edge labels/overlays while drawing the graph.

        Returns
        -------
        None
            This function performs side effects and returns nothing.
        """
        import matplotlib.pyplot as plt
        pos = nx.spring_layout(self)
        edge_labels = {}
        edges_to_draw = []

        for u, v, data in self.edges(data=True):
            if show_edges == "both" or data["type"] == show_edges:
                edges_to_draw.append((u, v))
                if data["type"] == "causal_link":
                    if "preconditions" in data and "effects" in data:
                        if data["preconditions"] == [""] and data["effects"] == [""]:
                            edge_labels[(u, v)] = ""
                        else:
                            edge_labels[(u, v)] = f"pre: {data['preconditions']}\neff: {data['effects']}"
                else:
                    # No label for ordering edges
                    edge_labels[(u, v)] = ""

        node_labels = {}
        for node, data in self.nodes(data=True):
            if "parameters" in data and data["parameters"] is not None:
                node_labels[node] = f"{node}(\n" + ",\n".join([f"  {key} = {value}" for key, value in data['parameters'].items()]) + "\n)"
            else:
                node_labels[node] = f"{node}()"

        nx.draw(self, pos, with_labels=False, arrows=True)
        nx.draw_networkx_labels(self, pos, labels=node_labels)
        nx.draw_networkx_edge_labels(self, pos, edge_labels=edge_labels)

        # Change color to red for the ordering edges
        ordering_edges = [(u, v) for u, v, data in self.edges(data=True) if data["type"] == "ordering" and (u, v) in edges_to_draw]
        nx.draw_networkx_edges(self, pos, edgelist=ordering_edges, edge_color='red')

        if path is not None and path != "":
            if path == "show":
                plt.show()
            else:
                plt.savefig(path)
        plt.close()


    def summarize(self) -> None:
        """
        Print a compact summary of the partial-order plan graph.

        Parameters
        ----------

        Returns
        -------
        None
            This function performs side effects and returns nothing.
        """
        ordering_edges = sum(1 for _, _, data in self.edges(data=True) if data.get("type") == "ordering")
        causal_edges = sum(1 for _, _, data in self.edges(data=True) if data.get("type") == "causal_link")

        logger.info("PartialOrderPlan loaded successfully.")
        logger.info(f"Nodes: {self.number_of_nodes()}")
        logger.info(f"Edges: {self.number_of_edges()}")
        logger.info(f"Ordering edges: {ordering_edges}")
        logger.info(f"Causal-link edges: {causal_edges}")
        logger.info(f"Partial Order Plan consistency check: {self.check_consistency()}")
        logger.info(f"DAG consistency (ordering edges): {self._no_ordering_edges_cycle()}")
        logger.info(f"Graph has solution from INIT to END: {self._exist_path_from_start_to_end()}")
        logger.info(f"Graph is weakly connected: {nx.is_weakly_connected(self)}")

        logger.info("Node details:")
        for node, data in self.nodes(data=True):
            logger.info(f"  - {node}: {data}")

        logger.info("Edge details:")
        logger.info(f"  - Total edges: {self.number_of_edges()}")
        logger.info(f"  - Ordering edges: {ordering_edges}")
        logger.info(f"  - Causal-link edges: {causal_edges}")
        logger.info(f"  - Mock edges: {sum(1 for _, _, data in self.edges(data=True) if data.get('type') == 'mock')}")

        logger.info("Ordering edges:")
        for u, v, data in self.edges(data=True):
            if data.get("type") == "ordering":
                logger.info(f"  - ({u}, {v})")
        logger.info("Causal-link edges:")
        for u, v, data in self.edges(data=True):
            if data.get("type") == "causal_link":
                logger.info(f"  - ({u}, {v}): {data}")
        logger.info("Mock edges:")
        for u, v, data in self.edges(data=True):
            if data.get("type") == "mock":
                logger.info(f"  - ({u}, {v})")

        logger.info("Summary complete.")


def parse_prolog_partial_order(
    prolog_output: str,
    include_assumptions: bool = True,
    include_causal: bool = True,
) -> PartialOrderPlan:
    """
    Parse Prolog planner output into a PartialOrderPlan.

    Parameters
    ----------
    prolog_output : str
        Raw planner output text produced by Prolog.
    include_assumptions : bool, optional
        Whether assumption-based links are included while parsing.
    include_causal : bool, optional
        Whether causal links are included while parsing.

    Returns
    -------
    PartialOrderPlan
        Result returned by `parse_prolog_partial_order`.
    """
    return PartialOrderPlan.from_prolog(
        prolog_output=prolog_output,
        include_assumptions=include_assumptions,
        include_causal=include_causal,
    )
    
