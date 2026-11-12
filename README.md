# PolyEvo

Code for **PolyEvo: An evolving workflow for polymer literature extraction**.

PolyEvo extracts polymer samples, property values, measurement conditions and preparation records. Saved stage records support changes to extraction prompts, record assembly and process links. The repository contains the existing extraction implementation, prompts, schemas, process recovery rules and utilities for reproducing the manuscript results.

## Contents

| Directory | Contents |
| --- | --- |
| `workflow/extraction/` | Extraction stages, configuration, prompts, schemas and agent components |
| `workflow/ocr/` | Document conversion and organization |
| `workflow/process_workflow/` | Archived general process recovery implementation and tests |
| `workflow/compat/` | Dependencies used by the process integration tests |
| `polyevo_release/` | Original scoring, projection, retention and prediction functions |
| `scripts/` | Figure reproduction |
| `docs/` | Component versions, execution modes and data mapping |
| `historical/` | Implementation files documenting the archived preparation composition route |

## Install

Use Python 3.11 or later. The tested environment is recorded in `requirements-reproduction.txt`.

```sh
python -m venv .venv
python -m pip install -r requirements-reproduction.txt
```

The extraction implementation has additional provider and document-conversion requirements described in its configuration. Credentials are supplied through environment variables. `.env.example` contains variable names only.

## Reproduce the reported results

Extract the accompanying data archive to `PolyEvo-data`. Supply its location explicitly, so execution does not depend on the original project directory.

```sh
python reproduce.py --data /path/to/PolyEvo-data --output outputs/reproduction
```

The command verifies the development relationship scores, preparation coverage, evolution endpoints and the 13 prediction tasks. It also replays duplicate handling on selected archived records. The calculations use the preserved scientific decisions. They do not make model requests or create new semantic judgments.

Individual checks are available through `--task relationships`, `preparation`, `evolution`, `prediction`, `retention` or `baselines`.

```sh
python scripts/draw_evolution.py --data /path/to/PolyEvo-data --output outputs/figures
python -m unittest discover -s workflow/process_workflow -t workflow -p "test_*.py" -q
```

The first command recreates Figure 2 from its source tables. The second exercises the process rules with synthetic software fixtures. Synthetic fixtures are separate from the scientific evaluation data.

## Extract information from documents

The production entry points expose their options through:

```sh
python workflow/pipeline_runner.py --help
python workflow/extraction/batch_runner.py --help
python workflow/process_workflow_runner.py --help
```

`pipeline_runner.py` starts with PDFs. `batch_runner.py` starts from processed document blocks. `process_workflow_runner.py` applies process recovery to an input manifest and supports preparing source-grounded requests and publishing supplied model responses. The default provider configuration is in `workflow/extraction/config/pipeline.yaml`. New extraction requires the configured model and document services.

See [execution modes](docs/execution.md) for the distinction between reproducing saved evaluations and generating new extractions. [Component versions](docs/component_versions.csv) identifies the source snapshots included here.

## Data

The companion data and archived code are available in [Zenodo](https://doi.org/10.5281/zenodo.24152249). The data archive contains development records, references, individual scoring decisions, figure source tables, method comparisons and prediction results. Final test results are included as summary metrics. `manuscript_map.csv` links the main and supplementary figures and tables to their source files.

## Licence

Original code is distributed under the [MIT licence](LICENSE). Original companion data use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See `THIRD_PARTY_NOTICES.md` for third-party material.
