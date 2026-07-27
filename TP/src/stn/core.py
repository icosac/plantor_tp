"""Core STN graph construction and consistency utilities."""

import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import networkx as nx
import yaml

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.logger import logger

try:
    from src.partial_order import PartialOrderPlan
except ImportError:  # Fallback for alternate package layouts.
    from TP.partial_order import PartialOrderPlan

try:
    from .utilities import SNAP_RE
except ImportError:
    from stn.utilities import SNAP_RE
    
class STNCore(nx.DiGraph):
    """Core Simple Temporal Network graph methods."""

    def __init__(self):
        """
        Initialize an empty directed STN graph.

        Returns
        -------
        None
            This constructor initializes internal graph state.
        """
        super(STNCore, self).__init__()

    
    ######################### FROM PARTIAL-ORDER PLAN #########################

    def from_partial_order(
            self,
            po_plan: PartialOrderPlan,
            default_min: float = 1e-3,
            default_max: float = float("inf"),
            snap: bool = True,
            snap_re: str = SNAP_RE,
        ) -> None:
        """
        Convert a PartialOrderPlan into STN timepoint nodes and constraints.

        Parameters
        ----------
        po_plan : PartialOrderPlan
            Partial-order plan used to construct this STN.
        default_min : float, optional
            Default minimum duration lower bound for action intervals.
        default_max : float, optional
            Default maximum duration upper bound for action intervals.
        snap : bool, optional
            Whether action steps are snap-style start/end nodes matched by `snap_re`.
        snap_re : str, optional
            Regular expression used to parse action step labels.

        Returns
        -------
        None
            This function performs side effects on the current graph.
        """
        assert default_max > default_min, f"default_max must be greater than default_min ({default_max} <= {default_min})"
        assert po_plan.check_consistency(), "The PartialOrderPlan must be consistent to convert to a Simple Temporal Network."

        if snap:
            self._from_partial_order_snap(po_plan)
        else:
            self._from_partial_order_durative(po_plan, default_min, default_max)

        if "INIT" not in self.nodes():
            logger.debug("Adding INIT node and edges to all other nodes with infinite upper bound.")
            self.add_node("INIT")
            for node in self.nodes():
                if node != "INIT":
                    self.add_edge("INIT", node, type="duration", weight=float("inf"))
        if "END" not in self.nodes():
            logger.debug("Adding END node and edges from all other nodes with infinite upper bound.")
            self.add_node("END")
            for node in self.nodes():
                if node != "END":
                    self.add_edge(node, "END", type="duration", weight=float("inf"))

        logger.info("Finished building the STN structure from the PartialOrderPlan. Checking consistency...")

        if not self.is_consistent():
            stn_html_path = "stn_inconsistent.html"
            self.to_cytoscape_html(
                str(stn_html_path),
                title="Simple Temporal Network after conversion from PartialOrderPlan",
            )
            logger.info(f"STN HTML visualization written to: {stn_html_path}")
            raise ValueError("The STN is inconsistent after conversion from the PartialOrderPlan.")


    def _from_partial_order_durative(
            self,
            po_plan: PartialOrderPlan,
            default_min: float = 1e-3,
            default_max: float = float("inf"),
        ) -> None:
        """
        Convert a PartialOrderPlan into STN timepoint nodes and constraints.

        Parameters
        ----------
        po_plan : PartialOrderPlan
            Partial-order plan used to construct this STN.
        default_min : float, optional
            Default minimum duration lower bound for action intervals.
        default_max : float, optional
            Default maximum duration upper bound for action intervals.

        Returns
        -------
        None
            This function performs side effects on the current graph.
        """
        # First pass: create STN timepoint nodes and intrinsic duration bounds.
        for node, data in po_plan.nodes(data=True):
            logger.debug(f"Adding time points for action node: {node}")
            if node not in ["INIT", "END"]:
                self.add_node(f"s_{node}", **data)
                self.add_node(f"e_{node}", **data)
                self.add_edge(f"s_{node}", f"e_{node}", weight=default_max)
                self.add_edge(f"e_{node}", f"s_{node}", weight=-default_min)
            else:
                self.add_node(node, **data)

        # Second pass: translate partial-order edges into temporal precedence constraints.
        for u, v, data in po_plan.edges(data=True):
            if u == "INIT":
                logger.debug(f"Adding edge from INIT to s_{v}")
                self.add_edge("INIT", f"s_{v}", weight=0, **data)
            elif v == "END":
                logger.debug(f"Adding edge from e_{u} to END")
                self.add_edge(f"e_{u}", "END", weight=0, **data)
            else:
                assert f"s_{u}" in self.nodes(), f"Node s_{v} not found in STN."
                assert f"e_{v}" in self.nodes(), f"Node e_{u} not found in STN."
                self.add_edge(f"e_{u}", f"s_{v}", **data)




    def _from_partial_order_snap(
            self,
            po_plan: PartialOrderPlan
        ) -> None:
        """
        Convert a PartialOrderPlan into STN timepoint nodes and constraints.

        Parameters
        ----------
        po_plan : PartialOrderPlan
            Partial-order plan used to construct this STN.

        Returns
        -------
        None
            This function performs side effects on the current graph.
        """
        # First pass: create STN timepoint nodes.
        for node, data in po_plan.nodes(data=True):
            if node == "INIT" or node == "END":
                logger.debug(f"Adding time points for action node: {node}")
                self.add_node(node, **data)
            elif self._parse_snap_action(node, SNAP_RE) is not None:
                logger.debug(f"Adding time points for action node: {node}")
                self.add_node(node, **data)

        for node in self.nodes():
            logger.debug(f"{node}")

        # Second pass: translate partial-order edges into temporal precedence constraints.
        for u, v, data in po_plan.edges(data=True):
            if u not in self.nodes():
                logger.debug(f"Skipping edge from '{u}' to '{v}' because the source node '{u}' is not present in the STN.")
                continue
            elif v not in self.nodes():
                logger.debug(f"Skipping edge from '{u}' to '{v}' because the target node '{v}' is not present in the STN.")
                continue
            existing_data = self.get_edge_data(u, v)
            if existing_data is not None:
                existing_type = existing_data.get("type")
                new_type = data.get("type")
                if existing_type != new_type and existing_type in {"ordering", "causal_link"} and new_type in {"ordering", "causal_link"}:
                    parallel_types = existing_data.setdefault("parallel_edge_types", [])
                    if new_type not in parallel_types:
                        parallel_types.append(new_type)
                    continue
            self.add_edge(u, v, **data)



    ######################### ADDING TIME CONSTRAINTS #########################

    def add_time_constraints(
            self,
            yaml_config: Union[dict, str],
            snap_re: str = SNAP_RE,
        ) -> None:
        """
        Add temporal bounds from YAML config or action-duration dictionaries.

        Parameters
        ----------
        yaml_config : Union[dict, str]
            Either a path to a YAML file or an in-memory dictionary containing
            duration constraints. The YAML or the dictionary is expected to be in one of the following formats:
            1. Format with `kmps` key:
                ```yaml
                kmps:
                    - action_list
                ```
            2. Format with `linked_actions` and `durations` keys, used from snap-style PO plans:
                ```yaml
                linked_actions:
                    start_action_name_1 : end_action_name_1
                    end_action_name_1 : start_action_name_1
                    start_action_name_2 : end_action_name_2
                    end_action_name_2 : start_action_name_2
                durations:
                    action_name_1:
                        min: min_duration_1
                        max: max_duration_1
                    action_name_2:
                        min: min_duration_2
                        max: max_duration_2
                ```
        snap_re : str, optional
            Regular expression used to map action IDs to STN start/end nodes.

        Returns
        -------
        None
            This function performs side effects on the current graph.

        Raises
        ------
        ValueError
            If the configuration format is invalid, if specified action nodes are missing, or if the resulting STN is inconsistent.
        """
        if isinstance(yaml_config, str):
            with open(yaml_config, "r") as file:
                config = yaml.safe_load(file)
        else:
            config = yaml_config

        if not isinstance(config, dict):
            raise TypeError("yaml_config must resolve to a dictionary.")

        if "kmps" in config:
            logger.info("Adding time constraints from YAML configuration...")
            self._add_time_constraints_from_yaml(config)
        else:
            # Check that both `linked_actions` and `durations` keys are present in the dictionary
            error_msg = "Expected '{}' key in the configuration dictionary when using split snap actions format."
            if "linked_actions" not in config.keys():
                logger.error(error_msg.format("linked_actions"))
                raise ValueError(error_msg.format("linked_actions"))
            elif "durations" not in config.keys():
                logger.error(error_msg.format("durations"))
                raise ValueError(error_msg.format("durations"))

            # Check that the dictionary is in the form key, {"min": val_min, "max": val_max}
            for action, bounds in config['durations'].items():
                if not isinstance(bounds, dict) or "min" not in bounds or "max" not in bounds:
                    raise ValueError(
                        f"Invalid duration constraint for action '{action}': expected a dict with 'min' and 'max' keys, got {bounds}."
                    )
            logger.info("Adding time constraints from action duration bounds...")
            self._add_time_constraints_from_actions(config['durations'], config['linked_actions'], snap_re)

        if self.check_consistency_durations():
            logger.info("The STN is consistent after adding time constraints.")
        else:
            stn_html_path = "stn_inconsistent.html"
            self.to_cytoscape_html(
                str(stn_html_path),
                title="Simple Temporal Network",
            )
            logger.info(f"STN HTML visualization written to: {stn_html_path}")
            raise ValueError("The STN is inconsistent after adding time constraints.")

        if not self.is_consistent():
            raise ValueError("The STN is inconsistent after adding time constraints.")


    def _add_time_constraints_from_actions(
            self,
            durations: dict,
            linked_actions: dict,
            snap_re: str = SNAP_RE,
        ) -> None:
        """
        Apply action-level duration bounds to existing STN start/end nodes.

        Parameters
        ----------
        durations : dict
            Mapping from action identifiers to `{min,max}` duration bounds. The
            dictionary keys are expected to be the durative actions, while the
            values are expected to be dictionaries with "min" and "max" keys,
            e.g. `{"move": {"min": 1.0, "max": 5.0}}`.
        linked_actions : dict
            Mapping from start action identifiers to end action identifiers.
        snap_re : str, optional
            Pattern used to extract action names and map to `s_*`/`e_*` nodes.

        Returns
        -------
        None
            This function performs side effects on the current graph.

        Raises
        ------
        ValueError
            If duration bounds are invalid or if specified action nodes are missing.
        """
        logger.debug("========================================================")
        logger.debug("Adding time constraints from action duration bounds...")
        done_actions = {node: False for node in self.nodes if node not in ["INIT", "END"]}  # Check all action nodes get duration bounds.

        assert all(min_duration <= max_duration for min_duration, max_duration in [
            (self._coerce_duration_value(durations[action].get("min")), self._coerce_duration_value(durations[action].get("max")))
            for action in durations
        ]), "Duration bounds are inconsistent: at least one action has min duration greater than max duration."

        for start_node, end_node in linked_actions.items():
            logger.debug(f'------- {start_node} -> {end_node} -------')
            start_data = self._parse_snap_action(start_node, snap_re)
            end_data = self._parse_snap_action(end_node, snap_re)

            # Skip actions inside the durations which are not low-level
            if not start_data:
                start_match = re.match(snap_re, str(start_node))
                start_action_name = start_match.group("action_name") if start_match else ""
                if start_match and not start_action_name.startswith("ll_"):
                    logger.debug(
                        f"Skipping linked action '{start_node}' -> '{end_node}' "
                        "because the start action is not low-level."
                    )
                    continue
                logger.error(f"Failed to parse start node '{start_node}' in linked action pair '{start_node}' -> '{end_node}'.")
                raise ValueError(f"Failed to parse start node '{start_node}' in linked action pair '{start_node}' -> '{end_node}'.")

            if not end_data:
                end_match = re.match(snap_re, str(end_node))
                end_action_name = end_match.group("action_name") if end_match else ""
                if end_match and not end_action_name.startswith("ll_"):
                    logger.debug(
                        f"Skipping linked action '{start_node}' -> '{end_node}' "
                        "because the end action is not low-level."
                    )
                    continue
                logger.error(f"Failed to parse end node '{end_node}' in linked action pair '{start_node}' -> '{end_node}'.")
                raise ValueError(f"Failed to parse end node '{end_node}' in linked action pair '{start_node}' -> '{end_node}'.")

            # Only consider start nodes for adding duration constraints
            if not start_data['phase'] == "start":
                continue

            # Validate that the parsed start and end nodes are correctly linked
            if end_data['phase'] == "start":
                raise ValueError(
                    f"Linked action pair has identical step identifiers: '{start_node}' -> '{end_node}' "
                    f"both parsed as step '{start_data['phase']}'."
                )

            # Validate that the parsed start and end nodes have the same action name
            if start_data["action_name"] != end_data["action_name"]:
                raise ValueError(
                    f"Linked action pair has mismatching action names: '{start_node}' -> '{end_node}' "
                    f"parsed as '{start_data['action_name']}' -> '{end_data['action_name']}'."
                )

            # Find the corresponding duration bounds for the action and add the edges to the graph
            for durative_action, d_bounds in durations.items():
                if durative_action == start_node or durative_action == start_data["action_name"]:
                    logger.info(f"Adding duration between {start_node} and {end_node} with bounds: {d_bounds}")
                    min_duration = self._coerce_duration_value(d_bounds.get("min"))
                    max_duration = self._coerce_duration_value(d_bounds.get("max"))

                    self.add_edge(start_node, end_node, type="duration", weight=max_duration)
                    self.add_edge(end_node, start_node, type="duration", weight=-min_duration)

                    done_actions[start_node] = True
                    done_actions[end_node] = True
        
        all_not_done_actions = [node for node, done in done_actions.items() if not done]
        if all_not_done_actions:
            logger.error(f"The following nodes were not linked to any duration constraints. {all_not_done_actions}")
            raise ValueError(f"Some action nodes were not linked to any duration constraints. Unlinked nodes: {all_not_done_actions}")


    def _add_time_constraints_from_yaml(self, config: dict) -> None:
        """
        Apply legacy YAML duration constraints keyed by edge labels.

        Parameters
        ----------
        config : dict
            YAML configuration dictionary expected to contain a `kmps` section.

        Returns
        -------
        None
            This function performs side effects on the current graph.
        """
        for u, v, data in self.edges(data=True):
            if self[u][v].get("weight") is not None:
                continue

            label = data.get("label")
            if label not in config["kmps"]:
                raise ValueError(f"Edge label '{label}' not found in the YAML configuration.")
            else:
                label_config = config["kmps"][label]
                if "time" in label_config:
                    time_constraints = label_config["time"]
                    if "duration" in time_constraints:
                        duration_constraints = time_constraints["duration"]
                        min_duration = duration_constraints.get("min", 0.0)
                        max_duration_value = duration_constraints.get("max", float("inf"))
                        if (v, u) not in self.edges():
                            self.add_edge(v, u, **data)
                            self[v][u]["weight"] = -min_duration
                        self[u][v]["weight"] = max_duration_value


    ######################### CONSISTENCY CHECKS #########################

    def is_consistent(self) -> bool:
        """
        Check overall STN consistency.

        Returns
        -------
        bool
            `True` when duration consistency and weak connectivity checks pass.
        """
        if not self.check_consistency_durations():
            return False
        if not nx.is_weakly_connected(self):
            logger.error(
                "The STN is inconsistent because the graph is not weakly connected. "
                "This may indicate missing constraints that could lead to unbounded time assignments."
            )
            return False
        return True


    def check_consistency_durations(self) -> bool:
        """
        Check STN duration consistency by detecting negative cycles.

        Notes
        -----
        Ordering and causal-link edges are treated as `+inf` weight in this
        check to focus specifically on weighted duration constraints.

        Returns
        -------
        bool
            `True` when no negative cycle is detected.
        """
        logger.info("Checking STN consistency by looking for negative cycles...")

        def w(u, v, data):
            if "type" in data and data["type"] in {"ordering", "causal_link"}:
                return float("inf")
            return data.get("weight", 0)

        fine = True
        for n in self.nodes():
            try:
                res = nx.find_negative_cycle(self, n, w)
            except Exception:
                continue

            edges_in_cycle = list(zip(res, res[1:] + [res[0]]))
            graph_edges = [
                (u, v, data.get("weight", 0))
                for u, v, data in self.edges(data=True)
                if (u, v) in edges_in_cycle
            ]
            cost = sum(weight for _, _, weight in graph_edges)
            logger.error(f"Negative cycle detected starting at node '{n}': {res}")
            logger.error(f"The cost of the negative cycle is: {cost}")
            fine = False
            break

        logger.info("Check passed")
        return fine

