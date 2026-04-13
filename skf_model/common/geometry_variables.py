"""
geometry_variables.py
=====================
Rolling and sliding frictional moment geometry variables G_rr and G_sl,
following SKF General Catalogue 10000 EN — Table 1a (radial bearings)
and Table 1b (thrust bearings).

Public API
----------
    get_G(bearing_type, rs, dm, Fr, Fa, n, v) -> dict
        Returns G_rr, G_sl and all intermediate values.

References
----------
    SKF General Catalogue 10000 EN, Table 1a (radial) and Table 1b (thrust).
"""

from __future__ import annotations
import math


# ---------------------------------------------------------------------------
# Safe power — avoids domain errors for zero/negative bases
# ---------------------------------------------------------------------------
def _pow(base: float, exp: float) -> float:
    if base <= 0.0:
        return 0.0
    return base ** exp


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _alpha_F(Fa: float, C0: float) -> float:
    """
    Pressure angle α_F for deep groove ball bearings under combined load.
    α_F = 24.6 * (Fa / C0)^0.24  [degrees]   — Table 1a footnote
    """
    return 24.6 * _pow(Fa / C0, 0.24)


# ---------------------------------------------------------------------------
# Table 1a — Radial bearings
# ---------------------------------------------------------------------------

def _deep_groove_ball(rs: dict, dm: float,
                      Fr: float, Fa: float,
                      C0: float = None) -> tuple[float, float, dict]:
    """
    Deep groove ball bearings — Table 1a.

    when Fa = 0:
        G_rr = R1 * dm^1.96 * Fr^0.54
        G_sl = S1 * dm^-0.26 * Fr^5/3

    when Fa > 0:
        alpha_F = 24.6 * (Fa/C0)^0.24
        G_rr = R1 * dm^1.96 * (Fr + R2/sin(alpha_F) * Fa)^0.54
        G_sl = S1 * dm^-0.145 * (Fr^5 + S2*dm^1.5 / sin(alpha_F) * Fa^4)^1/3

    C0 is required when Fa > 0.
    """
    R1 = rs["R1"]; R2 = rs["R2"]
    S1 = rs["S1"]; S2 = rs["S2"]
    extras = {}

    if Fa <= 0.0:
        G_rr = R1 * _pow(dm, 1.96) * _pow(Fr, 0.54)
        G_sl = S1 * _pow(dm, -0.26) * _pow(Fr, 5/3)
    else:
        if C0 is None:
            raise ValueError("C0 (static load rating) is required for DGBB with Fa > 0.")
        alpha = _alpha_F(Fa, C0)
        sin_a = math.sin(math.radians(alpha))
        extras["alpha_F_deg"] = alpha
        G_rr = R1 * _pow(dm, 1.96) * _pow(Fr + (R2 / sin_a) * Fa, 0.54)
        G_sl = S1 * _pow(dm, -0.145) * _pow(
            _pow(Fr, 5) + (S2 * _pow(dm, 1.5) / sin_a) * _pow(Fa, 4), 1/3)

    return G_rr, G_sl, extras


def _angular_contact_ball(rs: dict, dm: float,
                          Fr: float, Fa: float,
                          n: float, v: float) -> tuple[float, float, dict]:
    """
    Angular contact ball bearings (single row, double row) — Table 1a.

        Fg  = R3 * dm^4 * n^2
        G_rr = R1 * dm^1.97 * (Fr + Fg + R2*Fa)^0.54
        G_sl = S1 * dm^0.26 * [(Fr + Fg)^4/3 + S2*Fa^4/3]
        Fg_sl = S3 * dm^4 * n^2    (centrifugal load term for G_sl)
    """
    R1 = rs["R1"]; R2 = rs["R2"]; R3 = rs["R3"]
    S1 = rs["S1"]; S2 = rs["S2"]; S3 = rs["S3"]

    Fg_rr = R3 * _pow(dm, 4) * n**2
    Fg_sl = S3 * _pow(dm, 4) * n**2

    G_rr = R1 * _pow(dm, 1.97) * _pow(Fr + Fg_rr + R2 * Fa, 0.54)
    G_sl = S1 * _pow(dm, 0.26) * (_pow(Fr + Fg_sl, 4/3) + S2 * _pow(Fa, 4/3))

    return G_rr, G_sl, {"Fg_rr": Fg_rr, "Fg_sl": Fg_sl}


def _four_point_contact_ball(rs: dict, dm: float,
                             Fr: float, Fa: float,
                             n: float, v: float) -> tuple[float, float, dict]:
    """
    Four-point contact ball bearings — Table 1a.
    Same structure as angular contact ball bearings.
    """
    return _angular_contact_ball(rs, dm, Fr, Fa, n, v)


def _self_aligning_ball(rs: dict, dm: float,
                        Fr: float, Fa: float,
                        n: float, v: float) -> tuple[float, float, dict]:
    """
    Self-aligning ball bearings — Table 1a.

        Fg  = R3 * dm^3.5 * n^2
        G_rr = R1 * dm^2 * (Fr + Fg + R2*Fa)^0.54
        G_sl = S1 * dm^-0.12 * [(Fr + Fg)^4/3 + S2*Fa^4/3]
        Fg_sl = S3 * dm^3.5 * n^2
    """
    R1 = rs["R1"]; R2 = rs["R2"]; R3 = rs["R3"]
    S1 = rs["S1"]; S2 = rs["S2"]; S3 = rs["S3"]

    Fg_rr = R3 * _pow(dm, 3.5) * n**2
    Fg_sl = S3 * _pow(dm, 3.5) * n**2

    G_rr = R1 * _pow(dm, 2.0) * _pow(Fr + Fg_rr + R2 * Fa, 0.54)
    G_sl = S1 * _pow(dm, -0.12) * (_pow(Fr + Fg_sl, 4/3) + S2 * _pow(Fa, 4/3))

    return G_rr, G_sl, {"Fg_rr": Fg_rr, "Fg_sl": Fg_sl}


def _cylindrical_roller(rs: dict, dm: float,
                        Fr: float, Fa: float) -> tuple[float, float, dict]:
    """
    Cylindrical roller bearings — Table 1a.

        G_rr = R1 * dm^2.41 * Fr^0.31
        G_sl = S1 * dm^0.9 * Fa + S2 * dm * Fr
    """
    R1 = rs["R1"]
    S1 = rs["S1"]; S2 = rs["S2"]

    G_rr = R1 * _pow(dm, 2.41) * _pow(Fr, 0.31)
    G_sl = S1 * _pow(dm, 0.9) * Fa + S2 * dm * Fr

    return G_rr, G_sl, {}


def _tapered_roller(rs: dict, dm: float,
                    Fr: float, Fa: float) -> tuple[float, float, dict]:
    """
    Tapered roller bearings — Table 1a.

        G_rr = R1 * dm^2.38 * (Fr + R2*Y*Fa)^0.31
        G_sl = S1 * dm^0.82 * (Fr + S2*Y*Fa)

    Y is the axial load factor from the product tables.
    R2 and S2 act as Y in the formula (they encode the contact angle effect).
    """
    R1 = rs["R1"]; R2 = rs["R2"]
    S1 = rs["S1"]; S2 = rs["S2"]

    G_rr = R1 * _pow(dm, 2.38) * _pow(Fr + R2 * Fa, 0.31)
    G_sl = S1 * _pow(dm, 0.82) * (Fr + S2 * Fa)

    return G_rr, G_sl, {}


def _spherical_roller(rs: dict, dm: float,
                      Fr: float, Fa: float) -> tuple[float, float, dict]:
    """
    Spherical roller bearings — Table 1a.

    Two load cases (e and l — eccentric and line contact):
        G_rr_e = R1 * dm^1.85 * (Fr + R2*Fa)^0.54
        G_rr_l = R3 * dm^2.3  * (Fr + R4*Fa)^0.31

        G_sl_e = S1 * dm^0.25 * (Fr^4    + S2*Fa^4)^1/3
        G_sl_l = S3 * dm^0.94 * (Fr^3    + S4*Fa^4)^1/3   # note: Fr^3 per catalogue

        if G_rr_e < G_rr_l : G_rr = G_rr_e, G_sl = G_sl_e
        otherwise           : G_rr = G_rr_l, G_sl = G_sl_l
    """
    R1 = rs["R1"]; R2 = rs["R2"]; R3 = rs["R3"]; R4 = rs["R4"]
    S1 = rs["S1"]; S2 = rs["S2"]; S3 = rs["S3"]; S4 = rs["S4"]

    G_rr_e = R1 * _pow(dm, 1.85) * _pow(Fr + R2 * Fa, 0.54)
    G_rr_l = R3 * _pow(dm, 2.3)  * _pow(Fr + R4 * Fa, 0.31)

    G_sl_e = S1 * _pow(dm, 0.25) * _pow(_pow(Fr, 4) + S2 * _pow(Fa, 4), 1/3)
    G_sl_l = S3 * _pow(dm, 0.94) * _pow(_pow(Fr, 3) + S4 * _pow(Fa, 4), 1/3)

    if G_rr_e < G_rr_l:
        G_rr, G_sl, case = G_rr_e, G_sl_e, "e"
    else:
        G_rr, G_sl, case = G_rr_l, G_sl_l, "l"

    return G_rr, G_sl, {
        "G_rr_e": G_rr_e, "G_rr_l": G_rr_l,
        "G_sl_e": G_sl_e, "G_sl_l": G_sl_l,
        "case": case,
    }


def _carb_toroidal_roller(rs: dict, dm: float,
                          Fr: float, Fa: float) -> tuple[float, float, dict]:
    """
    CARB toroidal roller bearings — Table 1a.

    Threshold: Fr < (R2^1.85 * dm^0.78 / R1^1.85)^2.35

    when Fr < threshold:
        G_rr = R1 * dm^1.97 * Fr^0.54
        G_sl = S1 * dm^-0.19 * Fr^5/3

    otherwise:
        G_rr = R2 * dm^2.37 * Fr^0.31
        G_sl = S2 * dm^1.05 * Fr
    """
    R1 = rs["R1"]; R2 = rs["R2"]
    S1 = rs["S1"]; S2 = rs["S2"]

    threshold = _pow((R2**1.85 * _pow(dm, 0.78)) / (R1**1.85), 2.35)

    if Fr < threshold:
        G_rr = R1 * _pow(dm, 1.97) * _pow(Fr, 0.54)
        G_sl = S1 * _pow(dm, -0.19) * _pow(Fr, 5/3)
        case = "low_Fr"
    else:
        G_rr = R2 * _pow(dm, 2.37) * _pow(Fr, 0.31)
        G_sl = S2 * _pow(dm, 1.05) * Fr
        case = "high_Fr"

    return G_rr, G_sl, {"threshold": threshold, "case": case}


# ---------------------------------------------------------------------------
# Table 1b — Thrust bearings
# ---------------------------------------------------------------------------

def _thrust_ball(rs: dict, dm: float,
                 Fa: float) -> tuple[float, float, dict]:
    """
    Thrust ball bearings — Table 1b.

        G_rr = R1 * dm^1.83 * Fa^0.54
        G_sl = S1 * dm^0.05 * Fa^4/3
    """
    R1 = rs["R1"]
    S1 = rs["S1"]

    G_rr = R1 * _pow(dm, 1.83) * _pow(Fa, 0.54)
    G_sl = S1 * _pow(dm, 0.05) * _pow(Fa, 4/3)

    return G_rr, G_sl, {}


def _cylindrical_roller_thrust(rs: dict, dm: float,
                                Fa: float) -> tuple[float, float, dict]:
    """
    Cylindrical roller thrust bearings — Table 1b.

        G_rr = R1 * dm^2.38 * Fa^0.31
        G_sl = S1 * dm^0.62 * Fa
    """
    R1 = rs["R1"]
    S1 = rs["S1"]

    G_rr = R1 * _pow(dm, 2.38) * _pow(Fa, 0.31)
    G_sl = S1 * _pow(dm, 0.62) * Fa

    return G_rr, G_sl, {}


def _spherical_roller_thrust(rs: dict, dm: float,
                              Fr: float, Fa: float,
                              n: float, v: float) -> tuple[float, float, dict]:
    """
    Spherical roller thrust bearings — Table 1b.

    Rolling:
        G_rr_e = R1 * dm^1.96 * (Fr + R2*Fa)^0.54
        G_rr_l = R3 * dm^2.39 * (Fr + R4*Fa)^0.31
        if G_rr_e < G_rr_l: G_rr = G_rr_e  else G_rr = G_rr_l

    Sliding:
        G_sl_e = S1 * dm^-0.35 * (Fr^5/3 + S2*Fa^5/3)
        G_sl_l = S3 * dm^0.89  * (Fr + Fa)
        if G_sl_e < G_sl_l: G_sr = G_sl_e  else G_sr = G_sl_l

        G_f    = S4 * dm^0.76 * (Fr + S5*Fa)
        G_sl   = G_sr + G_f / exp(1e-6 * (n*v)^1.4 * dm)
    """
    R1 = rs["R1"]; R2 = rs["R2"]; R3 = rs["R3"]; R4 = rs["R4"]
    S1 = rs["S1"]; S2 = rs["S2"]; S3 = rs["S3"]; S4 = rs["S4"]; S5 = rs["S5"]

    # Rolling
    G_rr_e = R1 * _pow(dm, 1.96) * _pow(Fr + R2 * Fa, 0.54)
    G_rr_l = R3 * _pow(dm, 2.39) * _pow(Fr + R4 * Fa, 0.31)
    G_rr   = G_rr_e if G_rr_e < G_rr_l else G_rr_l

    # Sliding
    G_sl_e = S1 * _pow(dm, -0.35) * (_pow(Fr, 5/3) + S2 * _pow(Fa, 5/3))
    G_sl_l = S3 * _pow(dm, 0.89)  * (Fr + Fa)
    G_sr   = G_sl_e if G_sl_e < G_sl_l else G_sl_l

    G_f    = S4 * _pow(dm, 0.76) * (Fr + S5 * Fa)
    denom  = math.exp(1e-6 * _pow(n * v, 1.4) * dm)
    G_sl   = G_sr + G_f / denom

    return G_rr, G_sl, {
        "G_rr_e": G_rr_e, "G_rr_l": G_rr_l,
        "G_sl_e": G_sl_e, "G_sl_l": G_sl_l,
        "G_sr": G_sr, "G_f": G_f,
        "case_rr": "e" if G_rr_e < G_rr_l else "l",
        "case_sl": "e" if G_sl_e < G_sl_l else "l",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
_DISPATCH = {
    "deep_groove_ball":          _deep_groove_ball,
    "angular_contact_ball":      _angular_contact_ball,
    "four_point_contact_ball":   _four_point_contact_ball,
    "self_aligning_ball":        _self_aligning_ball,
    "cylindrical_roller":        _cylindrical_roller,
    "tapered_roller":            _tapered_roller,
    "spherical_roller":          _spherical_roller,
    "carb_toroidal_roller":      _carb_toroidal_roller,
    "thrust_ball":               _thrust_ball,
    "cylindrical_roller_thrust": _cylindrical_roller_thrust,
    "spherical_roller_thrust":   _spherical_roller_thrust,
}

def get_G(
    bearing_type: str,
    rs:           dict,
    dm:           float,
    Fr:           float,
    Fa:           float,
    n:            float  = 0.0,
    v:            float  = 0.0,
    C0:           float  = None,
) -> dict:
    """
    Return G_rr and G_sl for the given bearing type.

    Parameters
    ----------
    bearing_type : str
        SKF type key, e.g. 'deep_groove_ball', 'spherical_roller'.
    rs : dict
        R and S constants from get_RS_constants().
    dm : float
        Bearing mean diameter 0.5*(d+D) [mm].
    Fr : float
        Radial load [N].
    Fa : float
        Axial load [N].
    n : float
        Rotational speed [r/min]. Required for bearings with centrifugal
        load term Fg (angular contact, self-aligning, spherical roller thrust).
    v : float
        Actual viscosity [mm²/s]. Required for spherical roller thrust.
    C0 : float, optional
        Static load rating [N]. Required for deep groove ball with Fa > 0.

    Returns
    -------
    dict with keys:
        G_rr   : float
        G_sl   : float
        extras : dict   (intermediate values, case selectors, etc.)
    """
    func = _DISPATCH.get(bearing_type)
    if func is None:
        raise ValueError(
            f"Unknown bearing type: '{bearing_type}'.\n"
            f"Available: {list(_DISPATCH.keys())}"
        )

    # Route arguments based on bearing type
    thrust_types = {"thrust_ball", "cylindrical_roller_thrust"}
    speed_types  = {"angular_contact_ball", "four_point_contact_ball",
                    "self_aligning_ball", "spherical_roller_thrust"}

    if bearing_type in thrust_types:
        G_rr, G_sl, extras = func(rs, dm, Fa)
    elif bearing_type == "deep_groove_ball":
        G_rr, G_sl, extras = func(rs, dm, Fr, Fa, C0)
    elif bearing_type in speed_types:
        G_rr, G_sl, extras = func(rs, dm, Fr, Fa, n, v)
    else:
        G_rr, G_sl, extras = func(rs, dm, Fr, Fa)

    return {"G_rr": G_rr, "G_sl": G_sl, "extras": extras}


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Dummy RS constants for a 6206 (series 62)
    rs_dgbb = {
        "R1": 3.9e-7, "R2": 1.7,  "R3": None, "R4": None,
        "S1": 3.23e-3, "S2": 36.5, "S3": None, "S4": None, "S5": None,
    }

    dm = 46.0   # 0.5*(30+62)

    print("=== Deep groove ball — radial only ===")
    r = get_G("deep_groove_ball", rs_dgbb, dm, Fr=3000, Fa=0)
    print(f"  G_rr = {r['G_rr']:.4f}   G_sl = {r['G_sl']:.4f}")

    print("\n=== Deep groove ball — combined load (C0=11200 N) ===")
    r = get_G("deep_groove_ball", rs_dgbb, dm, Fr=3000, Fa=500, C0=11200)
    print(f"  G_rr = {r['G_rr']:.4f}   G_sl = {r['G_sl']:.4f}")
    print(f"  alpha_F = {r['extras'].get('alpha_F_deg', 'n/a'):.2f} deg")