"""Choropleth helpers: matplotlib for notebooks, plotly for the Streamlit app."""

import json

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


def plotly_choropleth(
    gdf,
    column,
    hover_name=None,
    hover_data=None,
    color_continuous_scale="Viridis",
    title=None,
    simplify_tolerance=None,
    range_color=None,
):
    """Interactive plotly choropleth from a GeoDataFrame (used by the app).

    simplify_tolerance : simplify geometry (degrees) before serializing —
    keeps municipal-level maps responsive.
    """
    import plotly.express as px

    gdf = gdf.reset_index(drop=True)
    if simplify_tolerance:
        gdf = gdf.set_geometry(gdf.geometry.simplify(simplify_tolerance))
    geojson = json.loads(gdf.to_json())

    fig = px.choropleth(
        gdf.drop(columns="geometry"),
        geojson=geojson,
        locations=gdf.index,
        color=column,
        hover_name=hover_name,
        hover_data=hover_data,
        color_continuous_scale=color_continuous_scale,
        range_color=range_color,
        title=title,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_traces(marker_line_width=0.3, marker_line_color="white")
    fig.update_layout(margin=dict(l=0, r=0, t=40 if title else 0, b=0), height=650)
    return fig
