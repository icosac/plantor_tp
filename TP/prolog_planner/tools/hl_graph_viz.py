#!/usr/bin/env python3
"""
Parse planner graph traces and generate interactive high-level search graph visualizations.
"""

import argparse
import csv
import json
import os
import re
from collections import defaultdict

import networkx as nx

DEFAULT_CYTOSCAPE_JS = "https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"

NODE_COLORS = {
    "node": "#2E86AB",
    "init": "#2D936C",
    "goal": "#D1495B",
    "goal_reached": "#E9B44C",
}

OUTCOME_COLORS = {
    "enqueued": "#2F6690",
    "replaced_open": "#1B998B",
    "skipped_open_better": "#E06C75",
    "skipped_close": "#7C7C7C",
    "goal_equivalent": "#C17C00",
}

PROLOG_VAR_RE = re.compile(r"^[_A-Z][A-Za-z0-9_]*$")


def safe_int(value):
    """
    Safely parse int.

    Parameters
    ----------
    value : Any
        Value to normalize, convert, or escape.

    Returns
    -------
    Any
        Result returned by `safe_int`.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_plan_from_line(line):
    """
    Extract plan from line.

    Parameters
    ----------
    line : Any
        Single text line being parsed.

    Returns
    -------
    Any
        Result returned by `extract_plan_from_line`.
    """
    if "Plan" not in line:
        return []
    marker = "Plan ["
    marker_idx = line.find(marker)
    if marker_idx != -1:
        start = line.find("[", marker_idx)
    else:
        plan_idx = line.find("Plan")
        start = line.find("[", plan_idx)
    if start == -1:
        return []
    end = line.rfind("]")
    if end == -1 or end <= start:
        end = line.find(" found", start)
        if end == -1:
            end = len(line)
    list_text = line[start + 1:end]
    if "[" in list_text and "]" not in list_text:
        list_text = list_text.split("[")[-1]
    if not list_text.strip():
        return []
    items = parse_state_items(list_text)
    cleaned = []
    for item in items:
        value = item.strip()
        if value.endswith("."):
            value = value[:-1].strip()
        if value:
            cleaned.append(value)
    return cleaned


def parse_graph_log(path):
    """
    Parse graph log.

    Parameters
    ----------
    path : Any
        Filesystem path used by this operation.

    Returns
    -------
    Any
        Result returned by `parse_graph_log`.
    """
    states = {}
    edges = []
    inits = set()
    goals = set()
    goal_reached = set()
    pops = []
    skips = []
    depths = {}
    plan_steps = []
    plan_collect = False
    plan_lines = []
    plan_from_lines = False
    action_catalog = {}

    def update_depth(key, depth):
        """
        Update depth.

        Parameters
        ----------
        key : Any
            Key associated with a state, node, or mapping entry.
        depth : Any
            Depth value associated with a state or graph node.

        Returns
        -------
        Any
            Result returned by `update_depth`.
        """
        if key is None or depth is None:
            return
        if key not in depths or depth < depths[key]:
            depths[key] = depth

    with open(path, "r") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            clean_line = line.lstrip()

            if "hl_d_action(" in clean_line:
                parsed_action = parse_hl_d_action_term(clean_line)
                if parsed_action and is_ground_action_name(parsed_action.get("action_name")):
                    register_action(action_catalog, parsed_action)

            # Capture the selected plan either from single-line or indented multi-line formats.
            if clean_line.startswith("[planner] Plan "):
                plan_steps = extract_plan_from_line(clean_line)
                plan_collect = False
                plan_lines = []
                plan_from_lines = False
            elif clean_line.strip() in {"Plan:", "High Level Plan:", "Low Level Plan:", "Partial Order Plan:"}:
                plan_collect = True
                plan_lines = []
                plan_from_lines = True
            elif plan_collect:
                stripped = clean_line.strip()
                if not stripped or stripped.startswith("%") or stripped.startswith("GRAPH ") or stripped.startswith("["):
                    plan_collect = False
                elif line.startswith("\t") or line.startswith("    "):
                    plan_lines.append(stripped)
                else:
                    plan_collect = False
            if plan_from_lines and plan_lines:
                plan_steps = [step.rstrip(".") for step in plan_lines if step.strip()]

            # Only GRAPH-prefixed records contribute to the exploration graph.
            if not line.startswith("GRAPH "):
                continue

            if line.startswith("GRAPH STATE "):
                parts = line.split(" ", 3)
                if len(parts) == 4:
                    key = parts[2]
                    states[key] = parts[3]
                continue

            if line.startswith("GRAPH INIT "):
                parts = line.split()
                if len(parts) >= 3:
                    inits.add(parts[2])
                    update_depth(parts[2], 0)
                continue

            if line.startswith("GRAPH GOAL_REACHED "):
                parts = line.split()
                if len(parts) >= 5:
                    key = parts[2]
                    depth = safe_int(parts[3])
                    cost = safe_int(parts[4])
                    goal_reached.add(key)
                    update_depth(key, depth)
                    pops.append((key, depth, cost))
                continue

            if line.startswith("GRAPH GOAL "):
                parts = line.split()
                if len(parts) >= 3:
                    goals.add(parts[2])
                continue

            if line.startswith("GRAPH POP "):
                parts = line.split()
                if len(parts) >= 5:
                    key = parts[2]
                    depth = safe_int(parts[3])
                    cost = safe_int(parts[4])
                    update_depth(key, depth)
                    pops.append((key, depth, cost))
                continue

            if line.startswith("GRAPH SKIP "):
                parts = line.split()
                if len(parts) >= 5:
                    key = parts[2]
                    reason = parts[3]
                    depth = safe_int(parts[4])
                    update_depth(key, depth)
                    skips.append((key, reason, depth))
                continue

            if line.startswith("GRAPH EDGE "):
                # GRAPH EDGE carries source/target, frontier outcome, and optional action payload.
                rest = line[len("GRAPH EDGE "):].strip()
                parts = rest.split(" ", 6)
                if len(parts) >= 6:
                    from_key, to_key, step_label, outcome, depth_s, cost_s = parts[:6]
                    data_s = parts[6] if len(parts) >= 7 else ""
                    depth = safe_int(depth_s)
                    cost = safe_int(cost_s)
                    edge_data = parse_edge_data(data_s)
                    if edge_data and is_ground_action_name(edge_data.get("action_name")):
                        register_action(action_catalog, edge_data)
                    if depth is not None:
                        update_depth(to_key, depth)
                        if depth > 0:
                            update_depth(from_key, depth - 1)
                    edges.append({
                        "from": from_key,
                        "to": to_key,
                        "step": step_label,
                        "outcome": outcome,
                        "depth": depth,
                        "cost": cost,
                        "data_raw": data_s,
                        "data": edge_data,
                    })
                continue

    goal_links = synthesize_goal_links(states, goals, goal_reached)

    return {
        "states": states,
        "edges": edges,
        "goal_links": goal_links,
        "inits": inits,
        "goals": goals,
        "goal_reached": goal_reached,
        "pops": pops,
        "skips": skips,
        "depths": depths,
        "plan_steps": plan_steps,
        "action_catalog": action_catalog,
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
    if value is None:
        return ""
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def parse_state_items(state):
    """
    Parse state items.

    Parameters
    ----------
    state : Any
        State term or state text being processed.

    Returns
    -------
    Any
        Result returned by `parse_state_items`.
    """
    if not state:
        return []
    inner = state.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    items = []
    current = []
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    in_single = False
    in_double = False
    idx = 0

    while idx < len(inner):
        ch = inner[idx]
        if ch == "\\":
            if idx + 1 < len(inner):
                current.append(ch)
                idx += 1
                current.append(inner[idx])
                idx += 1
                continue
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            idx += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            idx += 1
            continue
        if not in_single and not in_double:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                if paren_depth > 0:
                    paren_depth -= 1
            elif ch == "[":
                bracket_depth += 1
            elif ch == "]":
                if bracket_depth > 0:
                    bracket_depth -= 1
            elif ch == "{":
                brace_depth += 1
            elif ch == "}":
                if brace_depth > 0:
                    brace_depth -= 1
            elif ch == "," and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                item = "".join(current).strip()
                if item:
                    items.append(item)
                current = []
                idx += 1
                continue
        current.append(ch)
        idx += 1

    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def strip_outer_negation(literal):
    """
    Handle strip outer negation.

    Parameters
    ----------
    literal : Any
        Literal term string to inspect or normalize.

    Returns
    -------
    Any
        Result returned by `strip_outer_negation`.
    """
    value = (literal or "").strip()
    while value.startswith("neg(") and value.endswith(")"):
        value = value[4:-1].strip()
    while value.startswith("not(") and value.endswith(")"):
        value = value[4:-1].strip()
    return value


def parse_term(term_text):
    """
    Parse term.

    Parameters
    ----------
    term_text : Any
        Raw Prolog term text to parse.

    Returns
    -------
    Any
        Result returned by `parse_term`.
    """
    value = (term_text or "").strip()
    if not value:
        return "", []
    idx = value.find("(")
    if idx == -1 or not value.endswith(")"):
        return value, []
    functor = value[:idx].strip()
    inner = value[idx + 1:-1]
    args = parse_state_items(inner)
    return functor, args


def is_prolog_var(token):
    """
    Return whether prolog var.

    Parameters
    ----------
    token : Any
        Single token value being parsed or validated.

    Returns
    -------
    Any
        Result returned by `is_prolog_var`.
    """
    return bool(PROLOG_VAR_RE.match((token or "").strip()))


def terms_unify(left, right):
    """
    Evaluate whether unify.

    Parameters
    ----------
    left : Any
        Left-hand term used in a structural unification comparison.
    right : Any
        Right-hand term used in a structural unification comparison.

    Returns
    -------
    Any
        Result returned by `terms_unify`.
    """
    left_value = (left or "").strip()
    right_value = (right or "").strip()
    if not left_value or not right_value:
        return left_value == right_value
    if is_prolog_var(left_value) or is_prolog_var(right_value):
        return True

    left_functor, left_args = parse_term(left_value)
    right_functor, right_args = parse_term(right_value)
    left_is_compound = bool(left_args)
    right_is_compound = bool(right_args)

    if not left_is_compound and not right_is_compound:
        return left_value == right_value
    if left_is_compound != right_is_compound:
        return False
    if left_functor != right_functor or len(left_args) != len(right_args):
        return False
    return all(terms_unify(l_arg, r_arg) for l_arg, r_arg in zip(left_args, right_args))


def ll_prefixed_literal(literal):
    """
    Handle ll prefixed literal.

    Parameters
    ----------
    literal : Any
        Literal term string to inspect or normalize.

    Returns
    -------
    Any
        Result returned by `ll_prefixed_literal`.
    """
    value = strip_outer_negation(literal)
    if not value:
        return False
    functor, args = parse_term(value)
    if args:
        return functor.startswith("ll_")
    return value.startswith("ll_")


def high_level_literals(state_text):
    """
    Handle high level literals.

    Parameters
    ----------
    state_text : Any
        Serialized state term string parsed into Prolog terms.

    Returns
    -------
    Any
        Result returned by `high_level_literals`.
    """
    return [lit for lit in parse_state_items(state_text) if not ll_prefixed_literal(lit)]


def goal_matches_reached(goal_state_text, reached_state_text):
    """
    Handle goal matches reached.

    Parameters
    ----------
    goal_state_text : Any
        Text representation of goal state consumed by this function.
    reached_state_text : Any
        Text representation of reached state consumed by this function.

    Returns
    -------
    Any
        Result returned by `goal_matches_reached`.
    """
    goal_hl = high_level_literals(goal_state_text)
    reached_hl = high_level_literals(reached_state_text)
    if not goal_hl:
        return False
    for goal_lit in goal_hl:
        if not any(terms_unify(goal_lit, reached_lit) for reached_lit in reached_hl):
            return False
    return True


def synthesize_goal_links(states, goals, goal_reached):
    """
    Handle synthesize goal links.

    Parameters
    ----------
    states : Any
        Mapping from state identifiers to serialized state content.
    goals : Any
        Set or collection of goal-state identifiers.
    goal_reached : Any
        Set of state identifiers that reached a goal condition.

    Returns
    -------
    Any
        Result returned by `synthesize_goal_links`.
    """
    links = []
    seen = set()
    # Add synthetic links when a reached node semantically satisfies a canonical goal node.
    for reached_key in sorted(goal_reached):
        reached_state = states.get(reached_key, "")
        if not reached_state:
            continue
        for goal_key in sorted(goals):
            if goal_key == reached_key:
                continue
            goal_state = states.get(goal_key, "")
            if not goal_state:
                continue
            if not goal_matches_reached(goal_state, reached_state):
                continue
            link_key = (reached_key, goal_key)
            if link_key in seen:
                continue
            seen.add(link_key)
            links.append({
                "from": reached_key,
                "to": goal_key,
                "step": "!",
                "outcome": "goal_equivalent",
                "depth": None,
                "cost": None,
                "data_raw": "",
                "data": None,
                "synthetic": True,
                "synthetic_type": "goal_link",
                "info": "High-level goal satisfied. Linked to canonical goal_state node (LL predicates differ or are abstract).",
            })
    return links


def parse_edge_data(data_text):
    """
    Parse edge data.

    Parameters
    ----------
    data_text : Any
        Raw serialized edge or payload data.

    Returns
    -------
    Any
        Result returned by `parse_edge_data`.
    """
    if not data_text:
        return None
    cleaned = data_text.strip()
    if not cleaned or cleaned == "[]":
        return None
    items = parse_state_items(cleaned)
    if len(items) >= 7:
        return {
            "action_name": items[0],
            "pre_start": items[1],
            "pre_end": items[2],
            "overall": items[3],
            "eff_start": items[4],
            "eff_end": items[5],
            "duration": items[6],
            "raw": cleaned,
        }
    if len(items) == 6:
        # Backward compatibility with the old payload shape (without action name).
        return {
            "pre_start": items[0],
            "pre_end": items[1],
            "overall": items[2],
            "eff_start": items[3],
            "eff_end": items[4],
            "duration": items[5],
            "raw": cleaned,
        }
    if len(items) < 6:
        return {"raw": cleaned}
    return {"raw": cleaned}


def parse_hl_d_action_term(term_text):
    """
    Parse hl d action term.

    Parameters
    ----------
    term_text : Any
        Raw Prolog term text to parse.

    Returns
    -------
    Any
        Result returned by `parse_hl_d_action_term`.
    """
    if not term_text:
        return None
    cleaned = term_text.strip().rstrip(".,")
    marker = "hl_d_action("
    marker_idx = cleaned.find(marker)
    if marker_idx == -1:
        return None
    term = cleaned[marker_idx:]
    if not term.endswith(")"):
        return None
    inner = term[len(marker):-1]
    args = parse_state_items(inner)
    if len(args) != 7:
        return None
    return {
        "action_name": args[0],
        "pre_start": args[1],
        "pre_end": args[2],
        "overall": args[3],
        "eff_start": args[4],
        "eff_end": args[5],
        "duration": args[6],
    }


def is_ground_action_name(action_name):
    """
    Return whether ground action name.

    Parameters
    ----------
    action_name : Any
        Action identifier or Prolog action term name.

    Returns
    -------
    Any
        Result returned by `is_ground_action_name`.
    """
    if not action_name:
        return False
    return re.search(r"\b_[A-Za-z0-9_]*", action_name) is None


def register_action(catalog, action_data):
    """
    Register action.

    Parameters
    ----------
    catalog : Any
        Action metadata catalog indexed by action name.
    action_data : Any
        Action metadata dictionary extracted from log terms.

    Returns
    -------
    Any
        Result returned by `register_action`.
    """
    action_name = action_data.get("action_name")
    if not action_name:
        return
    entry = catalog.setdefault(action_name, {"action_name": action_name})
    for key in ("pre_start", "pre_end", "overall", "eff_start", "eff_end", "duration"):
        current = entry.get(key, "")
        incoming = action_data.get(key, "")
        if (not current or current == "[]") and incoming:
            entry[key] = incoming


def build_debug_payload(parsed, graph, label_map):
    """
    Build debug payload.

    Parameters
    ----------
    parsed : Any
        Parsed intermediate structure produced by earlier log parsing.
    graph : Any
        NetworkX graph to inspect, layout, or export.
    label_map : Any
        Mapping from internal node keys to display labels.

    Returns
    -------
    Any
        Result returned by `build_debug_payload`.
    """
    states = []
    for key in sorted(graph.nodes()):
        node_data = graph.nodes[key]
        state_text = node_data.get("state", "")
        state_items = parse_state_items(state_text)
        preview = ", ".join(state_items[:4])
        if len(state_items) > 4:
            preview = f"{preview}, ..."
        states.append({
            "id": key,
            "label": label_map.get(key, key),
            "depth": node_data.get("depth"),
            "state": state_text,
            "preview": preview,
        })

    actions = []
    for action_name in sorted(parsed.get("action_catalog", {}).keys()):
        action_data = parsed["action_catalog"][action_name]
        actions.append({
            "name": action_name,
            "pre_start": action_data.get("pre_start", "[]"),
            "pre_end": action_data.get("pre_end", "[]"),
            "overall": action_data.get("overall", "[]"),
            "eff_start": action_data.get("eff_start", "[]"),
            "eff_end": action_data.get("eff_end", "[]"),
            "duration": action_data.get("duration", ""),
        })

    return {"states": states, "actions": actions}


def parse_step_action(step_label):
    """
    Parse step action.

    Parameters
    ----------
    step_label : Any
        Step label string from a graph edge or plan entry.

    Returns
    -------
    Any
        Result returned by `parse_step_action`.
    """
    if not step_label:
        return None, None
    cleaned = step_label.strip()
    for phase in ("start", "end"):
        prefix = f"{phase}("
        if cleaned.startswith(prefix) and cleaned.endswith(")"):
            inner = cleaned[len(prefix):-1].strip()
            return phase, inner
    return None, None


def format_state(state, max_items=16):
    """
    Format state.

    Parameters
    ----------
    state : Any
        State term or state text being processed.
    max_items : Any, optional
        Numeric bound used for max items in this function.

    Returns
    -------
    Any
        Result returned by `format_state`.
    """
    if not state:
        return "(state missing)"
    items = parse_state_items(state)
    if not items:
        return "(empty state)"
    if max_items is None or len(items) <= max_items:
        return "<br>".join(f"&nbsp;&nbsp;{escape_html(item)}" for item in items)
    head = "<br>".join(f"&nbsp;&nbsp;{escape_html(item)}" for item in items[:max_items])
    return f"{head}<br>... (+{len(items) - max_items} more)"


def format_state_text(state, max_items=120):
    """
    Format state text.

    Parameters
    ----------
    state : Any
        State term or state text being processed.
    max_items : Any, optional
        Numeric bound used for max items in this function.

    Returns
    -------
    Any
        Result returned by `format_state_text`.
    """
    items = parse_state_items(state)
    if not items:
        return ""
    if len(items) > max_items:
        items = items[:max_items]
    return ", ".join(items)


def truncate_text(text, max_length=4000):
    """
    Handle truncate text.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.
    max_length : Any, optional
        Numeric bound used for max length in this function.

    Returns
    -------
    Any
        Result returned by `truncate_text`.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length]


def format_predicate_block(title, list_text, max_items=18):
    """
    Format predicate block.

    Parameters
    ----------
    title : Any
        Title text used in generated reports or visualizations.
    list_text : Any
        Text representation of list consumed by this function.
    max_items : Any, optional
        Numeric bound used for max items in this function.

    Returns
    -------
    Any
        Result returned by `format_predicate_block`.
    """
    items = parse_state_items(list_text)
    if not items:
        return f"<br>{escape_html(title)}: (none)"
    head = items[:max_items]
    lines = "<br>".join(f"&nbsp;&nbsp;{escape_html(item)}" for item in head)
    suffix = ""
    if len(items) > max_items:
        suffix = f"<br>... (+{len(items) - max_items} more)"
    return f"<br>{escape_html(title)}:<br>{lines}{suffix}"


def build_graph(parsed):
    """
    Build graph.

    Parameters
    ----------
    parsed : Any
        Parsed intermediate structure produced by earlier log parsing.

    Returns
    -------
    Any
        Result returned by `build_graph`.
    """
    edges = parsed["edges"] + parsed.get("goal_links", [])
    states = parsed["states"]
    depths = parsed["depths"]

    nodes = set()
    for edge in edges:
        nodes.add(edge["from"])
        nodes.add(edge["to"])
    nodes.update(states.keys())

    graph = nx.MultiDiGraph()
    for key in nodes:
        graph.add_node(key, state=states.get(key, ""), depth=depths.get(key))
    for edge in edges:
        graph.add_edge(
            edge["from"],
            edge["to"],
            step=edge["step"],
            outcome=edge["outcome"],
            depth=edge["depth"],
            cost=edge["cost"],
        )

    return graph


def layout_by_depth(graph, depths, x_spacing=1.7, y_spacing=1.4):
    """
    Handle layout by depth.

    Parameters
    ----------
    graph : Any
        NetworkX graph to inspect, layout, or export.
    depths : Any
        Per-node depth mapping used for layout or reporting.
    x_spacing : Any, optional
        Horizontal spacing used between depth columns.
    y_spacing : Any, optional
        Vertical spacing used between nodes in the same layer.

    Returns
    -------
    Any
        Result returned by `layout_by_depth`.
    """
    known_depths = [d for d in depths.values() if d is not None]
    max_depth = max(known_depths) if known_depths else 0

    groups = defaultdict(list)
    for node in graph.nodes():
        depth = depths.get(node)
        if depth is None:
            depth = max_depth + 1
        groups[depth].append(node)

    positions = {}
    for depth, nodes in groups.items():
        nodes = sorted(nodes)
        count = len(nodes)
        if count == 1:
            xs = [0.0]
        else:
            center = (count - 1) / 2.0
            xs = [(i - center) * x_spacing for i in range(count)]
        y = depth * y_spacing
        for idx, node in enumerate(nodes):
            positions[node] = (xs[idx], y)
    return positions


def layout_spring(graph):
    """
    Handle layout spring.

    Parameters
    ----------
    graph : Any
        NetworkX graph to inspect, layout, or export.

    Returns
    -------
    Any
        Result returned by `layout_spring`.
    """
    return nx.spring_layout(graph, seed=7, k=0.9)


def scale_positions(positions, scale=220.0):
    """
    Handle scale positions.

    Parameters
    ----------
    positions : Any
        Per-node layout coordinates for visualization output.
    scale : Any, optional
        Scale factor applied to computed layout coordinates.

    Returns
    -------
    Any
        Result returned by `scale_positions`.
    """
    if not positions:
        return {}
    xs = [pos[0] for pos in positions.values()]
    ys = [pos[1] for pos in positions.values()]
    x_center = (max(xs) + min(xs)) / 2.0
    y_center = (max(ys) + min(ys)) / 2.0

    scaled = {}
    for key, (x, y) in positions.items():
        scaled[key] = {
            "x": (x - x_center) * scale,
            "y": (y - y_center) * scale,
        }
    return scaled


def make_label_map(keys, mode):
    """
    Handle make label map.

    Parameters
    ----------
    keys : Any
        Subset of node keys used to build label mappings.
    mode : Any
        Output mode controlling rendering/display behavior.

    Returns
    -------
    Any
        Result returned by `make_label_map`.
    """
    keys = sorted(keys)
    if mode == "none":
        return {key: "" for key in keys}
    if mode == "short":
        return {key: f"S{idx}" for idx, key in enumerate(keys)}
    return {key: key for key in keys}


def export_csv(parsed, graph, label_map, path_prefix):
    """
    Handle export csv.

    Parameters
    ----------
    parsed : Any
        Parsed intermediate structure produced by earlier log parsing.
    graph : Any
        NetworkX graph to inspect, layout, or export.
    label_map : Any
        Mapping from internal node keys to display labels.
    path_prefix : Any
        Path prefix used when writing CSV output artifacts.

    Returns
    -------
    Any
        Result returned by `export_csv`.
    """
    nodes_path = f"{path_prefix}_nodes.csv"
    edges_path = f"{path_prefix}_edges.csv"

    with open(nodes_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "label", "depth", "state", "is_init", "is_goal", "is_goal_reached"])
        for key in graph.nodes():
            writer.writerow([
                key,
                label_map.get(key, key),
                graph.nodes[key].get("depth"),
                graph.nodes[key].get("state"),
                key in parsed["inits"],
                key in parsed["goals"],
                key in parsed["goal_reached"],
            ])

    with open(edges_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["from", "to", "step", "outcome", "depth", "cost", "data"])
        for edge in parsed["edges"]:
            writer.writerow([
                edge["from"],
                edge["to"],
                edge["step"],
                edge["outcome"],
                edge["depth"],
                edge["cost"],
                edge.get("data_raw", ""),
            ])

    return nodes_path, edges_path


def build_elements(parsed, graph, positions, label_mode, show_labels, edge_outcomes):
    """
    Build elements.

    Parameters
    ----------
    parsed : Any
        Parsed intermediate structure produced by earlier log parsing.
    graph : Any
        NetworkX graph to inspect, layout, or export.
    positions : Any
        Per-node layout coordinates for visualization output.
    label_mode : Any
        Node label mode controlling displayed text.
    show_labels : Any
        Whether text labels should be emitted in the graph output.
    edge_outcomes : Any
        Set of edge outcome categories to include in output.

    Returns
    -------
    Any
        Result returned by `build_elements`.
    """
    label_map = make_label_map(graph.nodes(), label_mode)

    allowed = None
    if edge_outcomes and edge_outcomes != "all":
        allowed = {item.strip() for item in edge_outcomes.split(",") if item.strip()}

    nodes = []
    status_counts = defaultdict(int)
    for key in graph.nodes():
        if key not in positions:
            continue
        state = graph.nodes[key].get("state", "")
        depth = graph.nodes[key].get("depth")
        status = "normal"
        if key in parsed["inits"]:
            status = "init"
        elif key in parsed["goals"]:
            status = "goal"
        elif key in parsed["goal_reached"]:
            status = "goal_reached"
        status_counts[status] += 1

        status_list = []
        if key in parsed["inits"]:
            status_list.append("init")
        if key in parsed["goals"]:
            status_list.append("goal")
        if key in parsed["goal_reached"]:
            status_list.append("goal_reached")
        status_text = ", ".join(status_list) if status_list else "normal"

        label = label_map.get(key, key)
        depth_text = "n/a" if depth is None else str(depth)
        hover_html = (
            f"{escape_html(label)}"
            f"<br>key: {escape_html(key)}"
            f"<br>depth: {escape_html(depth_text)}"
            f"<br>status: {escape_html(status_text)}"
            f"<br>state:<br>{format_state(state, max_items=16)}"
        )
        detail_html = (
            f"{escape_html(label)}"
            f"<br>key: {escape_html(key)}"
            f"<br>depth: {escape_html(depth_text)}"
            f"<br>status: {escape_html(status_text)}"
            f"<br>state:<br>{format_state(state, max_items=None)}"
        )

        search_parts = [key, label, format_state_text(state)]
        search_blob = truncate_text(" ".join(part for part in search_parts if part).lower())

        node_entry = {
            "data": {
                "id": key,
                "label": label,
                "key": key,
                "depth": depth,
                "state": state,
                "status": status,
                "hover": hover_html,
                "detail": detail_html,
                "search": search_blob,
            },
            "position": positions[key],
            "classes": status,
        }
        if not show_labels:
            node_entry["classes"] = f"{status} label-hidden"
        nodes.append(node_entry)

    edges = []
    visible_outcomes = defaultdict(int)
    render_edges = parsed["edges"] + parsed.get("goal_links", [])
    for idx, edge in enumerate(render_edges):
        if allowed and edge["outcome"] not in allowed:
            continue
        src = edge["from"]
        dst = edge["to"]
        if src not in positions or dst not in positions:
            continue
        visible_outcomes[edge["outcome"]] += 1
        phase, action_term = parse_step_action(edge["step"])
        edge_action_data = edge.get("data")
        action_details = ""
        details_source = edge_action_data
        if edge.get("synthetic_type") == "goal_link":
            action_details = (
                "<br>goal link: high-level match"
                f"<br>note: {escape_html(edge.get('info', ''))}"
            )
        elif details_source:
            action_label = action_term or details_source.get("action_name", "")
            action_details = f"<br>action: {escape_html(action_label)}"
            if details_source.get("duration"):
                action_details += f"<br>duration: {escape_html(details_source['duration'])}"
            if phase == "start":
                action_details += f"<br>phase: {escape_html(phase)}"
                action_details += format_predicate_block("preconditions (start)", details_source.get("pre_start", ""))
                action_details += format_predicate_block("effects (start)", details_source.get("eff_start", ""))
                action_details += format_predicate_block("invariants", details_source.get("overall", ""))
            elif phase == "end":
                action_details += f"<br>phase: {escape_html(phase)}"
                action_details += format_predicate_block("preconditions (end)", details_source.get("pre_end", ""))
                action_details += format_predicate_block("effects (end)", details_source.get("eff_end", ""))
                action_details += format_predicate_block("invariants", details_source.get("overall", ""))
            else:
                action_details += format_predicate_block("preconditions (start)", details_source.get("pre_start", ""))
                action_details += format_predicate_block("preconditions (end)", details_source.get("pre_end", ""))
                action_details += format_predicate_block("invariants", details_source.get("overall", ""))
                action_details += format_predicate_block("effects (start)", details_source.get("eff_start", ""))
                action_details += format_predicate_block("effects (end)", details_source.get("eff_end", ""))
        cost_text = edge["cost"] if edge["cost"] is not None else "n/a"
        hover_html = (
            "edge"
            f"<br>{escape_html(label_map.get(src, src))} -> {escape_html(label_map.get(dst, dst))}"
            f"<br>step: {escape_html(edge['step'])}"
            f"<br>cost: {escape_html(cost_text)}"
            f"{action_details}"
        )
        edge_entry = {
            "data": {
                "id": f"e{idx}",
                "source": src,
                "target": dst,
                "step": edge["step"],
                "outcome": edge["outcome"],
                "depth": edge["depth"],
                "cost": edge["cost"],
                "hover": hover_html,
                "detail": hover_html,
            }
        }
        if edge.get("synthetic_type") == "goal_link":
            edge_entry["classes"] = "synthetic-goal-link"
        edges.append(edge_entry)

    stats = {
        "nodes": graph.number_of_nodes(),
        "edges_total": len(parsed["edges"]),
        "edges_virtual": len(parsed.get("goal_links", [])),
        "edges_visible": len(edges),
        "init": status_counts.get("init", 0),
        "goal": status_counts.get("goal", 0),
        "goal_reached": status_counts.get("goal_reached", 0),
        "normal": status_counts.get("normal", 0),
    }

    return {"nodes": nodes, "edges": edges}, label_map, stats, visible_outcomes


def safe_json_dumps(payload, indent=None):
    """
    Safely parse json dumps.

    Parameters
    ----------
    payload : Any
        JSON-like request payload with query parameters.
    indent : Any, optional
        Indentation prefix used when formatting generated text.

    Returns
    -------
    Any
        Result returned by `safe_json_dumps`.
    """
    data = json.dumps(payload, ensure_ascii=True, indent=indent)
    return data.replace("</", "<\\/")


def render_legend(title, items):
    """
    Handle render legend.

    Parameters
    ----------
    title : Any
        Title text used in generated reports or visualizations.
    items : Any
        Legend row descriptors containing color, label, and count values.

    Returns
    -------
    Any
        Result returned by `render_legend`.
    """
    if not items:
        return ""
    entries = []
    for label, color, count in items:
        entries.append(
            "<div class=\"legend-item\">"
            f"<span class=\"legend-swatch\" style=\"background:{escape_html(color)}\"></span>"
            f"<span class=\"legend-label\">{escape_html(label)} ({count})</span>"
            "</div>"
        )
    entries_html = "".join(entries)
    return (
        "<div class=\"section\">"
        f"<div class=\"section-title\">{escape_html(title)}</div>"
        f"<div class=\"legend\">{entries_html}</div>"
        "</div>"
    )


def _load_text(path):
    """
    Handle load text.

    Parameters
    ----------
    path : Any
        Filesystem path used by this operation.

    Returns
    -------
    Any
        Result returned by `_load_text`.
    """
    with open(path, "r") as handle:
        return handle.read()


def render_html(
    title,
    elements,
    debug_payload,
    stats,
    show_labels,
    visible_outcomes,
    cytoscape_src,
    plan_steps,
    prolog_service_url,
):
    """
    Handle render html.

    Parameters
    ----------
    title : Any
        Title text used in generated reports or visualizations.
    elements : Any
        Cytoscape element payload containing nodes and edges.
    debug_payload : Any
        Flag controlling whether debug payload behavior is enabled.
    stats : Any
        Aggregate statistics shown in the generated visualization.
    show_labels : Any
        Whether text labels should be emitted in the graph output.
    visible_outcomes : Any
        Outcome categories that should remain visible in the rendered graph.
    cytoscape_src : Any
        URL or local path of the Cytoscape JavaScript bundle.
    plan_steps : Any
        Ordered plan-step labels highlighted in the rendered graph.
    prolog_service_url : Any
        Base URL of the Prolog applicability service endpoint.

    Returns
    -------
    Any
        Result returned by `render_html`.
    """
    elements_json = safe_json_dumps(elements, indent=2)
    debug_payload_json = safe_json_dumps(debug_payload, indent=2)
    outcomes_json = safe_json_dumps(OUTCOME_COLORS, indent=2)
    show_labels_js = "true" if show_labels else "false"
    prolog_service_url_json = safe_json_dumps(prolog_service_url or "")

    node_legend_items = [
        ("init", NODE_COLORS["init"], stats["init"]),
        ("goal", NODE_COLORS["goal"], stats["goal"]),
        ("goal_reached", NODE_COLORS["goal_reached"], stats["goal_reached"]),
        ("normal", NODE_COLORS["node"], stats.get("normal", 0)),
    ]
    edge_legend_items = [
        (label, OUTCOME_COLORS.get(label, "#888888"), count)
        for label, count in sorted(visible_outcomes.items())
    ]

    node_legend_html = render_legend("Node legend", node_legend_items)
    edge_legend_html = render_legend("Edge outcomes", edge_legend_items)

    if plan_steps:
        plan_items = []
        total_steps = len(plan_steps)
        for idx, step in enumerate(plan_steps):
            suffix = "," if idx < total_steps - 1 else ""
            plan_items.append(
                "<li class=\"plan-step\">"
                f"<span class=\"plan-index\">{idx}</span> "
                f"<span class=\"plan-action\">- {escape_html(step)}{suffix}</span>"
                "</li>"
            )
        plan_list_html = "<ul class=\"plan-list\">" + "".join(plan_items) + "</ul>"
    else:
        plan_list_html = "<div class=\"plan-empty\">No plan found in log.</div>"

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    html_template_path = os.path.join(template_dir, "hl_graph_viz_template.html")
    css_template_path = os.path.join(template_dir, "hl_graph_viz.css")

    html_template = _load_text(html_template_path)
    inline_css = _load_text(css_template_path)

    return html_template.format(
        page_title=escape_html(title),
        inline_css=inline_css,
        plan_list_html=plan_list_html,
        stats_nodes=stats["nodes"],
        stats_edges_visible=stats["edges_visible"],
        stats_edges_total=stats["edges_total"],
        stats_edges_virtual=stats["edges_virtual"],
        node_legend_html=node_legend_html,
        edge_legend_html=edge_legend_html,
        cytoscape_src=escape_html(cytoscape_src),
        elements_json=elements_json,
        debug_payload_json=debug_payload_json,
        outcomes_json=outcomes_json,
        show_labels_js=show_labels_js,
        prolog_service_url_json=prolog_service_url_json,
        node_color_node=NODE_COLORS["node"],
        node_color_init=NODE_COLORS["init"],
        node_color_goal=NODE_COLORS["goal"],
        node_color_goal_reached=NODE_COLORS["goal_reached"],
    )


def main():
    """
    Run the command-line entry point.

    Returns
    -------
    Any
        Result returned by `main`.
    """
    parser = argparse.ArgumentParser(
        description="Interactive visualization for GRAPH debug logs (Cytoscape.js)."
    )
    parser.add_argument("input", help="Log file that includes GRAPH lines.")
    parser.add_argument("--output", default="planner_graph.html", help="Output HTML path.")
    parser.add_argument("--layout", choices=["depth", "spring"], default="depth")
    parser.add_argument("--labels", choices=["none", "key", "short"], default="key")
    parser.add_argument(
        "--edge-outcomes",
        default="all",
        help="Comma-separated outcomes to show (or 'all').",
    )
    parser.add_argument("--no-labels", action="store_true", help="Hide node labels.")
    parser.add_argument("--export-csv", action="store_true", help="Export nodes/edges CSV.")
    parser.add_argument(
        "--cytoscape-js",
        default="",
        help="Path or URL to cytoscape.min.js (defaults to CDN).",
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use Cytoscape.js from CDN (default if --cytoscape-js is not set).",
    )
    parser.add_argument(
        "--prolog-service-url",
        default="",
        help="Optional URL for Prolog explain endpoint (e.g. http://127.0.0.1:8765/explain).",
    )

    args = parser.parse_args()

    parsed = parse_graph_log(args.input)
    graph = build_graph(parsed)

    if args.layout == "spring":
        positions = layout_spring(graph)
        positions = scale_positions(positions, scale=280.0)
    else:
        positions = layout_by_depth(graph, parsed["depths"])
        positions = scale_positions(positions, scale=220.0)

    elements, label_map, stats, visible_outcomes = build_elements(
        parsed,
        graph,
        positions,
        label_mode=args.labels,
        show_labels=not args.no_labels,
        edge_outcomes=args.edge_outcomes,
    )
    debug_payload = build_debug_payload(parsed, graph, label_map)

    cytoscape_src = DEFAULT_CYTOSCAPE_JS
    if args.cytoscape_js and not args.cdn:
        cytoscape_src = args.cytoscape_js

    html = render_html(
        title="High-Level Planner Search Graph",
        elements=elements,
        debug_payload=debug_payload,
        stats=stats,
        show_labels=not args.no_labels,
        visible_outcomes=visible_outcomes,
        cytoscape_src=cytoscape_src,
        plan_steps=parsed.get("plan_steps", []),
        prolog_service_url=args.prolog_service_url,
    )

    with open(args.output, "w") as handle:
        handle.write(html)

    print(f"Wrote {args.output}")
    print(f"Nodes: {graph.number_of_nodes()} | Edges shown: {stats['edges_visible']} | Edges logged: {stats['edges_total']}")
    print(f"Init: {stats['init']} | Goal: {stats['goal']} | Goal reached: {stats['goal_reached']}")

    if args.export_csv:
        nodes_path, edges_path = export_csv(parsed, graph, label_map, args.output.replace(".html", ""))
        print(f"CSV: {nodes_path}")
        print(f"CSV: {edges_path}")


if __name__ == "__main__":
    main()
