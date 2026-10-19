from .endmember_extraction import nfindr, vca, mvsa, nmf
from .abundance_estimation import ucls, fcls, hyperFcls, sunsal_mod
from .est_noise import est_noise
from .hysime import hysime
from .tools import match_endmembers, endmember_noise_floor, abundance_weighted_signal
from .matching import (
    cosine_matrix,
    match_to_reference,
    archetype_lineage,
    relabel_to_reference,
    relabel_density_to_reference,
)
from .metrics import resolution
from .methods import METHODS, method_params, extract_endmembers

__all__ = [
    # Endmember extraction
    "nfindr",
    "vca",
    "mvsa",
    "nmf",
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
    # Method switch (MVSA / NMF) shared by the pipeline scripts
    "METHODS",
    "method_params",
    "extract_endmembers",
]
