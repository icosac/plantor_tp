<p align='center'>
<a href="https://www.swi-prolog.org/" target="_blank">
    <img src="https://img.shields.io/badge/Prolog-8A2BE2?style=for-the-badge&logo=prolog&logoColor=white" target="_blank" />
</a>
<a href="https://www.python.org/" target="_blank">
    <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" target="_blank" />
</a>
</p>

<p align='center'>
    <h1 align="center">PLanning with Natural language for Task-Oriented Robots (PLANTOR) Enhanced</h1>
</p>

PLANTOR is a modular framework for turning natural-language robotics task descriptions into executable robot plans. The current framework combines LLM-based knowledge-base generation, symbolic task planning in Prolog, partial-order and temporal reasoning in Python, behavior-tree export, and optional web tooling for interactive plan generation and visualization.

----------

## Index

- [Index](#index)
- [Framework Overview](#framework-overview)
- [Repository Layout](#repository-layout)
- [Setup](#setup)
- [LLM Knowledge-Base Generation](#llm-knowledge-base-generation)
- [Task Planning and Temporal Reasoning](#task-planning-and-temporal-reasoning)
- [Behavior Tree Export](#behavior-tree-export)
- [Web GUI](#web-gui)
- [Profiling and Experiments](#profiling-and-experiments)
- [Testing](#testing)
- [Generated Artifacts](#generated-artifacts)
- [Paper and Citation](#paper-and-citation)
- [Authors and contributors](#authors-and-contributors)
  - [Current contributors](#current-contributors)
  - [Past contributors](#past-contributors)
- [License](#license)

## Framework Overview

The enhanced PLANTOR pipeline is organized around three main stages:

1. **Knowledge Management System (KMS)**: converts high-level and low-level natural-language scenario descriptions into Prolog knowledge bases with LLMs. It can run scenario-comprehension checks and repair generated KBs using Prolog consistency checks.
2. **Task Planning Module (TP)**: runs the Prolog planner, maps high-level actions to low-level actions, extracts enablers and start/end links, and builds a Python partial-order plan.
3. **Temporal Reasoning and Export**: converts the partial-order plan into a Simple Temporal Network (STN), checks consistency, optionally optimizes action timings with OR-Tools, and writes HTML/LaTeX diagnostics and behavior-tree XML artifacts.

The GUI wraps several of these pieces through a Flask API and React frontend. The command-line tools remain the most direct way to run reproducible experiments.

## Repository Layout

- `KMS/LLM/`: LLM abstraction layer and KB generation scripts.
  - `llm_gen.py`: main CLI for scenario comprehension and HL/LL KB generation.
  - `llm_base.py`, `llm_factory.py`: provider-independent LLM creation.
  - `LLMOpenAI/`, `LLMAzureOpenAI/`, `LLMAnthropic/`, `LLMGemini/`, `LLMGLM/`, `LLMHuggingFace/`, `LLMVLLM/`: provider backends.
  - `conf/`: model/provider configuration YAML files.
  - `examples/`: few-shot examples for high-level, low-level, and comprehension prompts.
- `TP/`: task planning and temporal reasoning.
  - `planner.py`: main planner pipeline from KB to PO/STN/optimized STN/BT artifacts.
  - `prolog_planner/src/`: symbolic planner, mappings, enabler extraction, consistency checks, and utilities.
  - `src/partial_order.py`: partial-order plan representation.
  - `src/stn/`: Simple Temporal Network construction, optimization, reports, and visualization.
  - `profile.py` and `profile/`: batch profiling over generated KBs.
  - `kb/`: curated example knowledge bases.
- `GUI/`: browser-based interface.
  - `backend/`: Flask API.
  - `frontend/`: React application.
- `docs/`: Sphinx documentation scaffold.
- `exp/`: experiment inputs and outputs.
- `utility/`: shared logging and utility code.

## Setup

System requirements:

- Python 3.9 or later
- [SWI-Prolog](https://www.swi-prolog.org/) available as `swipl`, tested on versions 9.2.8 and 10.0.0. Can be installed with Conda or from the SWI-Prolog website.
- [Node.js](https://nodejs.org/) 16+ for the frontend (suggested using the provided Docker compose setup)
- [OR-Tools](https://developers.google.com/optimization) and provider-specific LLM SDKs depending on the workflow

Create a Python environment with either `venv`/virtualenv or [conda](https://docs.conda.io/en/latest/).

Using `venv`:

```shell
python3 -m venv venv
source venv/bin/activate
```

Using conda:

```shell
conda env create -f conda.yaml
conda activate plantor_tp
```

Conda will automatically install SWI-Prolog. If you are using `venv`, you will need to install SWI-Prolog separately.

To install all the Python dependencies, run:

```shell
python3 -m pip install -r requirements-pip.txt
```

This will install all the required dependencies for the KMS and TP modules. The GUI backend dependencies are installed separately in `GUI/backend/requirements.txt`, and the frontend dependencies are managed by `npm` in `GUI/frontend/package.json`.

If you don't want to install all dependencies, for example you are interested only in one model for the KMS, then you can install only the dependencies for that model. For example, to install only the dependencies for the OpenAI model, run:

```shell
python3 -m pip install -r KMS/LLM/LLMOpenAI/requirements-pip.txt
```

Mind that some dependencies are still required for the KMS module and they are listed in `KMS/LLM/requirements-pip.txt`. 

The tree of dependencies is as follows:

```shell
requirements-pip.txt
├── KMS/LLM/requirements-pip.txt
│   ├── KMS/LLM/LLMOpenAI/requirements-pip.txt
│   ├── KMS/LLM/LLMAzureOpenAI/requirements-pip.txt
│   ├── KMS/LLM/LLMAnthropic/requirements-pip.txt
│   ├── KMS/LLM/LLMGemini/requirements-pip.txt
│   ├── KMS/LLM/LLMGLM/requirements-pip.txt
│   ├── KMS/LLM/LLMHuggingFace/requirements-pip.txt
│   └── KMS/LLM/LLMVLLM/requirements-pip.txt
└── TP/requirements-pip.txt
```

## LLM Knowledge-Base Generation

The KMS takes two descriptions:

- a **high-level description** for symbolic objects, resources, initial state, goal state, and high-level actions;
- a **low-level description** for executable actions and mappings from high-level actions to lower-level steps.

By default, generated files are written to `KMS/LLM/output/`:

- `output_cc.txt`: scenario-comprehension log;
- `output_hl.txt`: high-level generation log;
- `output_ll.txt`: low-level generation log;
- `kb_hl.pl`: generated high-level KB;
- `kb_ll.pl`: generated low-level KB.

Run the built-in example:

```shell
python3 KMS/LLM/llm_gen.py --use-example-queries --no-wait
```

Run on scenario files:

```shell
python3 KMS/LLM/llm_gen.py \
  --query-hl-file path/to/query_hl.txt \
  --query-ll-file path/to/query_ll.txt \
  --output-path path/to/output_dir \
  --conf KMS/LLM/conf/azure_gpt52.yaml \
  --verify-hl 3 \
  --verify-ll 3 \
  --no-wait
```

Useful options:

- `--skip-comprehension`: skip scenario-comprehension checks.
- `--only-comprehension`: run only scenario-comprehension checks.
- `--mandatory-verify`: fail when Prolog consistency checks still fail after repair attempts.
- `--log-file` and `--log-level`: redirect and control logging.

LLM credentials and provider-specific parameters are configured through the selected YAML file in `KMS/LLM/conf/`. Keep secrets in local environment files or shell environment variables, not in committed config, i.e., either `.env` files or `export <VAR>=<VALUE>` in the shell.

## Task Planning and Temporal Reasoning

`TP/planner.py` is the main planning entry point. It runs SWI-Prolog, parses planner output, constructs a partial-order plan, optionally builds and optimizes an STN, and writes visualization/report artifacts.

Run the default curated KB:

```shell
python3 TP/planner.py
```

Run a generated low-level KB without writing HTML:

```shell
python3 TP/planner.py \
  --kb KMS/LLM/output/kb_ll.pl \
  --no-po-html \
  --no-stn-html \
  --no-opt-stn-html
```

Run STN optimization and generate behavior-tree artifacts:

```shell
python3 TP/planner.py \
  --kb KMS/LLM/output/kb_ll.pl \
  --max-depth -1 \
  --optimize-stn \
  --optimize-objective end_time \
  --bt-xml TP/prolog_planner/optimized_bt.xml \
  --bt-save-viz TP/prolog_planner/optimized_bt.html
```

Useful planner options:

- `--from-prolog-log`: replay a saved planner log instead of invoking `swipl`.
- `--save-log`: save the full Python planner log, including same-process logger output and logged subprocess output.
- `--save-prolog-log`: save raw Prolog stdout/stderr for debugging or replay.
- `--po-labels`, `--po-reason-filter`, `--po-no-ll`: control partial-order visualization.
- `--no-assumptions` and `--no-causal`: filter enabler edge classes.
- `--stn-default-min` and `--stn-default-max`: set default action duration bounds.
- `--optimize-integer-time`: solve with integer time variables.
- `--optimize-report-latex`: write a LaTeX description of the optimization model.
- `--optimize-infeasibility-report`: write diagnostics when STN optimization fails.
- `--profile`: emit Prolog and Python phase timings.

The Prolog planner source is in `TP/prolog_planner/src/`. The active KB passed to `TP/planner.py` is consulted together with `bfs_planner.pl`, `mappings.pl`, and `enablers.pl`.

## Behavior Tree Export

The planner can export behavior-tree XML from an optimized STN with `--bt-xml`. Use `--bt-save-viz` when an HTML visualization of that XML is useful for inspection.

The behavior-tree XML is intended as the handoff artifact from task/temporal planning to an execution stack. The repository README does not currently document the execution-side implementation details.

## Web GUI

The GUI consists of a Flask backend and React frontend.

Install and start the backend:

```shell
cd GUI/backend
python3 -m pip install -r requirements.txt
python3 run.py --port 5000 --debug
```

Install and start the frontend in another shell:

```shell
cd GUI/frontend
npm install
npm start
```

The frontend proxies API requests to `http://localhost:5000/`. The backend exposes endpoints for listing LLM configs, validating descriptions, generating high-level and low-level KBs, generating BTs, and generating high-level plan visualizations.

## Profiling and Experiments

Batch planner profiling is available through `TP/profile.py`. By default it searches for `kb_ll.pl` files under `exp/kb_generation/` and writes logs, CSV summaries, plots, and LaTeX tables under `exp/planner/`.

Example:

```shell
python3 TP/profile.py \
  --kb-root exp/kb_generation \
  --output-root exp/planner \
  --runs 10 \
  --timeout 300 \
  --max-depth -1
```

To use the checked-in YAML configuration:

```shell
python3 TP/profile.py --config TP/config/experiments.yaml
```

Mind that the YAML configuration cannot be overridden with command-line arguments.

Use `--only-plot` to regenerate plots/tables from existing CSV data without rerunning the planner.

## Testing

Run the Prolog planner test suite from the repository root:

```shell
swipl -l "TP/prolog_planner/tests/suite.pl" -t "run_all."
```

Individual Prolog test groups can be run directly:

```shell
swipl -l "TP/prolog_planner/tests/applicability_test.pl" -t "run_all_applicability_tests."
swipl -l "TP/prolog_planner/tests/generate_test.pl" -t "run_all_generate_tests."
swipl -l "TP/prolog_planner/tests/utility_test.pl" -t "run_all_utility_tests."
swipl -l "TP/prolog_planner/tests/enablers_test.pl" -t "run_all_enablers_tests."
swipl -l "TP/prolog_planner/tests/consistency_checks_test.pl" -t "run_all_consistency_checks_tests."
swipl -l "TP/prolog_planner/tests/plan_extraction_test.pl" -t "run_all_plan_extraction_tests."
```

For Python syntax checks after planner changes:

```shell
python3 -m py_compile TP/planner.py TP/planner_support.py TP/src/partial_order.py
python3 -m py_compile TP/src/stn/core.py TP/src/stn/optimization.py TP/src/stn/reports.py TP/src/stn/visualization.py
```

## Generated Artifacts

Common generated files include:

- planner logs and visualizations such as `po_graph*.html`, `stn_graph*.html`, `opt_stn.html`, and `optimized_bt.xml`;
- GUI-generated files under `GUI/frontend/public_generated/`;
- GUI-generated LLM outputs under `KMS/LLM/output/`;
- experiment and profiling output under `exp/`;
- local model caches, checkpoints, and provider downloads.

These are intentionally ignored by `.gitignore` unless already tracked as curated fixtures.

For a full list of generated artifacts, visit the following link to the [Zenodo record](https://doi.org/10.5281/zenodo.21630757).


## Paper and Citation

The current pre-print of the PLANTOR framework is available at [arXiv:2502.19135](https://arxiv.org/abs/2502.19135). The paper describes the architecture, design choices, and evaluation of the framework. You can cite the paper as follows:

```
@misc{saccon2025temporalplanningframeworkmultiagent,
      title={A Temporal Planning Framework for Multi-Agent Systems via LLM-Aided Knowledge Base Management}, 
      author={Enrico Saccon and Ahmet Tikna and Davide De Martini and Edoardo Lamon and Luigi Palopoli and Marco Roveri},
      year={2025},
      eprint={2502.19135},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2502.19135}, 
}
```

If interested, the following papers describe previous or alternative versions of the PLANTOR framework:

- When Prolog Meets Generative Models: a New Approach for Managing Knowledge and Planning in Robotic Applications &mdash; [Github](https://github.com/idra-lab/PLANTOR/releases/tag/v0.3) &mdash; [IEEE ICRA 2024 paper](https://doi.org/10.1109/ICRA57147.2024.10610800)
- Automated Generation of MDPs Using Logic Programming and LLMs for Robotic Applications &mdash; [Github](https://github.com/idra-lab/prolog_mdp/releases/tag/RALv2) &mdash; [IEEE RA-L 2025 paper](https://doi.org/10.1109/LRA.2025.3643276)

## Authors and contributors

### Current contributors

- [Enrico Saccon](https://github.com/icosac), University of Trento, enrico.saccon[at]unitn.it
- [Edoardo Lamon](https://github.com/edoardolamon), University of Trento, edoardo.lamon[at]unitn.it
- [Matteo Saveriano](https://github.com/matteosaveriano), University of Trento, matteo.saveriano[at]unitn.it
- Luigi Palopoli, University of Trento, luigi.palopoli[at]unitn.it
- [Marco Roveri](https://github.com/marcoroveri), University of Trento, marco.roveri[at]unitn.it

### Past contributors

- [Ahmet Tikna](https://github.com/IngTIKNA)
- [Davide De Martini](https://github.com/davidedema), University of Trento, davide.demartini[at]unitn.it

## License

The software in this repository is licensed under the Apache License,
Version 2.0. See [LICENSE](LICENSE).

Experimental data and artifacts distributed separately through Zenodo are
licensed as specified in the corresponding Zenodo record.
