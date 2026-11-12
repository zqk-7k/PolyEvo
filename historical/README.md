# Archived implementation snapshots

`checkpoints/` contains the 72 original producer snapshots whose code hashes occur in the 145 displayed post-baseline preparation evaluations. The data file `figures/figure2/preparation_versions.csv` maps each recorded evaluation to its candidate freeze and producer file. These are archived drivers, not the entry points for final-score reproduction. Their complete execution requires their original parent candidate and source-acceptance inputs. The release uses `reproduce.py` to recompute the displayed endpoints from the deposited predictions, references and decisions.

`preparation/` contains the final composition implementation and its local utility module. The general reusable process engine is in `workflow/process_workflow/`.
