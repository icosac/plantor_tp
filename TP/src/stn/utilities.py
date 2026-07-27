"""STN utilities."""

from typing import Any, Dict, List, Optional, Tuple
import re

import sys
from pathlib import Path

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.logger import logger

SNAP_RE = r"^(?P<action_id>\d+)-(?P<type>start|end)\((?P<action_name>.*)\)$"


class STNUtilitiesMixin:
    """Utility methods mixed into SimpleTemporalNetwork."""

    @staticmethod
    def _parse_snap_action(
        action_label: Any, 
        snap_re: str = SNAP_RE, 
        low_level_re: str = r"ll_.*") -> Optional[Dict[str, Any]]:
        """
        Parse a snap-style action label into structured metadata.

        Parameters
        ----------
        action_label : Any
            Raw action label (for example `12-start(ll_pick(a,b))`).
        snap_re : str, optional
            Regular expression used to parse the action label.
        low_level_re : str, optional
            Regular expression used to identify low-level actions. If not empty, it will be used to skip high-level actions. If empty, no action will be skipped.

        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed dictionary with `raw`, `step_id`, `phase`, `action_name`, and
            `instance` fields, or `None` when parsing fails.
        """
        action_pattern = re.compile(snap_re)
        low_level_pattern = re.compile(low_level_re)
        raw = str(action_label)

        match = action_pattern.match(raw)
        if not match:
            logger.error(f"Failed to parse snap action label: '{raw}' does not match expected format '{snap_re}'.")
            return None

        if not low_level_pattern.match(match.group("action_name")):
            logger.debug(f"Skipping non low-level action '{match.group('action_name')}' not matching pattern '{low_level_re}'.")
            return None

        phase = match.group("type").lower()
        action_name = match.group("action_name")
        step_id = int(match.group("action_id"))

        logger.debug(f"Parsed snap action: raw='{raw}', step_id={step_id}, phase='{phase}', action_name='{action_name}'")
        return {
            "raw": raw,
            "step_id": step_id,
            "phase": phase,
            "action_name": action_name,
            "instance": f"{action_name}_{step_id}",
        }


    @staticmethod
    def _pair_snap_steps(
            parsed_steps: List[Dict[str, Any]],
        ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Pair start/end steps for each action name using ordered IDs.

        For each action name, starts are matched to the first unmatched end with
        a greater step id (mirroring Prolog-side ordering assumptions).

        Parameters
        ----------
        parsed_steps : List[Dict[str, Any]]
            Parsed snap-step descriptors.

        Returns
        -------
        Tuple[Dict[str, str], Dict[str, str]]
            Two dictionaries:
            - `start_to_end`: raw start label -> raw end label
            - `end_to_start`: raw end label -> raw start label
        """
        starts_by_action: Dict[str, List[Dict[str, Any]]] = {}
        ends_by_action: Dict[str, List[Dict[str, Any]]] = {}
        for step in parsed_steps:
            if step["phase"] == "start":
                starts_by_action.setdefault(step["action_name"], []).append(step)
            elif step["phase"] == "end":
                ends_by_action.setdefault(step["action_name"], []).append(step)

        for values in starts_by_action.values():
            values.sort(key=lambda item: item["step_id"])
        for values in ends_by_action.values():
            values.sort(key=lambda item: item["step_id"])

        start_to_end: Dict[str, str] = {}
        end_to_start: Dict[str, str] = {}
        for action_name, starts in starts_by_action.items():
            ends = ends_by_action.get(action_name, [])
            end_idx = 0
            for start in starts:
                while end_idx < len(ends) and ends[end_idx]["step_id"] <= start["step_id"]:
                    end_idx += 1
                if end_idx >= len(ends):
                    continue
                end = ends[end_idx]
                end_idx += 1
                start_to_end[start["raw"]] = end["raw"]
                end_to_start[end["raw"]] = start["raw"]

        return start_to_end, end_to_start
    

    @staticmethod
    def _coerce_duration_value(value) -> float:
        """
        Normalize a duration value into a float, supporting +/-infinity strings.

        Parameters
        ----------
        value : Any
            Raw value to parse.

        Returns
        -------
        float
            Parsed numeric value.
        """
        if value is None:
            raise ValueError("Duration value cannot be None")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"inf", "+inf", "infinity", "+infinity"}:
                return float("inf")
            if cleaned in {"-inf", "-infinity"}:
                return float("-inf")
            return float(cleaned)
        raise ValueError(f"Unsupported duration value: {value!r}")
    

    def _resolve_anchor_node(self, anchor_node: Optional[str]) -> str:
        """
        Resolve the effective optimization anchor node with strict fallback.

        Parameters
        ----------
        anchor_node : Optional[str]
            Requested anchor node name.

        Returns
        -------
        str
            Effective anchor name used by optimization/reporting.

        Raises
        ------
        ValueError
            If the STN is empty, or if neither the requested anchor nor `INIT`
            exists in the graph.
        """
        if self.number_of_nodes() == 0:
            raise ValueError("Cannot build optimization model for an empty STN.")
        if anchor_node is not None and anchor_node in self.nodes():
            return str(anchor_node)
        if "INIT" in self.nodes():
            return "INIT"
        if anchor_node is None:
            raise ValueError(
                "No anchor node specified and fallback node 'INIT' was not found in the STN."
            )
        raise ValueError(
            f"Requested anchor node '{anchor_node}' was not found and fallback node 'INIT' "
            "was not found in the STN."
        )