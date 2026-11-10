"""Toy-data figures for normalization.tex (per-ballot vs vote-sum vs row-max).

Everything is synthetic and seeded, so this needs no election data and no
sweep results. Run from anywhere:

    python docs/normalization/make_figures.py

Writes figures/*.pdf and table_mvsa.tex next to this file.

Notation follows Li & Bioucas-Dias (2008, MVSA): Y = M S with S >= 0 and
1_p^T S = 1_n^T. M is (L, p) with one voter type per column, S is (p, n) with
one precinct per column, and hats mark estimates. Candidates are l = 1..L,
types i = 1..p, precincts j = 1..n.
"""

import sys
import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parents[1]))
from src.unmixing import extract_endmembers, sunsal_mod  # noqa: E402

warnings.filterwarnings("ignore", message="sparse_svds failed")
warnings.filterwarnings("ignore", message="SNR estimation")

FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

# Colours from the dataviz reference palette: categorical slots 1-3 (one per normalization), ink, grid
NORMS = ["ballot", "sum", "rowmax"]
LABEL = {"ballot": "per-ballot", "sum": "vote-sum", "rowmax": "row-max"}
UNITS = {"ballot": "votes / ballot", "sum": "votes / vote", "rowmax": "votes / top vote"}
COLOR = {"ballot": "#2a78d6", "sum": "#eb6834", "rowmax": "#1baf7a"}
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

mpl.rcParams.update({
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "savefig.bbox": "tight", "pdf.fonttype": 42,
})


def normalize(V, kind, B=None):
    """Column-wise normalization of an (L, n) count (or expected-count) matrix."""
    if kind == "ballot":
        return V / B
    if kind == "sum":
        return V / V.sum(axis=0)
    if kind == "rowmax":
        return V / V.max(axis=0)
    raise ValueError(kind)


def fit_abundances(M, Y, asc=True):
    """S_hat >= 0 (and 1_p^T S_hat = 1_n^T if asc) by SUNSAL, for fixed M."""
    S_hat, _, _ = sunsal_mod(M, Y, positivity="yes", addone="yes" if asc else "no",
                             AL_iters=3000, tol=1e-8)
    return S_hat


def solid_legend(leg):
    for h in getattr(leg, "legend_handles", None) or leg.legendHandles:
        h.set_alpha(1)


# --------------------------------------------------------------------------
# Figure 1: two candidates, two voter types (the geometry, noise-free)
# --------------------------------------------------------------------------
M2 = np.array([[0.80, 0.30],
               [0.35, 0.60]])  # columns m_1, m_2
t = np.linspace(0, 1, 21)  # [S]_{2j}: fraction of type-2 voters
S2 = np.vstack([1 - t, t])
V2 = M2 @ S2  # expected names per ballot = V / B (B cancels)

fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.6), sharex=True, sharey=True)
for ax, kind in zip(axes, NORMS):
    Y = normalize(V2, kind, B=1.0)
    M_tilde = normalize(M2, kind, B=1.0)  # normalized pure types
    ax.plot(M_tilde[0], M_tilde[1], ls="--", lw=1.2, color=MUTED, zorder=1,
            label="segment between normalized pure types")
    ax.scatter(Y[0], Y[1], s=16, color=COLOR[kind], edgecolor="white", linewidth=0.6,
               zorder=3, label="precincts, $t=0,0.05,\\ldots,1$")
    ax.scatter(M_tilde[0], M_tilde[1], s=36, marker="s", color=INK, zorder=4)
    for i, (dx, dy) in enumerate([(0.03, -0.09), (-0.16, 0.04)]):
        ax.annotate(f"$\\tilde{{\\mathbf{{m}}}}_{i + 1}$", (M_tilde[0, i], M_tilde[1, i]),
                    (M_tilde[0, i] + dx, M_tilde[1, i] + dy), color=INK2, fontsize=9)
    if kind == "rowmax":
        ax.annotate("bulges past the\nsegment to (1, 1)", (1, 1), (0.12, 0.25),
                    color=INK2, fontsize=8, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set(title=f"{LABEL[kind]}\n[{UNITS[kind]}]", xlim=(0, 1.1), ylim=(0, 1.1), aspect="equal",
           xlabel="$y_1$ (candidate 1)")
axes[0].set_ylabel("$y_2$ (candidate 2)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=7.5, bbox_to_anchor=(0.5, -0.08))
fig.savefig(FIG / "fig1_geometry.pdf")
plt.close(fig)

# --------------------------------------------------------------------------
# Toy election: L = 12 candidates, p = 3 voter types with different top candidates
# --------------------------------------------------------------------------
L, p, n = 12, 3, 4000
M = np.full((L, p), 0.05)  # [M]_{li}: chance a type-i voter marks candidate l
M[[0, 1, 2, 3, 4, 5, 6, 7], 0] = [0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50]  # wide slate
M[[3, 4, 8, 9, 10, 2], 1] = [0.50, 0.45, 0.90, 0.60, 0.55, 0.40]
M[[5, 6, 10, 11], 2] = [0.35, 0.30, 0.40, 0.80]  # narrow slate
TOPS = M.argmax(axis=0)

rng = np.random.default_rng(0)
S = rng.dirichlet([0.7] * p, n).T  # (p, n) voter-type fractions
B = rng.integers(200, 800, n)  # ballots per precinct

# Lambda(s_j) for row-max: sum_i s_i max_l [M]_{li} / max_l [M s_j]_l
LAM = (M.max(axis=0) @ S) / (M @ S).max(axis=0)

# --------------------------------------------------------------------------
# Figure 2: noise-free, true endmembers known -> abundances and residuals
# --------------------------------------------------------------------------
MS = M @ S  # expected names per ballot (noise-free data, B cancels)
fit = {}
for kind in NORMS:
    Y = normalize(MS, kind, B=1.0)
    M_tilde = normalize(M, kind, B=1.0)
    S_hat = fit_abundances(M_tilde, Y)
    S_cone = fit_abundances(M_tilde, Y, asc=False)
    fit[kind] = {
        "S_hat": S_hat,
        "res": np.linalg.norm(Y - M_tilde @ S_hat, axis=0),
        "res_cone": np.linalg.norm(Y - M_tilde @ S_cone, axis=0),
    }

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.9))
I = 2  # the narrow-slate type: largest reweighting under vote-sum
ax1.plot([0, 1], [0, 1], color=AXIS, lw=0.8, zorder=1)
for kind in NORMS:
    ax1.scatter(S[I], fit[kind]["S_hat"][I], s=3, color=COLOR[kind], alpha=0.5, lw=0,
                label=LABEL[kind], rasterized=True)
ax1.set(xlabel=f"true voter fraction $[\\mathbf{{S}}]_{{{I + 1}j}}$  [ballots / ballot]",
        ylabel=f"fitted abundance $[\\hat{{\\mathbf{{S}}}}]_{{{I + 1}j}}$",
        xlim=(0, 1), ylim=(0, 1), aspect="equal", title="(a) abundance vs. voter fraction")
solid_legend(ax1.legend(loc="upper left", markerscale=4, fontsize=7.5))

ax2.scatter(LAM - 1, fit["rowmax"]["res"], s=3, color=COLOR["rowmax"], alpha=0.5, lw=0,
            rasterized=True, label="row-max, with ASC")
ax2.scatter(LAM - 1, fit["rowmax"]["res_cone"], s=3, color=INK2, alpha=0.5, lw=0,
            rasterized=True, label="row-max, no ASC (cone)")
ax2.set(xlabel="$\\Lambda(\\mathbf{s}_j) - 1$",
        ylabel="$\\|\\mathbf{y}_j - \\tilde{\\mathbf{M}}\\hat{\\mathbf{s}}_j\\|_2$\n[votes / top vote]",
        title="(b) row-max residual with the true endmembers")
solid_legend(ax2.legend(loc="upper left", markerscale=4, fontsize=7.5))
fig.tight_layout(w_pad=2.5)
fig.savefig(FIG / "fig2_abundances.pdf", dpi=300)
plt.close(fig)

# --------------------------------------------------------------------------
# Figure 3 + table: noisy counts, blind MVSA (the pipeline's extractor)
# --------------------------------------------------------------------------
V = rng.binomial(np.broadcast_to(B, (L, n)), np.clip(MS, 0, 1))  # (L, n) vote counts
rows, recov = [], {}
for kind in NORMS:
    Y = normalize(V, kind, B=B)
    M_tilde = normalize(M, kind, B=1.0)
    rmse_true = np.sqrt(np.mean((Y - M_tilde @ fit_abundances(M_tilde, Y)) ** 2))
    rmse_cone = np.sqrt(np.mean((Y - M_tilde @ fit_abundances(M_tilde, Y, asc=False)) ** 2))
    runs = []
    for seed in range(5):
        M_hat = extract_endmembers(Y, p, seed, "mvsa", {"MM_iters": 10})
        S_hat = fit_abundances(M_hat, Y)
        runs.append((np.sqrt(np.mean((Y - M_hat @ S_hat) ** 2)), M_hat, S_hat))
    rmse, M_hat, S_hat = min(runs, key=lambda r: r[0])
    cos = (M_tilde / np.linalg.norm(M_tilde, axis=0)).T @ (M_hat / np.linalg.norm(M_hat, axis=0))
    _, perm = linear_sum_assignment(-cos)
    M_hat, S_hat = M_hat[:, perm], S_hat[perm]
    recov[kind] = (M_tilde, M_hat)
    rows.append({
        "norm": LABEL[kind],
        "rmse_true": rmse_true,
        "rmse_cone": rmse_cone,
        "rmse_mvsa": rmse,
        # loadings below -1% of the largest true loading (scales differ by normalization)
        "n_neg": int((M_hat < -0.01 * M_tilde.max()).sum()),
        "min_rel": M_hat.min() / M_tilde.max(),
        "csum_true": M_tilde.sum(axis=0),
        "csum_mvsa": M_hat.sum(axis=0),
    })

fig, axes = plt.subplots(3, 3, figsize=(7.0, 5.6), sharex=True)
x = np.arange(1, L + 1)
for r, kind in enumerate(NORMS):
    M_tilde, M_hat = recov[kind]
    lo = min(M_hat.min(), 0) * 1.15 - 0.02
    hi = max(M_hat.max(), M_tilde.max()) * 1.1
    for i in range(p):
        ax = axes[r, i]
        ax.axhline(0, color=AXIS, lw=0.8, zorder=1)
        ax.vlines(x, 0, M_hat[:, i], color=COLOR[kind], lw=2, zorder=2)
        ax.scatter(x, M_hat[:, i], s=14, color=COLOR[kind], zorder=3,
                   label="MVSA $\\hat{\\mathbf{m}}_i$" if (r, i) == (0, 0) else None)
        ax.scatter(x, M_tilde[:, i], s=22, facecolor="none", edgecolor=INK, lw=0.9, zorder=4,
                   label="truth $\\tilde{\\mathbf{m}}_i$" if (r, i) == (0, 0) else None)
        ax.set_ylim(lo, hi)
        if r == 0:
            ax.set_title(f"type {i + 1} (top: cand. {TOPS[i] + 1})")
        if i == 0:
            ax.set_ylabel(f"{LABEL[kind]} loading\n[{UNITS[kind]}]")
        else:
            ax.tick_params(labelleft=False)
        ax.grid(axis="x", visible=False)
for ax in axes[-1]:
    ax.set_xticks(x[::2])
    ax.set_xlabel("candidate $\\ell$")
axes[0, 0].legend(loc="upper right", fontsize=7, handletextpad=0.3)
fig.tight_layout(h_pad=1.0, w_pad=0.6)
fig.savefig(FIG / "fig3_mvsa.pdf")
plt.close(fig)


def fmt(v):
    return "/".join(f"{val:.2f}" for val in v)


lines = [
    r"\begin{tabular}{lrrrrrll}",
    r"\toprule",
    r" & \multicolumn{3}{c}{RMSE $/$ noise floor} & \multicolumn{4}{c}{blind MVSA endmembers $\hat{\mathbf M}$} \\",
    r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}",
    r"normalization & true $\tilde{\mathbf M}$ & MVSA & noise floor & min loading & \# negative & column sums & true column sums \\",
    r"\midrule",
]
for row in rows:
    lines.append(
        f"{row['norm']} & {row['rmse_true'] / row['rmse_cone']:.2f} & {row['rmse_mvsa'] / row['rmse_cone']:.2f} & "
        f"{row['rmse_cone']:.4f} & {100 * row['min_rel']:.1f}\\% & {row['n_neg']} & "
        f"{fmt(row['csum_mvsa'])} & {fmt(row['csum_true'])} \\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
(HERE / "table_mvsa.tex").write_text("\n".join(lines) + "\n")

print("widths c_i:", M.sum(axis=0).round(2), " top candidates:", TOPS + 1)
print("noise-free max residual (true endmembers, ASC):",
      {LABEL[k]: float(fit[k]["res"].max()) for k in NORMS})
print("noise-free max residual (row-max, no ASC):", float(fit["rowmax"]["res_cone"].max()))
print("Lambda: median %.3f, 95th pct %.3f, max %.3f" % tuple(np.percentile(LAM, [50, 95, 100])))
for row in rows:
    print({k: (np.round(v, 4) if not isinstance(v, str) else v) for k, v in row.items()})
