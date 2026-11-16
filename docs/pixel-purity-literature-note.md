# Pixel purity and the validity of VCA and MVSA: literature note

Compiled 2026-11-16. Scope: what the hyperspectral unmixing literature says about pixel purity as a condition for VCA and MVSA, and what that implies for the precinct data at p = 4.

Reading status is marked per paper:
- [PDF] = read from the publisher PDF, tables checked on the page images.
- [extracted] = read in full text through a text-extraction tool. Figures not seen. Check specific numbers against the PDF before citing.

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
- Best pixel purity, rho (Lin et al. 2015): the largest Euclidean length of any abundance vector in the data. Length is 1 for a pure pixel and 1/sqrt(p) for an equal mixture.
- Uniform pixel purity, gamma (Lin et al. 2015): the largest r such that every possible abundance vector of length at most r lies inside the convex hull of the observed abundance vectors. It measures how well the data fill the simplex in all directions. gamma = 1 is the pure pixel assumption.
- Sufficiently scattered (Fu et al.): a condition on the abundance matrix that Fu et al. 2016 prove equivalent to gamma > 1/sqrt(p - 1).

**Methods**
- Pure-pixel methods: return actual data points as endmembers. VCA, N-FINDR, PPI.
- VCA (vertex component analysis): repeatedly projects the data onto a direction orthogonal to the endmembers found so far and takes the most extreme pixel.
- PPI (pixel purity index): projects the data onto many random directions and scores each pixel by how often it is an extreme.
- Minimum-volume methods: find the smallest simplex that contains all the data. Its vertices need not be data points. MVSA, MVES, SISAL, MVC-NMF.
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

- VCA is valid as an estimator only if pure pixels exist. Its own authors say so and show the failure.
- MVSA does not need pure pixels, but it needs precincts on or near every facet. It degrades steadily as mixing increases.
- The formal guarantee (Lin et al. 2015) is noiseless, assumes abundances sum to one, and concerns the global optimum. The quantity it uses, gamma, is NP-hard to compute. We do not compute it.
- No paper gives a practical purity test for real data. The validity argument for the precinct data has to be indirect.

## Our pipeline, for reference (repo checked 2026-11-16)

- `mvsa` in `src/unmixing/endmember_extraction.py` is the hard-constraint version (Q Y >= 0, interior point). No hinge.
- It projects to a (p - 1)-dimensional affine set by PCA, initializes with VCA and expands that simplex, and runs at most 10 outer iterations with relative tolerance 1e-2.
- Abundances come from SUNSAL with non-negativity and sum-to-one.
- Notebook 16 shows MVSA vertices several cloud radii outside the precinct cloud. The old notebook 11 found no vote-concentrated precinct above abundance 0.9 under MVSA.

## Per paper

### Nascimento & Bioucas-Dias 2005, VCA. IEEE TGRS 43(4):898-910. [PDF]
- Assumes at least one pure pixel per endmember (Sec. I, II-B, V). Called "a strong requisite that may not hold in some datasets."
- Without pure pixels it still returns the most pure pixels available (Sec. I).
- No-pure-pixel test (Sec. III, Figs. 6-7): p = 3, every pixel with any abundance below 0.2 removed, so the largest abundance left is 0.6. Endmember angle error is about 10 degrees at every SNR. With pure pixels (Fig. 5b) it is near 0 at high SNR and about 7 degrees at the noisiest setting.
- Authors' conclusion: this family is "more affected by the lack of pure pixels than by low SNR."
- More pixels help only because pure pixels become more likely.
- For us: VCA output is not a defensible archetype estimate unless near-pure precincts are shown to exist. Its use to initialize MVSA needs no purity argument.

### Li & Bioucas-Dias 2008, MVSA (IGARSS). [extracted]
- Written for the case where the pure pixel assumption fails.
- Starts from the VCA endmembers and inflates that simplex so more pixels fall inside. The authors report the inflated start lands "systematically in the attraction basin" of a good local minimum. An observation, not a proof.
- Simulations remove every pixel with an abundance above 0.8. MVSA recovers the endmembers. VCA gives the worst estimate.
- Introduces the hinge soft constraint for noise and outliers.
- States that minimum-volume algorithms are very sensitive to outliers and that the problem has many local minima.
- For us: the VCA step is justified as initialization only. Local minima are acknowledged, which is where cross-run stability fits.

### Li et al. 2015, MVSA journal version. IEEE TGRS 53(9):5067-5082. [PDF]
- Condition for correctness: enough samples on the facets (Sec. II). Called a "fundamental assumption": at least p - 1 samples on, or in the neighborhood of, each facet (Sec. V).
- Two purity settings only, at p = 5 and 10,000 pixels: maximum purity 1 (Table I) and 0.8 (Table II). Nothing below 0.8.
- Endmember angle in degrees at SNR 90 / 70 / 50 / 30 dB:
  - Purity 1: VCA 1.652 / 1.687 / 1.792 / 1.828. MVSA 0.026 / 0.026 / 0.163 / 1.543.
  - Purity 0.8: VCA 5.909 / 6.307 / 6.274 / 6.551. MVSA 0.023 / 0.026 / 0.151 / 1.421.
- On the real Cuprite scene the authors say the assumption fails and the problem is ill-posed. Their symptom: nearly all pixels lie outside the estimated simplex (47,733 of 47,750 for VCA). Workaround: run VCA 30 times, keep the largest simplex, project the data onto an inflated version of it, then run MVSA.
- Uses the hard constraint only and assumes noise is negligible after projection (Sec. II-B). The soft constraint is future work.
- Restores sum-to-one by affine projection and notes this can shift angles (Sec. II-A).
- Results are sensitive to the estimated number of endmembers (Sec. V).
- For us:
  - Facet coverage, not vertex purity, is the condition to argue for.
  - The count of precincts outside the simplex is a diagnostic the authors use themselves.
  - Our code matches this version (hard constraint), so its statements about noise apply to us.
  - The sum-to-one step interacts with the normalization choice and needs a sentence in the paper.

### Nascimento & Bioucas-Dias 2012, DECA. IEEE TGRS 50(3):863-878. [PDF]
- Calls p - 1 pixels per facet a "necessary condition" for minimum-volume methods (Sec. I, IV). Highly mixed data are "beyond the reach" of geometric methods.
- Experiment I: p = 3, 10,000 pixels, no noise, symmetric Dirichlet abundances. Mean endmember angle error (SMAE, units not stated):
  - theta = 1: VCA 0.0101, MVSA 0.0023, SISAL 0.0017, DECA 0.0013.
  - theta = 5: VCA 0.1268, MVSA 0.0576, SISAL 0.0604, DECA 0.0141.
  - theta = 10: VCA 0.1956, MVSA 0.1195, SISAL 0.1318, DECA 0.0434.
- MVSA degrades with mixing but stays ahead of VCA at every level.
- More pixels help slightly (Experiment III). In the highly mixed case, added noise did not hurt MVSA much, which the authors attribute to noise pushing points toward the facets (Experiment IV).
- For us: the closest thing to a purity sweep for MVSA, and a set of benchmark concentration levels. If the precinct abundances are concentrated in the interior, the literature recommends a statistical method.

### Lin et al. 2015, identifiability without pure pixels. IEEE TGRS 53(10):5530; arXiv:1406.5273. [extracted]
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
  - The paper defines rho and gamma on the true abundances. We report rho on estimated abundances and say so.

### Fu et al. 2019 (IEEE SPM) and Fu et al. 2016 (IEEE TSP 64(23):6254-6268). [extracted]
- Volume minimization is identifiable under full rank, sum-to-one, and a sufficiently scattered abundance matrix. M needs only full column rank.
- Fu et al. 2016 prove equivalence with Lin et al.'s gamma condition.
- The condition is NP-hard to check.
- A single outlier can make the criterion fail. There is no identifiability theorem under noise.
- Their simulations cap the largest abundance at 0.85. That cap is not Lin's gamma.
- For us: a second, independent source for the no-pure-pixel guarantee. Supports screening outliers before MVSA.

### Bioucas-Dias et al. 2012, overview. IEEE JSTARS 5(2):354-379. [extracted]
- Three regimes: pure pixels present (pure-pixel methods suffice); no pure pixels but points on the facets (minimum volume works); highly mixed (minimum volume returns a simplex smaller than the true one, use statistical methods).
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
- State the conditions the guarantee needs: facet coverage, sum-to-one, low noise, global optimum. Say which can be checked on the data and which cannot.
- Diagnostics to report are specified in `docs/handoff-notebook-11-pixel-purity.md`. They are limited to checks the papers themselves used: precincts outside the estimated simplex (Li et al. 2015), purity as maximum abundance, precincts near each facet, rho, and the papers' toy experiments with purity caps and Dirichlet mixing.
- Do not claim that purity was verified or that the theory covers noisy data.

## Open items

- Verify the Plaza 2012 table values and the Bioucas-Dias 2012 Fig. 15 values against the PDFs.
- Verify the statements of Lin et al.'s Theorems 1 and 2 against the PDF before citing the threshold.
- All synthetic evidence uses mineral spectra with p = 3 or 5 and 224 bands. Nothing in this literature tests data shaped like ours.
