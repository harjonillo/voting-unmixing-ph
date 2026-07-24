"""Single source of truth for plot colors and fonts.

Three colormap *roles*, set up separately and all generated with seaborn so
they scale with the data and stay perceptually principled:

* **discrete** — nominal identity (archetypes, model versions). HUSL gives `N`
  evenly-spaced hues at equal perceived lightness, for any `N`, so a model with
  `p` archetypes just asks for `p` colors.
* **continuous** — magnitude (abundance, RMSE, std). ``mako`` reversed: 0 is
  light (recedes into the surface), large values go dark. Perceptually uniform.
* **diverging** — signed quantities centered on 0 (e.g. a mean-vs-reference
  delta, a z-score). ``vlag``: blue (−1) ↔ white (0) ↔ red (+1); each arm is
  perceptually uniform, so a step near 0 reads the same on both sides.

Consistency across the three: the two *value* ramps share a cool→warm identity
(mako's blue-teal, vlag's blue arm), while the discrete ramp is necessarily a
full hue wheel — nominal categories must be told apart by hue, which a single
sequential ramp can't do without making some archetypes look alike.

Change the look in one place by editing the three ``*_NAME`` constants below.
Any seaborn/matplotlib palette name works
(https://seaborn.pydata.org/tutorial/color_palettes.html).
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import seaborn as sns
from matplotlib.colors import Colormap, to_hex

# --------------------------------------------------------------- typography
FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", sans-serif'
FONT_SIZE = 13
INK = "#1a1a1a"
GRID = "#e6e5df"
SURFACE = "#fcfcfb"

# -------------------------------------------------------- named seaborn ramps
CAT_NAME = "husl"  # discrete: evenly-spaced hues, any count (perceptual)
SEQ_NAME = "mako_r"  # continuous: light (0) -> dark (max), perceptually uniform
DIV_NAME = "vlag"  # diverging: blue (-1) -> white (0) -> red (+1), uniform arms


def _colorscale(cmap: Colormap, n: int = 32) -> list[list]:
    """A matplotlib/seaborn colormap as a plotly ``[[pos, hex], ...]`` scale."""
    return [[i / (n - 1), to_hex(cmap(i / (n - 1)))] for i in range(n)]


# Continuous & diverging, as plotly colorscales for the app...
SEQUENTIAL = _colorscale(sns.color_palette(SEQ_NAME, as_cmap=True))
DIVERGING = _colorscale(sns.color_palette(DIV_NAME, as_cmap=True))

# ...and as plain names for the matplotlib figures in ``src/figures``.
SEQUENTIAL_MPL = SEQ_NAME
DIVERGING_MPL = DIV_NAME

# One reserved accent for "look here" marks (mean lines, the lineage split link),
# taken from the warm end of the diverging ramp so it belongs to the same family.
HIGHLIGHT = to_hex(sns.color_palette(DIV_NAME, as_cmap=True)(0.88))


def rgba(hex_color: str, alpha: float) -> str:
    """``"#rrggbb"`` -> ``"rgba(r, g, b, alpha)"`` for translucent fills."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


# --------------------------------------------------------------- discrete API


def categorical(n: int) -> list[str]:
    """``n`` distinct hex colors (HUSL — equal perceived lightness)."""
    return [to_hex(c) for c in sns.color_palette(CAT_NAME, n)]


def _index(arch_col: str) -> int:
    """``arch_3`` -> ``3``."""
    return int(arch_col.split("_")[1])


def archetype_color(arch_col: str, n_arch: int) -> str:
    """Color for one archetype, keyed to its index within a ``p``-archetype model.

    Keying on the index (not the archetype's rank in the current view) is what
    keeps Archetype 3 the same color on the map, its loadings bar, and its
    histogram — regardless of how many archetypes are on screen.
    """
    return categorical(n_arch)[_index(arch_col) % n_arch]


def dominant_color_map(n_arch: int) -> dict[str, str]:
    """``color_discrete_map`` for the dominant-archetype choropleth.

    The ``dominant`` column holds the positional index as a string (``"0"`` …
    ``"p-1"``), so keys match that and colors line up with ``archetype_color``.
    """
    pal = categorical(n_arch)
    return {str(i): pal[i] for i in range(n_arch)}


def model_colors(ps: list[int]) -> dict[int, str]:
    """One stable color per endmember count ``p`` across a sweep."""
    pal = categorical(len(ps))
    return {p: pal[i] for i, p in enumerate(sorted(ps))}


# ------------------------------------------------------------ plotly template


def register_template() -> None:
    """Install the app's fonts, backgrounds, and default ramps on every figure.

    Call once at startup; afterwards every ``px``/``go`` figure inherits the
    typography and the discrete/continuous defaults for free. Charts that must
    pin color to a specific archetype still pass an explicit map.
    """
    pio.templates["voting"] = go.layout.Template(
        layout=dict(
            font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=INK),
            paper_bgcolor=SURFACE,
            plot_bgcolor=SURFACE,
            xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
            yaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
            colorway=categorical(8),
            colorscale=dict(sequential=SEQUENTIAL, diverging=DIVERGING),
        )
    )
    pio.templates.default = "plotly+voting"
