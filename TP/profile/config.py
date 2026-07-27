"""Argument and YAML configuration handling for TP/profile.py."""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser with all supported profile.py options.
    """
    tp_root = Path(__file__).resolve().parents[1]
    repo_root = tp_root.parent
    parser = argparse.ArgumentParser(
        description=(
            "Run TP/planner.py over every kb_ll.pl under exp/kb_generation, "
            "collect profile timings, and write CSV/LaTeX summaries."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML configuration file. When passed, it must be the only command-line option.",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=repo_root / "exp" / "kb_generation",
        help="Root directory searched recursively for kb_ll.pl files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=repo_root / "exp" / "planner",
        help="Root directory where logs, visualizations, and summaries are written.",
    )
    parser.add_argument(
        "--runs",
        "--run",
        dest="runs",
        type=int,
        default=100,
        help="Number of measured planner runs per KB; 0 skips measured runs.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=0,
        help=(
            "Stop profiling the current KB after N successive non-ok runs; "
            "0 disables early stopping."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout passed to planner.py in seconds; -1 disables the inner planner timeout.",
    )
    parser.add_argument(
        "--process-timeout",
        type=int,
        default=420,
        help="Outer timeout for each planner.py subprocess in seconds; -1 disables it.",
    )
    parser.add_argument(
        "--stack-limit",
        default="10G",
        help="SWI-Prolog stack limit forwarded to planner.py.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=-1,
        help="Maximum BFS depth passed to planner.py; -1 means unbounded.",
    )
    parser.add_argument(
        "--enable-graph-debug",
        action="store_true",
        help="Enable Prolog graph debug trace in forwarded planner.py runs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N KBs after sorting; 0 means all.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help=(
            "Regex matched against each kb_ll.pl path relative to KB_ROOT. "
            "Matching files are excluded. Can be passed multiple times."
        ),
    )
    parser.add_argument(
        "--table-path",
        type=Path,
        default=None,
        help="Output path for the LaTeX table. Defaults to OUTPUT_ROOT/profile_table.tex.",
    )
    parser.add_argument(
        "--runs-csv",
        type=Path,
        default=None,
        help="Output path for per-run measurements. Defaults to OUTPUT_ROOT/profile_runs.csv.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=None,
        help="Output path for per-KB aggregate measurements. Defaults to OUTPUT_ROOT/profile_summary.csv.",
    )
    parser.add_argument(
        "--normalized-to-plot-path",
        dest="normalized_to_plot_path",
        type=Path,
        default=None,
        help=(
            "Output path for the normalized per-model timing bar plot. "
            "Defaults to OUTPUT_ROOT/model_normalized_total_order.pdf."
        ),
    )
    parser.add_argument(
        "--normalized-to-data-csv",
        dest="normalized_to_data_csv",
        type=Path,
        default=None,
        help=(
            "Output path for normalized per-model timing values. "
            "Defaults to OUTPUT_ROOT/model_normalized_total_order.csv."
        ),
    )
    parser.add_argument(
        "--normalized-to-tikz-path",
        dest="normalized_to_tikz_path",
        type=Path,
        default=None,
        help=(
            "Output path for a LaTeX/PGFPlots version of the normalized plot. "
            "Defaults to OUTPUT_ROOT/model_normalized_total_order_tikz.tex."
        ),
    )
    parser.add_argument(
        "--normalized-to-plot-metric",
        dest="normalized_to_plot_metric",
        default="prolog.total_order_planning.wall_seconds",
        help="Aggregate timing metric used for the normalized per-model plot.",
    )
    parser.add_argument(
        "--no-to-normalized-plots",
        "--no-to-normalized-plot",
        dest="no_to_normalized_plot",
        action="store_true",
        help="Do not generate the normalized per-model timing plot.",
    )
    parser.add_argument(
        "--no-to-normalized-tikz",
        dest="no_to_normalized_tikz",
        action="store_true",
        help="Do not generate the LaTeX/PGFPlots normalized plot.",
    )
    parser.add_argument(
        "--no-timing-plots",
        action="store_true",
        help="Do not generate grouped raw timing plots.",
    )
    parser.add_argument(
        "--no-timing-tikz",
        action="store_true",
        help="Do not generate grouped raw timing LaTeX/PGFPlots plots.",
    )
    parser.add_argument(
        "--no-timing-tables",
        action="store_true",
        help="Do not generate grouped raw timing LaTeX tables.",
    )
    parser.add_argument(
        "--only-plot",
        action="store_true",
        help="Skip planner runs and regenerate tables/plots from the existing summary CSV.",
    )
    parser.add_argument(
        "--planner",
        type=Path,
        default=tp_root / "planner.py",
        help="Path to planner.py.",
    )
    parser.add_argument(
        "--save-logs-viz",
        action="store_true",
        help=(
            "Run one extra plain planner visualization pass per KB before measured runs "
            "and save the generated files. Measured run logs are always saved."
        ),
    )
    parser.add_argument("--force", action="store_true", help="Delete and recreate OUTPUT_ROOT before running.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Update existing CSV entries for the KBs processed in this run while preserving "
            "entries for other KBs. Unlike --force, this does not delete OUTPUT_ROOT."
        ),
    )
    parser.add_argument(
        "--sure",
        action="store_true",
        help="Skip the confirmation prompt required by --force or --overwrite.",
    )
    return parser


def parse_config_path_arg(argv: Sequence[str]) -> Optional[Path]:
    """
    Extract a standalone --config path from argv.

    Parameters
    ----------
    argv : Sequence[str]
        Command-line arguments excluding the executable name.

    Returns
    -------
    Optional[Path]
        Config path when --config was passed, otherwise None.
    """
    config_args = [arg for arg in argv if arg == "--config" or arg.startswith("--config=")]
    if not config_args:
        return None
    if len(config_args) > 1:
        raise ValueError("--config can only be passed once.")
    if argv[0].startswith("--config=") and len(argv) == 1:
        return Path(argv[0].split("=", 1)[1])
    if argv[0] == "--config" and len(argv) == 2:
        return Path(argv[1])
    raise ValueError("--config cannot be combined with any other option.")


def load_profile_config(path: Path) -> Dict[str, Any]:
    """
    Load a profile YAML configuration file.

    Parameters
    ----------
    path : Path
        YAML file path.

    Returns
    -------
    Dict[str, Any]
        Parsed configuration mapping.
    """
    if not path.is_file():
        raise ValueError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a YAML mapping at the top level.")
    return config


def set_config_value(args: argparse.Namespace, dest: str, value: Any, path_type: bool = False) -> None:
    """
    Assign one config value to the parsed argparse namespace.

    Parameters
    ----------
    args : argparse.Namespace
        Namespace to update.
    dest : str
        Destination attribute name.
    value : Any
        Raw YAML value.
    path_type : bool, optional
        Whether to convert non-None values to Path.

    Returns
    -------
    None
        This function mutates args.
    """
    if value is None:
        setattr(args, dest, None)
    elif path_type:
        setattr(args, dest, Path(value))
    else:
        setattr(args, dest, value)


def apply_profile_config(args: argparse.Namespace, config: Dict[str, Any]) -> argparse.Namespace:
    """
    Apply experiments.yaml-style configuration values to argparse defaults.

    Parameters
    ----------
    args : argparse.Namespace
        Namespace initialized with parser defaults.
    config : Dict[str, Any]
        Parsed YAML config.

    Returns
    -------
    argparse.Namespace
        Updated namespace.
    """
    root_keys = {
        "KB_ROOT": ("kb_root", True),
        "OUTPUT_ROOT": ("output_root", True),
        "TABLE_PATH": ("table_path", True),
        "RUNS_CSV": ("runs_csv", True),
        "SUMMARY_CSV": ("summary_csv", True),
        "FORCE": ("force", False),
        "OVERWRITE": ("overwrite", False),
        "SURE": ("sure", False),
        "RUNS": ("runs", False),
        "PATIENCE": ("patience", False),
        "TIMEOUT": ("timeout", False),
        "LIMIT": ("limit", False),
        "EXCLUDE": ("exclude", False),
        "SAVE_LOGS_VIZ": ("save_logs_viz", False),
        "ONLY_PLOT": ("only_plot", False),
    }
    planner_keys = {
        "PLANNER": ("planner", True),
        "PROCESS_TIMEOUT": ("process_timeout", False),
        "STACK_LIMIT": ("stack_limit", False),
        "MAX_DEPTH": ("max_depth", False),
        "ENABLE_GRAPH_DEBUG": ("enable_graph_debug", False),
    }
    normalized_keys = {
        "NORMALIZED_TO_PLOT_PATH": ("normalized_to_plot_path", True),
        "NORMALIZED_TO_DATA_CSV": ("normalized_to_data_csv", True),
        "NORMALIZED_TO_TIKZ_PATH": ("normalized_to_tikz_path", True),
        "NORMALIZED_TO_PLOT_METRIC": ("normalized_to_plot_metric", False),
        "NO_TO_NORMALIZED_PLOT": ("no_to_normalized_plot", False),
        "NO_TO_NORMALIZED_PLOTS": ("no_to_normalized_plot", False),
        "NO_TO_NORMALIZED_TIKZ": ("no_to_normalized_tikz", False),
    }
    timing_keys = {
        "NO_TIMING_PLOT": ("no_timing_plots", False),
        "NO_TIMING_PLOTS": ("no_timing_plots", False),
        "NO_TIMING_TIKZ": ("no_timing_tikz", False),
        "NO_TIMING_TABLES": ("no_timing_tables", False),
    }

    for key, (dest, is_path) in root_keys.items():
        if key in config:
            set_config_value(args, dest, config[key], path_type=is_path)

    nested_sections = {
        "PLANNER_OPTS": planner_keys,
        "TO_NORMALIZED": normalized_keys,
        "TIMINGS": timing_keys,
    }
    for section_name, mapping in nested_sections.items():
        section = config.get(section_name, {})
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"{section_name} must be a YAML mapping.")
        for key, (dest, is_path) in mapping.items():
            if key in section:
                set_config_value(args, dest, section[key], path_type=is_path)

    if args.exclude is None:
        args.exclude = []
    elif isinstance(args.exclude, str):
        args.exclude = [args.exclude]
    elif not isinstance(args.exclude, list):
        args.exclude = list(args.exclude)
    return args


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Validate parsed command-line or YAML-driven arguments.

    Parameters
    ----------
    args : argparse.Namespace
        Arguments to validate.
    parser : argparse.ArgumentParser
        Parser used to report user-facing errors.

    Returns
    -------
    None
        Raises SystemExit through parser.error on invalid input.
    """
    if args.runs < 0:
        parser.error("--runs must be zero or a positive integer.")
    if args.patience < 0:
        parser.error("--patience must be zero or a positive integer.")
    if args.timeout < -1 or args.timeout == 0:
        parser.error("--timeout must be -1 for no timeout or a positive integer.")
    if args.process_timeout < -1 or args.process_timeout == 0:
        parser.error("--process-timeout must be -1 for no timeout or a positive integer.")
    if args.max_depth < -1:
        parser.error("--max-depth must be -1 for unbounded search or a non-negative integer.")
    if args.force and args.overwrite:
        parser.error("--force and --overwrite are mutually exclusive.")
    for pattern in args.exclude:
        try:
            re.compile(pattern)
        except re.error as exc:
            parser.error(f"Invalid --exclude regex {pattern!r}: {exc}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """
    Parse command-line options or an exclusive YAML configuration file.

    Parameters
    ----------
    argv : Optional[Sequence[str]], optional
        Arguments excluding the executable name. Defaults to sys.argv[1:].

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        config_path = parse_config_path_arg(raw_argv)
    except ValueError as exc:
        parser.error(str(exc))

    if config_path is not None:
        args = parser.parse_args([])
        args.config = config_path
        try:
            config = load_profile_config(config_path)
            apply_profile_config(args, config)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        args = parser.parse_args(raw_argv)

    validate_args(args, parser)
    return args
