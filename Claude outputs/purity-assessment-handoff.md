# Handoff: pixel purity assessment for clustered precincts

For Claude Code, in the `voting-unmixing-ph` repo, conda env `voting_unmixing_ph_env`.

## Goal

One notebook that answers: are the clustered-precinct data pure enough, or well spread enough, for VCA and MVSA to be trusted at p = 4? Two tracks:

- Part A: the geometric diagnostics used or implied by the unmixing papers themselves.
- Part B: statistical checks (Dirichlet fits, simulation calibration, resampling).

Out of scope: interpreting the archetypes, changing the main pipeline, writing paper text.

## Step 0: inspect before writing anything

Read the repo and report back in a short note at the top of the notebook:

1. Where the precinct matrix is loaded and which normalization is applied (per voter, sum, or max).
2. Which functions already exist for HySime, VCA, MVSA, NMF, SUnSAL, and Hungarian matching (`tools.py` first). Reuse them. Do not reimplement.
3. Whether the MVSA code uses the hard constraint (QY >= 0) or the hinge soft constraint, and whether it does the affine projection step. Quote the lines.
4. Whether precinct metadata has region or province and registered-voter or turnout counts.

Stop and ask Hannah if (1) or (3) is ambiguous. Follow the repo's notebook convention (`.ipynb` or `.py` with `# %%`).

## Definitions

- `Y`: precinct by candidate matrix as used by the main pipeline. `p = 4`.
- `M_vca`, `M_mvsa`, `M_nmf`: endmember estimates from the existing pipeline.
- Work in the reduced space MVSA uses (signal subspace, then affine projection), as in Li et al. 2015 Sec. II-A.
- `A_free`: barycentric coordinates with sum-to-one only, no sign constraint. `A_con`: SUnSAL abundances (non-negative, sum-to-one).

## Known limitation to state in the notebook

Every purity measure below is computed relative to an estimated simplex. If MVSA returns a simplex that is too small, which is the documented failure on highly mixed data, the precincts will look purer than they are. Part A alone cannot detect this. Part B2 exists to calibrate it.

## Part A: geometric diagnostics

Compute each for `M_vca`, `M_mvsa`, `M_nmf`. Put new functions in a `purity.py` module with docstrings citing the source.

**A1. Outside-the-simplex count** (Li et al. 2015, Sec. V)
- Count precincts with any `A_free` coordinate below `-tol`, for tol in {0, 1e-3, 1e-2}. Report count and share.
- Also report the distribution of the most negative coordinate.
- Note: with hard-constraint MVSA the count is zero by construction, so for MVSA the informative outputs are A2 and A4.

**A2. Facet coverage** (Li et al. 2015 Sec. II and V; Nascimento & Bioucas-Dias 2012 Sec. I)
- Facet j is where archetype j has zero abundance. For delta in {0.01, 0.02, 0.05}, count precincts with `a_j <= delta`.
- Condition from the papers: at least p - 1 = 3 points on or near each facet. Report counts per facet.
- Also check that the near-facet points are spread over the facet and not bunched: report the range of the other three coordinates and the rank of those points.

**A3. Maximum-abundance purity** (Li et al. 2015 Sec. IV-B, purity as maximum abundance)
- Per precinct: `max_j a_j`. Histogram overall and by dominant archetype.
- Per archetype: number of precincts with purity above {0.6, 0.8, 0.9, 0.95, 0.99}. Reference caps from the papers: 0.6 (VCA 2005 test), 0.8 (MVSA tests).

**A4. Lin et al. 2015 purity levels**
- `rho`: maximum 2-norm of the abundance vectors. Also report the best 2-norm among precincts dominated by each archetype.
- Reference threshold: 1/sqrt(p-1) = 0.577. `rho` above it is necessary, not sufficient.
- `gamma`: NP-hard in general, but tractable at p = 4 because abundances live in 3 dimensions. Proposed method (our derivation, not from the paper, so it must be validated):
  1. Map abundances to 3D coordinates of the affine set sum = 1.
  2. `scipy.spatial.ConvexHull` on the points.
  3. For each hull facet, solve the small convex problem: minimize ||s|| over s in the unit simplex subject to s lying on or beyond that facet's outer half-space. Skip facets with no feasible point.
  4. `gamma` is the smallest of these values, capped at 1.
- Validation required before use: generate Lin-style data (Dirichlet, reject vectors with 2-norm above r) for r in {0.5, 0.6, 0.7, 0.8, 0.9}, large N. The function should return a value close to r. Also check gamma = 1 when the four unit vectors are included.

**A5. Optional: pixel purity index** (Boardman's PPI, as described in VCA 2005 Sec. I)
- Project onto about 1000 random directions, count how often each precinct is an extreme. Use only as a descriptive cross-check on which precincts A3 flags.

**A6. Stratification, if metadata exists**
- Repeat A2 to A4 summaries by region. Purpose: see whether near-pure or near-facet precincts come from a few places.

## Part B: statistical approaches

**B1. Dirichlet fits to abundances** (model from Nascimento & Bioucas-Dias 2012)
- Fit a single Dirichlet by maximum likelihood. Report the parameter vector and its sum.
- Fit Dirichlet mixtures with k = 1..5 and select k by BIC or MDL.
- Abundances that are exactly 0 break the likelihood. Shrink with `(a * (N - 1) + 1/p) / N` before fitting and report how sensitive the estimates are to this.
- Compare with the benchmark settings in that paper: symmetric theta = 1 (points reach facets), 5, and 10 (highly mixed, geometric methods fail).
- Do this for abundances relative to `M_mvsa` and `M_nmf`. Same circularity caveat as Part A.

**B2. Simulation calibration** (the main evidence)
- Truth: `M_mvsa` as the endmember matrix, real N, real candidate count.
- Abundance scenarios:
  - (a) draws from the B1 fitted mixture;
  - (b) symmetric Dirichlet, theta in {0.5, 1, 2, 5, 10};
  - (c) Dirichlet(1) with maximum abundance capped at {1.0, 0.9, 0.8, 0.7, 0.6};
  - (d) Dirichlet(1/p) with 2-norm capped at {0.9, 0.8, 0.7, 0.6, 0.55, 0.5}, which brackets the 0.577 threshold.
- Noise: (i) none; (ii) Gaussian matched to the residual of the real fit; (iii) if voter counts exist, binomial sampling of each candidate's vote share using the real per-precinct voter counts. Say which were run.
- Run the unchanged pipeline (VCA, MVSA, NMF, then SUnSAL) on each. At least 30 replicates per cell, fixed seeds.
- Metrics after Hungarian matching: spectral angle per archetype, Frobenius endmember error, abundance RMSE.
- Also run Part A on each simulated set and compare with the known truth. This shows how biased the Part A numbers are.
- Outputs: error against purity level per method, with the real data's estimated position marked using B1 and A3/A4.

**B3. Resampling**
- Bootstrap precincts (200 resamples if runtime allows), rerun MVSA, and report the spread of the endmembers and of A2 to A4.
- Minimum-volume estimates depend on extreme points, where the ordinary bootstrap is known to behave poorly. Also run an m-out-of-n subsample (m = N/2) and report both. Label these intervals as indicative.

**B4. Optional**
- If a maintained implementation of a statistical unmixer (DECA or similar) is found, run it and compare endmembers with MVSA. Do not write one in this pass.

## Deliverables

1. `purity.py` with the Part A functions and the Dirichlet fitting helpers, plus tests:
   - true endmembers on noiseless synthetic data give zero outside count;
   - `gamma` validation as in A4;
   - Dirichlet fit recovers known parameters on synthetic draws.
2. The notebook, sections in the order above, each ending with a two or three line plain summary of what was found.
3. One summary table: rows VCA, MVSA, NMF; columns outside share, minimum facet count, precincts above 0.8 purity per archetype, rho, gamma, fitted Dirichlet sum.
4. Figures: purity histograms by archetype; 2D projections of the data with each simplex drawn; facet coverage bars; B2 error against purity curves; B3 spread of endmembers.

## Rules

- Do not tune pipeline parameters to make diagnostics look better.
- Report numbers as found, including ones that count against MVSA.
- If the convex hull or bootstrap is too slow at full N, subsample, say so, and show that results are stable across two subsample sizes.
- No claims that purity is "verified." The notebook reports evidence for and against each condition.

## Sources for the methods

- Nascimento & Bioucas-Dias 2005, IEEE TGRS 43(4):898-910 (VCA; PPI description).
- Li et al. 2015, IEEE TGRS 53(9):5067-5082 (MVSA; facet condition; outside-simplex symptom; purity as maximum abundance).
- Nascimento & Bioucas-Dias 2012, IEEE TGRS 50(3):863-878 (DECA; Dirichlet benchmarks).
- Lin et al. 2015, IEEE TGRS 53(10):5530 (rho, gamma, threshold).
