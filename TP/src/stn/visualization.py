"""
Render temporal-plan and STN structures to interactive HTML visualizations.
"""

import html
import json
import math
import re
import sys
from pathlib import Path
import networkx as nx
from typing import Any, Dict, Iterable, List, Optional, Union, cast

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.logger import logger


PO_NODE_COLORS = {
    "hl_start": "#2E86AB",
    "hl_end": "#22577A",
    "ll_start": "#2A9D8F",
    "ll_end": "#E9C46A",
    "other": "#6C757D",
}

PO_EDGE_COLORS = {
    "causal": "#D1495B",
    "assumption": "#3A86FF",
    "other": "#7C7C7C",
}

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_HTML_TEMPLATE_PATH = _TEMPLATES_DIR / "stn_cytoscape.html"
_JS_TEMPLATE_PATH = _TEMPLATES_DIR / "stn_cytoscape.js"


def _read_template(template_path: Path) -> str:
        """Read a text template file used to render STN HTML/JS output."""
        with open(template_path, "r", encoding="utf-8") as handle:
                return handle.read()


def _render_template(template_text: str, values: Dict[str, str]) -> str:
        """Replace __TOKEN__ placeholders in template text with concrete values."""
        rendered = template_text
        for key, value in values.items():
                rendered = rendered.replace(f"__{key}__", value)
        return rendered


def _format_number(value: Optional[float]) -> str:
    """
    Handle format number.

    Parameters
    ----------
    value : Optional[float]
        Value to normalize, convert, or escape.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not isinstance(value, (int, float)):
        return "n/a"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return f"{value:.6g}"


def _coerce_step_id(value: Any) -> Optional[int]:
    """
    Convert a node step-id candidate to an integer when possible.

    Parameters
    ----------
    value : Any
        Raw value that may encode a numeric step id.

    Returns
    -------
    Optional[int]
        Parsed integer step id, otherwise `None`.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _parse_node_label_metadata(node_label: str) -> Dict[str, Any]:
    """
    Parse fallback metadata directly from supported STN label formats.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.

    Returns
    -------
    Dict[str, Any]
        Parsed metadata (`phase`, `action_term`, `step_id`) when available.
    """
    parsed: Dict[str, Any] = {
        "phase": None,
        "action_term": None,
        "step_id": None,
    }
    if not isinstance(node_label, str):
        return parsed

    # Legacy alias nodes sometimes appear as: s_12-start(ll_action(...))
    legacy_alias_match = re.match(
        r"^(?P<prefix>[se])_(?P<step_id>\d+)-(?P<phase>start|end)\((?P<action>.*)\)$",
        node_label,
    )
    if legacy_alias_match:
        parsed["step_id"] = int(legacy_alias_match.group("step_id"))
        parsed["phase"] = legacy_alias_match.group("phase")
        parsed["action_term"] = legacy_alias_match.group("action")
        return parsed

    # Original partial-order node label: 12-start(ll_action(...))
    po_match = re.match(r"^(?P<step_id>\d+)-(?P<phase>start|end)\((?P<action>.*)\)$", node_label)
    if po_match:
        parsed["step_id"] = int(po_match.group("step_id"))
        parsed["phase"] = po_match.group("phase")
        parsed["action_term"] = po_match.group("action")
        return parsed

    # New/canonical STN node naming: s_action_name_12 or e_action_name_12
    canonical_match = re.match(r"^(?P<prefix>[se])_(?P<action>.+)_(?P<step_id>\d+)$", node_label)
    if canonical_match:
        parsed["step_id"] = int(canonical_match.group("step_id"))
        parsed["phase"] = "start" if canonical_match.group("prefix") == "s" else "end"
        parsed["action_term"] = canonical_match.group("action")
        return parsed

    return parsed


def _node_label_format_rank(node_label: str) -> int:
    """
    Rank label formats to prefer canonical STN node ids when deduplicating aliases.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.

    Returns
    -------
    int
        Lower values indicate preferred/canonical label formats.
    """
    if re.match(r"^[se]_.+_\d+$", node_label):
        return 0
    if re.match(r"^[se]_\d+-(start|end)\(.*\)$", node_label):
        return 1
    return 2


def _node_metadata(node_label: str, node_attrs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle node metadata.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.
    node_attrs : Dict[str, Any]
        Node attributes dictionary attached to graph nodes.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing structured results from this function.
    """
    raw_parameters = node_attrs.get("parameters")
    parameters: Dict[str, Any] = raw_parameters if isinstance(raw_parameters, dict) else {}
    phase = parameters.get("phase", node_attrs.get("phase"))
    action_term = parameters.get("action_term", node_attrs.get("action_term"))
    step_id = _coerce_step_id(parameters.get("step_id", node_attrs.get("step_id")))

    if phase is None or step_id is None or not isinstance(action_term, str) or not action_term.strip():
        parsed = _parse_node_label_metadata(node_label)
        if phase is None:
            phase = parsed.get("phase")
        if step_id is None:
            step_id = parsed.get("step_id")
        if (not isinstance(action_term, str) or not action_term.strip()) and isinstance(parsed.get("action_term"), str):
            action_term = parsed.get("action_term")

    if isinstance(action_term, str):
        action_term = action_term.strip()

    return {
        "phase": phase,
        "action_term": action_term,
        "step_id": step_id,
    }


def _node_identity_key(node_label: str, node_attrs: Dict[str, Any]) -> Optional[str]:
    """
    Build a stable identity key for equivalent node aliases.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.
    node_attrs : Dict[str, Any]
        Node attributes dictionary attached to graph nodes.

    Returns
    -------
    Optional[str]
        Canonical identity key for start/end action nodes, otherwise `None`.
    """
    metadata = _node_metadata(node_label, node_attrs)
    phase = metadata.get("phase")
    action_term = metadata.get("action_term")
    step_id = metadata.get("step_id")
    if phase not in {"start", "end"}:
        return None
    if not isinstance(action_term, str) or not action_term:
        return None
    if not isinstance(step_id, int):
        return None
    return f"{phase}|{step_id}|{action_term}"


def _action_functor(action_term: Optional[str]) -> str:
    """
    Handle action functor.

    Parameters
    ----------
    action_term : Optional[str]
        Prolog action term associated with the node or step.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not isinstance(action_term, str):
        return ""
    value = action_term.strip()
    separator_idx = value.find("(")
    if separator_idx == -1:
        return value
    return value[:separator_idx].strip()


def _node_kind_for_colors(node_label: str, node_attrs: Dict[str, Any], phase: str) -> str:
    """
    Handle node kind for colors.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.
    node_attrs : Dict[str, Any]
        Node attributes dictionary attached to graph nodes.
    phase : str
        Execution phase label (for example `start`, `end`, or `other`).

    Returns
    -------
    str
        String result produced by this function.
    """
    if phase not in {"start", "end"}:
        return "other"

    metadata = _node_metadata(node_label, node_attrs)
    is_low_level = _action_functor(metadata.get("action_term")).startswith("ll_")
    if phase == "start":
        return "ll_start" if is_low_level else "hl_start"
    return "ll_end" if is_low_level else "hl_end"


def _build_node_labels(
        node_label: str,
        node_attrs: Dict[str, Any],
        timestamp: Optional[float],
        timeline_mode: bool
    ) -> Dict[str, str]:
    """
    Handle build node labels.

    Parameters
    ----------
    node_label : str
        Node label string shown in visualizations.
    node_attrs : Dict[str, Any]
        Node attributes dictionary attached to graph nodes.
    timestamp : Optional[float]
        Optional timestamp associated with a node.
    timeline_mode : bool
        Whether timeline-oriented layout/labels are enabled.

    Returns
    -------
    Dict[str, str]
        Dictionary containing structured results from this function.
    """
    metadata = _node_metadata(node_label, node_attrs)
    timestamp_text = _format_number(timestamp) if isinstance(timestamp, (int, float)) else ""

    if not timeline_mode:
        return {
            "display": node_label,
            "detail": node_label,
        }

    if node_label in {"INIT", "END"}:
        display = f"{node_label}\nt={timestamp_text}" if timestamp_text else node_label
    else:
        phase = metadata.get("phase") or "tp"
        step_id = metadata.get("step_id")
        action_term = metadata.get("action_term") if isinstance(metadata.get("action_term"), str) else ""
        action_name = _action_functor(action_term)

        if action_term:
            display = f"{phase}: {action_term}"
            if isinstance(step_id, int):
                display = f"{display} [{step_id}]"
        elif action_name:
            display = f"{phase}: {action_name}"
            if isinstance(step_id, int):
                display = f"{display} [{step_id}]"
        elif isinstance(step_id, int):
            display = f"{phase} [{step_id}]"
        else:
            display = phase

        if timestamp_text:
            display = f"{display}\nt={timestamp_text}"

    detail_parts = [node_label]
    action_term = metadata.get("action_term")
    if isinstance(action_term, str) and action_term:
        detail_parts.append(action_term)
    if timestamp_text:
        detail_parts.append(f"t={timestamp_text}")

    return {
        "display": display,
        "detail": " | ".join(detail_parts),
    }


def _build_action_schedule_html(scheduled_actions: List[Dict[str, Any]]) -> str:
    """
    Handle build action schedule html.

    Parameters
    ----------
    scheduled_actions : List[Dict[str, Any]]
        Solved action intervals used in schedule/timeline views.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not scheduled_actions:
        return '<div class="muted">No optimized action schedule available.</div>'

    items = []
    for action in scheduled_actions:
        label = html.escape(str(action.get("display_name") or action.get("action") or "action"))
        start = _format_number(action.get("start"))
        end = _format_number(action.get("end"))
        duration = _format_number(action.get("duration"))
        items.append(
            (
                '<div class="action-item">'
                f'<div class="action-name">{label}</div>'
                f'<div class="action-times">start={start} | end={end} | duration={duration}</div>'
                "</div>"
            )
        )
    return "".join(items)


def _build_timeline_button_html(enabled: bool) -> str:
    """
    Handle build timeline button html.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return '<button class="btn" id="layoutTimeline">Timeline</button>'


def _is_duration_pair_edge(source: str, target: str, edge_data: Dict[str, Any]) -> bool:
    """
    Handle is duration pair edge.

    Parameters
    ----------
    source : str
        Source node/action descriptor.
    target : str
        Target node/action descriptor.
    edge_data : Dict[str, Any]
        Edge attributes dictionary attached to an STN connection.

    Returns
    -------
    bool
        Boolean result indicating whether the check/operation succeeded.
    """
    if not isinstance(edge_data.get("weight"), (int, float)):
        return False
    if source.startswith("s_") and target.startswith("e_"):
        return source[2:] == target[2:]
    if source.startswith("e_") and target.startswith("s_"):
        return source[2:] == target[2:]
    return False


def _build_visible_edges(stn, visible_nodes: List[Any], timeline_mode: bool) -> List[Dict[str, Any]]:
    """
    Handle build visible edges.

    Parameters
    ----------
    stn : Any
        Simple Temporal Network instance to inspect or render.
    visible_nodes : List[Any]
        Subset of nodes included in the rendered view.
    timeline_mode : bool
        Whether timeline-oriented layout/labels are enabled.

    Returns
    -------
    List[Dict[str, Any]]
        Dictionary containing structured results from this function.
    """
    visible_nodes_set = {str(node) for node in visible_nodes}
    raw_edges: List[Dict[str, Any]] = []

    for source, target, data in stn.edges(data=True):
        source_id = str(source)
        target_id = str(target)
        if source_id not in visible_nodes_set or target_id not in visible_nodes_set:
            continue

        edge_type = data.get("type", "constraint")
        weight = data.get("weight")

        if _is_duration_pair_edge(source_id, target_id, data):
            if source_id.startswith("e_"):
                continue

            reverse_data = stn.get_edge_data(target_id, source_id, default={}) or {}
            min_duration = None
            max_duration = None
            if isinstance(reverse_data.get("weight"), (int, float)):
                min_duration = -float(reverse_data["weight"])
            if isinstance(weight, (int, float)):
                max_duration = float(weight)

            if timeline_mode:
                label = "duration"
            else:
                min_text = _format_number(min_duration)
                max_text = _format_number(max_duration)
                label = f"duration | [{min_text}, {max_text}]"

            raw_edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "type": "duration",
                    "label": label,
                    "timelineLabel": "" if timeline_mode else label,
                }
            )
            continue

        if edge_type in {"ordering", "causal_link"}:
            raw_edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                    "label": f"{edge_type} | w={_format_number(weight)}" if isinstance(weight, (int, float)) else str(edge_type),
                    "timelineLabel": str(edge_type),
                    "precedence": True,
                }
            )
            for parallel_edge_type in data.get("parallel_edge_types", []):
                raw_edges.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "type": parallel_edge_type,
                        "label": str(parallel_edge_type),
                        "timelineLabel": str(parallel_edge_type),
                        "precedence": True,
                    }
                )
            continue

        label = f"{edge_type} | w={_format_number(weight)}" if isinstance(weight, (int, float)) else str(edge_type)
        raw_edges.append(
            {
                "source": source_id,
                "target": target_id,
                "type": edge_type,
                "label": label,
                "timelineLabel": "" if timeline_mode else label,
            }
        )

    visible_edges: List[Dict[str, Any]] = []
    for edge in raw_edges:
        if edge.get("precedence"):
            edge.pop("precedence", None)
        visible_edges.append(edge)

    return visible_edges


def _edge_type_label(edge_type: str) -> str:
    """
    Build a human-readable label for an edge type key.

    Parameters
    ----------
    edge_type : str
        Raw edge type value stored in Cytoscape edge data.

    Returns
    -------
    str
        Readable edge label used in sidebar controls.
    """
    known_labels = {
        "ordering": "Ordering edge",
        "causal_link": "Causal-link edge",
        "duration": "Duration constraint",
        "constraint": "Temporal/default constraint",
    }
    if edge_type in known_labels:
        return known_labels[edge_type]
    return edge_type.replace("_", " ").strip() or "unknown"


def _build_edge_filters_html(visible_edges: List[Dict[str, Any]]) -> str:
    """
    Build checkbox controls used to toggle edge types in the HTML sidebar.

    Parameters
    ----------
    visible_edges : List[Dict[str, Any]]
        Edge payload currently rendered in the Cytoscape view.

    Returns
    -------
    str
        HTML fragment for edge-type filters.
    """
    if not visible_edges:
        return '<div class="muted">No edges available.</div>'

    type_counts: Dict[str, int] = {}
    for edge in visible_edges:
        edge_type = str(edge.get("type") or "constraint")
        type_counts[edge_type] = type_counts.get(edge_type, 0) + 1

    type_order = {
        "ordering": 0,
        "causal_link": 1,
        "duration": 2,
        "constraint": 3,
    }
    ordered_types = sorted(
        type_counts.keys(),
        key=lambda item: (type_order.get(item, 99), item),
    )

    controls: List[str] = []
    for edge_type in ordered_types:
        escaped_type = html.escape(edge_type, quote=True)
        label = html.escape(_edge_type_label(edge_type))
        controls.append(
            (
                '<label class="check-item">'
                f'<input class="edge-type-filter" type="checkbox" data-edge-type="{escaped_type}" checked> '
                f"{label} ({type_counts[edge_type]})"
                '</label>'
            )
        )
    return "".join(controls)


def _build_optimized_actions_section_html(
        enabled: bool,
        scheduled_actions: List[Dict[str, Any]]
    ) -> str:
    """
    Handle build optimized actions section html.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.
    scheduled_actions : List[Dict[str, Any]]
        Solved action intervals used in schedule/timeline views.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return (
        '<div class="section">'
        '<h2>Optimized Actions</h2>'
        f'<div class="action-list">{_build_action_schedule_html(scheduled_actions)}</div>'
        "</div>"
    )


def _build_timeline_panel_html(enabled: bool, timeline_markup: str) -> str:
    """
    Handle build timeline panel html.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.
    timeline_markup : str
        HTML markup fragment used to render the timeline panel.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return f'<div id="timeline">{timeline_markup}</div>'


def _build_timeline_button_script(enabled: bool) -> str:
    """
    Handle build timeline button script.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return """const timelineButton = document.getElementById("layoutTimeline");
    if (timelineButton) {
      timelineButton.addEventListener("click", () => {
        if (!hasTimeline) {
          return;
        }
        cy.layout({
          name: "preset",
          fit: true,
          padding: 50
        }).run();
      });
    }"""


def _build_timeline_sync_script(enabled: bool, timeline_config_json: str) -> str:
    """
    Handle build timeline sync script.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.
    timeline_config_json : str
        Serialized timeline configuration JSON passed to frontend code.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return f"""const timelineConfig = {timeline_config_json};
    const SVG_NS = "http://www.w3.org/2000/svg";

    function createTimelineSvgNode(tagName, attrs, textContent) {{
      const node = document.createElementNS(SVG_NS, tagName);
      Object.entries(attrs || {{}}).forEach(([key, value]) => {{
        node.setAttribute(key, String(value));
      }});
      if (textContent !== undefined) {{
        node.textContent = textContent;
      }}
      return node;
    }}

    function modelXToScreenX(modelX) {{
      return (cy.zoom() * modelX) + cy.pan().x;
    }}

    function renderTimeline() {{
      if (!hasTimeline || !timelineConfig) {{
        return;
      }}

      const svg = document.getElementById("timelineSvg");
      if (!svg) {{
        return;
      }}

      const viewportWidth = Math.max(svg.clientWidth || 0, 1);
      svg.setAttribute("viewBox", `0 0 ${{viewportWidth}} 84`);
      svg.replaceChildren();

      const axisY = 52;
      const labelY = 22;
      const axisStartX = modelXToScreenX(timelineConfig.axisStart);
      const axisEndX = modelXToScreenX(timelineConfig.axisEnd);

      svg.appendChild(
        createTimelineSvgNode("line", {{
          x1: axisStartX,
          y1: axisY,
          x2: axisEndX,
          y2: axisY,
          stroke: "#1f2937",
          "stroke-width": 2,
        }})
      );

      timelineConfig.ticks.forEach((tick) => {{
        const screenX = modelXToScreenX(tick.modelX);
        svg.appendChild(
          createTimelineSvgNode("line", {{
            x1: screenX,
            y1: axisY - 10,
            x2: screenX,
            y2: axisY + 10,
            stroke: "#475569",
            "stroke-width": 1.5,
          }})
        );
        svg.appendChild(
          createTimelineSvgNode(
            "text",
            {{
              x: screenX,
              y: labelY,
              "text-anchor": "middle",
              "font-size": 12,
              fill: "#0f172a",
            }},
            tick.label
          )
        );
      }});

      svg.appendChild(
        createTimelineSvgNode(
          "text",
          {{
            x: axisStartX,
            y: 76,
            "font-size": 12,
            fill: "#475569",
          }},
          `t = ${{timelineConfig.minLabel}}`
        )
      );
      svg.appendChild(
        createTimelineSvgNode(
          "text",
          {{
            x: axisEndX,
            y: 76,
            "text-anchor": "end",
            "font-size": 12,
            fill: "#475569",
          }},
          `t = ${{timelineConfig.maxLabel}}`
        )
      );
    }}

    if (hasTimeline) {{
      renderTimeline();
      cy.on("zoom pan", renderTimeline);
      cy.on("layoutstop", () => window.requestAnimationFrame(renderTimeline));
      window.addEventListener("resize", renderTimeline);
    }}"""


def _build_timeline_markup(enabled: bool) -> str:
    """
    Handle build timeline markup.

    Parameters
    ----------
    enabled : bool
        Whether the related UI or feature should be enabled.

    Returns
    -------
    str
        String result produced by this function.
    """
    if not enabled:
        return ""
    return '<svg id="timelineSvg" aria-label="timeline"></svg>'


def _format_hover_number(value: Any) -> str:
    """Format numeric values for hover labels."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.6g}"
    return "n/a"


def _timepoint_graph_node_kind(node_label: str, node_attrs: Dict[str, Any]) -> str:
    """Classify a raw STN timepoint for Cytoscape styling."""
    metadata = _node_metadata(node_label, node_attrs)
    phase = metadata.get("phase")
    if node_label in {"INIT", "END"}:
        return "boundary"
    if phase == "start" or node_label.startswith("s_"):
        return "start"
    if phase == "end" or node_label.startswith("e_"):
        return "end"
    return "other"


def _timepoint_relation_label(relation: str) -> str:
    """Build a human-readable label for a derived timepoint graph relation."""
    labels = {
        "ordering": "ordering",
        "causal_link": "enabler",
        "mock": "boundary",
        "duration": "action duration",
    }
    return labels.get(relation, relation.replace("_", " "))


def _format_timepoint_details(data: Dict[str, Any], kind: str) -> str:
    """Build compact sidebar details for a Cytoscape node or edge."""
    lines: List[str] = []
    if kind == "node":
        lines.append(f"Timepoint: {data.get('label', data.get('id', ''))}")
        timestamp = data.get("optimizedTime")
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            lines.append(f"Optimized time: {_format_number(float(timestamp))}")
        node_kind = data.get("nodeKind")
        if node_kind:
            lines.append(f"Kind: {node_kind}")
    else:
        lines.append(f"Edge: {data.get('source', '')} -> {data.get('target', '')}")
        relations = data.get("relations")
        if isinstance(relations, list) and relations:
            relation_text = ", ".join(_timepoint_relation_label(str(item)) for item in relations)
            lines.append(f"Sources: {relation_text}")
    return "\n".join(lines)


def _add_timepoint_relation(
    edge_map: Dict[tuple, Dict[str, Any]],
    source_id: str,
    target_id: str,
    relation: str,
) -> None:
    """Add or merge one derived timepoint relation."""
    if source_id == target_id:
        return
    edge_key = (source_id, target_id)
    edge_data = edge_map.setdefault(
        edge_key,
        {
            "source": source_id,
            "target": target_id,
            "relations": set(),
        },
    )
    edge_data["relations"].add(relation)


def _is_forward_action_duration_edge(source_id: str, target_id: str, edge_data: Dict[str, Any]) -> bool:
    """Return true for the forward start-to-end duration edge of one action."""
    if edge_data.get("type") != "duration":
        return False
    weight = edge_data.get("weight")
    if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0 or math.isinf(float(weight)):
        return False
    source_metadata = _parse_node_label_metadata(source_id)
    target_metadata = _parse_node_label_metadata(target_id)
    return bool(
        source_metadata.get("phase") == "start"
        and target_metadata.get("phase") == "end"
        and source_metadata.get("action_term")
        and source_metadata.get("action_term") == target_metadata.get("action_term")
    )


def _dependency_relation_types(source_id: str, target_id: str, edge_data: Dict[str, Any]) -> List[str]:
    """Return ordering/enabler relation types represented by one STN edge."""
    relation_types: List[str] = []
    edge_type = str(edge_data.get("type") or "")
    if edge_type in {"ordering", "causal_link", "mock"}:
        relation_types.append(edge_type)
    elif _is_forward_action_duration_edge(source_id, target_id, edge_data):
        relation_types.append("duration")
    for parallel_type in edge_data.get("parallel_edge_types", []):
        parallel_type = str(parallel_type)
        if parallel_type in {"ordering", "causal_link", "mock"} and parallel_type not in relation_types:
            relation_types.append(parallel_type)
    return relation_types


def _transitively_reduce_timepoint_edges(edge_map: Dict[tuple, Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    """Remove dependency edges that are implied by another dependency path."""
    if not edge_map:
        return {}

    graph = nx.DiGraph()
    graph.add_edges_from(edge_map.keys())
    if nx.is_directed_acyclic_graph(graph):
        kept_edges = set(nx.transitive_reduction(graph).edges())
    else:
        kept_edges = set()
        for source_id, target_id in edge_map:
            graph.remove_edge(source_id, target_id)
            if not nx.has_path(graph, source_id, target_id):
                kept_edges.add((source_id, target_id))
            graph.add_edge(source_id, target_id)

    return {edge_key: edge_map[edge_key] for edge_key in edge_map if edge_key in kept_edges}


def _reduce_execution_edges_preserving_init_fanout(
    edge_map: Dict[tuple, Dict[str, Any]],
    root_children: Optional[set] = None,
) -> Dict[tuple, Dict[str, Any]]:
    """Reduce execution edges while keeping explicit INIT branch roots."""
    if not edge_map:
        return {}
    if root_children is None:
        return _transitively_reduce_timepoint_edges(edge_map)

    root_children = {str(node) for node in root_children if str(node) not in {"INIT", "END"}}
    root_edges = {
        edge_key: edge_data
        for edge_key, edge_data in edge_map.items()
        if edge_key[0] == "INIT" and edge_key[1] in root_children
    }

    pruned_edges = {
        edge_key: edge_data
        for edge_key, edge_data in edge_map.items()
        if edge_key[0] != "INIT" or edge_key[1] in root_children or edge_key[1] == "END"
    }
    if len(root_children) > 1:
        for edge_key in list(pruned_edges):
            source_id, target_id = edge_key
            if source_id in root_children and target_id in root_children:
                del pruned_edges[edge_key]

    reduced_edges = _transitively_reduce_timepoint_edges(pruned_edges)
    for edge_key, edge_data in root_edges.items():
        reduced_edges[edge_key] = edge_data
    return reduced_edges


def _select_initial_root_children(edge_map: Dict[tuple, Dict[str, Any]], node_timestamp, node_order_index) -> set:
    """Select the first optimized execution layer below INIT."""
    init_edge_targets = sorted(
        {
            target_id
            for source_id, target_id in edge_map
            if source_id == "INIT" and target_id != "END"
        },
        key=lambda node: node_order_index.get(node, len(node_order_index)),
    )
    timed_init_targets = [
        (node_label, node_timestamp(node_label))
        for node_label in init_edge_targets
    ]
    timed_init_targets = [
        (node_label, timestamp)
        for node_label, timestamp in timed_init_targets
        if timestamp is not None
    ]
    if not timed_init_targets:
        return set(init_edge_targets)

    first_time = min(cast(float, timestamp) for _, timestamp in timed_init_targets)
    return {
        node_label
        for node_label, timestamp in timed_init_targets
        if cast(float, timestamp) <= first_time + 1.0e-3 + 1.0e-9
    }


def _build_stn_execution_dependency_edge_map(stn, visible_node_ids: set) -> Dict[tuple, Dict[str, Any]]:
    """Build the unreduced execution graph edge map."""
    dependency_edges: Dict[tuple, Dict[str, Any]] = {}
    for source, target, data in stn.edges(data=True):
        source_id = str(source)
        target_id = str(target)
        if source_id not in visible_node_ids or target_id not in visible_node_ids:
            continue

        for relation_type in _dependency_relation_types(source_id, target_id, data):
            _add_timepoint_relation(dependency_edges, source_id, target_id, relation_type)

    return dependency_edges


def _build_stn_execution_edge_map(stn, visible_node_ids: set) -> Dict[tuple, Dict[str, Any]]:
    """Build the reduced execution graph edge map used by BT export and HTML."""
    dependency_edges = _build_stn_execution_dependency_edge_map(stn, visible_node_ids)
    return _reduce_execution_edges_preserving_init_fanout(dependency_edges)


def export_stn_timepoint_graph_html(
    stn,
    path: str,
    title: str = "Optimized STN Execution Graph",
    max_nodes: Optional[int] = None,
    time_assignments: Optional[Dict[str, float]] = None,
) -> None:
    """
    Export a derived STN timepoint graph as a Cytoscape graph.

    The graph keeps the STN timepoints as nodes and renders the reduced
    dependency graph: ordering/enabler edges, forward action-duration edges,
    and mock INIT/END edges used only to preserve explicit branch roots and
    leaves.
    """
    graph_data = cast(Dict[str, Any], getattr(stn, "graph", {}))
    if not isinstance(time_assignments, dict):
        graph_assignments = graph_data.get("optimized_assignments")
        time_assignments = graph_assignments if isinstance(graph_assignments, dict) else {}

    all_nodes = list(stn.nodes())
    if max_nodes is None or max_nodes <= 0:
        visible_nodes_raw = all_nodes
    else:
        visible_nodes_raw = all_nodes[:max_nodes]
    visible_node_ids = {str(node) for node in visible_nodes_raw}

    elements = {"nodes": [], "edges": []}
    for node in visible_nodes_raw:
        node_label = str(node)
        node_attrs = stn.nodes[node]
        node_kind = _timepoint_graph_node_kind(node_label, node_attrs)
        metadata = _node_metadata(node_label, node_attrs)
        timestamp = time_assignments.get(node_label, node_attrs.get("optimized_time"))

        node_data: Dict[str, Any] = {
            "id": node_label,
            "label": node_label,
            "nodeKind": node_kind,
            "search": " ".join(
                str(value)
                for value in [
                    node_label,
                    node_kind,
                    metadata.get("phase"),
                    metadata.get("action_term"),
                    metadata.get("step_id"),
                ]
                if value is not None
            ).lower(),
        }
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            node_data["optimizedTime"] = float(timestamp)
        node_data["details"] = _format_timepoint_details(node_data, "node")
        elements["nodes"].append({"data": node_data})

    node_original_indexes = {str(node): index for index, node in enumerate(visible_nodes_raw)}
    visible_edge_candidates = _build_stn_execution_dependency_edge_map(stn, visible_node_ids)

    def visible_node_timestamp(node_label: str) -> Optional[float]:
        node_attrs = stn.nodes[node_label] if node_label in stn.nodes else {}
        timestamp = time_assignments.get(node_label, node_attrs.get("optimized_time"))
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            return float(timestamp)
        return None

    initial_root_children = _select_initial_root_children(
        visible_edge_candidates,
        visible_node_timestamp,
        node_original_indexes,
    )
    visible_edges = _reduce_execution_edges_preserving_init_fanout(
        visible_edge_candidates,
        root_children=initial_root_children,
    )

    edge_count = 0
    for edge_key in sorted(
        visible_edges,
        key=lambda item: (
            node_original_indexes.get(item[0], 0),
            node_original_indexes.get(item[1], 0),
            item[0],
            item[1],
        ),
    ):
        merged_data = visible_edges[edge_key]
        source_id = str(merged_data["source"])
        target_id = str(merged_data["target"])
        relations = sorted(
            str(relation)
            for relation in merged_data.get("relations", set())
        )
        relation_labels = [_timepoint_relation_label(relation) for relation in relations]
        edge_data: Dict[str, Any] = {
            "id": f"edge_{edge_count}",
            "source": source_id,
            "target": target_id,
            "type": "timepoint_relation",
            "label": "",
            "relations": relations,
        }
        edge_data["search"] = (
            f"{source_id} {target_id} {' '.join(relations)} {' '.join(relation_labels)}"
        ).lower()
        edge_data["details"] = _format_timepoint_details(edge_data, "edge")
        elements["edges"].append({"data": edge_data})
        edge_count += 1

    payload = json.dumps(elements, ensure_ascii=True, indent=2).replace("</", "<\\/")
    title_escaped = html.escape(title)
    default_details = "Click a timepoint or edge to inspect the derived STN relation."
    default_details_json = json.dumps(default_details, ensure_ascii=True)

    html_content = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__TITLE__</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f6f8fb; color: #172033; }
    .page { display: grid; grid-template-columns: 340px 1fr; min-height: 100vh; }
    .sidebar { padding: 16px; border-right: 1px solid #d0d7de; background: #ffffff; overflow-y: auto; }
    .title { margin: 0 0 6px; font-size: 20px; }
    .muted { color: #536173; font-size: 13px; line-height: 1.35; }
    .section { margin-top: 14px; padding-top: 10px; border-top: 1px solid #e3e8ef; }
    .section h2 { margin: 0 0 8px; font-size: 14px; }
    .stats { display: grid; gap: 4px; font-size: 13px; }
    .legend-list, .check-list { display: flex; flex-direction: column; gap: 7px; }
    .legend-item, .check-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #334155; }
    .swatch { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #334155; display: inline-block; }
    .swatch-line { width: 16px; height: 0; border-top: 3px solid #64748b; display: inline-block; }
    .control { width: 100%; box-sizing: border-box; border: 1px solid #c9d4e2; border-radius: 8px; padding: 8px 10px; font-size: 13px; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .btn { border: 1px solid #b8c7da; background: #eef4fb; color: #19324f; padding: 6px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
    #details { font-size: 13px; line-height: 1.35; white-space: pre-wrap; }
    #cy { width: 100%; height: 100vh; background: #ffffff; }
    @media (max-width: 900px) {
      .page { grid-template-columns: 1fr; }
      .sidebar { border-right: none; border-bottom: 1px solid #d0d7de; }
      #cy { height: 72vh; }
    }
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <h1 class="title">__TITLE__</h1>
      <div class="muted">Derived Simple Temporal Network: nodes are timepoints, edges show the reduced enabler/ordering structure from INIT to END.</div>
      <div class="section">
        <h2>Summary</h2>
        <div class="stats">
          <div>Timepoints shown: __VISIBLE_NODES__ / __TOTAL_NODES__</div>
          <div>Edges shown: __VISIBLE_EDGES__ / __TOTAL_EDGES__</div>
        </div>
      </div>
      <div class="section">
        <h2>Timepoints</h2>
        <div class="legend-list">
          <div class="legend-item"><span class="swatch" style="background:#2E86AB"></span>Start timepoint</div>
          <div class="legend-item"><span class="swatch" style="background:#E76F51"></span>End timepoint</div>
          <div class="legend-item"><span class="swatch" style="background:#6C757D"></span>Boundary/other</div>
        </div>
      </div>
      <div class="section">
        <h2>Edges</h2>
        <div class="legend-list">
          <div class="legend-item"><span class="swatch-line" style="border-top-color:#475569"></span>Derived timepoint relation</div>
        </div>
      </div>
      <div class="section">
        <h2>Search</h2>
        <input id="search" class="control" type="text" placeholder="Search timepoint or edge">
      </div>
      <div class="section">
        <h2>Layout</h2>
        <div class="btn-row">
          <button class="btn" id="layoutBreadth">Breadthfirst</button>
          <button class="btn" id="layoutCose">Force-directed</button>
          <button class="btn" id="fit">Fit</button>
        </div>
      </div>
      <div class="section">
        <h2>Details</h2>
        <div id="details">__DEFAULT_DETAILS__</div>
      </div>
    </aside>
    <main><div id="cy"></div></main>
  </div>

  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  <script>
    const payload = __PAYLOAD__;
    const defaultDetails = __DEFAULT_DETAILS_JSON__;
    const cy = cytoscape({
      container: document.getElementById("cy"),
      elements: [...payload.nodes, ...payload.edges],
      style: [
        {
          selector: "node",
          style: {
            "label": "data(label)",
            "font-size": 9,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "text-valign": "center",
            "text-halign": "center",
            "width": 38,
            "height": 38,
            "background-color": "#6C757D",
            "border-width": 1.2,
            "border-color": "#23395b",
            "color": "#0b1f33"
          }
        },
        { selector: "node[nodeKind = 'start']", style: { "background-color": "#2E86AB" } },
        { selector: "node[nodeKind = 'end']", style: { "background-color": "#E76F51" } },
        { selector: "node[nodeKind = 'boundary']", style: { "background-color": "#6C757D" } },
        { selector: "node.focus", style: { "border-width": 3, "border-color": "#0f172a" } },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "line-color": "#475569",
            "target-arrow-color": "#475569",
            "width": 1.8,
            "label": "data(label)",
            "font-size": 8,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": 2,
            "text-rotation": "autorotate"
          }
        },
        { selector: "edge.focus", style: { "width": 3.2 } }
      ],
      layout: {
        name: "breadthfirst",
        directed: true,
        spacingFactor: 1.25,
        fit: true,
        padding: 35
      }
    });

    const details = document.getElementById("details");

    function applySearchFilter() {
      const query = document.getElementById("search").value.trim().toLowerCase();
      if (!query) {
        cy.nodes().forEach((node) => node.style("opacity", 1.0));
        cy.edges().forEach((edge) => edge.style("opacity", 0.9));
        return;
      }
      cy.nodes().forEach((node) => {
        const match = String(node.data("search") || "").includes(query);
        node.style("opacity", match ? 1.0 : 0.18);
      });
      cy.edges().forEach((edge) => {
        const match = String(edge.data("search") || "").includes(query);
        edge.style("opacity", match ? 0.9 : 0.08);
      });
    }

    cy.on("tap", "node", (evt) => {
      cy.elements().removeClass("focus");
      const node = evt.target;
      node.addClass("focus");
      node.connectedEdges().addClass("focus");
      details.textContent = node.data("details") || node.id();
    });

    cy.on("tap", "edge", (evt) => {
      cy.elements().removeClass("focus");
      const edge = evt.target;
      edge.addClass("focus");
      edge.connectedNodes().addClass("focus");
      details.textContent = edge.data("details") || edge.id();
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass("focus");
        details.textContent = defaultDetails;
      }
    });

    document.getElementById("search").addEventListener("input", applySearchFilter);
    document.getElementById("layoutBreadth").addEventListener("click", () => {
      cy.layout({ name: "breadthfirst", directed: true, spacingFactor: 1.25, fit: true, padding: 35 }).run();
    });
    document.getElementById("layoutCose").addEventListener("click", () => {
      cy.layout({ name: "cose", animate: false, fit: true, padding: 35, nodeRepulsion: 6500, idealEdgeLength: 95 }).run();
    });
    document.getElementById("fit").addEventListener("click", () => cy.fit(undefined, 35));
  </script>
</body>
</html>
"""
    html_content = (
        html_content
        .replace("__TITLE__", title_escaped)
        .replace("__VISIBLE_NODES__", str(len(elements["nodes"])))
        .replace("__TOTAL_NODES__", str(stn.number_of_nodes()))
        .replace("__VISIBLE_EDGES__", str(len(elements["edges"])))
        .replace("__TOTAL_EDGES__", str(stn.number_of_edges()))
        .replace("__DEFAULT_DETAILS__", html.escape(default_details))
        .replace("__DEFAULT_DETAILS_JSON__", default_details_json)
        .replace("__PAYLOAD__", payload)
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html_content)


def export_stn_cytoscape_html(
    stn,
    path: str,
    title: str = "Simple Temporal Network",
    max_nodes: Optional[int] = None,
    time_assignments: Optional[Dict[str, float]] = None,
    scheduled_actions: Optional[List[Dict[str, Any]]] = None,
    show_timeline: bool = False,
) -> None:
    """
    Export an STN-like graph as an interactive Cytoscape HTML page.

    Parameters
    ----------
    stn : Any
        Simple Temporal Network instance to inspect or render.
    path : str
        Filesystem path used by this operation.
    title : str, optional
        Title text used in generated reports or visualizations.
    max_nodes : Optional[int]
        Upper bound on the number of nodes to include.
    time_assignments : Optional[Dict[str, float]]
        Mapping from node labels to solved timestamps.
    scheduled_actions : Optional[List[Dict[str, Any]]]
        Solved action intervals used in schedule/timeline views.
    show_timeline : bool, optional
        Whether to render timeline-specific UI and layout.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    scheduled_actions = scheduled_actions if isinstance(scheduled_actions, list) else []
    time_assignments = time_assignments if isinstance(time_assignments, dict) else {}

    elements = {"nodes": [], "edges": []}
    all_nodes = list(stn.nodes())
    if max_nodes is None or max_nodes <= 0:
        visible_nodes_raw = all_nodes
    else:
        # Keep a deterministic prefix for large graphs to avoid oversized HTML payloads.
        visible_nodes_raw = all_nodes[:max_nodes]

    # Collapse equivalent aliases (for example legacy `s_<id>-start(...)` vs canonical `s_<action>_<id>`).
    identity_groups: Dict[str, List[str]] = {}
    for node in visible_nodes_raw:
        node_label = str(node)
        node_attrs = stn.nodes[node]
        identity_key = _node_identity_key(node_label, node_attrs)
        if identity_key is None:
            identity_key = f"__raw__{node_label}"
        identity_groups.setdefault(identity_key, []).append(node_label)

    node_alias: Dict[str, str] = {}
    for grouped_labels in identity_groups.values():
        representative = min(grouped_labels, key=lambda label: (_node_label_format_rank(label), label))
        for label in grouped_labels:
            node_alias[label] = representative

    visible_nodes: List[str] = []
    seen_visible: set = set()
    for node in visible_nodes_raw:
        representative = node_alias.get(str(node), str(node))
        if representative in seen_visible:
            continue
        seen_visible.add(representative)
        visible_nodes.append(representative)

    visible_times: Dict[str, float] = {}
    for node in visible_nodes_raw:
        node_label = str(node)
        representative = node_alias.get(node_label, node_label)
        timestamp = time_assignments.get(node_label)
        if isinstance(timestamp, (int, float)):
            value = float(timestamp)
            if representative in visible_times:
                visible_times[representative] = min(visible_times[representative], value)
            else:
                visible_times[representative] = value

    # Timeline layout is enabled only when timestamps are actually available.
    has_timeline = bool(show_timeline and visible_times)
    min_time = min(visible_times.values()) if visible_times else 0.0
    max_time = max(visible_times.values()) if visible_times else 0.0
    time_span = max(max_time - min_time, 0.0)
    left_pad = 110.0
    right_pad = 110.0
    usable_width = max(1100.0, 220.0 * max(time_span, 1.0))
    canvas_width = left_pad + usable_width + right_pad
    lane_y = {
        "boundary": 110.0,
        "start": 240.0,
        "end": 370.0,
        "other": 500.0,
    }
    bucket_width = 70.0
    lane_buckets: Dict[str, Dict[int, int]] = {}

    sorted_nodes = sorted(
        visible_nodes,
        key=lambda item: (
            visible_times.get(str(item), min_time),
            str(item),
        ),
    )

    for node in sorted_nodes:
        node_label = str(node)
        node_attrs = stn.nodes[node] if node in stn.nodes else {}
        metadata = _node_metadata(node_label, node_attrs)

        phase = "other"
        if node_label in {"INIT", "END"}:
            phase = "boundary"
        elif metadata.get("phase") in {"start", "end"}:
            phase = metadata["phase"]
        elif node_label.startswith("s_"):
            phase = "start"
        elif node_label.startswith("e_"):
            phase = "end"

        labels = _build_node_labels(
            node_label=node_label,
            node_attrs=node_attrs,
            timestamp=visible_times.get(node_label),
            timeline_mode=has_timeline,
        )
        node_kind = _node_kind_for_colors(node_label, node_attrs, phase)
        search_parts = [
            node_label,
            labels["display"],
            labels["detail"],
            phase,
            node_kind,
            str(metadata.get("action_term") or ""),
        ]
        search_blob = " ".join(part for part in search_parts if part).lower()

        node_entry: Dict[str, Any] = {
            "data": {
                "id": node_label,
                "label": node_label,
                "displayLabel": labels["display"],
                "detailLabel": labels["detail"],
                "phase": phase,
                "nodeKind": node_kind,
                "search": search_blob,
            }
        }

        timestamp = visible_times.get(node_label)
        if isinstance(timestamp, (int, float)):
            node_entry["data"]["timestamp"] = float(timestamp)

        if has_timeline:
            # Place nodes on horizontal time axis; stack collisions in the same lane bucket.
            if isinstance(timestamp, (int, float)):
                if time_span <= 0:
                    x = left_pad + (usable_width / 2.0)
                else:
                    x = left_pad + ((timestamp - min_time) / time_span) * usable_width
            else:
                x = left_pad / 2.0

            bucket = int(round((x - left_pad) / bucket_width))
            phase_buckets = lane_buckets.setdefault(phase, {})
            offset_index = phase_buckets.get(bucket, 0)
            phase_buckets[bucket] = offset_index + 1
            y = lane_y.get(phase, lane_y["other"]) + (offset_index * 46.0)
            node_entry["position"] = {"x": x, "y": y}

        elements["nodes"].append(node_entry)

    raw_visible_edges = _build_visible_edges(
        stn=stn,
        visible_nodes=visible_nodes_raw,
        timeline_mode=has_timeline,
    )
    visible_edges: List[Dict[str, Any]] = []
    seen_edge_keys: set = set()
    for edge in raw_visible_edges:
        source_alias = node_alias.get(edge["source"], edge["source"])
        target_alias = node_alias.get(edge["target"], edge["target"])
        if source_alias == target_alias:
            continue

        remapped_edge = dict(edge)
        remapped_edge["source"] = source_alias
        remapped_edge["target"] = target_alias

        edge_key = (
            remapped_edge["source"],
            remapped_edge["target"],
            remapped_edge.get("type"),
            remapped_edge.get("label"),
            remapped_edge.get("timelineLabel"),
        )
        if edge_key in seen_edge_keys:
            continue
        seen_edge_keys.add(edge_key)
        visible_edges.append(remapped_edge)
    # Edge labels are switched in timeline mode to keep the graph readable.
    for edge_id, edge in enumerate(visible_edges):
        elements["edges"].append(
            {
                "data": {
                    "id": f"e{edge_id}",
                    "source": edge["source"],
                    "target": edge["target"],
                    "label": edge["label"],
                    "timelineLabel": edge["timelineLabel"],
                    "type": edge["type"],
                    "search": (
                        f"{edge['source']} {edge['target']} "
                        f"{edge['type']} {edge['label']} {edge['timelineLabel']}"
                    ).lower(),
                }
            }
        )

    payload = json.dumps(elements, ensure_ascii=True, indent=2).replace("</", "<\\/")
    title_escaped = html.escape(title)
    node_label_field = "data(displayLabel)" if has_timeline else "data(label)"
    edge_label_field = "data(timelineLabel)" if has_timeline else "data(label)"
    node_font_size = 9 if has_timeline else 10
    node_text_max_width = 110 if has_timeline else 180
    node_size = 42 if has_timeline else 34
    default_details = "Click to select. Ctrl/Cmd+click to multi-select. Click empty space to clear highlight."
    summary_time_html = ""
    if has_timeline:
        summary_time_html = (
            f"<div>Time range: {_format_number(min_time)} to {_format_number(max_time)}</div>"
        )

    graph_wrap_class = "graph-wrap timeline-graph" if has_timeline else "graph-wrap"
    timeline_html = _build_timeline_markup(enabled=has_timeline)
    timeline_panel_html = _build_timeline_panel_html(has_timeline, timeline_html)
    timeline_button_html = _build_timeline_button_html(has_timeline)
    timeline_button_script = _build_timeline_button_script(has_timeline)
    tick_count = 6 if time_span > 0 else 1
    tick_values = (
        [min_time + (time_span * idx / (tick_count - 1)) for idx in range(tick_count)]
        if tick_count > 1
        else [min_time]
    )
    timeline_config = {
        "axisStart": left_pad,
        "axisEnd": canvas_width - right_pad,
        "minLabel": _format_number(min_time),
        "maxLabel": _format_number(max_time),
        "ticks": [
            {
                "modelX": (
                    left_pad
                    if time_span <= 0
                    else left_pad + ((tick_value - min_time) / time_span) * usable_width
                ),
                "label": _format_number(tick_value),
            }
            for tick_value in tick_values
        ],
    }
    timeline_sync_script = _build_timeline_sync_script(
        has_timeline,
        json.dumps(timeline_config, ensure_ascii=True),
    )
    optimized_actions_section_html = _build_optimized_actions_section_html(
        has_timeline,
        scheduled_actions,
    )
    edge_filters_html = _build_edge_filters_html(visible_edges)

    js_template = _read_template(_JS_TEMPLATE_PATH)
    js_content = _render_template(
        js_template,
        {
            "PAYLOAD_JSON": payload,
            "HAS_TIMELINE": str(has_timeline).lower(),
            "NODE_LABEL_FIELD": node_label_field,
            "NODE_FONT_SIZE": str(node_font_size),
            "NODE_TEXT_MAX_WIDTH": str(node_text_max_width),
            "NODE_SIZE": str(node_size),
            "OTHER_NODE_COLOR": PO_NODE_COLORS["other"],
            "HL_START_COLOR": PO_NODE_COLORS["hl_start"],
            "HL_END_COLOR": PO_NODE_COLORS["hl_end"],
            "LL_START_COLOR": PO_NODE_COLORS["ll_start"],
            "LL_END_COLOR": PO_NODE_COLORS["ll_end"],
            "OTHER_EDGE_COLOR": PO_EDGE_COLORS["other"],
            "EDGE_LABEL_FIELD": edge_label_field,
            "ASSUMPTION_EDGE_COLOR": PO_EDGE_COLORS["assumption"],
            "CAUSAL_EDGE_COLOR": PO_EDGE_COLORS["causal"],
            "TIMELINE_SYNC_SCRIPT": timeline_sync_script,
            "TIMELINE_BUTTON_SCRIPT": timeline_button_script,
            "DEFAULT_DETAILS_JSON": json.dumps(default_details, ensure_ascii=True),
        },
    )

    html_template = _read_template(_HTML_TEMPLATE_PATH)
    html_content = _render_template(
        html_template,
        {
            "TITLE_ESCAPED": title_escaped,
            "VISIBLE_NODES_COUNT": str(len(visible_nodes)),
            "TOTAL_NODES_COUNT": str(stn.number_of_nodes()),
            "VISIBLE_EDGES_COUNT": str(len(elements["edges"])),
            "TOTAL_EDGES_COUNT": str(stn.number_of_edges()),
            "SUMMARY_TIME_HTML": summary_time_html,
            "HL_START_COLOR": PO_NODE_COLORS["hl_start"],
            "HL_END_COLOR": PO_NODE_COLORS["hl_end"],
            "LL_START_COLOR": PO_NODE_COLORS["ll_start"],
            "LL_END_COLOR": PO_NODE_COLORS["ll_end"],
            "OTHER_NODE_COLOR": PO_NODE_COLORS["other"],
            "ASSUMPTION_EDGE_COLOR": PO_EDGE_COLORS["assumption"],
            "CAUSAL_EDGE_COLOR": PO_EDGE_COLORS["causal"],
            "OTHER_EDGE_COLOR": PO_EDGE_COLORS["other"],
            "EDGE_FILTERS_HTML": edge_filters_html,
            "TIMELINE_BUTTON_HTML": timeline_button_html,
            "OPTIMIZED_ACTIONS_SECTION_HTML": optimized_actions_section_html,
            "DEFAULT_DETAILS_ESCAPED": html.escape(default_details),
            "GRAPH_WRAP_CLASS": graph_wrap_class,
            "TIMELINE_PANEL_HTML": timeline_panel_html,
            "INLINE_SCRIPT": js_content,
        },
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html_content)


class STNVisualizationMixin:
    """Visualization helpers mixed into SimpleTemporalNetwork."""

    def draw(self, path: str) -> None:
        """
        Draw the Simple Temporal Network using matplotlib.

        Parameters
        ----------
        path : str
            Output path for the rendered figure, or `show` to display interactively.

        Returns
        -------
        None
            This function performs side effects only.
        """
        import matplotlib.pyplot as plt

        graph = cast(nx.DiGraph, self)
        pos = nx.planar_layout(graph)

        def offset_label_pos(pos, u, v, offset=0.05):
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            xm = (x1 + x2) / 2
            ym = (y1 + y2) / 2
            ex = x2 - x1
            ey = y2 - y1
            nxp = -ey
            nyp = ex
            norm = (nxp**2 + nyp**2)**0.5
            nxp /= norm
            nyp /= norm
            return (xm + offset * nxp, ym + offset * nyp)

        positive_label_pos = {
            (u, v): offset_label_pos(pos, u, v, offset=0.05)
          for u, v in graph.edges()
        }

        nx.draw_networkx_nodes(graph, pos, node_size=200, node_color="lightgreen")
        nx.draw_networkx_labels(graph, pos)

        ordering_edges = [(u, v) for u, v, data in graph.edges(data=True) if data.get("type") == "ordering"]
        nx.draw_networkx_edges(graph, pos, edgelist=ordering_edges, edge_color="red", arrows=True)

        casual_link_edges = [(u, v) for u, v, data in graph.edges(data=True) if data.get("type") == "causal_link"]
        nx.draw_networkx_edges(graph, pos, edgelist=casual_link_edges, edge_color="green", arrows=True)

        positive_edges = {
            (u, v): data["weight"]
          for u, v, data in graph.edges(data=True)
            if (u, v) not in ordering_edges + casual_link_edges and data["weight"] >= +0
        }
        nx.draw_networkx_edges(
          graph,
            pos,
          edgelist=list(positive_edges.keys()),
            edge_color="blue",
            arrows=True,
            connectionstyle="arc3,rad=0.1",
        )
        nx.draw_networkx_edge_labels(graph, pos=positive_label_pos, edge_labels=positive_edges, font_color="blue")

        negative_edges = {
            (u, v): data["weight"]
          for u, v, data in graph.edges(data=True)
            if (u, v) not in ordering_edges + casual_link_edges and data["weight"] < +0
        }
        nx.draw_networkx_edges(
          graph,
            pos,
          edgelist=list(negative_edges.keys()),
            edge_color="orange",
            arrows=True,
            connectionstyle="arc3,rad=0.1",
        )
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=negative_edges, font_color="orange")

        if path is not None and path != "":
            if path == "show":
                plt.show()
            else:
                plt.savefig(path)
        plt.close()

    
    def to_xml_bt(
        self,
        filename: Optional[str] = None,
        robot_ids: Optional[Union[List[str], str]] = None,
        tree_id: Optional[str] = "MainTree",
        root_sequence_name: Optional[str] = "optimized_stn_sequence",
    ) -> str:
        """
        Convert the optimized STN schedule to an MP/BT-compatible XML tree.

        Parameters
        ----------
        filename : Optional[str], optional
            Output file path. When omitted, only the XML payload is returned.
        robot_ids : Optional[Union[List[str], str]], optional
            Optional list of robot IDs or a string of comma-separated robot IDs. They must match the agents or robots used inside the STN actions.
        tree_id : str, optional
            BehaviorTree ID and root main_tree_to_execute value.
        root_sequence_name : str, optional
            Deprecated; generated control nodes are named SEQUENCE or PARALLEL.

        Returns
        -------
        str
            XML payload string.
        """
        import xml.etree.ElementTree as ET

        graph_data = cast(Dict[str, Any], getattr(self, "graph", {}))
        time_assignments = graph_data.get("optimized_assignments")
        if not isinstance(time_assignments, dict):
            time_assignments = {}

        all_nodes = [str(node) for node in self.nodes()]
        visible_node_ids = set(all_nodes)
        execution_edges = _build_stn_execution_dependency_edge_map(self, visible_node_ids)
        node_metadata_by_label = {
            node: _node_metadata(node, self.nodes[node] if node in self.nodes else {})
            for node in all_nodes
        }
        action_start_to_end: Dict[str, str] = {}
        action_end_to_start: Dict[str, str] = {}

        scheduled_actions = graph_data.get("scheduled_actions", [])
        if isinstance(scheduled_actions, list):
            for entry in scheduled_actions:
                start_node = ""
                end_node = ""
                if isinstance(entry, dict):
                    start_node = str(entry.get("start_node", "")).strip()
                    end_node = str(entry.get("end_node", "")).strip()
                elif isinstance(entry, (list, tuple)) and len(entry) >= 5:
                    start_node = str(entry[3]).strip()
                    end_node = str(entry[4]).strip()
                if start_node and end_node and start_node in visible_node_ids and end_node in visible_node_ids:
                    action_start_to_end[start_node] = end_node
                    action_end_to_start[end_node] = start_node

        start_candidates_by_action: Dict[str, List[str]] = {}
        for node_label, metadata in node_metadata_by_label.items():
            action_term = metadata.get("action_term")
            if metadata.get("phase") == "start" and isinstance(action_term, str) and action_term:
                start_candidates_by_action.setdefault(action_term, []).append(node_label)

        for end_node, metadata in node_metadata_by_label.items():
            if end_node in action_end_to_start or metadata.get("phase") != "end":
                continue
            action_term = metadata.get("action_term")
            if not isinstance(action_term, str) or not action_term:
                continue
            candidates = start_candidates_by_action.get(action_term, [])
            if not candidates:
                continue
            end_step = metadata.get("step_id")

            def candidate_rank(start_node: str) -> tuple:
                start_step = node_metadata_by_label.get(start_node, {}).get("step_id")
                if isinstance(start_step, int) and isinstance(end_step, int):
                    if start_step == end_step:
                        return (0, 0, start_node)
                    if start_step < end_step:
                        return (1, end_step - start_step, start_node)
                    return (2, start_step - end_step, start_node)
                return (3, 0, start_node)

            start_node = sorted(candidates, key=candidate_rank)[0]
            action_start_to_end.setdefault(start_node, end_node)
            action_end_to_start[end_node] = start_node

        def node_timestamp(node_label: str) -> Optional[float]:
            node_attrs = self.nodes[node_label] if node_label in self.nodes else {}
            timestamp = time_assignments.get(node_label, node_attrs.get("optimized_time"))
            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
                return float(timestamp)
            return None

        def collapsed_node_label(node_label: str) -> str:
            return action_end_to_start.get(node_label, node_label)

        collapsed_nodes = sorted(
            {
                collapsed_node_label(node_label)
                for node_label in all_nodes
                if node_label not in action_end_to_start
            },
            key=lambda node: all_nodes.index(node) if node in all_nodes else len(all_nodes),
        )
        collapsed_edge_map: Dict[tuple, Dict[str, Any]] = {}
        for (source_id, target_id), edge_data in execution_edges.items():
            collapsed_source = collapsed_node_label(source_id)
            collapsed_target = collapsed_node_label(target_id)
            if collapsed_source == collapsed_target:
                continue
            for relation in edge_data.get("relations", set()):
                _add_timepoint_relation(collapsed_edge_map, collapsed_source, collapsed_target, str(relation))
            edge_key = (collapsed_source, collapsed_target)
            if edge_key in collapsed_edge_map:
                collapsed_edge_map[edge_key].setdefault("wait_for_nodes", set()).add(source_id)

        all_node_order_indexes = {node: index for index, node in enumerate(all_nodes)}
        initial_root_children = _select_initial_root_children(
            collapsed_edge_map,
            node_timestamp,
            all_node_order_indexes,
        )

        execution_edges = _reduce_execution_edges_preserving_init_fanout(
            collapsed_edge_map,
            root_children=initial_root_children,
        )

        execution_graph = nx.DiGraph()
        execution_graph.add_nodes_from(collapsed_nodes)
        for (source_id, target_id), edge_data in execution_edges.items():
            execution_graph.add_edge(
                source_id,
                target_id,
                relations=set(edge_data.get("relations", set())),
                wait_for_nodes=set(edge_data.get("wait_for_nodes", set())),
            )

        if "INIT" not in execution_graph:
            raise ValueError("Cannot generate optimized BT XML: INIT node is missing from the execution graph.")
        if "END" not in execution_graph:
            raise ValueError("Cannot generate optimized BT XML: END node is missing from the execution graph.")
        if not nx.is_directed_acyclic_graph(execution_graph):
            raise ValueError("Cannot generate optimized BT XML from a cyclic execution graph.")

        node_original_indexes = {node: index for index, node in enumerate(collapsed_nodes)}

        def node_sort_key(node_label: str) -> tuple:
            if node_label == "INIT":
                return (-1, -math.inf, -1, node_label)
            if node_label == "END":
                return (2, math.inf, node_original_indexes.get(node_label, 0), node_label)
            timestamp = node_timestamp(node_label)
            if timestamp is not None:
                return (0, timestamp, node_original_indexes.get(node_label, 0), node_label)
            return (1, 0.0, node_original_indexes.get(node_label, 0), node_label)

        def sorted_nodes(nodes: Iterable[str]) -> List[str]:
            return sorted((str(node) for node in nodes), key=node_sort_key)

        primary_parent_cache: Dict[str, Optional[str]] = {}

        def graph_parents(node_label: str) -> List[str]:
            return sorted_nodes(execution_graph.predecessors(node_label))

        def graph_children(node_label: str) -> List[str]:
            return sorted_nodes(execution_graph.successors(node_label))

        def primary_parent(node_label: str) -> Optional[str]:
            if node_label not in primary_parent_cache:
                parents = graph_parents(node_label)
                primary_parent_cache[node_label] = parents[0] if parents else None
            return primary_parent_cache[node_label]

        def renderable_children(node_label: str) -> List[str]:
            children: List[str] = []
            for child in graph_children(node_label):
                if child == "END":
                    continue
                parents = graph_parents(child)
                if len(parents) <= 1 or primary_parent(child) == node_label:
                    children.append(child)
            return children

        if not nx.has_path(execution_graph, "INIT", "END"):
            raise ValueError("Cannot generate optimized BT XML: END is not reachable from INIT.")

        reachable_from_init = set(nx.descendants(execution_graph, "INIT"))
        reachable_from_init.add("INIT")

        root = ET.Element("root", {"main_tree_to_execute": tree_id})
        behavior_tree = ET.SubElement(root, "BehaviorTree", {"ID": tree_id})

        if isinstance(robot_ids, str):
            normalized_robot_ids = [value.strip() for value in robot_ids.split(",") if value.strip()]
        elif isinstance(robot_ids, (list, tuple)):
            normalized_robot_ids = [str(value).strip() for value in robot_ids if str(value).strip()]
        else:
            normalized_robot_ids = []

        def format_number(value: float) -> str:
            if math.isfinite(value):
                return f"{value:.6g}"
            return str(value)

        def action_arguments(action_name: str) -> List[str]:
            opening = action_name.find("(")
            if opening < 0 or not action_name.endswith(")"):
                return []
            return re.findall(r"(?<![\w-])[\w-]+(?![\w-])", action_name[opening + 1:-1])

        def add_action_node(parent: ET.Element, node_label: str) -> None:
            completion_node = action_start_to_end.get(node_label, node_label)
            attrs = {
                "name": node_label,
                "use_socket": "false",
                "stn_node": node_label,
                "stn_end_node": completion_node,
            }
            if completion_node != node_label:
                attrs["stn_start_node"] = node_label
            timestamp = node_timestamp(node_label)
            if timestamp is not None:
                attrs["stn_time"] = format_number(timestamp)
            end_timestamp = node_timestamp(completion_node)
            if completion_node != node_label and end_timestamp is not None:
                attrs["stn_end_time"] = format_number(end_timestamp)

            metadata = _parse_node_label_metadata(node_label)
            action_term = metadata.get("action_term")
            if isinstance(action_term, str) and action_term.strip():
                attrs["action"] = action_term.strip()
                phase = metadata.get("phase")
                if isinstance(phase, str) and phase:
                    attrs["phase"] = phase
                arguments = set(action_arguments(action_term))
                matching_robot_ids = [robot_id for robot_id in normalized_robot_ids if robot_id in arguments]
                if matching_robot_ids:
                    attrs["robot_id"] = ",".join(matching_robot_ids)

            ET.SubElement(parent, "ActionNode", attrs)

        def add_wait_nodes(parent: ET.Element, node_label: str, incoming_parent: Optional[str]) -> None:
            parents = graph_parents(node_label)
            if len(parents) <= 1:
                return

            wait_for: List[str] = []
            for parent_label in parents:
                if parent_label in {"INIT", "END"}:
                    continue
                if parent_label == incoming_parent:
                    continue
                parent_completion = action_start_to_end.get(parent_label)
                if parent_completion:
                    wait_for.append(parent_completion)
                    continue
                edge_waits = execution_graph[parent_label][node_label].get("wait_for_nodes", set())
                if edge_waits:
                    wait_for.extend(str(wait_node) for wait_node in edge_waits)
                else:
                    wait_for.append(parent_label)
            wait_for = sorted(set(wait_for), key=lambda wait_node: node_sort_key(collapsed_node_label(wait_node)))
            if not wait_for:
                return
            wait_label_nodes = sorted(
                {collapsed_node_label(wait_node) for wait_node in wait_for},
                key=node_sort_key,
            )
            wait_name = f"wait({','.join(wait_label_nodes)})"
            ET.SubElement(
                parent,
                "ConditionNode",
                {
                    "name": wait_name,
                    "wait_for": json.dumps(wait_for, separators=(",", ":")),
                },
            )

        rendered: set = set()

        def render_node(
            node_label: str,
            parent_xml: ET.Element,
            incoming_parent: Optional[str],
        ) -> None:
            if node_label in rendered:
                return
            if node_label in {"INIT", "END"}:
                return
            if node_label not in reachable_from_init:
                return

            parents = graph_parents(node_label)
            if len(parents) > 1 and incoming_parent != primary_parent(node_label):
                return

            children = renderable_children(node_label)
            needs_sequence = (
                parent_xml.tag == "Parallel"
                and (len(children) == 1 or len(parents) > 1)
            )
            current_parent = parent_xml
            if needs_sequence:
                current_parent = ET.SubElement(
                    parent_xml,
                    "Sequence",
                    {"name": "SEQUENCE", "memory": "true"},
                )

            add_wait_nodes(current_parent, node_label, incoming_parent)
            add_action_node(current_parent, node_label)
            rendered.add(node_label)

            if len(children) > 1:
                parallel_node = ET.SubElement(current_parent, "Parallel", {"name": "PARALLEL"})
                for child in children:
                    render_node(child, parallel_node, node_label)
            elif len(children) == 1:
                render_node(children[0], current_parent, node_label)

        init_children = renderable_children("INIT")
        if not init_children:
            raise ValueError("Cannot generate optimized BT XML: INIT has no executable children.")
        if len(init_children) > 1:
            root_parallel = ET.SubElement(behavior_tree, "Parallel", {"name": "PARALLEL"})
            for child in init_children:
                render_node(child, root_parallel, "INIT")
        else:
            root_sequence = ET.SubElement(behavior_tree, "Sequence", {"name": "SEQUENCE", "memory": "true"})
            render_node(init_children[0], root_sequence, "INIT")

        missing_nodes = sorted_nodes(
            node for node in reachable_from_init
            if node not in rendered and node not in {"INIT", "END"} and node in execution_graph.nodes
        )
        if missing_nodes:
            raise ValueError(
                "Some execution graph nodes were not emitted in the BT XML: "
                + ", ".join(missing_nodes)
            )

        ET.indent(root, space="    ")
        xml_payload = ET.tostring(root, encoding="unicode")
        if filename:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(xml_payload)
                file.write("\n")
        return xml_payload

    def to_cytoscape_html(
            self,
            path: str,
            title: str = "Simple Temporal Network",
            max_nodes: Optional[int] = None,
        ) -> None:
        """
        Export the STN as an interactive Cytoscape HTML page.

        Parameters
        ----------
        path : str
            Output HTML file path.
        title : str, optional
            Page title.
        max_nodes : Optional[int]
            Optional upper bound on nodes rendered in the HTML.

        Returns
        -------
        None
            This function performs side effects only.
        """
        export_stn_cytoscape_html(
            stn=self,
            path=path,
            title=title,
            max_nodes=max_nodes,
        )

    def to_timepoint_graph_html(
            self,
            path: str,
            title: str = "Optimized STN Execution Graph",
            max_nodes: Optional[int] = None,
            time_assignments: Optional[Dict[str, float]] = None,
        ) -> None:
        """
        Export the STN as a raw timepoint/constraint Cytoscape graph.

        Parameters
        ----------
        path : str
            Output HTML file path.
        title : str, optional
            Page title.
        max_nodes : Optional[int]
            Optional upper bound on nodes rendered in the HTML.
        time_assignments : Optional[Dict[str, float]]
            Optional optimized timestamp mapping. When omitted, timestamps are
            read from graph/node metadata if available.

        Returns
        -------
        None
            This function performs side effects only.
        """
        export_stn_timepoint_graph_html(
            stn=self,
            path=path,
            title=title,
            max_nodes=max_nodes,
            time_assignments=time_assignments,
        )

    def to_optimized_timeline_html(
            self,
            path: str,
            title: str = "Optimized Simple Temporal Network",
            optimization_result: Optional[Dict[str, Any]] = None,
            show_slack_overlay: bool = True,
        ) -> None:
        """
        Export optimized STN HTML with solved timestamps and timeline section.

        Parameters
        ----------
        path : str
            Output HTML file path.
        title : str, optional
            Page title.
        optimization_result : Optional[Dict[str, Any]], optional
            Optional optimization output dictionary. When present, this method
            can read `scheduled_actions`, `earliest_start`, and `latest_start`
            from it as fallbacks.
        show_slack_overlay : bool, optional
            Whether to draw a translucent slack overlay when slack values exist.

        Returns
        -------
        None
            This function performs side effects only.
        """
        try:
            import pandas as pd
            import plotly.graph_objects as go
            from plotly.colors import qualitative
        except ImportError as exc:
            raise ImportError(
                "to_optimized_timeline_html requires pandas and plotly. "
                "Install them with: pip install pandas plotly"
            ) from exc

        graph_data = cast(Dict[str, Any], getattr(self, "graph", {}))
        result_data = optimization_result if isinstance(optimization_result, dict) else {}

        scheduled_actions = graph_data.get("scheduled_actions", [])
        if (not isinstance(scheduled_actions, list) or not scheduled_actions) and isinstance(result_data.get("scheduled_actions"), list):
            scheduled_actions = result_data.get("scheduled_actions", [])
        if not isinstance(scheduled_actions, list) or not scheduled_actions:
            raise ValueError("stn.graph['scheduled_actions'] is missing or empty.")

        action_groups = graph_data.get("action_groups")
        if not isinstance(action_groups, dict):
            action_groups = graph_data.get("action_resources")
        if not isinstance(action_groups, dict):
            action_groups = graph_data.get("resource_by_action")
        if not isinstance(action_groups, dict):
            action_groups = {}

        earliest_starts = graph_data.get("earliest_start")
        latest_starts = graph_data.get("latest_start")
        if not isinstance(earliest_starts, dict):
            earliest_starts = result_data.get("earliest_start")
        if not isinstance(latest_starts, dict):
            latest_starts = result_data.get("latest_start")
        if not isinstance(earliest_starts, dict):
            earliest_starts = {}
        if not isinstance(latest_starts, dict):
            latest_starts = {}

        rows: List[Dict[str, Any]] = []
        for entry_idx, entry in enumerate(scheduled_actions):
            if not isinstance(entry, (list, tuple)) or len(entry) < 5:
                continue

            durative_name = str(entry[0])
            start_time = float(entry[1])
            end_time = float(entry[2])
            start_action_name = str(entry[3])
            end_action_name = str(entry[4])

            if len(entry) > 5 and isinstance(entry[5], str) and entry[5].strip():
                group_value = entry[5].strip()
            else:
                group_value = str(action_groups.get(durative_name, "default"))

            earliest_start = earliest_starts.get(durative_name)
            latest_start = latest_starts.get(durative_name)
            slack_value = None
            if isinstance(earliest_start, (int, float)) and isinstance(latest_start, (int, float)):
                slack_value = float(latest_start) - float(earliest_start)

            rows.append(
                {
                    "entry_idx": entry_idx,
                    "action": durative_name,
                    "durative_name": durative_name,
                    "start": start_time,
                    "end": end_time,
                    "duration": end_time - start_time,
                    "group": group_value,
                    "start_action_name": start_action_name,
                    "end_action_name": end_action_name,
                    "earliest_start": earliest_start,
                    "latest_start": latest_start,
                    "slack": slack_value,
                }
            )

        if not rows:
            raise ValueError(
                "No valid scheduled actions found in stn.graph['scheduled_actions']. "
                "Expected tuples: (durative_name, start_time, end_time, start_snap, end_snap[, group])."
            )

        df = pd.DataFrame(rows).sort_values(by=["start", "end", "action", "entry_idx"]).reset_index(drop=True)
        df["entry_label"] = df.index.map(lambda idx: f"row_{idx + 1:04d}")
        lane_order = df["entry_label"].tolist()
        lane_tick_text = df["action"].tolist()

        df["start_text"] = df["start"].map(_format_hover_number)
        df["end_text"] = df["end"].map(_format_hover_number)
        df["slack_text"] = df["slack"].map(_format_hover_number)
        df["duration_text"] = df["duration"].map(_format_hover_number)

        use_group_color = bool(df["group"].astype(str).nunique() > 1 or any(df["group"] != "default"))

        fig = go.Figure()

        custom_columns = [
            "start_text",
            "end_text",
            "slack_text",
            "duration_text",
            "durative_name",
            "start_action_name",
            "end_action_name",
        ]

        if use_group_color:
            groups = sorted({str(value) for value in df["group"].tolist()})
            palette = qualitative.Plotly
            color_map = {group_name: palette[idx % len(palette)] for idx, group_name in enumerate(groups)}

            for group_name in groups:
                group_df = df[df["group"].astype(str) == group_name]
                if group_df.empty:
                    continue
                fig.add_trace(
                    go.Bar(
                        x=group_df["duration"],
                        y=group_df["entry_label"],
                        base=group_df["start"],
                        orientation="h",
                        name=group_name,
                        marker=dict(color=color_map[group_name], line=dict(color="#314158", width=0.8)),
                        opacity=0.95,
                        customdata=group_df[custom_columns].values,
                        hovertemplate=(
                            "start=%{customdata[0]}<br>"
                            "end=%{customdata[1]}<br>"
                            "slack=%{customdata[2]}<br>"
                            "duration=%{customdata[3]}<br>"
                            "durative name=%{customdata[4]}<br>"
                            "start action=%{customdata[5]}<br>"
                            "end action=%{customdata[6]}"
                            "<extra></extra>"
                        ),
                    )
                )
        else:
            fig.add_trace(
                go.Bar(
                    x=df["duration"],
                    y=df["entry_label"],
                    base=df["start"],
                    orientation="h",
                    name="Actions",
                    marker=dict(color="#3A86FF", line=dict(color="#314158", width=0.8)),
                    opacity=0.95,
                    customdata=df[custom_columns].values,
                    hovertemplate=(
                        "start=%{customdata[0]}<br>"
                        "end=%{customdata[1]}<br>"
                        "slack=%{customdata[2]}<br>"
                        "duration=%{customdata[3]}<br>"
                        "durative name=%{customdata[4]}<br>"
                        "start action=%{customdata[5]}<br>"
                        "end action=%{customdata[6]}"
                        "<extra></extra>"
                    ),
                )
            )

        task_count = max(len(lane_order), 1)
        chart_height = max(360, min(1400, 120 + 52 * task_count))

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Time",
            yaxis_title="Scheduled actions",
            barmode="overlay",
            bargap=0.25,
            height=chart_height,
            margin=dict(l=40, r=40, t=60, b=40),
            legend_title_text="Group/Resource" if use_group_color else "",
        )
        max_timestamp = float(df["end"].max()) if not df.empty else 0.0
        x_axis_max = max(0.0, max_timestamp)
        fig.update_xaxes(
            range=[0.0, x_axis_max],
            type="linear",
            showgrid=True,
            gridcolor="#D7DEE9",
            zeroline=False,
            ticks="outside",
            tickformat=".6g",
        )
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=lane_order,
            autorange="reversed",
            showgrid=True,
            gridcolor="#EEF2F7",
            tickmode="array",
            tickvals=lane_order,
            ticktext=lane_tick_text,
        )

        has_slack_values = bool(df["slack"].notna().any())
        if show_slack_overlay and has_slack_values:
            slack_df = df[df["slack"].notna() & (df["slack"] > 0)].copy()
            if not slack_df.empty:
                fig.add_trace(
                    go.Bar(
                        x=slack_df["slack"],
                        y=slack_df["entry_label"],
                        base=slack_df["start"],
                        orientation="h",
                        marker=dict(color="rgba(120, 120, 120, 0.22)", line=dict(width=0)),
                        name="Slack window",
                        hovertemplate="slack window=%{x:.6g}<extra></extra>",
                    )
                )

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path), full_html=True, include_plotlyjs=True)


def _run_timeline_html_example() -> None:
    """Generate a small standalone timeline HTML example from synthetic STN data."""

    class _ExampleSTN(STNVisualizationMixin):
        def __init__(self) -> None:
            self.graph: Dict[str, Any] = {}

    demo_stn = _ExampleSTN()
    demo_stn.graph["scheduled_actions"] = [
        ("pick_part", 0.0, 2.0, "s_pick_part_1", "e_pick_part_1", "robot"),
        ("move_to_station", 2.0, 5.5, "s_move_to_station_2", "e_move_to_station_2", "robot"),
        ("inspect_part", 1.0, 4.0, "s_inspect_part_3", "e_inspect_part_3", "camera"),
        ("place_part", 5.5, 7.0, "s_place_part_4", "e_place_part_4", "robot"),
    ]
    demo_stn.graph["earliest_start"] = {
        "pick_part": 0.0,
        "move_to_station": 2.0,
        "inspect_part": 0.5,
        "place_part": 5.0,
    }
    demo_stn.graph["latest_start"] = {
        "pick_part": 0.2,
        "move_to_station": 2.4,
        "inspect_part": 1.5,
        "place_part": 5.8,
    }

    output_path = Path(__file__).resolve().parents[3] / "output" / "optimized_timeline_example.html"
    demo_stn.to_optimized_timeline_html(
        path=str(output_path),
        title="Optimized STN Timeline Example",
        show_slack_overlay=True,
    )
    print(f"Timeline HTML written to: {output_path}")


if __name__ == "__main__":
    _run_timeline_html_example()
