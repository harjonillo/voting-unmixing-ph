"""Chart builders shared by the tabs."""

import pandas as pd
import plotly.express as px

from app.components.constants import arch_label


def loadings_bar(
    loadings: pd.DataFrame,
    arch_col: str,
    top_n: int = 15,
    *,
    errors: pd.DataFrame | None = None,
    height: int | None = None,
    title: str | None = None,
    x_label: str = "loading",
    color: str | None = None,
):
    """Horizontal bar chart of the top-N candidate loadings for one archetype.

    `errors`, when given, must be indexed like `loadings` and supplies the x
    error bars (e.g. the std over sweep trials). `color`, when given, pins the
    bars to that archetype's color (see `app.components.theme`).
    """
    sub = loadings[arch_col].sort_values(ascending=False).head(top_n)
    err = None if errors is None else errors.loc[sub.index, arch_col].to_numpy()[::-1]
    fig = px.bar(
        x=sub.values[::-1],
        y=sub.index[::-1],
        orientation="h",
        error_x=err,
        labels={"x": x_label, "y": ""},
        title=(
            title
            if title is not None
            else f"{arch_label(arch_col)} — top {top_n} loadings"
        ),
    )
    if color is not None:
        fig.update_traces(marker_color=color)
    fig.update_layout(
        height=height or max(300, 24 * top_n),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def abundance_histogram(
    source: pd.DataFrame, arch_col: str, unit: str, color: str | None = None
):
    """Distribution of one archetype's abundance over `unit`s (precincts, provinces...).

    `color`, when given, pins the bars to that archetype's color.
    """
    fig = px.histogram(
        source,
        x=arch_col,
        nbins=40,
        labels={arch_col: "abundance"},
        title=arch_label(arch_col),
        color_discrete_sequence=None if color is None else [color],
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis_title=f"# {unit}s",
    )
    return fig
