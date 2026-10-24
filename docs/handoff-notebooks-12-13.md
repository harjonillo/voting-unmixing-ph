# Handoff: run notebooks 12 and 13 (for Claude Code)

Paste this file, or point Claude Code at it, from the root of the
`voting-unmixing-ph` repo on Hannah's Mac.

## Context

Two new notebooks back the paper outline in the sibling repo
`../voting-unmixing-ph-paper/outline-organized.tex`:

- `notebooks/12_model_selection_tables.ipynb`: reads baked outputs only
  (`data/distinctness/`, `data/order_sensitivity/`, sweep `meta.json` and
  `loadings_mean.csv`). Tables for distinctness vs p, order and seed
  sensitivity, RMSE vs p, MVSA vs NMF agreement, and run provenance.
- `notebooks/13_negative_loadings.ipynb`: where MVSA's negative loadings sit,
  reruns the sweep's p = 4 reference runs (MVSA and NMF) from the raw CSVs,
  checks that reconstructed shares are non-negative, tests whether the
  mostly-negative archetype tracks ballot width (names per ballot), and
  measures how much of each method's squared error is ballot-width mismatch.

Both were written and test-run end to end in a cloud sandbox (Python 3.13,
pandas 3.0, numpy 2.5, scipy 1.18, scikit-learn 1.9; no pyarrow, no Jupyter;
`tqdm` stubbed) and saved **without outputs**. They have not yet been
run in `voting_unmixing_ph_env`.

## Task

1. Activate the environment and run both notebooks in place, from the repo root:

   ```bash
   conda activate voting_unmixing_ph_env
   jupyter nbconvert --to notebook --execute --inplace \
     --ExecutePreprocessor.timeout=3600 notebooks/12_model_selection_tables.ipynb
   jupyter nbconvert --to notebook --execute --inplace \
     --ExecutePreprocessor.timeout=3600 notebooks/13_negative_loadings.ipynb
   ```

   Notebook 12 takes seconds. Notebook 13 takes several minutes (it loads all five
   elections and runs MVSA, NMF and SUNSAL once per year and method).

2. If a cell fails, fix the notebook (not `src/`) and rerun. Likely friction:
   pandas version differences in `groupby`/`pivot_table` calls, or a missing
   package. Report what you changed.

3. Check the results against the sandbox run (expected values below). Report any
   difference larger than rounding.

4. Fill in the two "Summary" markdown cells at the end of each notebook with
   the actual numbers (short bullet points, no interpretation beyond what the
   numbers show).

5. Report back to Hannah: the summary bullets, the section 6 table of notebook
   13, and anything that did not match.

## Expected values (sandbox run)

Notebook 12:

- Section 0: provenance flags 2025 as the only year where the MVSA sweep
  (excluded OV, LAV) differs from the NMF sweep and the current config
  (OV, LAV, OAV).
- Section 1, MVSA min pairwise top-12 Jaccard distance, p = 2..7, 2025:
  1.00, 0.74, 0.86, 0.50, 0.50, 0.40. Metric consistency: `jac12` has
  "d(5) < min d(2..4)" in 5/5 years for MVSA and 4/5 for NMF.
- Section 2, at p = 4: NMF less order-sensitive in 5/5 years, more
  seed-sensitive in 4/5.
- Section 3: NMF RMSE above MVSA at every p in every year; MVSA 2025 p = 4
  RMSE 0.0476.
- Section 4: in every year the worst-matched MVSA archetype has a negative
  column sum.

Notebook 13:

- Section 2: each reference run's RMSE equals the sweep's reference RMSE
  (e.g. 2013 MVSA 0.094249, 2022 MVSA 0.059270). In 2019 one MVSA archetype
  matches the trial mean only at cosine about 0.70; that is expected (the
  trial mean averages over discrete solutions, notebook 09).
- Section 3: MVSA reconstructions have negative entries in 1.2 / 16.4 / 22.2 /
  10.9 / 18.9 % of precincts (2013 / 2016 / 2019 / 2022 / 2025); NMF none.
- Section 4: Spearman r between the mostly-negative archetype's abundance and
  precinct width w: -0.96 / -0.78 / -0.89 / -0.95 / -0.98. Mean w: 13.08 /
  13.54 / 7.12 / 7.03 / 6.47.
- Section 5: width share of squared error, NMF 32.0 / 22.6 / 42.6 / 39.0 /
  35.5 %, MVSA 2.0 / 2.7 / 1.7 / 1.5 / 1.8 %. SD of NMF's reconstructed width
  about 0.002.
- Section 6: reference-run column sums of the mostly-negative archetype
  -6.65 / -12.2 / -6.06 / -7.24 / -18.42 (trial means -7.12 / -8.44 / -8.99 /
  -4.54 / -9.86).

## Constraints

- Do not modify `src/`, `scripts/`, other notebooks, or anything under `data/`.
- Leave any uncommitted changes that are not yours alone.
- Do not commit or push unless Hannah asks.
- Do not edit the paper outline unless Hannah asks; if she does, only update
  numbers in the tables and evidence bullets, not the wording of claims.

## Optional follow-up (only if Hannah asks)

Rerun the 2025 MVSA sweep with the current config so both methods use the same
precincts, then re-bake and rerun:

```bash
python scripts/run_sweep.py --config configs/config_2025.ini
python scripts/bake_distinctness.py   # check its CLI for year/method flags
python scripts/bake_order_sensitivity.py
```

Then rerun notebooks 12 and 13 and report what changed for 2025.
