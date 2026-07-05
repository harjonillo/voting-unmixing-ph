from .endmember_extraction import nfindr, vca, mvsa
from .abundance_estimation import ucls, fcls, hyperFcls, sunsal_mod
from .est_noise import est_noise
from .hysime import hysime
from .tools import match_endmembers, plot_elbow, endmember_noise_floor, abundance_weighted_signal
from .matching import (
    cosine_matrix,
    match_to_reference,
    archetype_lineage,
    relabel_to_reference,
    relabel_density_to_reference,
)
from .metrics import resolution

__all__ = [
    # Endmember extraction
    "nfindr",
    "vca",
    "mvsa",
    # Abundance estimation
    "ucls",
    "fcls",
    "hyperFcls",
    "sunsal_mod",
    # Noise & subspace
    "est_noise",
    "hysime",
    # Analysis tools
    "match_endmembers",
    "plot_elbow",
    "endmember_noise_floor",
    "abundance_weighted_signal",
    # Matching / cluster alignment (cosine-based, multi-trial workflow)
    "cosine_matrix",
    "match_to_reference",
    "archetype_lineage",
    "relabel_to_reference",
    "relabel_density_to_reference",
    # Metrics
    "resolution",
]
