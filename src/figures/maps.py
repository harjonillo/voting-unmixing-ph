"""Choropleth helpers: ``plot_choropleth`` (matplotlib) for the notebooks."""

from typing import Optional

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes


def plot_choropleth(
    gdf: gpd.GeoDataFrame,
    column: str,
    ax: Optional[Axes] = None,
    cmap: str = "viridis",
    title: Optional[str] = None,
    legend_label: Optional[str] = None,
    missing_color: str = "#eeeeee",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> Axes:
    """Static (matplotlib/geopandas) choropleth for notebooks.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        One row per geographic unit with a ``geometry`` column, e.g.
        from ``src.geo.join_provinces``/``join_municipalities``.
    column : str
        Column of `gdf` to color by; NaN rows are drawn in
        `missing_color`.
    ax : matplotlib.axes.Axes, optional
        Axes to draw on; a new figure is created when None.
    cmap : str, default 'viridis'
        Matplotlib colormap name.
    title : str, optional
        Axes title.
    legend_label : str, optional
        Colorbar label; defaults to `column`.
    missing_color : str, default '#eeeeee'
        Fill color for units with no data.
    vmin, vmax : float, optional
        Color scale limits; inferred from the data when None.

    Returns
    -------
    matplotlib.axes.Axes
        The axes drawn on.
    """
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
