"""Labels and source-column names shared by the sidebar and the tabs."""

LEVEL_LABELS = {
    "national": "National",
    "region": "Region",
    "province": "Province",
    "municipality": "City / municipality",
    "clustered_precinct": "Clustered precinct",
}

BALLOT_COL = "information.numberOfValidBallot"
VOTERS_COL = "information.numberOfActuallyVoters"
REGISTERED_COL = "information.numberOfRegisteredVoters"


def arch_label(arch_col: str) -> str:
    """Column name to display name: ``arch_3`` -> ``Archetype 3``."""
    return f"Archetype {arch_col.split('_')[1]}"
