# SKF General Catalogue 10000 EN — Table 6
# Guideline values for contamination factor eta_c
#
# Values are given as (min, max) ranges.
# dm < 100 mm  → use eta_c_small
# dm >= 100 mm → use eta_c_large

ETA_C = {
    "extreme_cleanliness": {
        "description": (
            "Particle size of the order of the lubricant film thickness. "
            "Laboratory conditions."
        ),
        "eta_c_small": (1.0, 1.0),
        "eta_c_large": (1.0, 1.0),
    },
    "high_cleanliness": {
        "description": (
            "Oil filtered through an extremely fine filter. "
            "Typical conditions: sealed bearings that are greased for life."
        ),
        "eta_c_small": (0.6, 0.8),
        "eta_c_large": (0.8, 0.9),
    },
    "normal_cleanliness": {
        "description": (
            "Oil filtered through a fine filter. "
            "Typical conditions: shielded bearings that are greased for life."
        ),
        "eta_c_small": (0.5, 0.6),
        "eta_c_large": (0.6, 0.8),
    },
    "slight_contamination": {
        "description": (
            "Bearings without integral seals, coarse filtering, "
            "wear particles and slight ingress of contaminants."
        ),
        "eta_c_small": (0.3, 0.5),
        "eta_c_large": (0.4, 0.6),
    },
    "typical_contamination": {
        "description": (
            "Bearings without integral seals, coarse filtering, "
            "wear particles, and ingress from surroundings."
        ),
        "eta_c_small": (0.1, 0.3),
        "eta_c_large": (0.2, 0.4),
    },
    "severe_contamination": {
        "description": (
            "High levels of contamination due to excessive wear and/or ineffective seals. "
            "Bearing arrangement with ineffective or damaged seals."
        ),
        "eta_c_small": (0.0, 0.1),
        "eta_c_large": (0.0, 0.1),
    },
    "very_severe_contamination": {
        "description": (
            "Contamination levels so severe that values of eta_c are outside the scale, "
            "which significantly reduces the bearing life."
        ),
        "eta_c_small": (0.0, 0.0),
        "eta_c_large": (0.0, 0.0),
    },
}


def get_eta_c(condition: str, dm: float) -> tuple:
    """
    Return the (min, max) range of eta_c for a given contamination condition
    and bearing mean diameter dm [mm].

    Parameters
    ----------
    condition : str
        One of the keys in ETA_C, e.g. 'normal_cleanliness'.
        Valid options: extreme_cleanliness, high_cleanliness, normal_cleanliness,
        slight_contamination, typical_contamination, severe_contamination,
        very_severe_contamination.
    dm : float
        Bearing mean diameter dm = 0.5*(d+D) [mm].

    Returns
    -------
    (eta_c_min, eta_c_max) : tuple of float
    """
    if condition not in ETA_C:
        raise ValueError(
            f"Unknown condition '{condition}'. "
            f"Valid options: {list(ETA_C.keys())}"
        )
    entry = ETA_C[condition]
    if dm < 100:
        return entry["eta_c_small"]
    else:
        return entry["eta_c_large"]