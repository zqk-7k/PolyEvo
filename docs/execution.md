# Execution and version correspondence

The repository preserves existing implementations. Packaging changes replace local directory assumptions with explicit inputs and add commands that aggregate the saved evaluation records.

## Saved evaluation reproduction

`reproduce.py` reads only the companion data directory and writes to the chosen output directory. It uses the original relationship aggregation function and original duplicate-handling functions. Preparation coverage is recomputed from the fixed references and recorded complete-match decisions. The evolution check verifies the source tables and paired endpoints. Prediction errors are recomputed from preserved predictions, with the two one-variable printing tasks refitted using their original training-fold standardization and ridge penalty.

The current development relationship endpoint is `taxonomy_v2_r69`. The preparation endpoint is `process_relation_trial_158`, evaluated using `reference_frozen_v2`. Individual preparation documents can originate in earlier candidates when later candidates retained them unchanged. `prediction_versions.csv` records that document-level correspondence. It is therefore necessary to follow the frozen candidate inventory rather than assume all files were rewritten at candidate 158.

The archived general process implementation is the 2026-10-22 `general158-v1` snapshot. It supplies reusable rules for processing source and native records. The source composition files in `historical/preparation` document an additional route used to build the evaluated preparation collection. The portable score reproduction does not depend on the original development directory.

## New extraction

The extraction stages use the prompts and schema distributed in `workflow/extraction`. Configuration records identify the provider, model, reasoning effort, input limits and retry settings. These files are a captured implementation snapshot. They are not evidence that every recorded development candidate used an identical configuration. Exact model or prompt assignments for an individual run must come from that run's saved metadata.

The document workflow reads text, tables and schemes, resolves material and sample identities, extracts preparation and property records, and assembles the linked outputs. The agent components review records and propose changes to prompts and handling rules. Model requests occur only when the user executes the extraction or agent entry points with configured services.

## Historical development

The 146 evaluated preparation candidates are supplied as their source tables and final evaluated records. The package does not describe those saved evaluations as 146 independent runs of a newly introduced controller. The earlier small `self_evolution_recall` pilot is excluded because it does not correspond to the current manuscript results.

The scripts in `historical/preparation` retain the archived composition logic. Re-executing those historical drivers requires their parent candidate and source-acceptance inputs. Those intermediate candidate collections are not required for the portable final-score reproduction and are not duplicated into the data deposit.

## Test and method comparison records

The final PolyEvo test metrics and the earlier baseline comparison results belong to different collections. They retain their recorded dataset labels. The baseline data must not be treated as predictions on the newer test set. KnowMat2 preparation records retain their per-paper model assignments. Metrics omitted from the displayed ChatExtract and PropertyExtractor preparation configurations are not represented as zero capability.
