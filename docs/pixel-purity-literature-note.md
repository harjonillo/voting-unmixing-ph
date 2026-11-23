# Pixel purity and the validity of VCA, MVSA and NMF: literature note

Compiled 2026-11-16, revised the same day to match what was implemented. Scope: what the unmixing literature says about pixel purity as a condition for VCA, MVSA and NMF, which of the papers' own checks were run on the precinct data, and what they show. The checks cover every year and normalization of the sweep, p = 2 to 7.

Reading status is marked per paper:
- [local PDF] = the PDF is in `research_hyperspectral_unmixing/papers/`, and the sections cited here were checked against it on 2026-11-16.
- [extracted] = read in full text through a text-extraction tool. Figures not seen. Check specific numbers against the PDF before citing.

Only the [local PDF] papers are used for the assumptions table and for the checks. The others are background.

## Terms

Translation used throughout: pixel = clustered precinct, spectral band = candidate, endmember = voting archetype.

**Model**
- Linear mixing model: each precinct's vote vector y is a weighted average of p archetype vectors, y = M s, plus noise. M has one column per archetype.
- Endmember: one column of M. The vote profile of a precinct made up entirely of one voter type.
- Abundance: the weight s_j of archetype j in a precinct. Abundances are non-negative and sum to one.
- p: the number of endmembers. Lin et al. write N for the same thing.

**Geometry**
- Simplex: the set of all mixtures of the p endmembers. A line segment for p = 2, a triangle for p = 3, a tetrahedron for p = 4. Under the model, every noise-free precinct lies inside it.
- Vertex: a corner of the simplex. The vertices are the endmembers.
- Facet: a flat side of the simplex. It is the set of mixtures in which one archetype has zero abundance, so it is spanned by the other p - 1 vertices. For p = 3 the facets are the three edges of the triangle. For p = 4 they are the four triangular faces of the tetrahedron. "Samples on a facet" means precincts with essentially none of one archetype.
- Why "p - 1 points per facet": a facet is a flat piece of dimension p - 2, and it takes p - 1 points in general position to fix where such a piece lies (two points fix a line, three fix a plane). With fewer data points on it, the data do not pin that side of the simplex down. This explanation is ours. The papers state the condition without deriving it.
- Convex hull: the smallest convex set containing the data points.
- Affine projection: fitting the best (p - 1)-dimensional flat through the data and projecting onto it. After this step, coordinates relative to p points in the flat sum to one automatically.

**Purity**
- Pure pixel: a precinct whose abundance vector has a single 1 and zeros elsewhere. It sits exactly on a vertex.
- Pure pixel assumption: at least one pure pixel exists for every endmember.
- Purity of a pixel (Li et al. 2015, after Berman et al. 2004): its largest abundance. "Maximum purity 0.8" means no pixel in the data has any abundance above 0.8.
- Highly mixed data: no points near the vertices and none near the facets. The data cloud sits in the interior of the simplex.
- Maximum purity of a data set (Li et al. 2015): the largest purity of any pixel in it. It is 1 when every endmember has a pure pixel.
- Separability (Donoho & Stodden 2003, as stated in Javadi & Montanari 2020): for each archetype there is a sample with weight 1 on it and 0 on the others. For the weights, this is the pure pixel assumption.
- Best pixel purity, rho (Lin et al. 2015): the largest Euclidean length of any abundance vector in the data. Length is 1 for a pure pixel and 1/sqrt(p) for an equal mixture. Background only: not computed here.
- Uniform pixel purity, gamma (Lin et al. 2015): the largest r such that every possible abundance vector of length at most r lies inside the convex hull of the observed abundance vectors. It measures how well the data fill the simplex in all directions. gamma = 1 is the pure pixel assumption. Background only: not computed here.
- Sufficiently scattered (Fu et al.): a condition on the abundance matrix that Fu et al. 2016 prove equivalent to gamma > 1/sqrt(p - 1).

**Methods**
- Pure-pixel methods: return actual data points as endmembers. VCA, N-FINDR, PPI.
- VCA (vertex component analysis): repeatedly projects the data onto a direction orthogonal to the endmembers found so far and takes the most extreme pixel.
- PPI (pixel purity index): projects the data onto many random directions and scores each pixel by how often it is an extreme.
- Minimum-volume methods: find the smallest simplex that contains all the data. Its vertices need not be data points. MVSA, MVES, SISAL, MVC-NMF.
- NMF (non-negative matrix factorization): factors the data into non-negative archetypes and non-negative weights by minimizing a reconstruction loss. It has no volume criterion and does not return data points.
- Hard constraint: every data point must lie inside the simplex (all abundances non-negative).
- Soft constraint, or hinge: points may fall outside at a penalty proportional to how negative their abundances are. Meant for noise and outliers.
- Statistical methods: fit a probability model for the abundances instead of a pure geometric criterion. DECA models them as a mixture of Dirichlet distributions.
- Dirichlet distribution: a distribution over abundance vectors. With all parameters equal to theta: theta = 1 is uniform over the simplex, larger theta concentrates points near the centre, theta below 1 pushes them toward vertices and facets.
- HySime: the method used to estimate the signal subspace and the number of endmembers.

**Evaluation**
- Identifiability: whether the criterion's solution is the true endmember matrix, uniquely.
- SNR: signal-to-noise ratio in dB. Higher is cleaner.
- Spectral angle (SAD, SAE, SMAE): the angle between a true endmember and its estimate. Zero is perfect.
- Outlier: a point that does not follow the model. A single one outside the true simplex forces a hard-constraint simplex to grow.
- NP-hard: no efficient general algorithm is known. Stated for computing gamma and for checking the sufficiently scattered condition in arbitrary dimension.

## Bottom line

What each method assumes:

| Method | Assumption about purity | Source |
|---|---|---|
| VCA (and N-FINDR) | At least one pure pixel per endmember. Without it, the method returns the most pure pixels available. | Nascimento & Bioucas-Dias 2005, Sec. I, III, V |
| MVSA | No pure pixels needed. At least p - 1 samples on, or in the neighborhood of, each facet. Hard constraint, noise negligible after projection. | Li et al. 2015, Sec. II, V; Nascimento & Bioucas-Dias 2012, Sec. I, IV; Bioucas-Dias et al. 2012, Fig. 6 |
| NMF | The factorization is unique only if the weights (or the archetypes) are sufficiently sparse, a regime captured by separability. | Javadi & Montanari 2020, Sec. 1, after Donoho & Stodden 2003 |

- VCA is valid as an estimator only if pure pixels exist. Its own authors say so and show the failure.
- MVSA does not need pure pixels, but it needs precincts on or near every facet. It degrades steadily as mixing increases.
- NMF needs separability or enough sparsity for its answer to be unique. Without it, different archetypes fit the data equally well.
- The formal guarantee for minimum volume (Lin et al. 2015) is noiseless, assumes abundances sum to one, and concerns the global optimum. The quantity it uses, gamma, is NP-hard to compute. We do not compute it, or rho.
- The only purity check the papers run on real data is the count of samples outside an estimated simplex (Li et al. 2015, Sec. V). No paper gives a test of the facet condition for real data, so it is not tested.

## What was checked on the precinct data

Two measures, both taken from Li et al. 2015 and both relative to an estimated simplex, not the true one. Code: `src/unmixing/purity.py`. Results: `notebooks/11_pure_precincts.ipynb` and the site's Model comparison tab. Run of 2026-11-16; values are means over 50 trials per sweep.

1. **Share of precincts outside the estimated simplex** (Sec. V). A precinct is outside when its abundances under sum-to-one alone, with no sign constraint, have a negative entry (float tolerance 1e-8; the paper gives no tolerance).
2. **Purity as maximum abundance** (Sec. IV-B), from the pipeline's SUNSAL abundances: per archetype, the highest purity among the precincts it dominates, and the number of precincts above the papers' caps of 0.8 and 0.6.

Results, in the papers' terms:

- **VCA.** If every archetype had a pure precinct and the linear model held, no precinct would be outside the VCA simplex. At each run's HySime k, 0.41 to 0.96 of precincts are outside (0.80 or more in seven of eight runs; 0.41 ± 0.42 for 2013 at k = 3). N-FINDR, one run each, gives 0.73 to 0.99, except 0.002 for 2013. At p = 3 the share is below 0.05 in three runs (2022 per ballot, 2022 per vote, 2025 per vote). For comparison, Li et al. find more than 99.9% of Cuprite outside; the precinct data approach that only at p >= 6.
- **MVSA.** The outside count is 0 by construction, so that check says nothing about MVSA. Relative to the MVSA simplex there are no pure precincts from p = 3: the least-pure archetype's best precinct has purity 0.47 to 0.86 at p = 3 and 0.26 to 0.36 at p = 7. This is the situation MVSA is built for, but it does not show that the facet condition holds. The papers' failure case, highly mixed data giving a simplex smaller than the true one, cannot be ruled out with these measures.
- **NMF.** Its simplex leaves 0.01 to 0.52 of precincts outside, more as p grows. Every archetype has a precinct with purity near 1 up to p = 3 (per vote, up to p = 4), but precincts outside the simplex are pulled onto its boundary, which raises their purity, so this does not show separability.
- **By construction, not evidence:** VCA's purity of 1 (its archetypes are precincts), MVSA's outside count of 0 (hard constraint), and everything at p = 2 for VCA, MVSA and N-FINDR (all end at the two extreme precincts of a line).
- **Purity above 1.** SUNSAL abundances of a small share of precincts outside the simplex sum to slightly more than one, so the largest purity under NMF reaches 1.13. Purity is not rescaled.

Considered and not done, because the papers do not do them on real data or they are not in the papers on hand: counts of precincts near each facet (needs a distance threshold no paper gives), Lin et al.'s rho, VCA pick lists, and replications of the papers' toy experiments with purity caps and Dirichlet mixing.

## Our pipeline, for reference (repo checked 2026-11-16)

- `mvsa` in `src/unmixing/endmember_extraction.py` is the hard-constraint version (Q Y >= 0, interior point). No hinge.
- It projects to a (p - 1)-dimensional affine set by PCA, initializes with VCA and expands that simplex, and runs at most 10 outer iterations with relative tolerance 1e-2.
- Abundances come from SUNSAL with non-negativity and sum-to-one, for every method.
- VCA is also run as a method of its own (`--method vca`), with the same pipeline run, sweeps, bakes and site view as MVSA and NMF. NMF is scikit-learn's, with the KL loss.
- Sweeps: 50 trials per p, p = 2 to 7, for per ballot (2019, 2022, 2025) and per vote (2013 to 2025). Each sweep folder holds the per-trial purity measures (`purity_trials.parquet`, `purity_stats.parquet`) and the reference trial's counts by purity threshold (`purity_ref.parquet`).
- Notebook 16 shows MVSA vertices several cloud radii outside the precinct cloud. It is the counterpart of the papers' scatterplots (Bioucas-Dias et al. 2012, Fig. 6; Nascimento & Bioucas-Dias 2012, Fig. 3).
- The earlier notebook 11 defined a pure precinct by vote concentration. It is in git history at commit `3176c2c`.

## Per paper

### Nascimento & Bioucas-Dias 2005, VCA. IEEE TGRS 43(4):898-910. [local PDF]
- Assumes at least one pure pixel per endmember (Sec. I, II-B, V). Called "a strong requisite that may not hold in some datasets."
- Without pure pixels it still returns the most pure pixels available (Sec. I).
- No-pure-pixel test (Sec. III, Figs. 6-7): p = 3, every pixel with any abundance below 0.2 removed, so the largest abundance left is 0.6. Endmember angle error is about 10 degrees at every SNR. With pure pixels (Fig. 5b) it is near 0 at high SNR and about 7 degrees at the noisiest setting.
- Authors' conclusion: this family is "more affected by the lack of pure pixels than by low SNR."
- More pixels help only because pure pixels become more likely.
- For us: VCA output is not a defensible archetype estimate unless near-pure precincts are shown to exist. Its use to initialize MVSA needs no purity argument. The 0.6 purity cap used in notebook 11 comes from the Sec. III experiment.

### Li & Bioucas-Dias 2008, MVSA (IGARSS). [local PDF]
- Written for the case where the pure pixel assumption fails.
- Starts from the VCA endmembers and inflates that simplex so more pixels fall inside. The authors report the inflated start lands "systematically in the attraction basin" of a good local minimum. An observation, not a proof.
- Simulations remove every pixel with an abundance above 0.8 (Sec. 3). MVSA recovers the endmembers. VCA gives the worst estimate.
- Introduces the hinge soft constraint for noise and outliers.
- States that minimum-volume algorithms are very sensitive to outliers and that the problem has many local minima.
- For us: the VCA step is justified as initialization only. Local minima are acknowledged, which is where cross-run stability fits.

### Li et al. 2015, MVSA journal version. IEEE TGRS 53(9):5067-5082. [local PDF]
- Condition for correctness: enough samples on the facets (Sec. II). Called a "fundamental assumption": at least p - 1 samples on, or in the neighborhood of, each facet (Sec. V).
- Defines the purity of a pixel as its maximum abundance fraction (Sec. IV-B, after Berman et al. 2004).
- Its simulations use two purity settings only: maximum purity 1 and 0.8. Nothing below 0.8. This is the source of the 0.8 cap in notebook 11.
- On the real Cuprite scene the authors say the assumption fails and the problem is ill-posed. Their symptom: nearly all pixels lie outside the estimated simplex (47,733, 47,732 and 47,734 of 47,750 for VCA, N-FINDR and successive volume maximization, with "a similar pattern" for minimum-volume algorithms). Workaround: run VCA 30 times, keep the largest simplex, project the data onto an inflated version of it, then run MVSA. The epsilon = 0.01 in the paper belongs to that inflation step (Fig. 5b); it is not a tolerance for counting samples outside.
- Uses the hard constraint only and assumes noise is negligible after projection (Sec. II-B). The soft constraint is future work.
- Restores sum-to-one by affine projection and notes this can shift angles (Sec. II-A).
- Results are sensitive to the estimated number of endmembers (Sec. V).
- For us:
  - Facet coverage, not vertex purity, is the condition to argue for.
  - The count of precincts outside the simplex is a diagnostic the authors use themselves. It is the first check in notebook 11; the purity definition is the second.
  - Our code matches this version (hard constraint), so its statements about noise apply to us.
  - The sum-to-one step interacts with the normalization choice and needs a sentence in the paper.

### Nascimento & Bioucas-Dias 2012, DECA. IEEE TGRS 50(3):863-878. [local PDF]
- Calls p - 1 pixels per facet a "necessary condition" for minimum-volume methods (Sec. I, IV). Highly mixed data are "beyond the reach" of geometric methods.
- Experiment I (Sec. IV-A, Tables V to VII): p = 3, 10,000 pixels, no noise, symmetric Dirichlet abundances with theta = 1, 5 and 10 (more mixed as theta grows). MVSA degrades with mixing but stays ahead of VCA at every level.
- More pixels help slightly (Experiment III). In the highly mixed case, added noise did not hurt MVSA much, which the authors attribute to noise pushing points toward the facets (Experiment IV).
- For us: the closest thing to a purity sweep for MVSA, and a set of benchmark concentration levels. If the precinct abundances are concentrated in the interior, the literature recommends a statistical method. The Dirichlet experiment was not replicated.

### Javadi & Montanari 2020, non-negative matrix factorization via archetypal analysis. JASA 115(530):896-907. [local PDF]
- NMF is in general not unique. Uniqueness needs the weights, or the archetypes, to be sufficiently sparse (Sec. 1).
- Separability (Donoho & Stodden 2003) is the regime in which this holds: for each archetype, a sample that is that archetype alone. For the weights it is the pure pixel assumption under another name.
- For us: the citation for what NMF assumes. Purity near 1 under NMF's own simplex is not a demonstration of separability, because NMF leaves precincts outside its simplex and those are pulled onto the boundary.

### Lin et al. 2015, identifiability without pure pixels. IEEE TGRS 53(10):5530; arXiv:1406.5273. [extracted; not in the papers folder, read from the arXiv HTML]
- Defines rho and gamma (see Terms).
- For p >= 3: rho > 1/sqrt(p - 1) is necessary for exact recovery (Theorem 1) and gamma > 1/sqrt(p - 1) is sufficient (Theorem 2).
- Assumptions: no noise, abundances non-negative and summing to one, full-rank M, p known.
- gamma is NP-hard to compute in general. rho and gamma can differ a lot when the abundances are spread unevenly.
- The theory concerns the exact global optimum. The paper's own simulations use an approximate solver.
- Treats MVSA as another name for the same criterion.
- For us:
  - At p = 4 the threshold is 1/sqrt(3), about 0.58 (our arithmetic). It applies to the length of the abundance vector, not to the largest abundance.
  - This is the citation for "MVSA does not need pure pixels," with the no-noise and sum-to-one caveats.
  - A few near-pure precincts for some archetypes do not establish gamma.
  - The paper defines rho and gamma on the true abundances. Neither is computed here.

### Fu et al. 2019 (IEEE SPM) and Fu et al. 2016 (IEEE TSP 64(23):6254-6268). [extracted]
- Volume minimization is identifiable under full rank, sum-to-one, and a sufficiently scattered abundance matrix. M needs only full column rank.
- Fu et al. 2016 prove equivalence with Lin et al.'s gamma condition.
- The condition is NP-hard to check.
- A single outlier can make the criterion fail. There is no identifiability theorem under noise.
- Their simulations cap the largest abundance at 0.85. That cap is not Lin's gamma.
- For us: a second, independent source for the no-pure-pixel guarantee. Supports screening outliers before MVSA.

### Bioucas-Dias et al. 2012, overview. IEEE JSTARS 5(2):354-379. [local PDF]
- Three regimes (Fig. 6): pure pixels present (pure-pixel methods suffice); no pure pixels but points on the facets (minimum volume works); highly mixed (minimum volume returns a simplex smaller than the true one, use statistical methods).
- Hard-constraint fitting is pulled far off by noise that pushes points outside the simplex.
- For us: the standard reference for placing the precinct data in one of the three regimes.

### Ma et al. 2014, signal processing perspective. IEEE SPM 31(1):67-81. [extracted]
- VCA recovers all endmembers with probability one when pure pixels exist and there is no noise. No guarantee otherwise.
- Calls no-pure-pixel identifiability of volume minimization an open question. This predates Lin 2015 and Fu 2015, which closed it.
- For us: cite for VCA's guarantee. Do not cite for the no-pure-pixel case.

### Plaza et al. 2012, comparison without pure pixels. J Math Imaging Vis 42:163-175. [extracted]
- Nine algorithms on synthetic scenes without pure pixels (p = 9) and on Cuprite.
- Minimum-volume methods generally win at moderate to low noise. At SNR 30 they are much worse than pure-pixel methods on spectral angle (reported as 12.6 to 15.3 degrees against about 2.1).
- For us: independent evidence that the advantage of minimum-volume methods depends on noise level. Verify the table values before citing.

### Ma 2021 (arXiv:2106.14177) and Wu et al. 2022, PRISM (IEEE TSP 70:582-599). [extracted]
- Noise sensitivity analysis for simplex volume minimization is still unsolved.
- Without noise, maximum likelihood under uniformly distributed abundances reduces to volume minimization.
- For us: supports stating plainly that there is no noise-robust guarantee for MVSA.

## What to do with this in the paper

- Claim: MVSA is the appropriate estimator because precincts are mixtures and pure precincts cannot be assumed. Cite Li 2015, Lin 2015, Fu 2016.
- Evidence against the pure pixel assumption: the share of precincts outside the VCA and N-FINDR simplexes (0.80 or more at HySime k in seven of eight runs). Report the exceptions too: 2013 at k = 3, and the small shares at p = 3 in three runs.
- State the conditions the MVSA guarantee needs: facet coverage, sum-to-one, low noise, global optimum. Say that facet coverage was not tested, because the papers give no test for real data, and that the highly mixed case cannot be ruled out.
- For NMF, state that uniqueness needs separability or sparsity, and that the fit does not establish either.
- Diagnostics reported are the two in "What was checked on the precinct data". Say that every number is relative to an estimated simplex.
- Do not claim that purity was verified or that the theory covers noisy data.

## Open items

- Verify the Plaza 2012 table values and the Bioucas-Dias 2012 Fig. 15 values against the PDFs.
- Verify the statements of Lin et al.'s Theorems 1 and 2 against the PDF before citing the threshold. The paper is not in the papers folder.
- Fu et al., Ma et al. 2014, Plaza et al. 2012, Ma 2021 and Wu et al. 2022 are not in the papers folder either; their entries here are from extracted text only.
- The facet condition for MVSA and separability for NMF remain untested.
- All synthetic evidence uses mineral spectra with p = 3 or 5 and 224 bands. Nothing in this literature tests data shaped like ours.
