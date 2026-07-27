#!/usr/bin/env python3

"""
Parse planner logs and render interactive partial-order plan visualizations.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

try:
    from utility.logger import logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.logger import logger


DEFAULT_CYTOSCAPE_JS = "https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"
DEFAULT_DAGRE_JS = "https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"
DEFAULT_CY_DAGRE_JS = "https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"
DEFAULT_ELK_JS = "https://unpkg.com/elkjs/lib/elk.bundled.js"
DEFAULT_CY_ELK_JS = "https://unpkg.com/cytoscape-elk/cytoscape-elk.js"

NODE_COLORS = {
    "hl_start": "#2E86AB",
    "hl_end": "#22577A",
    "ll_start": "#2A9D8F",
    "ll_end": "#E9C46A",
    "other": "#6C757D",
}

EDGE_COLORS = {
    "causal": "#D1495B",
    "assumption": "#3A86FF",
    "mock": "#8A7E72",
    "other": "#7C7C7C",
}


def escape_html(value):
    """
    Escape html.

    Parameters
    ----------
    value : Any
        Value to normalize, convert, or escape.

    Returns
    -------
    Any
        Result returned by `escape_html`.
    """
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def safe_json_dumps(payload):
    """
    Safely parse json dumps.

    Parameters
    ----------
    payload : Any
        JSON-like request payload with query parameters.

    Returns
    -------
    Any
        Result returned by `safe_json_dumps`.
    """
    return json.dumps(payload, ensure_ascii=True, indent=2).replace("</", "<\\/")


def extract_balanced_terms(text, functor):
    """
    Extract balanced terms.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.
    functor : Any
        Prolog functor name used as extraction target.

    Returns
    -------
    Any
        Result returned by `extract_balanced_terms`.
    """
    terms = []
    marker = f"{functor}("
    idx = 0
    text_len = len(text)

    while idx < text_len:
        start = text.find(marker, idx)
        if start == -1:
            break
        if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            idx = start + len(marker)
            continue

        end = find_balanced_term_end(text, start + len(functor))
        if end == -1:
            idx = start + len(marker)
            continue

        terms.append(text[start : end + 1])
        idx = end + 1

    return terms


def find_balanced_term_end(text, open_paren_idx):
    """
    Find balanced term end.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.
    open_paren_idx : Any
        Index of the opening parenthesis that starts a term.

    Returns
    -------
    Any
        Result returned by `find_balanced_term_end`.
    """
    depth_round = 0
    depth_square = 0
    depth_curly = 0
    in_single = False
    in_double = False
    escaped = False

    for i in range(open_paren_idx, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue

        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue

        if ch == "'":
            in_single = True
            continue
        if ch == '"':
            in_double = True
            continue

        if ch == "(":
            depth_round += 1
        elif ch == ")":
            depth_round -= 1
            if depth_round == 0 and depth_square == 0 and depth_curly == 0:
                return i
            if depth_round < 0:
                return -1
        elif ch == "[":
            depth_square += 1
        elif ch == "]":
            depth_square -= 1
            if depth_square < 0:
                return -1
        elif ch == "{":
            depth_curly += 1
        elif ch == "}":
            depth_curly -= 1
            if depth_curly < 0:
                return -1

    return -1


def split_top_level(text, delimiter=","):
    """
    Split top level.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.
    delimiter : Any, optional
        Delimiter character used for top-level splitting.

    Returns
    -------
    Any
        Result returned by `split_top_level`.
    """
    parts = []
    current = []
    depth_round = 0
    depth_square = 0
    depth_curly = 0
    in_single = False
    in_double = False
    escaped = False

    for ch in text:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
            continue

        if in_single:
            current.append(ch)
            if ch == "'":
                in_single = False
            continue
        if in_double:
            current.append(ch)
            if ch == '"':
                in_double = False
            continue

        if ch == "'":
            in_single = True
            current.append(ch)
            continue
        if ch == '"':
            in_double = True
            current.append(ch)
            continue

        if ch == "(":
            depth_round += 1
            current.append(ch)
            continue
        if ch == ")":
            depth_round -= 1
            current.append(ch)
            continue
        if ch == "[":
            depth_square += 1
            current.append(ch)
            continue
        if ch == "]":
            depth_square -= 1
            current.append(ch)
            continue
        if ch == "{":
            depth_curly += 1
            current.append(ch)
            continue
        if ch == "}":
            depth_curly -= 1
            current.append(ch)
            continue

        if ch == delimiter and depth_round == 0 and depth_square == 0 and depth_curly == 0:
            chunk = "".join(current).strip()
            if chunk:
                parts.append(chunk)
            current = []
            continue

        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_id_step(text):
    """
    Parse id step.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.

    Returns
    -------
    Any
        Result returned by `parse_id_step`.
    """
    value = text.strip()
    depth_round = 0
    depth_square = 0
    depth_curly = 0
    in_single = False
    in_double = False
    escaped = False

    for i, ch in enumerate(value):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue

        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue

        if ch == "'":
            in_single = True
            continue
        if ch == '"':
            in_double = True
            continue

        if ch == "(":
            depth_round += 1
            continue
        if ch == ")":
            depth_round -= 1
            continue
        if ch == "[":
            depth_square += 1
            continue
        if ch == "]":
            depth_square -= 1
            continue
        if ch == "{":
            depth_curly += 1
            continue
        if ch == "}":
            depth_curly -= 1
            continue

        if ch == "-" and depth_round == 0 and depth_square == 0 and depth_curly == 0:
            step_id = value[:i].strip()
            step = value[i + 1 :].strip()
            if not step_id or not step:
                return None
            try:
                step_id_num = int(step_id)
            except ValueError:
                step_id_num = None
            return {
                "id": step_id,
                "id_num": step_id_num,
                "step": step,
            }

    return None


def parse_reason(reason_text):
    """
    Parse reason.

    Parameters
    ----------
    reason_text : Any
        Raw reason term text attached to an enabler edge.

    Returns
    -------
    Any
        Result returned by `parse_reason`.
    """
    value = reason_text.strip()
    idx = value.find("(")
    if idx == -1 or not value.endswith(")"):
        return {"kind": value, "detail": ""}
    return {
        "kind": value[:idx].strip(),
        "detail": value[idx + 1 : -1].strip(),
    }


def parse_phase_and_action(step):
    """
    Parse phase and action.

    Parameters
    ----------
    step : Any
        Plan step term string (for example `start(...)` or `end(...)`).

    Returns
    -------
    Any
        Result returned by `parse_phase_and_action`.
    """
    value = step.strip()
    if value.startswith("start(") and value.endswith(")"):
        return "start", value[len("start(") : -1].strip()
    if value.startswith("end(") and value.endswith(")"):
        return "end", value[len("end(") : -1].strip()
    return "other", value


def action_functor(action):
    """
    Handle action functor.

    Parameters
    ----------
    action : Any
        Action term string being inspected or transformed.

    Returns
    -------
    Any
        Result returned by `action_functor`.
    """
    value = action.strip()
    idx = value.find("(")
    if idx == -1:
        return value
    return value[:idx].strip()


def classify_node(step):
    """
    Classify node.

    Parameters
    ----------
    step : Any
        Plan step term string (for example `start(...)` or `end(...)`).

    Returns
    -------
    Any
        Result returned by `classify_node`.
    """
    phase, action = parse_phase_and_action(step)
    if phase == "other":
        return "other"
    functor = action_functor(action)
    is_ll = functor.startswith("ll_")
    if phase == "start" and is_ll:
        return "ll_start"
    if phase == "end" and is_ll:
        return "ll_end"
    if phase == "start":
        return "hl_start"
    return "hl_end"


def is_low_level_step(step):
    """
    Return whether low level step.

    Parameters
    ----------
    step : Any
        Plan step term string (for example `start(...)` or `end(...)`).

    Returns
    -------
    Any
        Result returned by `is_low_level_step`.
    """
    phase, action = parse_phase_and_action(step)
    if phase == "other":
        return False
    return action_functor(action).startswith("ll_")


def build_short_label(step_id, step):
    """
    Build short label.

    Parameters
    ----------
    step_id : Any
        Numeric plan step identifier.
    step : Any
        Plan step term string (for example `start(...)` or `end(...)`).

    Returns
    -------
    Any
        Result returned by `build_short_label`.
    """
    phase, action = parse_phase_and_action(step)
    if phase == "other":
        return f"{step_id}: {step}"
    functor = action_functor(action)
    return f"{step_id}: {phase} {functor}"


def parse_enabler_terms(content):
    """
    Parse enabler terms.

    Parameters
    ----------
    content : Any
        Full text content being parsed or transformed.

    Returns
    -------
    Any
        Result returned by `parse_enabler_terms`.
    """
    # Each enabler(Source, Target, Reason) term becomes a directed dependency edge.
    parsed_edges = []
    for term in extract_balanced_terms(content, "enabler"):
        inside = term[len("enabler(") : -1]
        parts = split_top_level(inside, delimiter=",")
        if len(parts) != 3:
            continue
        source = parse_id_step(parts[0])
        target = parse_id_step(parts[1])
        if source is None or target is None:
            continue

        reason = parse_reason(parts[2])
        parsed_edges.append(
            {
                "source": source,
                "target": target,
                "reason_kind": reason["kind"] or "other",
                "reason_detail": reason["detail"],
                "reason_raw": parts[2].strip(),
                "term": term,
            }
        )
    return parsed_edges


def parse_plan_actions_with_enablers(content):
    """
    Parse the explicit plan-action block emitted by the planner.

    Parameters
    ----------
    content : Any
        Full text content being parsed or transformed.

    Returns
    -------
    Any
        Result returned by `parse_plan_actions_with_enablers`.
    """
    rows = []
    collecting = False
    line_pattern = re.compile(r"^\s*(?P<step_id>\d+)\s*-\s*(?P<action_name>.*?)\s*<=\s*\[(?P<enablers>.*?)\]\s*$")

    for line in content.splitlines():
        if re.match(r"^\s*\[enablers\]\s*Plan actions with enablers", line):
            collecting = True
            continue

        if not collecting:
            continue

        if re.match(r"^\s*\[", line):
            break

        if not line.strip() and rows:
            break

        match = line_pattern.match(line)
        if not match:
            continue

        step_id = int(match.group("step_id"))
        action = match.group("action_name").strip()
        rows.append(
            {
                "step_id": step_id,
                "step": action,
            }
        )

    rows.sort(key=lambda row: row["step_id"])
    return rows


def build_graph(parsed_edges, plan_rows=None):
    """
    Build graph.

    Parameters
    ----------
    parsed_edges : Any
        List of parsed enabler/dependency edge records.
    plan_rows : Any, optional
        Optional rows extracted from the explicit plan-action block.

    Returns
    -------
    Any
        Result returned by `build_graph`.
    """
    nodes = {}
    edges = []

    def ensure_node(entry):
        """
        Handle ensure node.

        Parameters
        ----------
        entry : Any
            Node descriptor dictionary containing id and step information.

        Returns
        -------
        Any
            Result returned by `ensure_node`.
        """
        node_id = entry["id"]
        if node_id not in nodes:
            step = entry["step"]
            nodes[node_id] = {
                "id": node_id,
                "id_num": entry["id_num"],
                "step": step,
                "display": f"{node_id}-{step}",
                "kind": classify_node(step),
            }
        return node_id

    for edge in parsed_edges:
        src = ensure_node(edge["source"])
        dst = ensure_node(edge["target"])
        edges.append(
            {
                "source": src,
                "target": dst,
                "reason_kind": edge["reason_kind"],
                "reason_detail": edge["reason_detail"],
                "reason_raw": edge["reason_raw"],
                "term": edge["term"],
            }
        )

    for row in plan_rows or []:
        node_id = str(row["step_id"])
        if node_id not in nodes:
            step = row["step"]
            nodes[node_id] = {
                "id": node_id,
                "id_num": row["step_id"],
                "step": step,
                "display": f"{node_id}-{step}",
                "kind": classify_node(step),
            }

    return nodes, edges


def add_boundary_mock_edges(nodes, edges):
    """
    Add INIT/GOAL nodes and synthetic mock edges for boundary visibility.

    Parameters
    ----------
    nodes : Any
        Collection or mapping of graph nodes.
    edges : Any
        Collection of graph edges.

    Returns
    -------
    Any
        Result returned by `add_boundary_mock_edges`.
    """
    if "INIT" not in nodes:
        nodes["INIT"] = {
            "id": "INIT",
            "id_num": None,
            "step": "INIT",
            "display": "INIT",
            "kind": "other",
        }
    if "GOAL" not in nodes:
        nodes["GOAL"] = {
            "id": "GOAL",
            "id_num": None,
            "step": "GOAL",
            "display": "GOAL",
            "kind": "other",
        }

    candidate_nodes = [node_id for node_id in nodes.keys() if node_id not in {"INIT", "GOAL"}]
    if not candidate_nodes:
        return

    edge_keys = {
        (
            str(edge.get("source")),
            str(edge.get("target")),
            str(edge.get("reason_kind")),
        )
        for edge in edges
    }

    # Mirror PartialOrderPlan.from_prolog behavior: connect INIT/GOAL to every action node.
    for node_id in sorted(candidate_nodes):
        key = ("INIT", node_id, "mock")
        if key in edge_keys:
            continue
        edges.append(
            {
                "source": "INIT",
                "target": node_id,
                "reason_kind": "mock",
                "reason_detail": "",
                "reason_raw": "mock(init)",
                "term": "",
            }
        )
        edge_keys.add(key)

    for node_id in sorted(candidate_nodes):
        key = (node_id, "GOAL", "mock")
        if key in edge_keys:
            continue
        edges.append(
            {
                "source": node_id,
                "target": "GOAL",
                "reason_kind": "mock",
                "reason_detail": "",
                "reason_raw": "mock(goal)",
                "term": "",
            }
        )
        edge_keys.add(key)


def node_sort_key(node):
    """
    Handle node sort key.

    Parameters
    ----------
    node : Any
        Node object or node descriptor currently being processed.

    Returns
    -------
    Any
        Result returned by `node_sort_key`.
    """
    id_num = node.get("id_num")
    if id_num is None:
        return (1, node.get("id", ""))
    return (0, id_num)


def compute_depths(nodes, edges):
    """
    Handle compute depths.

    Parameters
    ----------
    nodes : Any
        Collection or mapping of graph nodes.
    edges : Any
        Collection of graph edges.

    Returns
    -------
    Any
        Result returned by `compute_depths`.
    """
    adjacency = defaultdict(list)
    indegree = {node_id: 0 for node_id in nodes}

    for edge in edges:
        src = edge["source"]
        dst = edge["target"]
        adjacency[src].append(dst)
        indegree[dst] = indegree.get(dst, 0) + 1

    # Kahn-style topological traversal to assign layers in the rendered DAG.
    queue = deque(
        sorted(
            [nodes[node_id] for node_id, degree in indegree.items() if degree == 0],
            key=node_sort_key,
        )
    )

    depth = {node_id: 0 for node_id in nodes}
    visited = set()

    while queue:
        node = queue.popleft()
        node_id = node["id"]
        visited.add(node_id)
        for neighbor in adjacency.get(node_id, []):
            depth[neighbor] = max(depth.get(neighbor, 0), depth.get(node_id, 0) + 1)
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(nodes[neighbor])

    # Fallback for cyclic components (should not happen in PO DAG).
    if len(visited) < len(nodes):
        current_max = max(depth.values()) if depth else 0
        for node in sorted(nodes.values(), key=node_sort_key):
            if node["id"] not in visited:
                current_max += 1
                depth[node["id"]] = current_max

    return depth


def build_positions(nodes, edges):
    """
    Build positions.

    Parameters
    ----------
    nodes : Any
        Collection or mapping of graph nodes.
    edges : Any
        Collection of graph edges.

    Returns
    -------
    Any
        Result returned by `build_positions`.
    """
    depth = compute_depths(nodes, edges)
    by_depth = defaultdict(list)
    for node in nodes.values():
        by_depth[depth.get(node["id"], 0)].append(node)

    positions = {}
    for layer, layer_nodes in by_depth.items():
        ordered = sorted(layer_nodes, key=node_sort_key)
        total = len(ordered)
        for idx, node in enumerate(ordered):
            x = (idx - (total - 1) / 2.0) * 260.0
            y = layer * 180.0
            positions[node["id"]] = {"x": x, "y": y}

    return positions, depth


def build_elements(nodes, edges, positions, depths, label_mode):
    """
    Build elements.

    Parameters
    ----------
    nodes : Any
        Collection or mapping of graph nodes.
    edges : Any
        Collection of graph edges.
    positions : Any
        Per-node layout coordinates for visualization output.
    depths : Any
        Per-node depth mapping used for layout or reporting.
    label_mode : Any
        Node label mode controlling displayed text.

    Returns
    -------
    Any
        Result returned by `build_elements`.
    """
    node_elements = []
    edge_elements = []
    reason_counts = defaultdict(int)
    node_kind_counts = defaultdict(int)

    for node in sorted(nodes.values(), key=node_sort_key):
        node_kind = node["kind"]
        node_kind_counts[node_kind] += 1
        display = node["display"]
        short = build_short_label(node["id"], node["step"])
        if label_mode == "id":
            label = node["id"]
        elif label_mode == "short":
            label = short
        else:
            label = display

        detail_html = (
            f"<b>{escape_html(display)}</b>"
            f"<br>node id: {escape_html(node['id'])}"
            f"<br>depth: {escape_html(depths.get(node['id'], 'n/a'))}"
            f"<br>kind: {escape_html(node_kind)}"
            f"<br>step: {escape_html(node['step'])}"
        )
        search_blob = f"{node['id']} {display} {short} {node['step']}".lower()
        node_elements.append(
            {
                "data": {
                    "id": node["id"],
                    "label": label,
                    "display": display,
                    "kind": node_kind,
                    "depth": depths.get(node["id"]),
                    "detail": detail_html,
                    "search": search_blob,
                },
                "position": positions[node["id"]],
                "classes": f"node {node_kind}",
            }
        )

    for index, edge in enumerate(edges):
        # Normalize reason kinds so stylesheet rules can remain small and predictable.
        reason_kind = edge["reason_kind"] if edge["reason_kind"] in {"causal", "assumption", "mock"} else "other"
        reason_counts[reason_kind] += 1
        reason_detail = edge["reason_detail"]
        if reason_kind == "causal":
            compact_label = "causal"
            if reason_detail.startswith("[") and reason_detail.endswith("]"):
                literals = split_top_level(reason_detail[1:-1], delimiter=",")
                compact_label = f"causal ({len(literals)})"
        elif reason_kind == "assumption":
            compact_label = "assumption"
        elif reason_kind == "mock":
            compact_label = "mock"
        else:
            compact_label = reason_kind

        edge_detail_html = (
            f"<b>{escape_html(edge['source'])} -> {escape_html(edge['target'])}</b>"
            f"<br>reason: {escape_html(edge['reason_raw'])}"
        )
        if reason_detail:
            edge_detail_html += f"<br>detail: {escape_html(reason_detail)}"

        edge_elements.append(
            {
                "data": {
                    "id": f"e{index}",
                    "source": edge["source"],
                    "target": edge["target"],
                    "label": compact_label,
                    "reason_kind": reason_kind,
                    "reason_raw": edge["reason_raw"],
                    "reason_detail": reason_detail,
                    "detail": edge_detail_html,
                },
                "classes": f"edge {reason_kind}",
            }
        )

    stats = {
        "nodes": len(node_elements),
        "edges": len(edge_elements),
        "node_kind_counts": dict(node_kind_counts),
        "reason_counts": dict(reason_counts),
    }

    return {"nodes": node_elements, "edges": edge_elements}, stats


def render_html(elements, stats, cytoscape_src, title):
    """
    Handle render html.

    Parameters
    ----------
    elements : Any
        Cytoscape element payload containing nodes and edges.
    stats : Any
        Aggregate statistics shown in the generated visualization.
    cytoscape_src : Any
        URL or local path of the Cytoscape JavaScript bundle.
    title : Any
        Title text used in generated reports or visualizations.

    Returns
    -------
    Any
        Result returned by `render_html`.
    """
    elements_json = safe_json_dumps(elements)

    node_legend = []
    for key in ("hl_start", "hl_end", "ll_start", "ll_end", "other"):
        node_legend.append(
            {
                "label": key.replace("_", " "),
                "count": stats["node_kind_counts"].get(key, 0),
                "color": NODE_COLORS[key],
            }
        )
    edge_legend = []
    for key in ("causal", "assumption", "mock", "other"):
        edge_legend.append(
            {
                "label": key,
                "count": stats["reason_counts"].get(key, 0),
                "color": EDGE_COLORS[key],
            }
        )

    legend_nodes_html = "".join(
        [
            (
                "<div class=\"legend-item\">"
                f"<span class=\"swatch\" style=\"background:{escape_html(entry['color'])}\"></span>"
                f"<span>{escape_html(entry['label'])} ({entry['count']})</span>"
                "</div>"
            )
            for entry in node_legend
        ]
    )
    legend_edges_html = "".join(
        [
            (
                "<div class=\"legend-item\">"
                f"<span class=\"swatch\" style=\"background:{escape_html(entry['color'])}\"></span>"
                f"<span>{escape_html(entry['label'])} ({entry['count']})</span>"
                "</div>"
            )
            for entry in edge_legend
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(title)}</title>
  <style>
    :root {{
      --bg: #f5f8fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #52606d;
      --border: #d9e2ec;
      --accent: #2e86ab;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, #eef4fa 0%, #f8fbfd 100%);
    }}
    .page {{
      display: grid;
      grid-template-columns: 360px 1fr;
      min-height: 100vh;
    }}
    .sidebar {{
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 16px;
      overflow-y: auto;
    }}
    .title {{
      font-weight: 700;
      margin: 0 0 10px 0;
      font-size: 20px;
    }}
    .muted {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 14px;
    }}
    .section {{
      margin-bottom: 14px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: #fff;
    }}
    .section-title {{
      font-size: 13px;
      font-weight: 700;
      margin: 0 0 8px 0;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      color: var(--muted);
    }}
    .stat {{
      font-size: 14px;
      margin: 4px 0;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 5px 0;
      font-size: 13px;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 3px;
      border: 1px solid rgba(0, 0, 0, 0.15);
      flex: 0 0 auto;
    }}
    .control {{
      display: block;
      width: 100%;
      margin: 8px 0;
      padding: 7px 9px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      font-size: 14px;
    }}
    .inline {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 6px 0;
      font-size: 14px;
    }}
    .btn-row {{
      display: flex;
            flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .btn {{
      border: 1px solid var(--border);
      background: #f7fafc;
      color: var(--text);
      border-radius: 8px;
      font-size: 13px;
      padding: 7px 10px;
      cursor: pointer;
            flex: 1 1 calc(50% - 8px);
            min-width: 0;
    }}
    .btn:hover {{
      background: #edf2f7;
    }}
    #details {{
      font-size: 13px;
      line-height: 1.35;
    }}
    .main {{
      position: relative;
      min-height: 100vh;
    }}
    #cy {{
      width: 100%;
      height: 100vh;
    }}
    @media (max-width: 1000px) {{
      .page {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        border-right: none;
        border-bottom: 1px solid var(--border);
      }}
      #cy {{
        height: 70vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <h1 class="title">{escape_html(title)}</h1>
      <div class="muted">Interactive partial-order graph from extracted enablers.</div>

      <div class="section">
        <div class="section-title">Summary</div>
        <div class="stat">Nodes: {stats["nodes"]}</div>
        <div class="stat">Edges: {stats["edges"]}</div>
      </div>

      <div class="section">
        <div class="section-title">Node Types</div>
        {legend_nodes_html}
      </div>

      <div class="section">
        <div class="section-title">Edge Reasons</div>
        {legend_edges_html}
      </div>

      <div class="section">
        <div class="section-title">Filters</div>
        <input id="search" class="control" type="text" placeholder="Search node id/step/action">
        <label class="inline"><input id="showCausal" type="checkbox" checked> Show causal edges</label>
        <label class="inline"><input id="showAssumption" type="checkbox" checked> Show assumption edges</label>
                <label class="inline"><input id="showMock" type="checkbox" checked> Show mock edges</label>
        <label class="inline"><input id="showOther" type="checkbox" checked> Show other edges</label>
        <div class="btn-row">
                    <button class="btn" id="layoutDagre">Dagre</button>
                    <button class="btn" id="layoutElk">ELK (layered)</button>
                    <button class="btn" id="layoutBreadth">Breadthfirst</button>
          <button class="btn" id="fit">Fit</button>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Details</div>
        <div id="details">Click a node or edge to inspect details.</div>
      </div>
    </aside>
    <main class="main">
      <div id="cy"></div>
    </main>
  </div>

  <script src="{escape_html(cytoscape_src)}"></script>
    <script src="{escape_html(DEFAULT_DAGRE_JS)}"></script>
    <script src="{escape_html(DEFAULT_CY_DAGRE_JS)}"></script>
    <script src="{escape_html(DEFAULT_ELK_JS)}"></script>
    <script src="{escape_html(DEFAULT_CY_ELK_JS)}"></script>
  <script>
    const elements = {elements_json};
        const dagreAvailable = typeof cytoscapeDagre === "function";
        const elkAvailable = typeof cytoscapeElk === "function";
        if (dagreAvailable) {{
            cytoscape.use(cytoscapeDagre);
        }}
        if (elkAvailable) {{
            cytoscape.use(cytoscapeElk);
        }}

        function renderLayoutStatus(name, direction, engine) {{
            showDetails(
                `<div><strong>Active layout:</strong> ${{name}}</div>` +
                `<div><strong>Direction:</strong> ${{direction}}</div>` +
                `<div><strong>Engine:</strong> ${{engine}}</div>`
            );
        }}

        function runBreadthLayout() {{
            cy.layout({{
                name: "breadthfirst",
                directed: true,
                spacingFactor: 1.2,
                fit: true,
                padding: 30
            }}).run();
            renderLayoutStatus("Breadthfirst", "Top to bottom", "Cytoscape built-in");
        }}

        function runDagreLayout() {{
            if (dagreAvailable) {{
                cy.layout({{
                    name: "dagre",
                    rankDir: "TB",
                    nodeSep: 40,
                    edgeSep: 12,
                    rankSep: 85,
                    fit: true,
                    padding: 30
                }}).run();
                renderLayoutStatus("Dagre", "Top to bottom", "dagre");
                return;
            }}
            runBreadthLayout();
        }}

        function runElkLayeredLayout() {{
            if (elkAvailable) {{
                cy.layout({{
                    name: "elk",
                    fit: true,
                    padding: 30,
                    nodeDimensionsIncludeLabels: true,
                    elk: {{
                        algorithm: "layered",
                        "elk.direction": "RIGHT",
                        "elk.spacing.nodeNode": "30.0",
                        "elk.layered.spacing.nodeNodeBetweenLayers": "80.0",
                        "elk.edgeRouting": "ORTHOGONAL"
                    }}
                }}).run();
                renderLayoutStatus("ELK layered", "Left to right", "elkjs");
                return;
            }}
            runDagreLayout();
        }}

    const cy = cytoscape({{
      container: document.getElementById("cy"),
      elements: [...elements.nodes, ...elements.edges],
      style: [
        {{
          selector: "node",
          style: {{
            "label": "data(label)",
            "font-size": 11,
            "color": "#0b1f33",
            "text-wrap": "wrap",
            "text-max-width": 180,
            "text-valign": "center",
            "text-halign": "center",
            "width": 34,
            "height": 34,
            "border-width": 1.3,
            "border-color": "#23395b",
            "background-color": "{NODE_COLORS["other"]}",
          }}
        }},
        {{ selector: "node.hl_start", style: {{ "background-color": "{NODE_COLORS["hl_start"]}" }} }},
        {{ selector: "node.hl_end", style: {{ "background-color": "{NODE_COLORS["hl_end"]}" }} }},
        {{ selector: "node.ll_start", style: {{ "background-color": "{NODE_COLORS["ll_start"]}" }} }},
        {{ selector: "node.ll_end", style: {{ "background-color": "{NODE_COLORS["ll_end"]}" }} }},
        {{
          selector: "edge",
          style: {{
            "width": 2.0,
            "line-color": "{EDGE_COLORS["other"]}",
            "target-arrow-color": "{EDGE_COLORS["other"]}",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 1.0,
            "opacity": 0.9,
            "label": "data(label)",
            "font-size": 9,
            "color": "#3e4c59",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": 2,
            "text-rotation": "autorotate",
          }}
        }},
        {{
          selector: "edge.causal",
          style: {{
            "line-color": "{EDGE_COLORS["causal"]}",
            "target-arrow-color": "{EDGE_COLORS["causal"]}",
          }}
        }},
        {{
          selector: "edge.assumption",
          style: {{
            "line-color": "{EDGE_COLORS["assumption"]}",
            "target-arrow-color": "{EDGE_COLORS["assumption"]}",
            "line-style": "dashed",
          }}
        }},
                {{
                    selector: "edge.mock",
                    style: {{
                        "line-color": "{EDGE_COLORS["mock"]}",
                        "target-arrow-color": "{EDGE_COLORS["mock"]}",
                        "line-style": "dotted",
                    }}
                }},
      ],
      layout: {{
                name: dagreAvailable ? "dagre" : "breadthfirst",
                rankDir: "TB",
                nodeSep: 40,
                edgeSep: 12,
                rankSep: 85,
        fit: true,
        padding: 30
      }},
      wheelSensitivity: 0.15
    }});

    function updateEdgeFilters() {{
      const showCausal = document.getElementById("showCausal").checked;
      const showAssumption = document.getElementById("showAssumption").checked;
            const showMock = document.getElementById("showMock").checked;
      const showOther = document.getElementById("showOther").checked;

      cy.edges().forEach((edge) => {{
        const reason = edge.data("reason_kind");
        let show = true;
        if (reason === "causal") show = showCausal;
        else if (reason === "assumption") show = showAssumption;
                else if (reason === "mock") show = showMock;
        else show = showOther;
        edge.style("display", show ? "element" : "none");
      }});
    }}

    function updateSearch() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      if (!query) {{
        cy.nodes().forEach((node) => node.style("opacity", 1.0));
        cy.edges().forEach((edge) => edge.style("opacity", 0.9));
        return;
      }}
      const matchedIds = new Set();
      cy.nodes().forEach((node) => {{
        const hit = String(node.data("search") || "").includes(query);
        node.style("opacity", hit ? 1.0 : 0.15);
        if (hit) matchedIds.add(node.id());
      }});
      cy.edges().forEach((edge) => {{
        const hit = matchedIds.has(edge.source().id()) || matchedIds.has(edge.target().id());
        edge.style("opacity", hit ? 1.0 : 0.08);
      }});
    }}

    function showDetails(html) {{
      document.getElementById("details").innerHTML = html;
    }}

    cy.on("tap", "node", (evt) => {{
      showDetails(evt.target.data("detail"));
    }});

    cy.on("tap", "edge", (evt) => {{
      showDetails(evt.target.data("detail"));
    }});

    document.getElementById("showCausal").addEventListener("change", updateEdgeFilters);
    document.getElementById("showAssumption").addEventListener("change", updateEdgeFilters);
    document.getElementById("showMock").addEventListener("change", updateEdgeFilters);
    document.getElementById("showOther").addEventListener("change", updateEdgeFilters);
    document.getElementById("search").addEventListener("input", updateSearch);

        document.getElementById("layoutDagre").addEventListener("click", runDagreLayout);
        document.getElementById("layoutElk").addEventListener("click", runElkLayeredLayout);
    document.getElementById("layoutBreadth").addEventListener("click", () => {{
            runBreadthLayout();
    }});
    document.getElementById("fit").addEventListener("click", () => {{
      cy.fit(undefined, 30);
    }});

    updateEdgeFilters();
    updateSearch();
        if (dagreAvailable) {{
            renderLayoutStatus("Dagre", "Top to bottom", "dagre");
        }} else {{
            renderLayoutStatus("Breadthfirst", "Top to bottom", "Cytoscape built-in");
        }}
  </script>
</body>
</html>
"""
    return html


def run(input_path, output_path, labels, cytoscape_js, reason_filter, no_ll):
    """
    Handle run.

    Parameters
    ----------
    input_path : Any
        Path to the input file to parse.
    output_path : Any
        Path where the generated output file is written.
    labels : Any
        Node-label style used by the visualizer.
    cytoscape_js : Any
        URL or local path of the Cytoscape JavaScript bundle.
    reason_filter : Any
        Comma-separated reason kinds to keep in the visualization.
    no_ll : Any
        Whether low-level actions should be hidden from output.

    Returns
    -------
    Any
        Result returned by `run`.
    """
    with open(input_path, "r") as handle:
        content = handle.read()

    plan_rows = parse_plan_actions_with_enablers(content)
    parsed_edges = parse_enabler_terms(content)
    if not parsed_edges and not plan_rows:
        raise RuntimeError("No enabler(...) terms found in the input.")

    if reason_filter != "all":
        allowed = {item.strip() for item in reason_filter.split(",") if item.strip()}
        parsed_edges = [edge for edge in parsed_edges if edge["reason_kind"] in allowed]
        if not parsed_edges:
            raise RuntimeError("No enablers left after applying --reason-filter.")

    if no_ll:
        parsed_edges = [
            edge
            for edge in parsed_edges
            if not is_low_level_step(edge["source"]["step"]) and not is_low_level_step(edge["target"]["step"])
        ]
        plan_rows = [row for row in plan_rows if not is_low_level_step(row["step"])]
        if not parsed_edges and not plan_rows:
            raise RuntimeError("No enablers left after applying --no-ll.")

    nodes, edges = build_graph(parsed_edges, plan_rows=plan_rows)
    add_boundary_mock_edges(nodes, edges)
    positions, depths = build_positions(nodes, edges)
    elements, stats = build_elements(nodes, edges, positions, depths, labels)

    html = render_html(
        elements=elements,
        stats=stats,
        cytoscape_src=cytoscape_js or DEFAULT_CYTOSCAPE_JS,
        title="Partial Order Enabler Graph",
    )

    with open(output_path, "w") as handle:
        handle.write(html)

    return stats


def build_arg_parser():
    """
    Build arg parser.

    Returns
    -------
    Any
        Result returned by `build_arg_parser`.
    """
    parser = argparse.ArgumentParser(
        description="Visualize a partial-order graph from enabler(Source, Target, Reason) terms."
    )
    parser.add_argument("input", help="Input file containing extracted enablers (e.g., planner log).")
    parser.add_argument(
        "--output",
        default="partial_order_graph.html",
        help="Output HTML file path (default: partial_order_graph.html).",
    )
    parser.add_argument(
        "--labels",
        choices=["id", "short", "full"],
        default="short",
        help="Node label style.",
    )
    parser.add_argument(
        "--reason-filter",
        default="all",
        help="Comma-separated reason kinds to keep (default: all). Example: causal,assumption",
    )
    parser.add_argument(
        "--cytoscape-js",
        default="",
        help="Optional local path or URL for cytoscape.min.js (defaults to CDN).",
    )
    parser.add_argument(
        "--no-ll",
        action="store_true",
        help="Hide low-level actions (steps with ll_* functors).",
    )
    return parser


def main():
    """
    Run the command-line entry point.

    Returns
    -------
    Any
        Result returned by `main`.
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.abspath(output_path)

    stats = run(
        input_path=args.input,
        output_path=output_path,
        labels=args.labels,
        cytoscape_js=args.cytoscape_js,
        reason_filter=args.reason_filter,
        no_ll=args.no_ll,
    )

    logger.info(f"Wrote {output_path}")
    logger.info(f"Nodes: {stats['nodes']} | Edges: {stats['edges']}")


if __name__ == "__main__":
    main()
