"""Generate plots from TP/profile.py summary CSV files."""

import argparse
import csv
import math
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_METRIC = "prolog.total_order_planning.wall_seconds"
MODEL_CHOICES = [
    "azure_claude-opus46-multi",
    "azure_claude-sonnet46-multi",
    "azure_gpt52-multi",
    "azure_gpt54-mini-multi",
    "hf_Qwen_Qwen3.6-35B-A3B-multi",
    "hf_meta-llama_Llama-3.3-70B-Instruct-multi",
]
MODEL_ALIASES = {model.removesuffix("-multi"): model for model in MODEL_CHOICES}
MODEL_DISPLAY_ORDER = ["GPT5.2", "GPT5.4 Mini", "Sonnet 4.6", "Opus 4.6", "Qwen", "Llama"]
TABLE_METRICS = [
    ("to", "prolog.total_order_planning.wall_seconds"),
    ("ll", "prolog.low_level_mapping.wall_seconds"),
    ("enab", "prolog.enabler_extraction.wall_seconds"),
    ("po", "python.partial_order_construction.wall_seconds"),
    ("stn", "python.stn_generation.wall_seconds"),
    ("stn+c", "python.stn_time_constraint_application.wall_seconds"),
    ("opt", "python.stn_optimization.wall_seconds"),
    ("total", "python.total_pipeline.wall_seconds"),
]
TIMING_PLOT_GROUPS = {
    "total_order_low_level": {
        "title": "Total-order and low-level-order timings",
        "ylabel": "Mean time (s)",
        "output_stem": "total_order_low_level_timings",
        "log_y": True,
        "metrics": [
            ("Total order", "prolog.total_order_planning.wall_seconds"),
            ("Low-level order", "prolog.low_level_mapping.wall_seconds"),
        ],
    },
    "enablers": {
        "title": "Enabler timings",
        "ylabel": "Mean time (s)",
        "output_stem": "enabler_timings",
        "metrics": [
            ("Enablers", "prolog.enabler_extraction.wall_seconds"),
        ],
    },
    "stn": {
        "title": "STN construction and computation timings",
        "ylabel": "Mean time (s)",
        "output_stem": "stn_construction_computation_timings",
        "metrics": [
            (
                "STN build",
                (
                    "python.stn_generation.wall_seconds",
                    "python.stn_time_constraint_application.wall_seconds",
                ),
            ),
            ("Optimization", "python.stn_optimization.wall_seconds"),
        ],
    },
}


def model_display_name(model: str) -> Optional[str]:
    """
    Map raw experiment directory names to paper-friendly model names.

    Parameters
    ----------
    model : str
        Raw model directory name.

    Returns
    -------
    Optional[str]
        Display name, or None when the model should not be shown in plots.
    """
    model_lower = model.lower()
    if "gpt52" in model_lower or "gpt5.2" in model_lower:
        return "GPT5.2"
    if "gpt54-mini" in model_lower or "gpt5.4-mini" in model_lower or "gpt5.4 mini" in model_lower:
        return "GPT5.4 Mini"
    if "sonnet46" in model_lower or "sonnet-4.6" in model_lower or "sonnet 4.6" in model_lower:
        return "Sonnet 4.6"
    if "opus46" in model_lower or "opus-4.6" in model_lower or "opus 4.6" in model_lower:
        return "Opus 4.6"
    if "qwen" in model_lower:
        return "Qwen"
    if "llama" in model_lower:
        return "Llama"
    return None


def parse_model_argument(value: str) -> List[str]:
    """
    Parse a comma-separated model filter argument.

    Parameters
    ----------
    value : str
        Raw CLI value.

    Returns
    -------
    List[str]
        Valid model directory names, preserving input order.
    """
    models = []
    for model in value.split(","):
        model = model.strip()
        if not model:
            continue
        canonical_model = model if model in MODEL_CHOICES else MODEL_ALIASES.get(model)
        if canonical_model and canonical_model not in models:
            models.append(canonical_model)
    if not models:
        raise argparse.ArgumentTypeError("--model requires at least one model name")

    invalid_models = [
        model.strip()
        for model in value.split(",")
        if model.strip() and model.strip() not in MODEL_CHOICES and model.strip() not in MODEL_ALIASES
    ]
    if invalid_models:
        valid_models = ", ".join(MODEL_CHOICES + list(MODEL_ALIASES))
        invalid = ", ".join(invalid_models)
        raise argparse.ArgumentTypeError(f"unknown model(s): {invalid}. Valid models: {valid_models}")
    return models


def read_summary_csv(path: Path) -> List[Dict[str, Any]]:
    """
    Read profile summary rows from CSV.

    Parameters
    ----------
    path : Path
        Input CSV path.

    Returns
    -------
    List[Dict[str, Any]]
        Summary rows.
    """
    conflict_markers = ("<<<<<<<", "=======", ">>>>>>>")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.startswith(conflict_markers):
                raise ValueError(
                    f"{path} contains an unresolved conflict marker at line {line_number}: "
                    f"{line.strip()}"
                )

    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def natural_sort_key(value: str) -> List[Any]:
    """
    Build a sort key that treats digit runs numerically.

    Parameters
    ----------
    value : str
        String to sort.

    Returns
    -------
    List[Any]
        Sort key.
    """
    parts = re.split(r"(\d+)", value)
    return [int(part) if part.isdigit() else part for part in parts]


def pgf_number(value: float) -> str:
    """
    Format a numeric value for compact PGFPlots coordinates.

    Parameters
    ----------
    value : float
        Numeric coordinate or bound.

    Returns
    -------
    str
        Compact decimal representation.
    """
    if abs(value) < 1e-12:
        value = 0.0
    return f"{value:.6g}"


def positive_log_bounds(rows: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Compute decade-aligned bounds for a positive logarithmic timing axis.

    Parameters
    ----------
    rows : List[Dict[str, Any]]
        Timing rows with mean_seconds and std_seconds fields.

    Returns
    -------
    Tuple[float, float]
        Positive ymin/ymax values suitable for a log axis.
    """
    lower_candidates = []
    upper_candidates = []
    for row in rows:
        mean_seconds = float(row["mean_seconds"])
        std_seconds = max(float(row.get("std_seconds", 0.0)), 0.0)
        if mean_seconds <= 0:
            continue
        lower_candidates.append(max(mean_seconds - std_seconds, min(mean_seconds, 1e-12)))
        upper_candidates.append(mean_seconds + std_seconds)

    if not lower_candidates or not upper_candidates:
        return 1e-6, 1.0

    min_value = min(value for value in lower_candidates if value > 0)
    max_value = max(upper_candidates)
    y_min = 10 ** math.floor(math.log10(min_value))
    y_max = 10 ** math.ceil(math.log10(max_value))
    if y_min >= y_max:
        y_max = y_min * 10
    return y_min, y_max


def kb_identity(kb_path: Path, kb_root: Path) -> Optional[Dict[str, str]]:
    """
    Extract instance/model labels from a generated KB path.

    Parameters
    ----------
    kb_path : Path
        KB path from a summary row.
    kb_root : Path
        Root used to make labels relative.

    Returns
    -------
    Optional[Dict[str, str]]
        Parsed labels, or None if the path does not match the expected layout.
    """
    try:
        relative_path = kb_path.relative_to(kb_root)
    except ValueError:
        relative_path = kb_path

    relative_parts = relative_path.parts
    if "kb_generation" in relative_parts:
        relative_parts = relative_parts[relative_parts.index("kb_generation") + 1 :]
    if "output" not in relative_parts:
        return None
    output_index = relative_parts.index("output")
    model_index = output_index - 1
    if model_index < 1:
        return None
    return {
        "instance": "/".join(relative_parts[:model_index]),
        "model": relative_parts[model_index],
        "relative_kb": "/".join(relative_parts),
    }


def kb_label(kb_path: Path, kb_root: Path) -> str:
    """
    Build a stable KB label for tables and plots.

    Parameters
    ----------
    kb_path : Path
        KB path from a summary row.
    kb_root : Path
        Root used to make paths relative.

    Returns
    -------
    str
        Relative KB label when possible.
    """
    identity = kb_identity(kb_path, kb_root)
    if identity is not None:
        return identity["relative_kb"]
    try:
        return str(kb_path.relative_to(kb_root))
    except ValueError:
        return str(kb_path)


def model_output_folder(models: Optional[List[str]]) -> str:
    """
    Build the subdirectory name used for model-filtered outputs.

    Parameters
    ----------
    models : Optional[List[str]]
        Selected model directory names.

    Returns
    -------
    str
        Subdirectory name, or an empty string when no model filter is active.
    """
    if not models:
        return ""
    return "_".join(model.removesuffix("-multi") for model in models)


def place_in_output_folder(path: Path, folder: str) -> Path:
    """
    Place an output path inside a model-specific subdirectory.

    Parameters
    ----------
    path : Path
        Original output path.
    folder : str
        Subdirectory name.

    Returns
    -------
    Path
        Output path inside the subdirectory.
    """
    if not folder:
        return path
    return path.parent / folder / path.name


def domain_name(instance: str) -> str:
    """
    Extract the benchmark domain from an instance label.

    Parameters
    ----------
    instance : str
        Instance or KB label such as ``blocks_world/6/...``.

    Returns
    -------
    str
        First path component, or ``unknown`` for empty labels.
    """
    parts = str(instance).split("/")
    return parts[0] if parts and parts[0] else "unknown"


def rows_by_domain(rows: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Group plotting rows by benchmark domain while preserving stable ordering.

    Parameters
    ----------
    rows : List[Dict[str, Any]]
        Plot rows with an ``instance`` field.

    Returns
    -------
    List[Tuple[str, List[Dict[str, Any]]]]
        Domain name and rows belonging to that domain.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(domain_name(row["instance"]), []).append(row)
    return [(domain, grouped[domain]) for domain in sorted(grouped, key=natural_sort_key)]


def domain_axis_label(instance: str, domain: str) -> str:
    """
    Shorten an instance label for plots that already have one page per domain.

    Parameters
    ----------
    instance : str
        Full instance or KB label.
    domain : str
        Domain name being plotted.

    Returns
    -------
    str
        Compact label suitable for vertical tick labels.
    """
    label = str(instance)
    domain_prefix = f"{domain}/" if domain else ""
    if domain_prefix and label.startswith(domain_prefix):
        label = label[len(domain_prefix) :]
    label = label.removesuffix("/output/kb_ll.pl")
    parts = label.split("/")
    if not domain and len(parts) >= 3:
        display_model = model_display_name(parts[2]) or parts[2].removesuffix("-multi")
        return f"{parts[0]}/{parts[1]}/{display_model}"
    if len(parts) >= 2:
        display_model = model_display_name(parts[1]) or parts[1].removesuffix("-multi")
        return f"{parts[0]}/{display_model}"
    return label


def domain_output_path(path: Path, domain: str) -> Path:
    """
    Add a domain suffix to a plot artifact path.

    Parameters
    ----------
    path : Path
        Base output path.
    domain : str
        Domain name.

    Returns
    -------
    Path
        Path with ``_<domain>`` inserted before the extension.
    """
    return path.with_name(f"{path.stem}_{domain}{path.suffix}")


def filter_summaries_by_model(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    models: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """
    Keep only summary rows for a selected model.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        Root used to parse KB identities.
    models : Optional[List[str]]
        Raw model directory names to keep, or None to keep all rows.

    Returns
    -------
    List[Dict[str, Any]]
        Filtered summary rows.
    """
    if not models:
        return summaries

    allowed_models = set(models)
    filtered = []
    for summary in summaries:
        identity = kb_identity(Path(summary["kb"]), kb_root)
        if identity is not None and identity["model"] in allowed_models:
            filtered.append(summary)
    return filtered


def normalized_model_rows(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    metric: str,
) -> List[Dict[str, Any]]:
    """
    Compute per-model timings normalized by the instance mean.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        Root used to parse KB identities.
    metric : str
        Base metric key, without the .mean suffix.

    Returns
    -------
    List[Dict[str, Any]]
        Normalized rows.
    """
    rows_by_instance: Dict[str, List[Dict[str, Any]]] = {}
    for summary in summaries:
        mean_key = f"{metric}.mean"
        mean_value = summary.get(mean_key, "")
        if mean_value == "":
            continue
        try:
            time_value = float(mean_value)
        except (TypeError, ValueError):
            continue
        if time_value <= 0:
            continue

        identity = kb_identity(Path(summary["kb"]), kb_root)
        if identity is None:
            continue
        display_model = model_display_name(identity["model"])
        if display_model is None:
            continue
        row = {
            "instance": identity["instance"],
            "model": identity["model"],
            "display_model": display_model,
            "kb": identity["relative_kb"],
            "metric": metric,
            "metric_mean_seconds": time_value,
            "ok": summary.get("ok", ""),
            "timeouts": summary.get("timeouts", ""),
            "failed": summary.get("failed", ""),
        }
        rows_by_instance.setdefault(identity["instance"], []).append(row)

    normalized_rows: List[Dict[str, Any]] = []
    for instance, instance_rows in rows_by_instance.items():
        instance_mean = statistics.mean(row["metric_mean_seconds"] for row in instance_rows)
        if instance_mean <= 0:
            continue
        for row in instance_rows:
            normalized = row["metric_mean_seconds"] / instance_mean
            out_row = dict(row)
            out_row["instance_mean_seconds"] = instance_mean
            out_row["normalized"] = normalized
            out_row["deviation_from_1"] = normalized - 1.0
            out_row["abs_deviation_from_1"] = abs(normalized - 1.0)
            normalized_rows.append(out_row)

    display_rank = {model: index for index, model in enumerate(MODEL_DISPLAY_ORDER)}
    normalized_rows.sort(
        key=lambda row: (
            natural_sort_key(row["instance"]),
            display_rank.get(row["display_model"], len(display_rank)),
            row["model"],
        )
    )
    return normalized_rows


def write_normalized_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    """
    Write normalized per-model rows to CSV.

    Parameters
    ----------
    path : Path
        Output CSV path.
    rows : List[Dict[str, Any]]
        Normalized rows.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    fieldnames = [
        "instance",
        "model",
        "display_model",
        "kb",
        "metric",
        "metric_mean_seconds",
        "instance_mean_seconds",
        "normalized",
        "deviation_from_1",
        "abs_deviation_from_1",
        "ok",
        "timeouts",
        "failed",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_normalized_plot(path: Path, rows: List[Dict[str, Any]], metric: str) -> List[str]:
    """
    Write normalized per-model timing strip plot.

    Parameters
    ----------
    path : Path
        Output plot path.
    rows : List[Dict[str, Any]]
        Normalized rows.
    metric : str
        Metric used to generate the normalized values.

    Returns
    -------
    List[str]
        Written PDF paths.
    """
    if not rows:
        return []
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/plantor_matplotlib")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/plantor_cache")
    try:
        import matplotlib
        matplotlib.use("Agg")
        matplotlib.rcParams.update(
            {
                "pdf.fonttype": 42,
                "ps.fonttype": 42,
                "font.family": "serif",
                "mathtext.fontset": "dejavuserif",
                "axes.unicode_minus": False,
            }
        )
        import matplotlib.pyplot as plt
    except ImportError as error:
        print(f"matplotlib import failed; skipping normalized timing plot: {error}", file=sys.stderr)
        return []

    display_rank = {model: index for index, model in enumerate(MODEL_DISPLAY_ORDER)}
    domain_groups = rows_by_domain(rows)
    plot_groups = [("all", rows, path)]
    if len(domain_groups) > 1:
        plot_groups.extend(
            (domain, domain_rows, domain_output_path(path, domain))
            for domain, domain_rows in domain_groups
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    written_paths = []
    for domain, domain_rows, output_path in plot_groups:
        label_domain = "" if domain == "all" else domain
        instances = sorted({row["instance"] for row in domain_rows}, key=natural_sort_key)
        models = sorted(
            {row["display_model"] for row in domain_rows},
            key=lambda model: display_rank.get(model, len(display_rank)),
        )
        value_by_pair = {
            (row["instance"], row["display_model"]): float(row["normalized"])
            for row in domain_rows
        }

        x_positions = list(range(len(instances)))
        fig_width = max(8.0, len(instances) * (0.75 if label_domain else 0.85))
        fig_height = max(
            5.8,
            5.0
            + max((len(domain_axis_label(instance, label_domain)) for instance in instances), default=0)
            * 0.035,
        )
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        for x_position in x_positions:
            ax.axvline(x_position, color="0.82", linewidth=1.0, zorder=0)

        marker_cycle = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">"]
        color_cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", [])
        jitter_width = min(0.14, 0.018 * max(len(models) - 1, 0))
        for model_index, model in enumerate(models):
            xs = []
            ys = []
            offset = 0.0
            if len(models) > 1:
                offset = -jitter_width / 2.0 + (jitter_width * model_index / (len(models) - 1))
            for instance_index, instance in enumerate(instances):
                value = value_by_pair.get((instance, model))
                if value is None:
                    continue
                xs.append(x_positions[instance_index] + offset)
                ys.append(value)
            if xs:
                ax.scatter(
                    xs,
                    ys,
                    label=model,
                    marker=marker_cycle[model_index % len(marker_cycle)],
                    color=color_cycle[model_index % len(color_cycle)] if color_cycle else None,
                    s=46,
                    edgecolors="black",
                    linewidths=0.4,
                    zorder=3,
                )

        ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--")
        ax.set_title("All domains" if domain == "all" else domain)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(
            [domain_axis_label(instance, label_domain) for instance in instances],
            rotation=90,
            ha="center",
            va="top",
        )
        ax.set_ylabel("Normalized time (instance mean = 1)")
        ax.set_xlabel("Instance")
        ax.grid(axis="y", linestyle=":", linewidth=0.7, alpha=0.7)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize="small", frameon=False)
        fig.tight_layout()
        fig.savefig(
            output_path,
            bbox_inches="tight",
            metadata={
                "Creator": "TP/profile/plot.py",
                "Producer": "matplotlib",
                "Title": f"Relative {metric} by model - {domain}",
            },
        )
        plt.close(fig)
        written_paths.append(str(output_path))
    return written_paths


def latex_escape(value: str) -> str:
    """
    Escape a string for LaTeX text contexts.

    Parameters
    ----------
    value : str
        Raw string.

    Returns
    -------
    str
        Escaped string.
    """
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
    }
    escaped = value
    for old, new in replacements.items():
        escaped = escaped.replace(old, new)
    return escaped


def metric_components(metric: Any) -> Tuple[str, ...]:
    """
    Return the raw summary metric keys represented by a metric spec.

    Parameters
    ----------
    metric : Any
        Metric key, or a tuple/list of keys to be summed.

    Returns
    -------
    Tuple[str, ...]
        One or more raw summary metric keys.
    """
    if isinstance(metric, (tuple, list)):
        return tuple(str(component) for component in metric)
    return (str(metric),)


def aggregate_metric(summary: Dict[str, Any], metric: Any) -> Optional[Tuple[float, float]]:
    """
    Extract or sum aggregate timing statistics for a metric spec.

    Parameters
    ----------
    summary : Dict[str, Any]
        Aggregate row.
    metric : Any
        Metric key, or a tuple/list of keys to be summed.

    Returns
    -------
    Optional[Tuple[float, float]]
        Mean and standard deviation, or None when any component is missing.
    """
    mean_seconds = 0.0
    variance_seconds = 0.0
    for component in metric_components(metric):
        mean_value = summary.get(f"{component}.mean", "")
        std_value = summary.get(f"{component}.std", "")
        if mean_value in ("", None):
            return None
        mean_seconds += float(mean_value)
        std_seconds = float(std_value) if std_value not in ("", None) else 0.0
        variance_seconds += std_seconds * std_seconds
    return mean_seconds, math.sqrt(variance_seconds)


def format_latex_metric(summary: Dict[str, Any], metric: Any) -> str:
    """
    Format one aggregate timing value for LaTeX.

    Parameters
    ----------
    summary : Dict[str, Any]
        Aggregate row.
    metric : str
        Metric key.

    Returns
    -------
    str
        Table cell.
    """
    stats = aggregate_metric(summary, metric)
    if stats is None:
        return r"\texttt{X}"
    mean_seconds, std_seconds = stats
    return f"${mean_seconds:.4f} \\pm {std_seconds:.4f}$"


def write_latex_table(path: Path, summaries: List[Dict[str, Any]], kb_root: Path) -> None:
    """
    Write a LaTeX-compatible timing table.

    Parameters
    ----------
    path : Path
        Output .tex path.
    summaries : List[Dict[str, Any]]
        Aggregate rows.
    kb_root : Path
        Source KB root used for relative row labels.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    columns = "lrrrr" + ("r" * len(TABLE_METRICS))
    headers = ["KB", "Runs", "OK", "Timeout", "Fail"] + [label for label, _metric in TABLE_METRICS]
    lines = [
        rf"\begin{{tabular}}{{{columns}}}",
        r"\hline",
        " & ".join(headers) + r" \\",
        r"\hline",
    ]
    for summary in summaries:
        kb_label_value = kb_label(Path(summary["kb"]), kb_root)
        cells = [
            latex_escape(kb_label_value),
            str(summary["runs"]),
            str(summary["ok"]),
            str(summary["timeouts"]),
            str(summary["failed"]),
        ]
        cells.extend(format_latex_metric(summary, metric) for _label, metric in TABLE_METRICS)
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_timing_latex_table(
    path: Path,
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    metrics: List[Tuple[str, Any]],
) -> bool:
    """
    Write a LaTeX-compatible timing table for a selected metric group.

    Parameters
    ----------
    path : Path
        Output .tex path.
    summaries : List[Dict[str, Any]]
        Aggregate rows.
    kb_root : Path
        Source KB root used for relative row labels.
    metrics : List[Tuple[str, str]]
        Table headers and metric keys.

    Returns
    -------
    bool
        True when a table was written.
    """
    if not summaries:
        return False

    columns = "lrrrr" + ("r" * len(metrics))
    headers = ["KB", "Runs", "OK", "Timeout", "Fail"] + [label for label, _metric in metrics]
    lines = [
        rf"\begin{{tabular}}{{{columns}}}",
        r"\hline",
        " & ".join(latex_escape(header) for header in headers) + r" \\",
        r"\hline",
    ]
    wrote_metric = False
    for summary in summaries:
        kb_label_value = kb_label(Path(summary["kb"]), kb_root)
        cells = [
            latex_escape(kb_label_value),
            str(summary["runs"]),
            str(summary["ok"]),
            str(summary["timeouts"]),
            str(summary["failed"]),
        ]
        for _label, metric in metrics:
            if aggregate_metric(summary, metric) is not None:
                wrote_metric = True
            cells.append(format_latex_metric(summary, metric))
        lines.append(" & ".join(cells) + r" \\")

    if not wrote_metric:
        return False

    lines.extend([r"\hline", r"\end{tabular}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def write_normalized_tikz(path: Path, rows: List[Dict[str, Any]], metric: str) -> bool:
    """
    Write a LaTeX/PGFPlots strip plot for normalized per-model timings.

    Parameters
    ----------
    path : Path
        Output .tex path.
    rows : List[Dict[str, Any]]
        Normalized rows.
    metric : str
        Metric used to generate the normalized values.

    Returns
    -------
    bool
        True when a TikZ/PGFPlots file was written.
    """
    if not rows:
        return False

    domain_groups = rows_by_domain(rows)
    if len(domain_groups) > 1:
        for domain, domain_rows in domain_groups:
            domain_path = domain_output_path(path, domain)
            write_normalized_tikz(domain_path, domain_rows, metric)

    domain = "" if len(domain_groups) > 1 else domain_groups[0][0]
    instances = sorted({row["instance"] for row in rows}, key=natural_sort_key)
    display_rank = {model: index for index, model in enumerate(MODEL_DISPLAY_ORDER)}
    models = sorted(
        {row["display_model"] for row in rows},
        key=lambda model: display_rank.get(model, len(display_rank)),
    )
    value_by_pair = {(row["instance"], row["display_model"]): float(row["normalized"]) for row in rows}
    values = [float(row["normalized"]) for row in rows]
    y_min = min(values + [1.0])
    y_max = max(values + [1.0])
    y_padding = max((y_max - y_min) * 0.12, 0.1)
    y_min = max(0.0, y_min - y_padding)
    y_max = y_max + y_padding

    colors = [
        "blue!70!black",
        "red!75!black",
        "teal!75!black",
        "orange!85!black",
        "purple!75!black",
        "brown!80!black",
        "cyan!70!black",
        "magenta!75!black",
        "olive!80!black",
        "black",
    ]
    marks = ["*", "square*", "triangle*", "diamond*", "pentagon*", "otimes*", "oplus*", "star", "x", "+"]
    jitter_width = min(0.14, 0.018 * max(len(models) - 1, 0))

    xticks = ",".join(str(index) for index in range(len(instances)))
    xticklabels = ",".join("{" + latex_escape(domain_axis_label(instance, domain)) + "}" for instance in instances)
    x_min = -0.5
    x_max = max(len(instances) - 0.5, 0.5)

    lines = [
        r"% Requires: \usepackage{pgfplots}",
        r"% Recommended: \pgfplotsset{compat=1.18}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  width=0.96\textwidth,",
        r"  height=0.42\textwidth,",
        f"  title={{{latex_escape(domain or 'All domains')}}},",
        r"  xlabel={Instance},",
        r"  ylabel={Normalized time (instance mean = 1)},",
        f"  xmin={pgf_number(x_min)}, xmax={pgf_number(x_max)},",
        f"  ymin={pgf_number(y_min)}, ymax={pgf_number(y_max)},",
        f"  xtick={{{xticks}}},",
        f"  xticklabels={{{xticklabels}}},",
        r"  tick align=outside,",
        r"  tick pos=left,",
        r"  x tick label style={rotate=90, anchor=east, font=\scriptsize},",
        r"  y tick label style={font=\scriptsize},",
        r"  label style={font=\small},",
        r"  ymajorgrids=true,",
        r"  grid style={dotted, gray!45},",
        r"  legend style={at={(0.02,0.98)}, anchor=north west, draw=black!25, fill=white, fill opacity=0.88, text opacity=1, font=\scriptsize},",
        r"  legend cell align={left},",
        r"  axis line style={black!70},",
        r"  clip=false",
        r"]",
    ]

    for index in range(len(instances)):
        lines.append(
            "\\addplot[gray!35, thin, forget plot] coordinates "
            f"{{({pgf_number(float(index))},{pgf_number(y_min)}) "
            f"({pgf_number(float(index))},{pgf_number(y_max)})}};"
        )
    lines.append(
        "\\addplot[black, dashed, forget plot] coordinates "
        f"{{({pgf_number(x_min)},1) ({pgf_number(x_max)},1)}};"
    )

    for model_index, model in enumerate(models):
        offset = 0.0
        if len(models) > 1:
            offset = -jitter_width / 2.0 + (jitter_width * model_index / (len(models) - 1))
        coords = []
        for instance_index, instance in enumerate(instances):
            value = value_by_pair.get((instance, model))
            if value is None:
                continue
            coords.append(f"({pgf_number(instance_index + offset)},{pgf_number(value)})")
        if not coords:
            continue
        color = colors[model_index % len(colors)]
        mark = marks[model_index % len(marks)]
        lines.append(
            f"\\addplot+[only marks, mark={mark}, color={color}, "
            "mark options={solid, draw=black, line width=0.25pt}, mark size=2.2pt] coordinates {"
            + " ".join(coords)
            + "};"
        )
        lines.append(f"\\addlegendentry{{{latex_escape(model)}}}")

    lines.extend([r"\end{axis}", r"\end{tikzpicture}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def timing_plot_rows(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    metrics: List[Tuple[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build long-form raw timing rows from summary rows.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        KB root used to make instance labels readable.
    metrics : List[tuple[str, str]]
        Plot labels and metric keys.

    Returns
    -------
    List[Dict[str, Any]]
        Long-form rows with one row per KB/metric pair.
    """
    rows: List[Dict[str, Any]] = []
    for summary in summaries:
        instance = kb_label(Path(summary["kb"]), kb_root)
        for metric_index, (label, metric) in enumerate(metrics):
            try:
                stats = aggregate_metric(summary, metric)
            except (TypeError, ValueError):
                continue
            if stats is None:
                continue
            mean_seconds, std_seconds = stats
            rows.append(
                {
                    "instance": instance,
                    "metric_label": label,
                    "metric": metric,
                    "metric_rank": metric_index,
                    "mean_seconds": mean_seconds,
                    "std_seconds": std_seconds,
                }
            )
    rows.sort(key=lambda row: (natural_sort_key(row["instance"]), row["metric_rank"]))
    return rows


def write_timing_plot(
    path: Path,
    rows: List[Dict[str, Any]],
    title: str,
    ylabel: str = "Mean time (s)",
    log_y: bool = False,
) -> List[str]:
    """
    Write a grouped raw timing bar plot.

    Parameters
    ----------
    path : Path
        Output plot path.
    rows : List[Dict[str, Any]]
        Long-form rows from timing_plot_rows.
    title : str
        Plot title.
    ylabel : str, optional
        Y-axis label.
    log_y : bool, optional
        Whether to use a logarithmic y-axis.

    Returns
    -------
    List[str]
        Written PDF paths.
    """
    if not rows:
        return []
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/plantor_matplotlib")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/plantor_cache")
    try:
        import matplotlib
        matplotlib.use("Agg")
        matplotlib.rcParams.update(
            {
                "pdf.fonttype": 42,
                "ps.fonttype": 42,
                "font.family": "serif",
                "mathtext.fontset": "dejavuserif",
                "axes.unicode_minus": False,
            }
        )
        import matplotlib.pyplot as plt
    except ImportError as error:
        print(f"matplotlib import failed; skipping grouped timing plot: {error}", file=sys.stderr)
        return []

    metric_labels = sorted(
        {row["metric_label"] for row in rows},
        key=lambda label: min(row["metric_rank"] for row in rows if row["metric_label"] == label),
    )
    domain_groups = rows_by_domain(rows)
    plot_groups = [("all", rows, path)]
    if len(domain_groups) > 1:
        plot_groups.extend(
            (domain, domain_rows, domain_output_path(path, domain))
            for domain, domain_rows in domain_groups
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    written_paths = []
    for domain, domain_rows, output_path in plot_groups:
        label_domain = "" if domain == "all" else domain
        instances = sorted({row["instance"] for row in domain_rows}, key=natural_sort_key)
        value_by_pair = {
            (row["instance"], row["metric_label"]): (row["mean_seconds"], row["std_seconds"])
            for row in domain_rows
        }

        x_positions = list(range(len(instances)))
        group_width = 0.74
        bar_width = group_width / max(len(metric_labels), 1)
        fig_width = max(8.0, len(instances) * (0.62 if label_domain else 0.72))
        fig_height = max(
            6.0,
            5.0
            + max((len(domain_axis_label(instance, label_domain)) for instance in instances), default=0)
            * 0.035,
        )
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        color_cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", [])

        for metric_index, metric_label in enumerate(metric_labels):
            offset = -group_width / 2.0 + bar_width / 2.0 + (metric_index * bar_width)
            xs = []
            heights = []
            errors = []
            for instance_index, instance in enumerate(instances):
                values = value_by_pair.get((instance, metric_label))
                if values is None:
                    continue
                if log_y and values[0] <= 0:
                    continue
                xs.append(x_positions[instance_index] + offset)
                heights.append(values[0])
                errors.append(values[1])
            if xs:
                ax.bar(
                    xs,
                    heights,
                    width=bar_width * 0.88,
                    yerr=errors if any(error > 0 for error in errors) else None,
                    capsize=2.5,
                    label=metric_label,
                    color=color_cycle[metric_index % len(color_cycle)] if color_cycle else None,
                    edgecolor="black",
                    linewidth=0.4,
                )

        ax.set_title(title if domain == "all" else f"{title} - {domain}")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(
            [domain_axis_label(instance, label_domain) for instance in instances],
            rotation=90,
            ha="center",
            va="top",
        )
        ax.set_ylabel(ylabel)
        ax.set_xlabel("KB")
        if log_y:
            y_min, y_max = positive_log_bounds(domain_rows)
            ax.set_yscale("log")
            ax.set_ylim(y_min, y_max)
        ax.grid(axis="y", linestyle=":", linewidth=0.7, alpha=0.7)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize="small", frameon=False)
        fig.tight_layout()
        fig.savefig(
            output_path,
            bbox_inches="tight",
            metadata={
                "Creator": "TP/profile/plot.py",
                "Producer": "matplotlib",
                "Title": title if domain == "all" else f"{title} - {domain}",
            },
        )
        plt.close(fig)
        written_paths.append(str(output_path))
    return written_paths


def write_timing_tikz(
    path: Path,
    rows: List[Dict[str, Any]],
    title: str,
    ylabel: str = "Mean time (s)",
    log_y: bool = False,
) -> bool:
    """
    Write a LaTeX/PGFPlots grouped raw timing bar plot.

    Parameters
    ----------
    path : Path
        Output .tex path.
    rows : List[Dict[str, Any]]
        Long-form rows from timing_plot_rows.
    title : str
        Plot title.
    ylabel : str, optional
        Y-axis label.
    log_y : bool, optional
        Whether to use a logarithmic y-axis.

    Returns
    -------
    bool
        True when a TikZ/PGFPlots file was written.
    """
    if not rows:
        return False

    domain_groups = rows_by_domain(rows)
    if len(domain_groups) > 1:
        for domain, domain_rows in domain_groups:
            domain_path = domain_output_path(path, domain)
            write_timing_tikz(domain_path, domain_rows, title, ylabel, log_y=log_y)

    domain = "" if len(domain_groups) > 1 else domain_groups[0][0]
    instances = sorted({row["instance"] for row in rows}, key=natural_sort_key)
    metric_labels = sorted(
        {row["metric_label"] for row in rows},
        key=lambda label: min(row["metric_rank"] for row in rows if row["metric_label"] == label),
    )
    value_by_pair = {
        (row["instance"], row["metric_label"]): (row["mean_seconds"], row["std_seconds"])
        for row in rows
    }
    max_value = max(row["mean_seconds"] + row["std_seconds"] for row in rows)
    if log_y:
        y_min, y_max = positive_log_bounds(rows)
        y_tick_min = math.floor(math.log10(y_min))
        y_tick_max = math.ceil(math.log10(y_max))
        y_ticks = ",".join(str(exponent) for exponent in range(y_tick_min, y_tick_max + 1))
    else:
        y_min = 0.0
        y_max = max_value * 1.15 if max_value > 0 else 1.0
        y_ticks = ""
    xticks = ",".join(str(index) for index in range(len(instances)))
    xticklabels = ",".join("{" + latex_escape(domain_axis_label(instance, domain)) + "}" for instance in instances)
    x_min = -0.5
    x_max = max(len(instances) - 0.5, 0.5)
    group_width = 0.74
    bar_width = group_width / max(len(metric_labels), 1)
    error_cap_half_width = min(bar_width * 0.18, 0.045)
    colors = ["mplBlue", "mplOrange", "mplGreen", "mplRed", "mplPurple"]

    lines = [
        r"% Requires: \usepackage{pgfplots}",
        r"% Recommended: \pgfplotsset{compat=1.18}",
        r"\definecolor{mplBlue}{HTML}{1F77B4}",
        r"\definecolor{mplOrange}{HTML}{FF7F0E}",
        r"\definecolor{mplGreen}{HTML}{2CA02C}",
        r"\definecolor{mplRed}{HTML}{D62728}",
        r"\definecolor{mplPurple}{HTML}{9467BD}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  width=0.96\textwidth,",
        r"  height=0.42\textwidth,",
        f"  title={{{latex_escape(title if not domain else f'{title} -- {domain}')}}},",
        r"  xlabel={KB},",
        f"  ylabel={{{latex_escape(ylabel)}}},",
        f"  xmin={pgf_number(x_min)}, xmax={pgf_number(x_max)},",
    ]
    if log_y:
        lines.extend(
            [
                r"  ymode=log,",
                r"  log origin=infty,",
                f"  ymin={pgf_number(y_min)}, ymax={pgf_number(y_max)},",
                f"  ytickten={{{y_ticks}}},",
                r"  minor y tick num=8,",
                r"  major tick length=2.6pt,",
                r"  minor tick length=1.8pt,",
                r"  minor tick style={black!70, line width=0.35pt},",
            ]
        )
    else:
        lines.append(f"  ymin=0, ymax={pgf_number(y_max)},")
    lines.extend(
        [
            f"  xtick={{{xticks}}},",
            f"  xticklabels={{{xticklabels}}},",
            r"  tick align=outside,",
            r"  tick pos=left,",
            r"  x tick label style={rotate=90, anchor=east, font=\scriptsize},",
            r"  y tick label style={font=\scriptsize},",
            r"  label style={font=\small},",
            r"  ymajorgrids=true,",
            r"  grid style={dotted, gray!45},",
            r"  minor grid style={dotted, gray!25},",
            r"  legend style={at={(0.02,0.98)}, anchor=north west, draw=black!25, fill=white, fill opacity=0.88, text opacity=1, font=\scriptsize},",
            r"  legend cell align={left},",
            r"  axis line style={black!70},",
            r"  clip=false",
            r"]",
        ]
    )

    error_bar_lines = []
    for metric_index, metric_label in enumerate(metric_labels):
        offset = -group_width / 2.0 + bar_width / 2.0 + (metric_index * bar_width)
        coords = []
        for instance_index, instance in enumerate(instances):
            values = value_by_pair.get((instance, metric_label))
            if values is None:
                continue
            if log_y and values[0] <= 0:
                continue
            x_value = instance_index + offset
            mean_seconds, std_seconds = values
            coords.append(f"({pgf_number(x_value)},{pgf_number(mean_seconds)})")
            if std_seconds > 0:
                lower = mean_seconds - std_seconds
                if log_y:
                    lower = max(lower, y_min)
                else:
                    lower = max(lower, y_min)
                upper = mean_seconds + std_seconds
                if upper > lower:
                    left = x_value - error_cap_half_width
                    right = x_value + error_cap_half_width
                    error_bar_lines.extend(
                        [
                            (
                                r"\draw[black, line width=0.8pt] "
                                f"(axis cs:{pgf_number(x_value)},{pgf_number(lower)}) -- "
                                f"(axis cs:{pgf_number(x_value)},{pgf_number(upper)});"
                            ),
                            (
                                r"\draw[black, line width=0.8pt] "
                                f"(axis cs:{pgf_number(left)},{pgf_number(lower)}) -- "
                                f"(axis cs:{pgf_number(right)},{pgf_number(lower)});"
                            ),
                            (
                                r"\draw[black, line width=0.8pt] "
                                f"(axis cs:{pgf_number(left)},{pgf_number(upper)}) -- "
                                f"(axis cs:{pgf_number(right)},{pgf_number(upper)});"
                            ),
                        ]
                    )
        if not coords:
            continue
        color = colors[metric_index % len(colors)]
        lines.append(
            "\\addplot[ybar, area legend, bar width="
            f"{bar_width * 0.88:.6g}, fill={color}, draw=black, "
            "line width=0.4pt] coordinates {"
            + " ".join(coords)
            + "};"
        )
        lines.append(f"\\addlegendentry{{{latex_escape(metric_label)}}}")

    lines.extend(error_bar_lines)
    lines.extend([r"\end{axis}", r"\end{tikzpicture}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def generate_timing_group_outputs(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    output_root: Path,
    write_plot: bool = True,
    write_tikz: bool = True,
    write_tables: bool = True,
) -> Dict[str, Dict[str, bool]]:
    """
    Generate the predefined grouped raw timing plots.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        KB root for path labels.
    output_root : Path
        Directory where plot artifacts are written.
    write_plot : bool, optional
        Whether to write PDF plots.
    write_tikz : bool, optional
        Whether to write LaTeX/PGFPlots plots.
    write_tables : bool, optional
        Whether to write LaTeX tabular timing tables.

    Returns
    -------
    Dict[str, Dict[str, bool]]
        Per-group flags describing which artifacts were written.
    """
    outputs: Dict[str, Dict[str, bool]] = {}
    for group_name, config in TIMING_PLOT_GROUPS.items():
        rows = timing_plot_rows(summaries, kb_root, config["metrics"])
        stem = config["output_stem"]
        plot_path = output_root / f"{stem}.pdf"
        tikz_path = output_root / f"{stem}_tikz.tex"
        table_path = output_root / f"{stem}_table.tex"
        log_y = bool(config.get("log_y", False))
        plot_paths = (
            write_timing_plot(plot_path, rows, config["title"], config["ylabel"], log_y=log_y)
            if write_plot
            else []
        )
        tikz_written = (
            write_timing_tikz(tikz_path, rows, config["title"], config["ylabel"], log_y=log_y)
            if write_tikz
            else False
        )
        table_written = (
            write_timing_latex_table(table_path, summaries, kb_root, config["metrics"])
            if write_tables
            else False
        )
        outputs[group_name] = {
            "plot": bool(plot_paths),
            "plot_paths": plot_paths,
            "tikz": tikz_written,
            "table": table_written,
            "plot_path": str(plot_path),
            "tikz_path": str(tikz_path),
            "table_path": str(table_path),
        }
    return outputs


def generate_normalized_outputs(
    summaries: List[Dict[str, Any]],
    kb_root: Path,
    metric: str,
    normalized_csv: Path,
    normalized_plot_path: Path,
    tikz_path: Optional[Path] = None,
    write_plot: bool = True,
    write_tikz: bool = True,
) -> Dict[str, bool]:
    """
    Generate normalized CSV and optional plot from summary rows.

    Parameters
    ----------
    summaries : List[Dict[str, Any]]
        Aggregate profile rows.
    kb_root : Path
        KB root for path interpretation.
    metric : str
        Timing metric to normalize.
    normalized_csv : Path
        Output normalized CSV path.
    normalized_plot_path : Path
        Output plot path.
    tikz_path : Optional[Path], optional
        Output LaTeX/PGFPlots path.
    write_plot : bool, optional
        Whether to write the plot.
    write_tikz : bool, optional
        Whether to write the LaTeX/PGFPlots plot.

    Returns
    -------
    Dict[str, bool]
        Flags describing which plot artifacts were written.
    """
    normalized_rows = normalized_model_rows(summaries, kb_root, metric)
    write_normalized_csv(normalized_csv, normalized_rows)
    plot_paths = write_normalized_plot(normalized_plot_path, normalized_rows, metric) if write_plot else []
    tikz_written = (
        write_normalized_tikz(tikz_path, normalized_rows, metric)
        if write_tikz and tikz_path is not None
        else False
    )
    return {"plot": bool(plot_paths), "plot_paths": plot_paths, "tikz": tikz_written}
