import os
import pandas as pd

# ---------------------------------------------------------------------------
# Path to the CSV — same folder as this file
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
_DRAG_CSV = os.path.join(_DATA_DIR, "drag_loss_constants.csv")

# ---------------------------------------------------------------------------
# Bearing types where subtype is required for lookup
# ---------------------------------------------------------------------------
_SUBTYPE_REQUIRED = {
    "angular_contact_ball",   # single_row / double_row / four_point
    "cylindrical_roller",     # with_cage / full_complement
    "carb_toroidal_roller",   # with_cage / full_complement
}

# ---------------------------------------------------------------------------
# KL is only meaningful for single-mounted spherical_roller_thrust bearings.
# For all other configurations it is not applicable (None).
# This note is documented here rather than in the CSV.
# ---------------------------------------------------------------------------
_KL_SINGLE_MOUNT_ONLY = {"spherical_roller_thrust"}

# ---------------------------------------------------------------------------
# Lazy loader
# ---------------------------------------------------------------------------
_drag_table: pd.DataFrame | None = None

def _get_drag_table() -> pd.DataFrame:
    global _drag_table
    if _drag_table is None:
        df = pd.read_csv(
            _DRAG_CSV,
            skipinitialspace=True,
            comment="#",
        )
        df.columns = df.columns.str.strip()
        df["bearing_type"] = df["bearing_type"].str.strip()
        df["subtype"]      = df["subtype"].str.strip().fillna("")
        _drag_table = df
    return _drag_table

# ---------------------------------------------------------------------------
# Public — get drag loss constants
# ---------------------------------------------------------------------------
def get_drag_constants(
    bearing_type: str,
    subtype: str = "",
    single_mounted: bool = True,
) -> dict:
    """
    Return the drag loss geometric constants KZ and KL for a given bearing.

    Parameters
    ----------
    bearing_type : str
        e.g. 'deep_groove_ball', 'cylindrical_roller'. Must match the CSV.
    subtype : str, optional
        Required for bearing types in _SUBTYPE_REQUIRED:
          - angular_contact_ball  : 'single_row', 'double_row', 'four_point'
          - cylindrical_roller    : 'with_cage', 'full_complement'
          - carb_toroidal_roller  : 'with_cage', 'full_complement'
        Ignored for all other bearing types.
    single_mounted : bool, optional
        Only relevant for spherical_roller_thrust. KL is defined only for
        single-mounted bearings — if False, KL is returned as None.
        Defaults to True. Ignored for all other bearing types.

    Returns
    -------
    dict with keys:
        bearing_type  : str
        subtype       : str  ('' if not applicable)
        KZ            : float
        KL            : float or None  (None if not applicable)
        KL_note       : str or None    (note if KL has usage restrictions)

    Raises
    ------
    ValueError
        If bearing_type is not found, or subtype is missing/invalid when required.
    """
    df = _get_drag_table()

    df_type = df[df["bearing_type"] == bearing_type]
    if df_type.empty:
        available = df["bearing_type"].unique().tolist()
        raise ValueError(
            f"Bearing type '{bearing_type}' not found in drag_loss_constants.csv.\n"
            f"Available types: {available}"
        )

    # subtype matching
    if bearing_type in _SUBTYPE_REQUIRED:
        if not subtype:
            available_subtypes = df_type["subtype"].tolist()
            raise ValueError(
                f"Bearing type '{bearing_type}' requires a subtype.\n"
                f"Available subtypes: {available_subtypes}"
            )
        subtype = subtype.strip()
        row_df = df_type[df_type["subtype"] == subtype]
        if row_df.empty:
            available_subtypes = df_type["subtype"].tolist()
            raise ValueError(
                f"Subtype '{subtype}' not found for bearing type '{bearing_type}'.\n"
                f"Available subtypes: {available_subtypes}"
            )
        row = row_df.iloc[0]
    else:
        row = df_type.iloc[0]
        subtype = ""

    def _val(col: str):
        if col not in row.index:
            return None
        v = row[col]
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    KL = _val("KL")
    KL_note = None

    if bearing_type in _KL_SINGLE_MOUNT_ONLY and KL is not None:
        KL_note = "KL applies to single-mounted bearings only"
        if not single_mounted:
            KL = None  # not applicable for paired/stack mounting

    return {
        "bearing_type": bearing_type,
        "subtype":      subtype,
        "KZ":           _val("KZ"),
        "KL":           KL,
        "KL_note":      KL_note,
    }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        ("deep_groove_ball",          ""),
        ("angular_contact_ball",      "single_row"),
        ("angular_contact_ball",      "double_row"),
        ("angular_contact_ball",      "four_point"),
        ("self_aligning_ball",        ""),
        ("cylindrical_roller",        "with_cage"),
        ("cylindrical_roller",        "full_complement"),
        ("tapered_roller",            ""),
        ("spherical_roller",          ""),
        ("carb_toroidal_roller",      "with_cage"),
        ("carb_toroidal_roller",      "full_complement"),
        ("thrust_ball",               ""),
        ("cylindrical_roller_thrust", ""),
        ("spherical_roller_thrust",   "",  True),   # single mounted  → KL valid
        ("spherical_roller_thrust",   "",  False),  # paired/stacked  → KL = None
    ]

    print(f"{'bearing_type':<26} {'subtype':<18} {'KZ':>5} {'KL':>6}  note")
    print("-" * 80)

    for args in test_cases:
        btype, subtype = args[0], args[1]
        single_mounted = args[2] if len(args) > 2 else True
        try:
            r = get_drag_constants(btype, subtype, single_mounted)
            KL_str = str(r["KL"]) if r["KL"] is not None else "—"
            note   = r["KL_note"] or ""
            print(f"{r['bearing_type']:<26} {r['subtype']:<18} "
                  f"{r['KZ']:>5} {KL_str:>6}  {note}")
        except ValueError as e:
            print(f"{btype:<26} {subtype:<18} ERROR: {e}")