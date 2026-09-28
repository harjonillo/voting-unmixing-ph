"""Choropleth helpers: ``plot_choropleth`` (matplotlib) for the notebooks."""

import matplotlib.pyplot as plt


def plot_choropleth(
    gdf,
    column,
    ax=None,
    cmap="viridis",
    title=None,
    legend_label=None,
    missing_color="#eeeeee",
    vmin=None,
    vmax=None,
):
    """Static (matplotlib/geopandas) choropleth for notebooks."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 9))
    gdf.plot(
        column=column,
        ax=ax,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        legend=True,
        legend_kwds={"label": legend_label or column, "shrink": 0.6},
        missing_kwds={"color": missing_color, "label": "no data"},
        edgecolor="white",
        linewidth=0.3,
    )
    ax.set_axis_off()
    if title:
        ax.set_title(title)
    return ax
