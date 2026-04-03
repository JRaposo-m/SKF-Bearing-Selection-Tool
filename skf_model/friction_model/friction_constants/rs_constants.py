import os
import re
import pandas as pd

# ---------------------------------------------------------------------------
# Path to the CSV — same folder as this file
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
_RS_CSV = os.path.join(_DATA_DIR, "friction_RS_constants.csv")

# ---------------------------------------------------------------------------
# Bearing types where the CSV 'series' column is a full string key
# (not derivable from designation via get_series).
# For these, the designation passed to get_RS_constants must match
# the series string in the CSV exactly.
# ---------------------------------------------------------------------------
_DIRECT_SERIES_TYPES = {
    "angular_contact_ball",
    "carb_toroidal_roller",       # series like "C22", "C30", ...
    "spherical_roller_thrust",    # series like "292", "292 E", "293 E", ...
    "tapered_roller",             # covers inch series: "LL", "L", "LM", "M", ...
}

# ---------------------------------------------------------------------------
# High-capacity suffix -> CSV series key mapping
# Cylindrical roller high-capacity variants are identified by their suffix,
# not by the numeric series alone (e.g. NU 2222 ECML -> "22_high_cap").
# Add more entries here if new high-capacity series are introduced.
# ---------------------------------------------------------------------------
_HIGH_CAP_SUFFIXES: dict[str, dict[str, str]] = {
    "cylindrical_roller": {
        # suffix (upper-case)  ->  CSV series key
        "ECML": "22_high_cap",
        "ECM":  "22_high_cap",
        "ECP":  "22_high_cap",
        "ECMB": "22_high_cap",
        "ECJL": "23_high_cap",
        "ECJ":  "23_high_cap",
    },
}

# ---------------------------------------------------------------------------
# Lazy loader — reads CSV once, caches the DataFrame
# ---------------------------------------------------------------------------
_rs_table: pd.DataFrame | None = None

def _get_rs_table() -> pd.DataFrame:
    global _rs_table
    if _rs_table is None:
        _rs_table = pd.read_csv(
            _RS_CSV,
            skipinitialspace=True,
            comment="#",       # allows comment lines in the CSV
        )
        # normalise column names and string columns
        _rs_table.columns = _rs_table.columns.str.strip()
        _rs_table["type"]   = _rs_table["type"].str.strip()
        _rs_table["series"] = _rs_table["series"].astype(str).str.strip()
    return _rs_table

# ---------------------------------------------------------------------------
# Series extraction from designation
# ---------------------------------------------------------------------------
def get_series(designation: str) -> str:
    """
    Extract bearing series string from an SKF designation.

    Rules (applied in order):
        1. Has '/'  -> series = everything before '/'       e.g. '618/500 MA' -> '618'
        2. Leading digit count:
             >= 5 digits -> first 3                         e.g. '61880 MA'   -> '618'
              4 digits   -> first 2                         e.g. '6080 M'     -> '60'
              3 digits   -> first 2                         e.g. '623'        -> '62'

    Suffixes after a space or dash are ignored.
    Leading alphabetic prefixes (e.g. NU, NJ, NUP) are stripped first.
    """
    # Remove leading alphabetic prefix (e.g. "NU", "NJ", "NUP", "N", "NF"...)
    # and any spaces, so "NU 210" -> "210", "NJ 2310" -> "2310"
    stripped = designation.strip()
    stripped = re.sub(r'^[A-Za-z]+\s*', '', stripped)
    clean = re.split(r'[\s\-]', stripped)[0]

    if '/' in clean:
        return clean.split('/')[0]

    digits = re.match(r'\d+', clean)
    if not digits:
        raise ValueError(f"Cannot parse series from designation: '{designation}'")

    num = digits.group()
    if len(num) >= 5:
        return num[:3]
    else:
        return num[:2]

# ---------------------------------------------------------------------------
# Series matching with progressive fallback
# ---------------------------------------------------------------------------
def _match_series(designation: str, df_type: pd.DataFrame, bearing_type: str) -> str:
    """
    Extract series from designation and match against the known series in
    df_type. Steps:

    1. Check high-capacity suffix table (e.g. "NU 2222 ECML" -> "22_high_cap")
    2. Try get_series() directly
    3. Progressively shorten candidate until a match is found

    This handles cases like cylindrical roller "NU 210" where get_series()
    returns "21" but the CSV series is "2" (bore code is 2 digits).
    """
    known = set(df_type["series"].tolist())

    # 1. High-capacity suffix check
    suffix_map = _HIGH_CAP_SUFFIXES.get(bearing_type, {})
    if suffix_map:
        upper = designation.upper()
        for suffix, series_key in suffix_map.items():
            if upper.endswith(suffix) or f" {suffix}" in upper:
                if series_key in known:
                    return series_key

    # 2. Normal numeric extraction
    try:
        candidate = get_series(designation)
    except ValueError:
        candidate = None

    if candidate and candidate in known:
        return candidate

    # 3. Progressive shortening fallback
    if candidate:
        for length in range(len(candidate) - 1, 0, -1):
            shorter = candidate[:length]
            if shorter in known:
                return shorter

    available = df_type["series"].tolist()
    raise ValueError(
        f"Series for designation '{designation}' not found for type '{bearing_type}'.\n"
        f"Available series: {available}"
    )

# ---------------------------------------------------------------------------
# Public — get R and S constants
# ---------------------------------------------------------------------------
def get_RS_constants(bearing_type: str, designation: str) -> dict:
    """
    Return the R and S geometric constants for friction moment calculation.

    Parameters
    ----------
    bearing_type : str
        e.g. 'deep_groove_ball'. Must match the 'type' column in the CSV.
    designation : str
        Full bearing designation, e.g. '6206', '618/500 MA', '61802-2RS1'.
        The series is extracted automatically for most types.
        For bearing types in _DIRECT_SERIES_TYPES, the designation must match
        the series string in the CSV exactly.
        For bearing types with a single constant set (thrust_ball,
        cylindrical_roller_thrust), the designation is not used for series
        matching — the 'all' row is returned directly.

    Returns
    -------
    dict with keys: series, R1, R2, R3, R4, S1, S2, S3, S4, S5
        Missing constants are returned as None.

    Raises
    ------
    ValueError
        If bearing_type or series is not found in the CSV.
    """
    df = _get_rs_table()

    # filter by type first
    df_type = df[df["type"] == bearing_type]
    if df_type.empty:
        available = df["type"].unique().tolist()
        raise ValueError(
            f"Bearing type '{bearing_type}' not found in friction_RS_constants.csv.\n"
            f"Available types: {available}"
        )

    # bearing types with a single 'all' row — no series extraction needed
    if (df_type["series"] == "all").all():
        row = df_type.iloc[0]
        series = "all"
    # bearing types where designation IS the series key
    elif bearing_type in _DIRECT_SERIES_TYPES:
        series = designation.strip()
        row_df = df_type[df_type["series"] == series]
        if row_df.empty:
            available_series = df_type["series"].tolist()
            raise ValueError(
                f"Series '{series}' not found for type '{bearing_type}'.\n"
                f"Available series: {available_series}"
            )
        row = row_df.iloc[0]
    else:
        series = _match_series(designation, df_type, bearing_type)
        row_df = df_type[df_type["series"] == series]
        row = row_df.iloc[0]

    def _val(col: str):
        """Return float or None for missing/NaN columns."""
        if col not in row.index:
            return None
        v = row[col]
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    return {
        "series": series,
        "R1":     _val("R1"),
        "R2":     _val("R2"),
        "R3":     _val("R3"),
        "R4":     _val("R4"),
        "S1":     _val("S1"),
        "S2":     _val("S2"),
        "S3":     _val("S3"),
        "S4":     _val("S4"),
        "S5":     _val("S5"),
    }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        # deep groove ball — series extracted from designation
        ("deep_groove_ball",          "623"),
        ("deep_groove_ball",          "624-2Z"),
        ("deep_groove_ball",          "618/500 MA"),
        ("deep_groove_ball",          "61880 MA"),
        ("deep_groove_ball",          "6080 M"),
        ("deep_groove_ball",          "61802-2RS1"),
        ("deep_groove_ball",          "619/4"),
        # angular contact — series is the full series string in the CSV
        ("angular_contact_ball",      "72xx BECBP"),
        ("angular_contact_ball",      "73xx ACCBM"),
        # self aligning ball
        ("self_aligning_ball",        "1206"),
        ("self_aligning_ball",        "2210"),
        # cylindrical roller — normal, high-cap series 22, high-cap series 23
        ("cylindrical_roller",        "NU 210"),
        ("cylindrical_roller",        "NJ 2310"),
        ("cylindrical_roller",        "NU 2222 ECML"),
        ("cylindrical_roller",        "NU 2222 ECM"),
        ("cylindrical_roller",        "NU 2322 ECJL"),
        ("cylindrical_roller",        "NU 2322 ECJ"),
        # tapered roller — metric series extracted; inch series passed directly
        ("tapered_roller",            "302"),
        ("tapered_roller",            "330"),
        ("tapered_roller",            "LL"),
        ("tapered_roller",            "LM"),
        ("tapered_roller",            "HM"),
        ("tapered_roller",            "all_other"),
        # spherical roller — series extracted
        ("spherical_roller",          "22210"),
        ("spherical_roller",          "23040"),
        ("spherical_roller",          "24048"),
        # thrust types — single 'all' row, designation irrelevant for lookup
        ("thrust_ball",               "51106"),
        ("cylindrical_roller_thrust", "81106"),
        # CARB toroidal roller — series passed directly
        ("carb_toroidal_roller",      "C22"),
        ("carb_toroidal_roller",      "C49"),
        ("carb_toroidal_roller",      "C60"),
        # spherical roller thrust — series passed directly
        ("spherical_roller_thrust",   "292"),
        ("spherical_roller_thrust",   "292 E"),
        ("spherical_roller_thrust",   "293 E"),
        ("spherical_roller_thrust",   "294 E"),
    ]

    print(f"{'Designation':<25} {'Type':<30} {'series':<14} "
          f"{'R1':>10} {'R2':>8} {'R3':>10} {'R4':>6} "
          f"{'S1':>8} {'S2':>8} {'S3':>10} {'S4':>6} {'S5':>6}")
    print("-" * 140)

    for btype, desig in test_cases:
        try:
            r = get_RS_constants(btype, desig)
            print(f"{desig:<25} {btype:<30} {r['series']:<14} "
                  f"{str(r['R1']):>10} {str(r['R2']):>8} {str(r['R3']):>10} {str(r['R4']):>6} "
                  f"{str(r['S1']):>8} {str(r['S2']):>8} {str(r['S3']):>10} {str(r['S4']):>6} {str(r['S5']):>6}")
        except ValueError as e:
            print(f"{desig:<25} {btype:<30} ERROR: {e}")