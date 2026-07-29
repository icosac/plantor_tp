# Experiment Table Scripts

This directory contains small scripts used to regenerate paper-table data from the checked-in experiment artifacts.
Run the scripts from the repository root unless noted otherwise.

## Table Mapping

| Script | Paper table | Input data | Output |
| --- | --- | --- | --- |
| `domain_validation_table.py` | Table 1 | `exp/domain_validation/**/output_cc.txt` | LaTeX table rows printed to stdout |
| `consistency_failure_table.py` | Table 4 | `exp/kb_generation/**/log.log` | LaTeX table by default; CSV with `--format csv` |
| `kb_generation_metrics.py` | Table D.8 | final KB files under `exp/kb_generation/` plus the manual correction counts encoded in the script | text summary by default; LaTeX, CSV, or JSON with `--format` |

## Domain Validation

Regenerate the domain-validation table rows:

```shell
python3 scripts/domain_validation_table.py
```

The script scans `exp/domain_validation` and prints the result table directly.
It uses the same output symbols as the paper table, such as `\cm`, `\wl`, and `\wh`.

## Consistency-Failure Counts

Regenerate the failed-consistency-check hierarchy:

```shell
python3 scripts/consistency_failure_table.py
```

The script parses failed repair iterations from `exp/kb_generation/**/log.log`.
It builds the hierarchy from explicit log lines:

- `[consistency_checks] Failed checks: [...]` gives the failed checker families.
- `[family] Failed checks: [...]` gives the failed checks inside each family.

CSV output is useful for auditing or post-processing:

```shell
python3 scripts/consistency_failure_table.py --format csv
```

Debug logging can be enabled with:

```shell
python3 scripts/consistency_failure_table.py --debug
```

## KB-Generation Metrics

Regenerate the aggregate KB-generation metrics used for Table D.8:

```shell
python3 scripts/kb_generation_metrics.py
```

**NOTICE**: before running the script, the user must manually update `HL_CORRECTIONS` and `LL_CORRECTIONS` in the script to reflect the final corrected Prolog files in `exp/kb_generation`. The script uses these matrices to compute the logical correction counts.

Useful variants:

```shell
python3 scripts/kb_generation_metrics.py --format latex
python3 scripts/kb_generation_metrics.py --format csv --scope summary
python3 scripts/kb_generation_metrics.py --format json --scope instances
```

The script computes KB size metrics from the final corrected Prolog files in `exp/kb_generation`.
The logical correction counts are encoded in the script as the manual correction matrices used for the paper.

## Batch Experiment Runners

`kg_generation.sh` runs `KMS/LLM/llm_gen.py` over the `plantor` KB-generation experiments for a fixed set of configured models.
It writes each run under `exp/kb_generation/plantor/<experiment>/<model>-multi/`, including the model log and generated KB output files.
Additional command-line arguments are forwarded to `llm_gen.py`.

```shell
bash scripts/kg_generation.sh
```

`planner.sh` runs `TP/planner.py` over the generated `plantor` low-level KBs for the Opus configuration.
It saves planner logs, Prolog logs, partial-order/STN visualizations, optimized behavior-tree artifacts, and profiling output under each experiment's `planner_output/` directory.

```shell
bash scripts/planner.sh
```

Both scripts expect the conda environment (or virtual environment) to be active before running.

**NOTICE**: `scripts/planner.sh` should not be run to compute the planner results for the KBs. Instead use the `TP/profile.py` script, which is more efficient and correctly handles the planner output. The `planner.sh` script is only provided as a test script.
