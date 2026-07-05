import numpy as np
import matplotlib.pyplot as plt
from typing import List, Union


def plot_arr_cols_to_subplots(
    arr: np.ndarray, 
    arr_ref: np.ndarray, 
    n_row: int, titles: List[str], 
    plot_type="bar", 
    label: str = "extracted", 
    label_ref: str = "reference"
):
    """
    Plots a column in the given array into its own subplot.
    """
    n_col = arr.shape[1] // n_row

    fig, axs = plt.subplots(n_row, n_col, figsize=(15, 6))
    for m in range(arr.shape[1]):
        
        if n_row == 1:
            if plot_type == "bar":
                axs[m].bar(range(len(arr[:, m])), arr[:, m], label=label, alpha=0.7)
                axs[m].bar(range(len(arr_ref[:, m])), arr_ref[:, m], label=label_ref, alpha=0.7)
            
            else:
                axs[m].plot(arr_ref[:, m], color="C3", label=label_ref, alpha=0.7)
                axs[m].plot(arr[:, m], color="C0", label=label, linestyle='--', alpha=0.7)
            
            axs[m].legend(loc="best")
            axs[m].set_title(titles[m])

        else:
            i = m // n_col
            j = m - (i * n_col)

            if plot_type == "bar":
                axs[i, j].bar(range(len(arr[:, m])), arr[:, m], label=label, alpha=0.7)
                axs[i, j].bar(range(len(arr_ref[:, m])), arr_ref[:, m], label=label_ref, alpha=0.7)

            else:
                axs[i, j].plot(arr_ref[:, m], color="C3", label=label_ref, linestyle='--', alpha=0.7)
                axs[i, j].plot(arr[:, m], color="C0", label=label, alpha=0.7)

            axs[i, j].legend(loc="best")
            axs[i, j].set_title(titles[m])
            # axs[i, j].set_ylim(0, 1)

    fig.tight_layout()


def plot_reconstruction_histograms(
    Y: np.ndarray,
    Y_rec: np.ndarray,
    top_n_index: List[int],
    top_n_names: List[str],
    n_cols: int = 4,
    col_width: int = 3,
    x_range: Union[tuple, None] = None,
    n_bins: int = 50,
    log_scale: bool = True,
):
    """
    For each candidate (in rank order), plot a density histogram of their
    vote distribution in the original data vs. the VCA reconstruction.

    Parameters
    ----------
    Y : ndarray, shape (L, N)
        Original data matrix (candidates × precincts).
    Y_rec : ndarray, shape (L, N)
        Reconstructed data matrix from VCA (same shape as Y).
    top_n_index : list of int
        Indices into Y rows, in rank order (highest total votes first).
    top_n_names : list of str
        Candidate name for each index in top_n_index.
    n_cols : int
        Number of subplot columns. Default 4.
    col_width : int
        Width (inches) of each subplot column. Default 3.
    x_range : (float, float) or None
        (xmin, xmax) for histogram bins. If None, inferred from Y_rec.
    n_bins : int
        Number of histogram bins. Default 50.
    log_scale : bool
        If True, use log scale on the y-axis. Default True.
    """
    n_show = len(top_n_index)
    n_rows = n_show // n_cols + int(n_show % n_cols > 0)

    if x_range is None:
        xmin = np.floor(np.nanmin(Y_rec))
        xmax = np.ceil(np.nanmax(Y_rec))
    else:
        xmin, xmax = x_range

    bins = np.linspace(xmin, xmax, n_bins)

    fig, axs = plt.subplots(n_rows, n_cols, figsize=(n_cols * col_width, n_rows * col_width))
    axs = axs.flatten()

    for i, (idx, name) in enumerate(zip(top_n_index, top_n_names)):
        hist = Y[idx, :]
        hist_rec = Y_rec[idx, :]
        hist_rec = hist_rec[~np.isnan(hist_rec)]
        axs[i].hist(hist, bins=bins, color="C0", density=True, alpha=0.5, label="Original")
        axs[i].hist(hist_rec, bins=bins, color="C3", density=True, alpha=0.5, label="Reconstructed")
        axs[i].set_title(f"{i + 1}: {name}", fontsize=10)
        axs[i].set_xlabel("Vote fraction per precinct")
        axs[i].set_ylabel("Density")
        axs[i].legend(loc="upper right")
        if log_scale:
            axs[i].set_yscale("log")

    for ax in axs[n_show:]:
        ax.set_visible(False)

    fig.tight_layout()


def plot_archetype_weights(
    endm: np.ndarray,
    candidate_labels: List[str],
    year: Union[int, str] = "",
    top_n: int = 24,
    seat_line: Union[int, None] = 12,
):
    """
    Bar chart of candidate weights per archetype, one subplot per archetype.

    Parameters
    ----------
    endm : ndarray, shape (L, p)
        Endmember matrix (candidates × archetypes).
    candidate_labels : list of str
        Human-readable name for each of the L candidates (in endm row order).
    year : int or str
        Election year shown in the figure title. Default "".
    top_n : int
        Number of top-weighted candidates to show per archetype. Default 24.
    seat_line : int or None
        If given, draw a dashed line after this many candidates (e.g. 12 for
        the 12 electable seats). Default 12. Pass None to omit.
    """
    import pandas as pd
    import seaborn as sns

    L, p = endm.shape

    df = pd.DataFrame(
        endm,
        columns=list(range(p)),
        index=candidate_labels,
    ).reset_index().rename(columns={"index": "candidate"}).melt(
        id_vars=["candidate"], var_name="archetype", value_name="weight"
    )

    fig, axs = plt.subplots(1, p, figsize=(8 * p, 8))
    if p == 1:
        axs = [axs]

    for i, ax in zip(range(p), axs):
        sns.barplot(
            ax=ax,
            data=df.query(f"archetype == {i}").sort_values(by="weight", ascending=False).head(top_n),
            x="weight",
            y="candidate",
        )
        ax.set_title(f"Archetype {i}", fontsize=15)
        if seat_line is not None and seat_line <= top_n:
            ax.axhline(y=seat_line - 0.5, color="r", linestyle="--", linewidth=1)

    title = f"Candidate weights per archetype"
    if year:
        title += f", {year}"
    fig.suptitle(title, fontsize=20)
    fig.tight_layout()
