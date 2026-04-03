import os
import pandas as pd

# ---------------------------------------------------------------------------
# Path to the CSV — same folder as this file
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
_SEAL_CSV = os.path.join(_DATA_DIR, "seal_frictional_moment.csv")

# ---------------------------------------------------------------------------
# Lazy loader — reads CSV once, caches the DataFrame
# ---------------------------------------------------------------------------
_seal_table: pd.DataFrame | None = None

def _get_seal_table() -> pd.DataFrame:
    global _seal_table
    if _seal_table is None:
        df = pd.read_csv(
            _SEAL_CSV,
            skipinitialspace=True,
            comment="#",
        )
        df.columns = df.columns.str.strip()
        df["seal_type"]    = df["seal_type"].str.strip()
        df["bearing_type"] = df["bearing_type"].str.strip()
        df["ds"]           = df["ds"].str.strip()

        # Convert D range columns: empty → 0 for D_over, inf for D_incl
        df["D_over"] = pd.to_numeric(df["D_over"], errors="coerce").fillna(0.0)
        df["D_incl"] = pd.to_numeric(df["D_incl"], errors="coerce").fillna(float("inf"))

        _seal_table = df
    return _seal_table


# ---------------------------------------------------------------------------
# Public — get seal constants
# ---------------------------------------------------------------------------
def get_seal_constants(seal_type: str, bearing_type: str, D: float) -> dict:
    """
    Return the seal frictional moment exponent and constants for a given
    seal type, bearing type, and bearing outside diameter D [mm].

    Parameters
    ----------
    seal_type : str
        One of: 'RSL', 'RSH', 'RS1', 'LS', 'CS_CS2_CS5'.
        CS, CS2 and CS5 seals share the same constants — pass 'CS_CS2_CS5'.
    bearing_type : str
        e.g. 'deep_groove_ball', 'cylindrical_roller'. Must match the CSV.
    D : float
        Bearing outside diameter [mm]. Used to select the correct D range row.

    Returns
    -------
    dict with keys: seal_type, bearing_type, D_over, D_incl, beta, KS1, KS2, ds
        ds is a list of strings, e.g. ['d1', 'd2'], ['d2'], ['E'].

    Raises
    ------
    ValueError
        If no matching row is found for the given combination.
    """
    df = _get_seal_table()

    # filter by seal_type and bearing_type
    mask = (df["seal_type"] == seal_type) & (df["bearing_type"] == bearing_type)
    df_filtered = df[mask]

    if df_filtered.empty:
        available = df[["seal_type", "bearing_type"]].drop_duplicates().values.tolist()
        raise ValueError(
            f"No entry found for seal_type='{seal_type}', "
            f"bearing_type='{bearing_type}'.\n"
            f"Available combinations: {available}"
        )

    # find the row where D_over < D <= D_incl
    mask_d = (df_filtered["D_over"] < D) & (D <= df_filtered["D_incl"])
    df_match = df_filtered[mask_d]

    if df_match.empty:
        ranges = df_filtered[["D_over", "D_incl"]].values.tolist()
        raise ValueError(
            f"Outside diameter D={D} mm is outside all defined ranges for "
            f"seal_type='{seal_type}', bearing_type='{bearing_type}'.\n"
            f"Defined ranges (D_over, D_incl]: {ranges}"
        )

    row = df_match.iloc[0]

    return {
        "seal_type":    row["seal_type"],
        "bearing_type": row["bearing_type"],
        "D_over":       row["D_over"],
        "D_incl":       row["D_incl"],
        "beta":         float(row["beta"]),
        "KS1":          float(row["KS1"]),
        "KS2":          float(row["KS2"]),
        "ds":           row["ds"].split(),   # e.g. "d1 d2" -> ["d1", "d2"]
    }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        # RSL — D <= 25 (beta=0 row)
        ("RSL", "deep_groove_ball",      20),
        # RSL — 25 < D <= 52
        ("RSL", "deep_groove_ball",      40),
        # RSH
        ("RSH", "deep_groove_ball",      35),
        # RS1 deep groove ball — four D ranges
        ("RS1", "deep_groove_ball",      50),
        ("RS1", "deep_groove_ball",      70),
        ("RS1", "deep_groove_ball",      90),
        ("RS1", "deep_groove_ball",     120),
        # RS1 angular contact
        ("RS1", "angular_contact_ball",  80),
        # RS1 self-aligning
        ("RS1", "self_aligning_ball",    60),
        # LS
        ("LS",  "cylindrical_roller",   200),
        # CS/CS2/CS5
        ("CS_CS2_CS5", "spherical_roller",      150),
        ("CS_CS2_CS5", "carb_toroidal_roller",  100),
    ]

    print(f"{'seal_type':<12} {'bearing_type':<22} {'D':>5}  "
          f"{'D_over':>7} {'D_incl':>7}  {'beta':>5} {'KS1':>7} {'KS2':>5}  ds")
    print("-" * 90)

    for seal, btype, D in test_cases:
        try:
            r = get_seal_constants(seal, btype, D)
            D_incl_str = str(r["D_incl"]) if r["D_incl"] != float("inf") else "inf"
            print(f"{r['seal_type']:<12} {r['bearing_type']:<22} {D:>5}  "
                  f"{r['D_over']:>7} {D_incl_str:>7}  "
                  f"{r['beta']:>5} {r['KS1']:>7} {r['KS2']:>5}  {r['ds']}")
        except ValueError as e:
            print(f"{seal:<12} {btype:<22} {D:>5}  ERROR: {e}")