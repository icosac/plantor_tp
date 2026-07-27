import os
import html
import re
import shlex
import subprocess
import sys
import threading
import uuid
from typing import Any, Dict, Iterable, Optional

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from . import PLANTOR_PATH, PUBLIC_PATH

IMPORT_ERROR: Optional[Exception] = None
BACKEND_IMPL: Optional[str] = None
llm_gen_module = None

try:
    import KMS.LLM.llm_gen as llm_gen_module
    from KMS.LLM.llm_gen import (
        hl_llm_multi_step,
        ll_llm_multi_step,
        llm_scenario_comprehension,
        write_to_file,
    )

    BACKEND_IMPL = "KMS.LLM.llm_gen"
except Exception as old_err:
    IMPORT_ERROR = RuntimeError(
        "Could not import backend generation functions from "
        "`KMS.LLM.llm_gen`."
    )
    IMPORT_ERROR.__cause__ = Exception(f"old_err={old_err}")

MOCK = False
LLM_CONF_DIR = os.path.join(PLANTOR_PATH, "KMS", "LLM", "conf")
PROLOG_PLANNER_PATH = os.path.join(PLANTOR_PATH, "TP", "prolog_planner")
PROLOG_PLANNER_SRC_PATH = os.path.join(PROLOG_PLANNER_PATH, "src")
HL_GRAPH_VIZ_SCRIPT_PATH = os.path.join(PROLOG_PLANNER_PATH, "tools", "hl_graph_viz.py")
PO_VIZ_SCRIPT_PATH = os.path.join(PROLOG_PLANNER_PATH, "tools", "po_viz.py")
TP_PLANNER_SCRIPT_PATH = os.path.join(PLANTOR_PATH, "TP", "planner.py")
ACTIVE_PLANNER_LOCK = threading.Lock()
ACTIVE_PLANNER_PROCESS: Optional[subprocess.Popen] = None
ACTIVE_PLANNER_RUN_ID: Optional[str] = None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get_first(data: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        if key in data and data.get(key) is not None:
            return _clean_text(data.get(key))
    return ""


def _get_non_negative_int(data: Dict[str, Any], keys: Iterable[str], default: int = 0) -> int:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            value_int = int(value)
            return value_int if value_int >= 0 else default
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "y", "on"}:
                return 1
            if normalized in {"false", "no", "n", "off"}:
                return 0
            try:
                value_int = int(normalized)
                return value_int if value_int >= 0 else default
            except ValueError:
                continue
    return default


def _get_int_in_range(
    data: Dict[str, Any],
    keys: Iterable[str],
    default: int,
    min_value: int,
    max_value: Optional[int] = None,
) -> int:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, bool):
            continue
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if parsed < min_value:
            return default
        if max_value is not None and parsed > max_value:
            return default
        return parsed
    return default


def _run_interruptible_planner(
    planner_cmd: list[str],
    run_id: str,
    timeout_s: int,
) -> subprocess.CompletedProcess:
    global ACTIVE_PLANNER_PROCESS, ACTIVE_PLANNER_RUN_ID

    with ACTIVE_PLANNER_LOCK:
        if ACTIVE_PLANNER_PROCESS is not None and ACTIVE_PLANNER_PROCESS.poll() is None:
            raise RuntimeError("A planner search is already running. Stop it or wait for it to finish.")

        process = subprocess.Popen(
            planner_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ACTIVE_PLANNER_PROCESS = process
        ACTIVE_PLANNER_RUN_ID = run_id

    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        return subprocess.CompletedProcess(
            planner_cmd,
            process.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            planner_cmd,
            timeout_s,
            output=stdout,
            stderr=stderr,
        )
    finally:
        with ACTIVE_PLANNER_LOCK:
            if ACTIVE_PLANNER_PROCESS is process:
                ACTIVE_PLANNER_PROCESS = None
                ACTIVE_PLANNER_RUN_ID = None


def _list_llm_configs() -> list[str]:
    if not os.path.isdir(LLM_CONF_DIR):
        return []
    return sorted(
        name
        for name in os.listdir(LLM_CONF_DIR)
        if name.endswith(".yaml") and os.path.isfile(os.path.join(LLM_CONF_DIR, name))
    )


def _prolog_quote(path: str) -> str:
    return path.replace("\\", "/").replace("'", "\\'")


def _set_llm_config(selected_config: str) -> Optional[str]:
    if not selected_config:
        return None
    if BACKEND_IMPL != "KMS.LLM.llm_gen" or llm_gen_module is None:
        return "Dynamic LLM selection is not available for current backend."

    cfg_name = os.path.basename(selected_config)
    cfg_path = os.path.join(LLM_CONF_DIR, cfg_name)
    if not os.path.isfile(cfg_path):
        return f"LLM config '{cfg_name}' not found in {LLM_CONF_DIR}."

    llm_gen_module.LLM_CONF_PATH = cfg_path
    current_app.logger.info("[llm] Selected LLM config: %s", cfg_path)
    return None


def validate_descriptions(high_level, low_level):
    """Validate compatibility of high-level and low-level descriptions."""

    current_app.logger.info("Calling validate_descriptions")
    comp, resp = llm_scenario_comprehension(high_level, low_level)
    if comp:
        return {"isValid": True}
    else:
        return {"isValid": False, "error": resp}


def generate_high_level_kb(high_level, verify=0):
    """Generate the high-level knowledge base."""
    hl_d = hl_llm_multi_step(high_level, verify=verify)
    current_app.logger.info(f"[generate_high_level_kb] constructed\n{hl_d}")

    return hl_d


def generate_low_level_kb(low_level_desc, hl_kb, verify=0):
    """Generate the low-level knowledge base."""
    ll_d = ll_llm_multi_step(low_level_desc, hl_kb, verify=verify)
    if isinstance(ll_d, dict) and "actions" in ll_d and "ll_actions" not in ll_d:
        ll_d["ll_actions"] = ll_d["actions"]
    current_app.logger.info(f"[generate_low_level_kb] constructed\n{ll_d}")

    return ll_d


def generate_behavior_tree(kb):
    """Generate the behavior tree (BT) in XML format."""
    bt_xml_path = os.path.join(PUBLIC_PATH, "bt.xml")
    bt_html_path = os.path.join(PUBLIC_PATH, "BT.html")
    current_app.logger.info(f"[generate_behavior_tree] generating BT XML file at {bt_xml_path}")

    ll_kb_path = os.path.join(PUBLIC_PATH, "ll_kb.pl")
    write_to_file(kb, ll_kb_path)

    if os.path.exists(bt_xml_path):
        os.remove(bt_xml_path)

    planner_path = os.path.join(PLANTOR_PATH, "python_interface", "planner.py")
    if not os.path.exists(planner_path):
        current_app.logger.error(
            "[generate_behavior_tree] planner not found at %s. "
            "BT generation is unavailable with the current backend setup.",
            planner_path,
        )
        return {"bt_error": f"Planner not found at {planner_path}"}

    result = subprocess.run(
        ["python3", planner_path, "-x", bt_xml_path, "-H", bt_html_path, "-i", ll_kb_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        current_app.logger.error(
            "[generate_behavior_tree] planner failed with code %s. stderr: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return {"bt_error": "Error generating the behavior tree with planner.py."}

    if os.path.exists(bt_xml_path):
        with open(bt_xml_path, "r") as f:
            xml = f.read()
    else:
        current_app.logger.error(
            "[generate_behavior_tree] Error generating the behavior tree because file was not "
            "found at %s.",
            bt_xml_path,
        )
        return {"bt_error": "Error generating the behavior tree because file was not found."}

    if xml.strip() in ["init", ""]:
        return {"bt_error": "Error generating the behavior tree because file was not found."}

    return {"behavior_tree": xml}


def _extract_hl_plan_steps(log_output: str) -> list[str]:
    steps: list[str] = []
    collecting = False

    for line in log_output.splitlines():
        if line.startswith("[planner] Plan found"):
            collecting = True
            continue

        if not collecting:
            continue

        if line.startswith("[planner] LL Plan"):
            break

        stripped = line.strip()
        if not stripped:
            if steps:
                break
            continue

        if line.startswith("\t"):
            steps.append(stripped.rstrip("."))
            continue

        if steps:
            break

    return steps


def _extract_ll_plan_steps(log_output: str) -> list[str]:
    steps: list[str] = []
    collecting = False

    for line in log_output.splitlines():
        if line.startswith("[planner] LL Plan"):
            collecting = True
            # The first LL step can be printed on the same line as the section header.
            _, _, remainder = line.partition(":")
            inline_step = remainder.strip()
            if inline_step:
                steps.append(inline_step.rstrip("."))
            continue

        if not collecting:
            continue

        if line.startswith("[planner] "):
            break

        stripped = line.strip()
        if not stripped:
            if steps:
                break
            continue

        if line.startswith("\t"):
            steps.append(stripped.rstrip("."))
            continue

        # Be tolerant of logs where indentation uses spaces instead of tabs.
        if line.startswith(" "):
            steps.append(stripped.rstrip("."))
            continue

        if steps:
            break

    return steps


def _extract_enabler_terms(log_output: str) -> list[str]:
    terms: list[str] = []
    collecting = False

    for line in log_output.splitlines():
        if line.startswith("[planner] Enablers"):
            collecting = True
            # First enabler can be present on the same line as the section header.
            _, _, remainder = line.partition(":")
            inline_term = remainder.strip()
            if inline_term:
                terms.append(inline_term.rstrip("."))
            continue

        if not collecting:
            continue

        if line.startswith("[planner] ") or line.startswith("[enablers] "):
            break

        stripped = line.strip()
        if not stripped:
            if terms:
                break
            continue

        if line.startswith("\t") or line.startswith(" "):
            terms.append(stripped.rstrip("."))
            continue

        if terms:
            break

    return terms


def _extract_plan_with_enablers(log_output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    collecting = False
    line_pattern = re.compile(r"^\s*(\d+)\s*-\s*(.*?)\s*<=\s*\[(.*?)\]\s*$")

    for line in log_output.splitlines():
        if line.startswith("[enablers] Plan actions with enablers"):
            collecting = True
            continue

        if not collecting:
            continue

        if line.startswith("["):
            break

        stripped = line.strip()
        if not stripped:
            if rows:
                break
            continue

        match = line_pattern.match(line)
        if not match:
            continue

        step_id = int(match.group(1))
        step_text = match.group(2).strip()
        incoming_raw = match.group(3).strip()
        incoming_ids: list[int] = []
        if incoming_raw:
            for part in incoming_raw.split(","):
                token = part.strip()
                if not token:
                    continue
                try:
                    incoming_ids.append(int(token))
                except ValueError:
                    continue

        rows.append(
            {
                "step_id": step_id,
                "step": step_text,
                "incoming_enablers": incoming_ids,
            }
        )

    rows.sort(key=lambda row: row.get("step_id", 0))
    return rows


def _build_fallback_plan_html(title: str, message: str, plan_log: str = "", viz_log: str = "") -> str:
    escaped_title = html.escape(title or "Planner Debug View")
    escaped_message = html.escape(message or "No additional details available.")
    escaped_plan_log = html.escape(plan_log or "(empty)")
    escaped_viz_log = html.escape(viz_log or "")

    viz_block = ""
    if viz_log:
        viz_block = (
            "<h2>Visualizer Output</h2>"
            f"<pre>{escaped_viz_log}</pre>"
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escaped_title}</title>
    <style>
      body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; margin: 0; padding: 24px; background: #f8f9fb; color: #222; }}
      h1 {{ margin: 0 0 12px; font-size: 20px; }}
      h2 {{ margin: 24px 0 8px; font-size: 16px; }}
      .card {{ background: #fff; border: 1px solid #d8dee6; border-radius: 8px; padding: 14px; }}
      .warn {{ background: #fff7e6; border: 1px solid #f0c36d; border-radius: 8px; padding: 10px; margin-bottom: 12px; white-space: pre-wrap; }}
      pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; max-height: 70vh; overflow: auto; }}
    </style>
  </head>
  <body>
    <h1>{escaped_title}</h1>
    <div class="warn">{escaped_message}</div>
    <div class="card">
      <h2>Planner Log</h2>
      <pre>{escaped_plan_log}</pre>
      {viz_block}
    </div>
  </body>
</html>
"""


def generate_high_level_plan_visualization(
    kb,
    max_depth: int = 10,
    timeout_s: int = 180,
    enable_graph_debug: bool = False,
):
    """Run the high-level total-order planner and build the HTML graph visualization."""
    run_id = uuid.uuid4().hex[:10]
    kb_file = os.path.join(PUBLIC_PATH, f"hl_plan_input_{run_id}.pl")
    log_file = os.path.join(PUBLIC_PATH, f"hl_plan_log_{run_id}.txt")
    html_file = os.path.join(PUBLIC_PATH, f"hl_plan_graph_{run_id}.html")
    enablers_html_file = os.path.join(PUBLIC_PATH, f"hl_plan_enablers_{run_id}.html")
    cmd_file = os.path.join(PUBLIC_PATH, f"hl_plan_command_{run_id}.txt")

    plan_warning_messages: list[str] = []
    plan_log = ""
    html_content = ""
    enablers_html_content = ""

    required_files = {
        "bfs_planner.pl": os.path.join(PROLOG_PLANNER_SRC_PATH, "bfs_planner.pl"),
        "mappings.pl": os.path.join(PROLOG_PLANNER_SRC_PATH, "mappings.pl"),
        "enablers.pl": os.path.join(PROLOG_PLANNER_SRC_PATH, "enablers.pl"),
    }

    missing_required = []
    for name, path in required_files.items():
        if not os.path.isfile(path):
            missing_required.append(f"{name} ({path})")
    if missing_required:
        plan_warning_messages.append(
            "Planner prerequisites are missing:\n- " + "\n- ".join(missing_required)
        )

    write_to_file(kb, kb_file)

    # kb_file = '/app/GUI/backend/app/../../frontend/public_generated/hl_plan_input_91bc7cdcc7.pl'

    goal_parts = [
        "style_check(-singleton)",
        "style_check(-discontiguous)",
        "set_prolog_flag(verbose, silent)",
        f"['{_prolog_quote(kb_file)}']",
        f"['{_prolog_quote(required_files['bfs_planner.pl'])}']",
        f"['{_prolog_quote(required_files['mappings.pl'])}']",
        f"['{_prolog_quote(required_files['enablers.pl'])}']",
    ]
    if enable_graph_debug:
        goal_parts.append("enable_graph_debug")
    goal_parts.extend(
        [
            "format('[planner] Starting BFS planner\\n')",
            f"call_time(bfs_planner({max_depth}, Plan), Time)",
            (
                "(Plan \\= [] -> "
                "(format('[planner] Plan found in ~w\\n', [Time]), "
                "print_list(Plan, true), "
                "init_state(Init), "
                "(catch(apply_mappings(Init, Plan, LL_Plan), MappingError, "
                "(format('[planner] Mapping error: ~w\\n', [MappingError]), fail)) -> "
                "(format('[planner] LL Plan:'), "
                "print_list(LL_Plan, true), "
                "extract_enablers(LL_Plan, Enablers), "
                "format('[planner] Enablers:'), "
                "print_list(Enablers, true), "
                "extract_start_end_links(LL_Plan, StartEndLinks), "
                "format('[planner] Start/end link terms:'), "
                "print_list(StartEndLinks, true), "
                "print_start_end_links(LL_Plan, StartEndLinks), "
                "print_plan_with_enablers(LL_Plan, Enablers), "
                "print_plan_durations(LL_Plan)); "
                "format('[planner] Mapping failed during apply_mappings\\n'))); "
                "format('[planner] No plan found\\n'))"
            ),
        ]
    )

    planner_cmd = [
        "swipl",
        "--stack_limit=10G",
        "-q",
        "-g",
        ", ".join(goal_parts),
        "-t",
        "halt",
    ]
    viz_cmd = [
        "python3",
        HL_GRAPH_VIZ_SCRIPT_PATH,
        log_file,
        "--output",
        html_file,
    ]
    po_viz_cmd = [
        "python3",
        PO_VIZ_SCRIPT_PATH,
        log_file,
        "--output",
        enablers_html_file,
    ]

    current_app.logger.info("[generate_high_level_plan_visualization] Running planner command.")
    planner_result = None
    viz_result = None
    enablers_viz_result = None
    if missing_required:
        plan_log = "Planner not executed due to missing required Prolog files."
    else:
        try:
            planner_result = _run_interruptible_planner(
                planner_cmd,
                run_id=run_id,
                timeout_s=timeout_s,
            )
            plan_log = ((planner_result.stdout or "") + "\n" + (planner_result.stderr or "")).strip()
            if planner_result.returncode is not None and planner_result.returncode < 0:
                plan_warning_messages.append("Planner search was stopped.")
                if not plan_log:
                    plan_log = "Planner search was stopped."
        except FileNotFoundError:
            plan_warning_messages.append("Could not run `swipl`: executable not found in PATH.")
            plan_log = "Planner executable `swipl` was not found."
        except subprocess.TimeoutExpired:
            plan_warning_messages.append(f"High-level planning timed out after {timeout_s} seconds.")
            plan_log = f"Planner timed out after {timeout_s} seconds."
        except RuntimeError as err:
            plan_warning_messages.append(str(err))
            plan_log = str(err)

    with open(log_file, "w", encoding="utf-8") as handle:
        handle.write(plan_log + ("\n" if plan_log else ""))
    planner_failed = planner_result is not None and planner_result.returncode != 0
    has_graph_debug_trace = "GRAPH " in plan_log

    mapping_failed = (
        "[planner] Mapping failed during apply_mappings" in plan_log
        or "[planner] Mapping error:" in plan_log
    )
    plan_found = "[planner] Plan found" in plan_log and not mapping_failed

    viz_log = ""
    viz_failed = False
    if enable_graph_debug and os.path.isfile(HL_GRAPH_VIZ_SCRIPT_PATH):
        try:
            viz_result = subprocess.run(
                viz_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if viz_result.returncode != 0:
                viz_failed = True
                viz_log = ((viz_result.stdout or "") + "\n" + (viz_result.stderr or "")).strip()
                current_app.logger.error(
                    "[generate_high_level_plan_visualization] Visualization failed with code %s. log: %s",
                    viz_result.returncode,
                    viz_log,
                )
                plan_warning_messages.append(
                    "Graph visualizer failed. Showing fallback debug page."
                )
        except FileNotFoundError:
            viz_failed = True
            plan_warning_messages.append("Could not run `python3`: executable not found in PATH.")
            viz_log = "Python executable was not found while running visualizer."
        except subprocess.TimeoutExpired:
            viz_failed = True
            plan_warning_messages.append("Visualization generation timed out after 120 seconds.")
            viz_log = "Visualizer timed out after 120 seconds."
    elif enable_graph_debug:
        viz_failed = True
        plan_warning_messages.append(f"Visualizer script not found at {HL_GRAPH_VIZ_SCRIPT_PATH}.")
        viz_log = "Visualizer script is missing."

    enablers_viz_log = ""
    enablers_viz_failed = False
    if plan_found and os.path.isfile(PO_VIZ_SCRIPT_PATH):
        try:
            enablers_viz_result = subprocess.run(
                po_viz_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if enablers_viz_result.returncode != 0:
                enablers_viz_failed = True
                enablers_viz_log = (
                    (enablers_viz_result.stdout or "") + "\n" + (enablers_viz_result.stderr or "")
                ).strip()
                current_app.logger.error(
                    "[generate_high_level_plan_visualization] Enablers visualization failed with code %s. log: %s",
                    enablers_viz_result.returncode,
                    enablers_viz_log,
                )
                plan_warning_messages.append(
                    "Enablers visualizer failed. Showing fallback debug page."
                )
        except FileNotFoundError:
            enablers_viz_failed = True
            plan_warning_messages.append("Could not run `python3`: executable not found in PATH.")
            enablers_viz_log = "Python executable was not found while running enablers visualizer."
        except subprocess.TimeoutExpired:
            enablers_viz_failed = True
            plan_warning_messages.append("Enablers visualization generation timed out after 120 seconds.")
            enablers_viz_log = "Enablers visualizer timed out after 120 seconds."
    elif plan_found:
        enablers_viz_failed = True
        plan_warning_messages.append(f"Enablers visualizer script not found at {PO_VIZ_SCRIPT_PATH}.")
        enablers_viz_log = "Enablers visualizer script is missing."

    if enable_graph_debug and not viz_failed and os.path.isfile(html_file):
        with open(html_file, "r", encoding="utf-8") as handle:
            html_content = handle.read()
    elif enable_graph_debug:
        fallback_message = "\n".join(plan_warning_messages) or "Visualization could not be generated."
        html_content = _build_fallback_plan_html(
            "High-Level Planner Debug View",
            fallback_message,
            plan_log=plan_log,
            viz_log=viz_log,
        )
        with open(html_file, "w", encoding="utf-8") as handle:
            handle.write(html_content)

    if plan_found and not enablers_viz_failed and os.path.isfile(enablers_html_file):
        with open(enablers_html_file, "r", encoding="utf-8") as handle:
            enablers_html_content = handle.read()
    elif plan_found:
        enablers_fallback_message = "Could not generate enablers visualization."
        if enablers_viz_log:
            enablers_fallback_message += "\n" + enablers_viz_log
        enablers_html_content = _build_fallback_plan_html(
            "Enablers Debug View",
            enablers_fallback_message,
            plan_log=plan_log,
            viz_log=enablers_viz_log,
        )
        with open(enablers_html_file, "w", encoding="utf-8") as handle:
            handle.write(enablers_html_content)

    if planner_failed:
        current_app.logger.warning(
            "[generate_high_level_plan_visualization] Planner exited with code %s but visualization was generated.",
            planner_result.returncode,
        )
        if has_graph_debug_trace:
            plan_warning_messages.append(
                f"Planner exited with non-zero status ({planner_result.returncode}), but debug graph trace was captured."
            )
        else:
            plan_warning_messages.append(
                f"Planner exited with non-zero status ({planner_result.returncode}) and no GRAPH trace was found."
            )

    result = {
        "plan_found": plan_found,
        "mapping_failed": mapping_failed,
        "search_debug_enabled": enable_graph_debug,
        "plan_steps": _extract_hl_plan_steps(plan_log),
        "ll_plan_steps": _extract_ll_plan_steps(plan_log),
        "enabler_terms": _extract_enabler_terms(plan_log),
        "plan_with_enablers": _extract_plan_with_enablers(plan_log),
        "plan_log": plan_log,
        "visualization_html": html_content,
        "visualization_run_id": run_id,
        "visualization_url": f"/api/hl_plan_viz/{run_id}",
        "enablers_visualization_html": enablers_html_content,
        "enablers_visualization_url": f"/api/hl_plan_enablers_viz/{run_id}",
    }
    if not result["plan_found"] and not mapping_failed:
        plan_warning_messages.append(
            "No plan found. Visualization is still available for debugging."
        )
    if mapping_failed:
        plan_warning_messages.append("Problem in applying the mappings.")
    if plan_warning_messages:
        result["plan_warning"] = "\n".join(plan_warning_messages)

    command_log_lines = [
        f"run_id: {run_id}",
        f"kb_file: {kb_file}",
        f"plan_log_file: {log_file}",
        f"visualization_html_file: {html_file}",
        f"enablers_visualization_html_file: {enablers_html_file}",
        f"max_depth: {max_depth}",
        f"timeout_seconds: {timeout_s}",
        f"enable_graph_debug: {enable_graph_debug}",
        "",
        "planner_command:",
        shlex.join(planner_cmd),
        "",
        "visualizer_command:",
        shlex.join(viz_cmd),
        "",
        "enablers_visualizer_command:",
        shlex.join(po_viz_cmd),
        "",
        f"planner_return_code: {planner_result.returncode if planner_result is not None else 'not_executed'}",
        f"visualizer_return_code: {viz_result.returncode if viz_result is not None else 'not_executed'}",
        f"enablers_visualizer_return_code: {enablers_viz_result.returncode if enablers_viz_result is not None else 'not_executed'}",
    ]
    with open(cmd_file, "w", encoding="utf-8") as handle:
        handle.write("\n".join(command_log_lines) + "\n")

    result["command_log_file"] = cmd_file
    result["command_log_url"] = f"/api/hl_plan_command/{run_id}"
    return result


def generate_optimized_stn_visualization(plan_log: str):
    """Generate the optimized STN HTML visualization from a planner log."""
    run_id = uuid.uuid4().hex[:10]
    planner_log_file = os.path.join(PUBLIC_PATH, f"optimized_stn_plan_log_{run_id}.txt")
    optimized_html_file = os.path.join(PUBLIC_PATH, f"optimized_stn_{run_id}.html")
    optimized_graph_html_file = os.path.join(PUBLIC_PATH, f"optimized_stn_execution_graph_{run_id}.html")
    full_log_file = os.path.join(PUBLIC_PATH, f"optimized_stn_full_log_{run_id}.txt")
    cmd_file = os.path.join(PUBLIC_PATH, f"optimized_stn_command_{run_id}.txt")

    with open(planner_log_file, "w", encoding="utf-8") as handle:
        handle.write(plan_log + ("\n" if plan_log else ""))

    stn_warning_messages: list[str] = []
    planner_output = ""
    planner_result = None
    planner_cmd = []

    if not os.path.isfile(TP_PLANNER_SCRIPT_PATH):
        stn_warning_messages.append(f"TP planner script not found at {TP_PLANNER_SCRIPT_PATH}.")
    else:
        planner_cmd = [
            sys.executable,
            TP_PLANNER_SCRIPT_PATH,
            "--from-prolog-log",
            planner_log_file,
            "--optimize-stn",
            "--optimize-objective",
            "end_time",
            "--no-po-html",
            "--no-stn-html",
            "--opt-stn-html",
            optimized_html_file,
            "--opt-stn-graph-html",
            optimized_graph_html_file,
        ]

        try:
            planner_result = subprocess.run(
                planner_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            planner_output = ((planner_result.stdout or "") + "\n" + (planner_result.stderr or "")).strip()
            if planner_result.returncode != 0:
                stn_warning_messages.append(
                    f"Optimized STN generation failed with code {planner_result.returncode}."
                )
        except FileNotFoundError:
            stn_warning_messages.append(f"Could not run `{sys.executable}`: executable not found.")
            planner_output = "Python executable was not found while running TP planner."
        except subprocess.TimeoutExpired:
            stn_warning_messages.append("Optimized STN generation timed out after 180 seconds.")
            planner_output = "TP planner timed out after 180 seconds."


    command_log_lines = [
        f"run_id: {run_id}",
        f"planner_log_file: {planner_log_file}",
        f"optimized_stn_html_file: {optimized_html_file}",
        f"optimized_stn_execution_graph_html_file: {optimized_graph_html_file}",
        "",
        "tp_planner_command:",
        shlex.join(planner_cmd) if planner_cmd else "not_executed",
        "",
        f"tp_planner_return_code: {planner_result.returncode if planner_result is not None else 'not_executed'}",
    ]
    with open(cmd_file, "w", encoding="utf-8") as handle:
        handle.write("\n".join(command_log_lines) + "\n")

    with open(full_log_file, "w", encoding="utf-8") as handle:
        handle.write(planner_output + ("\n" if planner_output else ""))

    optimized_html_content = ""
    if os.path.isfile(optimized_html_file):
        with open(optimized_html_file, "r", encoding="utf-8") as handle:
            optimized_html_content = handle.read()

    if not optimized_html_content.strip():
        fallback_message = "\n".join(stn_warning_messages) or "Optimized STN visualization could not be generated."
        optimized_html_content = _build_fallback_plan_html(
            "Optimized STN Debug View",
            fallback_message,
            plan_log=plan_log,
            viz_log=planner_output,
        )
        with open(optimized_html_file, "w", encoding="utf-8") as handle:
            handle.write(optimized_html_content)

    optimized_graph_html_content = ""
    if os.path.isfile(optimized_graph_html_file):
        with open(optimized_graph_html_file, "r", encoding="utf-8") as handle:
            optimized_graph_html_content = handle.read()

    result = {
        "optimized_stn_generated": planner_result is not None and planner_result.returncode == 0,
        "optimized_stn_html": optimized_html_content,
        "optimized_stn_url": f"/api/optimized_stn_viz/{run_id}",
        "optimized_stn_execution_graph_html": optimized_graph_html_content,
        "optimized_stn_execution_graph_url": f"/api/optimized_stn_execution_graph_viz/{run_id}",
        "optimized_stn_log": planner_output,
        "optimized_stn_run_id": run_id,
        "command_log_file": cmd_file,
        "command_log_url": f"/api/optimized_stn_command/{run_id}",
    }
    if stn_warning_messages:
        result["optimized_stn_warning"] = "\n".join(stn_warning_messages)
    return result


def generate_optimized_bt_visualization(plan_log: str):
    """Generate behavior-tree XML and HTML from an optimized STN replay."""
    run_id = uuid.uuid4().hex[:10]
    planner_log_file = os.path.join(PUBLIC_PATH, f"optimized_bt_plan_log_{run_id}.txt")
    bt_xml_file = os.path.join(PUBLIC_PATH, f"bt_{run_id}.xml")
    bt_html_file = os.path.join(PUBLIC_PATH, f"bt_viz_{run_id}.html")
    full_log_file = os.path.join(PUBLIC_PATH, f"optimized_bt_full_log_{run_id}.txt")
    cmd_file = os.path.join(PUBLIC_PATH, f"optimized_bt_command_{run_id}.txt")

    with open(planner_log_file, "w", encoding="utf-8") as handle:
        handle.write(plan_log + ("\n" if plan_log else ""))

    bt_warning_messages: list[str] = []
    planner_output = ""
    planner_result = None
    planner_cmd = []

    if not os.path.isfile(TP_PLANNER_SCRIPT_PATH):
        bt_warning_messages.append(f"TP planner script not found at {TP_PLANNER_SCRIPT_PATH}.")
    else:
        planner_cmd = [
            sys.executable,
            TP_PLANNER_SCRIPT_PATH,
            "--from-prolog-log",
            planner_log_file,
            "--optimize-stn",
            "--optimize-objective",
            "end_time",
            "--no-po-html",
            "--no-stn-html",
            "--no-opt-stn-html",
            "--bt-xml",
            bt_xml_file,
            "--bt-save-viz",
            bt_html_file,
        ]

        try:
            planner_result = subprocess.run(
                planner_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            planner_output = ((planner_result.stdout or "") + "\n" + (planner_result.stderr or "")).strip()
            if planner_result.returncode != 0:
                bt_warning_messages.append(
                    f"Behavior tree extraction failed with code {planner_result.returncode}."
                )
        except FileNotFoundError:
            bt_warning_messages.append(f"Could not run `{sys.executable}`: executable not found.")
            planner_output = "Python executable was not found while running TP planner."
        except subprocess.TimeoutExpired:
            bt_warning_messages.append("Behavior tree extraction timed out after 180 seconds.")
            planner_output = "TP planner timed out after 180 seconds."

    command_log_lines = [
        f"run_id: {run_id}",
        f"planner_log_file: {planner_log_file}",
        f"bt_xml_file: {bt_xml_file}",
        f"bt_html_file: {bt_html_file}",
        "",
        "tp_planner_command:",
        shlex.join(planner_cmd) if planner_cmd else "not_executed",
        "",
        f"tp_planner_return_code: {planner_result.returncode if planner_result is not None else 'not_executed'}",
    ]
    with open(cmd_file, "w", encoding="utf-8") as handle:
        handle.write("\n".join(command_log_lines) + "\n")

    with open(full_log_file, "w", encoding="utf-8") as handle:
        handle.write(planner_output + ("\n" if planner_output else ""))

    bt_html_content = ""
    if os.path.isfile(bt_html_file):
        with open(bt_html_file, "r", encoding="utf-8") as handle:
            bt_html_content = handle.read()

    if not bt_html_content.strip():
        fallback_message = "\n".join(bt_warning_messages) or "Behavior tree visualization could not be generated."
        bt_html_content = _build_fallback_plan_html(
            "Behavior Tree Debug View",
            fallback_message,
            plan_log=plan_log,
            viz_log=planner_output,
        )
        with open(bt_html_file, "w", encoding="utf-8") as handle:
            handle.write(bt_html_content)

    bt_xml_content = ""
    if os.path.isfile(bt_xml_file):
        with open(bt_xml_file, "r", encoding="utf-8") as handle:
            bt_xml_content = handle.read()

    result = {
        "bt_generated": (
            planner_result is not None
            and planner_result.returncode == 0
            and bool(bt_xml_content.strip())
        ),
        "bt_html": bt_html_content,
        "bt_xml": bt_xml_content,
        "bt_url": f"/api/optimized_bt_viz/{run_id}",
        "bt_xml_url": f"/api/optimized_bt_xml/{run_id}",
        "bt_log": planner_output,
        "bt_run_id": run_id,
        "command_log_file": cmd_file,
        "command_log_url": f"/api/optimized_bt_command/{run_id}",
    }
    if bt_warning_messages:
        result["bt_warning"] = "\n".join(bt_warning_messages)
    return result


app_routes = Blueprint('app_routes', __name__)


@app_routes.route('/api/llm_configs', methods=['GET'])
def get_llm_configs():
    """List available LLM config files for dropdown selection."""
    configs = _list_llm_configs()
    selected = ""
    if llm_gen_module is not None:
        selected = os.path.basename(getattr(llm_gen_module, "LLM_CONF_PATH", "") or "")
    return jsonify({"configs": configs, "selected": selected})


@app_routes.route('/api/validate', methods=['POST'])
def validate():
    """Validate compatibility of high-level and low-level descriptions."""
    current_app.logger.info(f"[validate] received {request}")
    current_app.logger.info(f"[validate] backend implementation: {BACKEND_IMPL}")
    if MOCK:
        return jsonify({"isValid": True})

    data = request.get_json(silent=True) or {}
    high_level = _get_first(data, ["highLevel", "high_level", "hl_description", "description"])
    low_level = _get_first(data, ["lowLevel", "low_level", "ll_description"])
    selected_llm = _get_first(data, ["llmConfig", "llm_config", "llm"])

    current_app.logger.info(f"[validate] received\n{high_level}\n{low_level}")

    if not high_level or not low_level:
        return jsonify({"error": "Both fields 'highLevel' and 'lowLevel' are required."}), 400

    llm_error = _set_llm_config(selected_llm)
    if llm_error:
        return jsonify({"error": llm_error}), 400

    try:
        validation_result = validate_descriptions(high_level, low_level)
    except Exception as err:
        current_app.logger.exception("[validate] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    return jsonify(validation_result)

    # if validation_result['valid']:
    #     return jsonify({"isValid": True})
    # else:
    #     return jsonify({"isValid": False, "error": validation_result['error']}), 400

@app_routes.route('/api/generate_hl_kb', methods=['POST'])
def generate_hl_kb():
    """Generate the high-level knowledge base."""
    if MOCK:
        return jsonify({
            "kb": "This is the generated hl knowledge base",
            "init": "This is the generated hl initial state",
            "goal": "This is the generated hl goal state",
            "actions": "These are the generated hl actions"
        })

    data = request.get_json(silent=True) or {}
    high_level = _get_first(data, ["description", "highLevel", "high_level", "hl_description"])
    selected_llm = _get_first(data, ["llmConfig", "llm_config", "llm"])
    verify_hl = _get_non_negative_int(
        data,
        ["verify", "verifyHl", "verify_hl", "verifyRetries", "verify_retries", "verifyKb", "verify_kb"],
        default=0,
    )

    if not high_level:
        return jsonify({"error": "Field 'description' is required."}), 400

    llm_error = _set_llm_config(selected_llm)
    if llm_error:
        return jsonify({"error": llm_error}), 400

    try:
        hl_kb = generate_high_level_kb(high_level, verify=verify_hl)
    except Exception as err:
        current_app.logger.exception("[generate_hl_kb] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(hl_kb, dict):
        return jsonify({"error": f"Expected dict, got {type(hl_kb)}"}), 500

    return jsonify(hl_kb)

@app_routes.route('/api/generate_ll_kb', methods=['POST'])
def generate_ll_kb():
    """Generate the low-level knowledge base."""
    if MOCK:
        return jsonify({
            'kb': "ll_kb_content",
            'init': "ll_init_content",
            'goal': "ll_goal_content",
            'actions': "ll_actions_content",
            'll_actions': "ll_actions_content",
            'mappings': "ll_mappings_content",
        })

    data = request.get_json(silent=True) or {}
    low_level_desc = _get_first(data, ["lowLevelDesc", "low_level_desc", "lowLevel", "low_level"])
    selected_llm = _get_first(data, ["llmConfig", "llm_config", "llm"])
    verify_ll = _get_non_negative_int(
        data,
        ["verify", "verifyLl", "verify_ll", "verifyRetries", "verify_retries", "verifyKb", "verify_kb"],
        default=0,
    )
    hl_kb_content = _get_first(data, ["hlkbContent", "hl_kb_content", "hlKB", "kb"])
    hl_init_content = _get_first(data, ["hlInitContent", "hl_init_content", "hlInit", "init"])
    hl_goal_content = _get_first(data, ["hlGoalContent", "hl_goal_content", "hlGoal", "goal"])
    hl_actions_content = _get_first(data, ["hlActionsContent", "hl_actions_content", "hlActions", "actions"])

    if not all([low_level_desc, hl_kb_content, hl_init_content, hl_goal_content, hl_actions_content]):
        return jsonify({
            "error": (
                "Required fields are missing. Expected low-level description and full HL KB "
                "(kb/init/goal/actions)."
            )
        }), 400

    llm_error = _set_llm_config(selected_llm)
    if llm_error:
        return jsonify({"error": llm_error}), 400

    hl_d = {
        'kb': hl_kb_content,
        'init': hl_init_content,
        'goal': hl_goal_content,
        'actions': hl_actions_content
    }

    try:
        ll_kb = generate_low_level_kb(low_level_desc, hl_d, verify=verify_ll)
    except Exception as err:
        current_app.logger.exception("[generate_ll_kb] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(ll_kb, dict):
        return jsonify({"error": f"Expected dict, got {type(ll_kb)}"}), 500

    return jsonify(ll_kb)

@app_routes.route('/api/generate_bt', methods=['POST'])
def generate_bt():
    """Generate the behavior tree (BT) in XML format."""
    if MOCK:
        return jsonify({"behavior_tree": "This is a BT"})

    current_app.logger.info(f"[generate_bt] received {request.json}")
    data = request.get_json(silent=True) or {}
    low_level_kb = _get_first(data, ["low_level_kb", "ll_kb", "kb"])
    low_level_init = _get_first(data, ["low_level_init", "ll_init", "init"])
    low_level_goal = _get_first(data, ["low_level_goal", "ll_goal", "goal"])
    low_level_actions = _get_first(data, ["low_level_actions", "ll_actions", "actions"])
    low_level_mappings = _get_first(data, ["low_level_mappings", "mappings"])

    if not low_level_kb or not low_level_init or not low_level_goal or not low_level_actions or not low_level_mappings:
        return jsonify({"error": "All fields `low-level_{kb,init,goal,actions,mappings}` are required."}), 400

    kb = {
        'kb': low_level_kb,
        'init': low_level_init,
        'goal': low_level_goal,
        'll_actions': low_level_actions,
        'mappings': low_level_mappings
    }

    try:
        bt_xml = generate_behavior_tree(kb)
    except Exception as err:
        current_app.logger.exception("[generate_bt] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(bt_xml, dict):
        return jsonify({"error": f"Expected dict, got {type(bt_xml)}"}), 500

    return jsonify(bt_xml)


@app_routes.route('/api/generate_hl_plan_viz', methods=['POST'])
def generate_hl_plan_viz():
    """Generate the high-level total-order plan and corresponding HTML visualization."""
    if MOCK:
        return jsonify({
            "plan_found": True,
            "plan_steps": ["start(sample_action)", "end(sample_action)"],
            "ll_plan_steps": ["0-start(sample_action)", "1-end(sample_action)"],
            "enabler_terms": ["enabler(0-start(sample_action),1-end(sample_action),assumption(mock))"],
            "plan_with_enablers": [
                {"step_id": 0, "step": "start(sample_action)", "incoming_enablers": []},
                {"step_id": 1, "step": "end(sample_action)", "incoming_enablers": [0]},
            ],
            "plan_log": "[planner] Plan found in 0.0",
            "visualization_html": "<html><body><h1>Mock HL Plan Visualization</h1></body></html>",
            "visualization_run_id": "0000000000",
            "visualization_url": "/api/hl_plan_viz/0000000000",
            "enablers_visualization_html": "<html><body><h1>Mock Enablers Visualization</h1></body></html>",
            "enablers_visualization_url": "/api/hl_plan_enablers_viz/0000000000",
        })

    data = request.get_json(silent=True) or {}
    hl_actions = _get_first(data, ["hl_actions", "high_level_actions", "actions"])
    low_level_kb = _get_first(data, ["low_level_kb", "ll_kb", "kb"])
    low_level_init = _get_first(data, ["low_level_init", "ll_init", "init"])
    low_level_goal = _get_first(data, ["low_level_goal", "ll_goal", "goal"])
    low_level_actions = _get_first(data, ["low_level_actions", "ll_actions", "actions_ll"])
    low_level_mappings = _get_first(data, ["low_level_mappings", "ll_mappings", "mappings"])
    max_depth = _get_int_in_range(data, ["max_depth", "maxDepth"], default=10, min_value=-1)
    timeout_s = _get_int_in_range(data, ["timeout_seconds", "timeoutSeconds", "timeout"], default=180, min_value=1)
    enable_graph_debug = bool(_get_non_negative_int(
        data,
        ["enable_graph_debug", "enableGraphDebug", "search_debug", "searchDebug"],
        default=0,
    ))

    if not all([hl_actions, low_level_kb, low_level_init, low_level_goal, low_level_actions, low_level_mappings]):
        return jsonify({
            "error": (
                "All fields are required: hl_actions, low_level_kb, low_level_init, "
                "low_level_goal, low_level_actions, low_level_mappings."
            )
        }), 400

    planner_input = {
        "actions": hl_actions,
        "kb": low_level_kb,
        "init": low_level_init,
        "goal": low_level_goal,
        "ll_actions": low_level_actions,
        "mappings": low_level_mappings,
    }

    try:
        result = generate_high_level_plan_visualization(
            planner_input,
            max_depth=max_depth,
            timeout_s=timeout_s,
            enable_graph_debug=enable_graph_debug,
        )
    except Exception as err:
        current_app.logger.exception("[generate_hl_plan_viz] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(result, dict):
        return jsonify({"error": f"Expected dict, got {type(result)}"}), 500

    return jsonify(result)


@app_routes.route('/api/stop_hl_plan', methods=['POST'])
def stop_hl_plan():
    """Stop the active high-level planner subprocess, if one is running."""
    with ACTIVE_PLANNER_LOCK:
        process = ACTIVE_PLANNER_PROCESS
        run_id = ACTIVE_PLANNER_RUN_ID

    if process is None or process.poll() is not None:
        return jsonify({
            "stopped": False,
            "message": "No planner search is currently running.",
        })

    process.terminate()
    try:
        process.wait(timeout=5)
        killed = False
    except subprocess.TimeoutExpired:
        process.kill()
        killed = True

    return jsonify({
        "stopped": True,
        "killed": killed,
        "run_id": run_id,
        "message": "Planner search stopped.",
    })


@app_routes.route('/api/generate_optimized_stn_viz', methods=['POST'])
def generate_optimized_stn_viz():
    """Generate optimized STN HTML from a high-level planning log."""
    if MOCK:
        return jsonify({
            "optimized_stn_generated": True,
            "optimized_stn_html": "<html><body><h1>Mock Optimized STN Visualization</h1></body></html>",
            "optimized_stn_url": "/api/optimized_stn_viz/0000000000",
            "optimized_stn_execution_graph_html": "<html><body><h1>Mock Optimized STN Execution Graph</h1></body></html>",
            "optimized_stn_execution_graph_url": "/api/optimized_stn_execution_graph_viz/0000000000",
            "optimized_stn_log": "[planner] Optimized STN generated.",
            "optimized_stn_run_id": "0000000000",
        })

    data = request.get_json(silent=True) or {}
    plan_log = _get_first(data, ["plan_log", "planner_log", "hl_plan_log"])

    if not plan_log:
        return jsonify({
            "error": "Field 'plan_log' is required. Run high-level planning before optimized STN generation."
        }), 400

    try:
        result = generate_optimized_stn_visualization(plan_log)
    except Exception as err:
        current_app.logger.exception("[generate_optimized_stn_viz] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(result, dict):
        return jsonify({"error": f"Expected dict, got {type(result)}"}), 500

    return jsonify(result)


@app_routes.route('/api/generate_optimized_bt', methods=['POST'])
def generate_optimized_bt():
    """Generate behavior-tree XML and HTML from the current planner log."""
    if MOCK:
        return jsonify({
            "bt_generated": True,
            "bt_html": "<html><body><h1>Mock Behavior Tree Visualization</h1></body></html>",
            "bt_xml": "<root BTCPP_format=\"4\"><BehaviorTree ID=\"mock\" /></root>",
            "bt_url": "/api/optimized_bt_viz/0000000000",
            "bt_xml_url": "/api/optimized_bt_xml/0000000000",
            "bt_log": "[planner] Behavior tree generated.",
            "bt_run_id": "0000000000",
        })

    data = request.get_json(silent=True) or {}
    plan_log = _get_first(data, ["plan_log", "planner_log", "hl_plan_log"])

    if not plan_log:
        return jsonify({
            "error": "Field 'plan_log' is required. Run high-level planning before BT extraction."
        }), 400

    try:
        result = generate_optimized_bt_visualization(plan_log)
    except Exception as err:
        current_app.logger.exception("[generate_optimized_bt] failed: %s", err)
        return jsonify({"error": str(err)}), 500

    if not isinstance(result, dict):
        return jsonify({"error": f"Expected dict, got {type(result)}"}), 500

    return jsonify(result)


@app_routes.route('/api/hl_plan_viz/<run_id>', methods=['GET'])
def get_hl_plan_viz(run_id):
    """Serve a generated HL plan visualization HTML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"hl_plan_graph_{run_id}.html"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Visualization '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/html")


@app_routes.route('/api/hl_plan_enablers_viz/<run_id>', methods=['GET'])
def get_hl_plan_enablers_viz(run_id):
    """Serve a generated enablers visualization HTML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"hl_plan_enablers_{run_id}.html"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Visualization '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/html")


@app_routes.route('/api/hl_plan_command/<run_id>', methods=['GET'])
def get_hl_plan_command(run_id):
    """Serve the logged planner/visualizer commands for a run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"hl_plan_command_{run_id}.txt"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Command log '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/plain")


@app_routes.route('/api/optimized_stn_viz/<run_id>', methods=['GET'])
def get_optimized_stn_viz(run_id):
    """Serve a generated optimized STN visualization HTML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"optimized_stn_{run_id}.html"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Visualization '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/html")


@app_routes.route('/api/optimized_stn_execution_graph_viz/<run_id>', methods=['GET'])
def get_optimized_stn_execution_graph_viz(run_id):
    """Serve a generated optimized STN execution graph HTML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"optimized_stn_execution_graph_{run_id}.html"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Visualization '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/html")


@app_routes.route('/api/optimized_stn_command/<run_id>', methods=['GET'])
def get_optimized_stn_command(run_id):
    """Serve the logged optimized STN command for a run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"optimized_stn_command_{run_id}.txt"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Command log '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/plain")


@app_routes.route('/api/optimized_bt_viz/<run_id>', methods=['GET'])
def get_optimized_bt_viz(run_id):
    """Serve a generated behavior-tree visualization HTML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"bt_viz_{run_id}.html"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Visualization '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/html")


@app_routes.route('/api/optimized_bt_xml/<run_id>', methods=['GET'])
def get_optimized_bt_xml(run_id):
    """Serve a generated behavior-tree XML file by run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"bt_{run_id}.xml"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Behavior tree XML '{filename}' not found."}), 404

    return send_from_directory(
        PUBLIC_PATH,
        filename,
        mimetype="application/xml",
        as_attachment=True,
        download_name="bt.xml",
    )


@app_routes.route('/api/optimized_bt_command/<run_id>', methods=['GET'])
def get_optimized_bt_command(run_id):
    """Serve the logged behavior-tree extraction command for a run id."""
    if not re.fullmatch(r"[0-9a-f]{10}", run_id or ""):
        return jsonify({"error": "Invalid run id format."}), 400

    filename = f"optimized_bt_command_{run_id}.txt"
    full_path = os.path.join(PUBLIC_PATH, filename)
    if not os.path.isfile(full_path):
        return jsonify({"error": f"Command log '{filename}' not found."}), 404

    return send_from_directory(PUBLIC_PATH, filename, mimetype="text/plain")
