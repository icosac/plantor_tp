#!/usr/bin/env python3
"""
Serve HTTP endpoints that query Prolog action applicability explanations.
"""

import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def prolog_quote_atom(value):
    """
    Handle prolog quote atom.

    Parameters
    ----------
    value : Any
        Value to normalize, convert, or escape.

    Returns
    -------
    Any
        Result returned by `prolog_quote_atom`.
    """
    text = "" if value is None else str(value)
    return "'" + text.replace("'", "''") + "'"


def build_goal(src_dir, kb_file, state_text, action_text, phase_text, invariants_text):
    """
    Build goal.

    Parameters
    ----------
    src_dir : Any
        Directory containing Prolog source files used during execution.
    kb_file : Any
        Path to the Prolog knowledge-base file to consult.
    state_text : Any
        Serialized state term string parsed into Prolog terms.
    action_text : Any
        Serialized action term string parsed into Prolog terms.
    phase_text : Any
        Execution phase string, typically `start` or `end`.
    invariants_text : Any
        Optional invariants term string used for applicability checks.

    Returns
    -------
    Any
        Result returned by `build_goal`.
    """
    invariants_goal = "executing_invariants(State, Invariants)"
    if invariants_text is not None:
        invariants_goal = f"atom_to_term({prolog_quote_atom(invariants_text)}, Invariants, _)"

    # Build a single atomic goal so each request runs in a fresh, isolated Prolog process.
    return ",".join(
        [
            f"working_directory(_,{prolog_quote_atom(str(src_dir))})",
            "with_output_to(string(_), consult('applicability.pl'))",
            f"with_output_to(string(_), consult({prolog_quote_atom(str(kb_file))}))",
            f"atom_to_term({prolog_quote_atom(state_text)}, State, _)",
            f"atom_to_term({prolog_quote_atom(action_text)}, Action, _)",
            f"atom_to_term({prolog_quote_atom(phase_text)}, Phase, _)",
            invariants_goal,
            "why_not_applicable_hl_action(State, Invariants, Action, Phase, Result)",
            "write_term(Result, [quoted(true)])",
        ]
    )


def run_explain(swipl_path, src_dir, kb_file, payload, timeout_s):
    """
    Run explain.

    Parameters
    ----------
    swipl_path : Any
        SWI-Prolog executable path or command name.
    src_dir : Any
        Directory containing Prolog source files used during execution.
    kb_file : Any
        Path to the Prolog knowledge-base file to consult.
    payload : Any
        JSON-like request payload with query parameters.
    timeout_s : Any
        Maximum time allowed for the operation, in seconds.

    Returns
    -------
    Any
        Result returned by `run_explain`.
    """
    state_text = payload.get("state")
    action_text = payload.get("action")
    phase_text = payload.get("phase")
    invariants_text = payload.get("invariants")

    if not isinstance(state_text, str) or not state_text.strip():
        return {"ok": False, "error": "Missing or invalid 'state'."}, 400
    if not isinstance(action_text, str) or not action_text.strip():
        return {"ok": False, "error": "Missing or invalid 'action'."}, 400
    if phase_text not in {"start", "end"}:
        return {"ok": False, "error": "Phase must be 'start' or 'end'."}, 400
    if invariants_text is not None and not isinstance(invariants_text, str):
        return {"ok": False, "error": "If provided, 'invariants' must be a string term."}, 400

    goal = build_goal(src_dir, kb_file, state_text, action_text, phase_text, invariants_text)
    cmd = [swipl_path, "-q", "-g", goal, "-t", "halt"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Prolog query timed out."}, 504
    except Exception as exc:
        return {"ok": False, "error": f"Failed to run swipl: {exc}"}, 500

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "swipl returned non-zero exit code.",
            "stderr": proc.stderr.strip(),
        }, 500

    result_term = proc.stdout.strip()
    if not result_term:
        return {
            "ok": False,
            "error": "No result term returned by Prolog.",
        }, 500

    return {
        "ok": True,
        "result_term": result_term,
    }, 200


def run_list_actions(swipl_path, src_dir, kb_file, timeout_s):
    """
    Run list actions.

    Parameters
    ----------
    swipl_path : Any
        SWI-Prolog executable path or command name.
    src_dir : Any
        Directory containing Prolog source files used during execution.
    kb_file : Any
        Path to the Prolog knowledge-base file to consult.
    timeout_s : Any
        Maximum time allowed for the operation, in seconds.

    Returns
    -------
    Any
        Result returned by `run_list_actions`.
    """
    # Query all high-level durative action names and return them as a sorted Prolog list term.
    goal = ",".join(
        [
            f"working_directory(_,{prolog_quote_atom(str(src_dir))})",
            "with_output_to(string(_), consult('applicability.pl'))",
            f"with_output_to(string(_), consult({prolog_quote_atom(str(kb_file))}))",
            "findall(Name, hl_d_action(Name, _, _, _, _, _, _), Names)",
            "sort(Names, UniqueNames)",
            "write_term(UniqueNames, [quoted(true)])",
        ]
    )
    cmd = [swipl_path, "-q", "-g", goal, "-t", "halt"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Prolog action query timed out."}, 504
    except Exception as exc:
        return {"ok": False, "error": f"Failed to run swipl: {exc}"}, 500

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "swipl returned non-zero exit code.",
            "stderr": proc.stderr.strip(),
        }, 500

    actions_term = proc.stdout.strip()
    if not actions_term:
        return {"ok": True, "actions_term": "[]"}, 200

    return {"ok": True, "actions_term": actions_term}, 200


def make_handler(swipl_path, src_dir, kb_file, timeout_s):
    """
    Handle make handler.

    Parameters
    ----------
    swipl_path : Any
        SWI-Prolog executable path or command name.
    src_dir : Any
        Directory containing Prolog source files used during execution.
    kb_file : Any
        Path to the Prolog knowledge-base file to consult.
    timeout_s : Any
        Maximum time allowed for the operation, in seconds.

    Returns
    -------
    Any
        Result returned by `make_handler`.
    """
    class Handler(BaseHTTPRequestHandler):
        """
        Handle HTTP requests for the local applicability API.
        """
        def _write_cors_headers(self):
            """
            Handle write cors headers.

            Returns
            -------
            Any
                Result returned by `_write_cors_headers`.
            """
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _write_json(self, status_code, payload):
            """
            Handle write json.

            Parameters
            ----------
            status_code : Any
                HTTP status code to send in the response.
            payload : Any
                JSON-like request payload with query parameters.

            Returns
            -------
            Any
                Result returned by `_write_json`.
            """
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._write_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            """
            Handle do OPTIONS.

            Returns
            -------
            Any
                Result returned by `do_OPTIONS`.
            """
            self.send_response(204)
            self._write_cors_headers()
            self.end_headers()

        def do_POST(self):
            """
            Handle do POST.

            Returns
            -------
            Any
                Result returned by `do_POST`.
            """
            if self.path != "/explain":
                self._write_json(404, {"ok": False, "error": "Unknown endpoint."})
                return

            length = self.headers.get("Content-Length")
            if not length:
                self._write_json(400, {"ok": False, "error": "Missing request body."})
                return
            try:
                # Content-Length is required because BaseHTTPRequestHandler does not buffer JSON bodies automatically.
                raw = self.rfile.read(int(length))
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._write_json(400, {"ok": False, "error": "Invalid JSON body."})
                return

            if not isinstance(payload, dict):
                self._write_json(400, {"ok": False, "error": "JSON body must be an object."})
                return

            response, status = run_explain(swipl_path, src_dir, kb_file, payload, timeout_s)
            self._write_json(status, response)

        def do_GET(self):
            """
            Handle do GET.

            Returns
            -------
            Any
                Result returned by `do_GET`.
            """
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._write_json(200, {"ok": True, "status": "up"})
                return
            if path == "/actions":
                response, status = run_list_actions(swipl_path, src_dir, kb_file, timeout_s)
                self._write_json(status, response)
                return
            self._write_json(404, {"ok": False, "error": "Unknown endpoint."})

        def log_message(self, format_text, *args):
            """
            Handle log message.

            Parameters
            ----------
            format_text : Any
                Text representation of format consumed by this function.
            *args : Any
                Parsed command-line arguments namespace.

            Returns
            -------
            Any
                Result returned by `log_message`.
            """
            return

    return Handler


def main():
    """
    Run the command-line entry point.

    Returns
    -------
    Any
        Result returned by `main`.
    """
    parser = argparse.ArgumentParser(
        description="Local HTTP service that runs why_not_applicable_hl_action/5 through swipl."
    )
    parser.add_argument(
        "--kb",
        required=True,
        help="Path to the KB file to consult (e.g. TP/kb/sara_easy_temporal.pl).",
    )
    parser.add_argument(
        "--src-dir",
        default="TP/prolog_planner/src",
        help="Path to Prolog src dir (must contain applicability.pl).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument("--swipl", default="swipl", help="SWI-Prolog executable.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Per-request timeout in seconds.")
    args = parser.parse_args()

    src_dir = Path(args.src_dir).resolve()
    kb_file = Path(args.kb).resolve()
    if not src_dir.exists():
        raise SystemExit(f"src dir not found: {src_dir}")
    if not kb_file.exists():
        raise SystemExit(f"kb file not found: {kb_file}")

    handler = make_handler(args.swipl, src_dir, kb_file, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Applicability service listening on http://{args.host}:{args.port}")
    print("POST /explain  | GET /health")
    server.serve_forever()


if __name__ == "__main__":
    main()
