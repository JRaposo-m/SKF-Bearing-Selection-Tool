"""
selector.py
===========
Bearing selector for deep groove ball bearings (DGBB).
Follows the SKF selection procedure described in SKF General Catalogue 10000 EN.

Workflow
--------
1. Compute required dynamic load rating C_req from L10h target (ISO 281 inverted)
2. Filter bearing database: C >= C_req  (and optionally d, D, designation filters)
3. For each candidate: run BearingLife → L10h, L_skf, s0, kappa
4. Run frictional_moment for candidates that pass (optional, controlled by
   `compute_friction=True`)
5. Return a ranked DataFrame + print a summary table

Usage
-----
    from selector import select_bearings

    df = select_bearings(
        Fr              = 4060,      # radial load [N]
        Fa              = 0,         # axial load  [N]
        n               = 1500,      # speed [rpm]
        L10h_required   = 20_000,    # minimum required life [h]
        viscosity_grade = "100",     # ISO VG grade
        temperature     = 70,        # operating temperature [°C]
        contamination   = "normal_cleanliness",
        # --- optional filters ---
        d               = None,      # fix bore diameter [mm]
        D               = None,      # fix outside diameter [mm]
        designation_contains = None, # e.g. "2RS1"
        # --- friction ---
        compute_friction = True,
        v_actual         = None,     # if None, computed from VG + temperature
        H                = 0,        # oil level [mm] — 0 for grease/oil-air
        lubrication      = "oil_air",
        lubricant        = "mineral",
        seal_type        = None,
        # --- output ---
        top_n           = None,      # limit output rows (None = all)
        sort_by         = "L_skf",   # 'L_skf', 'L10h', 'M_tot', 'margin'
        print_table     = True,
    )
"""

from __future__ import annotations

import os
import sys
import math
import warnings
from typing import Literal, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup — works whether selector.py sits at repo root or inside skf_model
# ---------------------------------------------------------------------------
_HERE = os.path.abspath(os.path.dirname(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))  # sobe para a raiz do repo
sys.path.insert(0, _ROOT)

from skf_model.common.life import BearingLife
from skf_model.common.frictional_moment import frictional_moment
from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CSV_PATH = os.path.join(
    _ROOT, "skf_model", "bearings", "data",
    "deep_groove_ball", "deep_groove_ball.csv",
)

_LIFE_EXPONENT = 3  # ball bearings (ISO 281)

SortKey       = Literal["L_skf", "L10h", "M_tot", "margin", "s0"]
LubricationType = Literal["oil_bath", "oil_air"]


# ---------------------------------------------------------------------------
# Step 1 — Required C from L10h target  (ISO 281 inverted)
# ---------------------------------------------------------------------------

def required_C(Fr: float, Fa: float, n: float, L10h_req: float,
               f0: float = 14.0, C0_est: float = None,
               clearance: str = "normal") -> float:
    """
    Minimum dynamic load rating C [N] to achieve L10h_req [h].

    Uses P = Fr (conservative — ignores axial factors) for the first pass.
    If you already know C0, pass it to refine P with axial factors.

    ISO 281:  L10h = (10^6 / 60*n) * (C/P)^3
    Inverted: C = P * (L10h * 60 * n / 10^6)^(1/3)
    """
    # Conservative equivalent load: ignore axial for the filter step
    P = Fr
    L10_req = L10h_req * 60.0 * n / 1e6   # million revolutions
    return P * (L10_req ** (1.0 / _LIFE_EXPONENT))


# ---------------------------------------------------------------------------
# Step 2 — Load and filter database
# ---------------------------------------------------------------------------

def _load_db() -> pd.DataFrame:
    db = pd.read_csv(_CSV_PATH, skipinitialspace=True)
    # CSV está sempre em kN → converter sempre para N
    db["C"]  = db["C"]  * 1000
    db["C0"] = db["C0"] * 1000
    db["Pu"] = db["Pu"] * 1000
    return db

def _filter_db(
    db: pd.DataFrame,
    C_req: float,
    d: Optional[float],
    D: Optional[float],
    designation_contains: Optional[str],
) -> pd.DataFrame:
    mask = db["C"] >= C_req
    if d is not None:
        mask &= db["d"] == d
    if D is not None:
        mask &= db["D"] == D
    if designation_contains:
        mask &= db["designation"].str.contains(designation_contains, na=False)
    return db[mask].copy()


# ---------------------------------------------------------------------------
# Step 3 — BearingLife for each candidate
# ---------------------------------------------------------------------------

def _run_life(row: pd.Series, Fr: float, Fa: float, n: float,
              viscosity_grade: str, temperature: float,
              contamination: str, clearance: str = "normal") -> dict:
    bearing = {
        "type":      "deep_groove_ball",
        "C":         float(row["C"]),
        "C0":        float(row["C0"]),
        "Pu":        float(row["Pu"]),
        "f0":        float(row["f0"]),
        "d":         float(row["d"]),
        "dm":        0.5 * (float(row["d"]) + float(row["D"])),
        "kr":        float(row["kr"]),
        "clearance": clearance,
    }
    bl = BearingLife(
        bearing         = bearing,
        Fr              = Fr,
        Fa              = Fa,
        n               = n,
        viscosity_grade = viscosity_grade,
        temperature     = temperature,
        contamination   = contamination,
    )
    s = bl.summary()
    return {
        "P":      s["P"],
        "L10h":   s["L10h"],
        "a_skf":  s["a_skf"],
        "L_skf":  s["L_skf"],
        "kappa":  s["kappa"],
        "eta_c":  s["eta_c"],
        "s0":     s["s0"],
    }


# ---------------------------------------------------------------------------
# Step 4 — frictional_moment for each candidate
# ---------------------------------------------------------------------------

def _run_friction(row: pd.Series, Fr: float, Fa: float, n: float,
                  v: float, H: float, lubrication: str,
                  lubricant: str, seal_type) -> dict:
    
    # Detetar vedante automaticamente pela designação se seal_type não for fornecido
    if seal_type is None:
        desig = str(row["designation"]).upper()
        if "2RSL" in desig or "RSL" in desig:
            detected_seal = "RSL"
        elif "2RSH" in desig or "RSH" in desig:
            detected_seal = "RSH"
        elif "2RS" in desig or "-RS" in desig:
            detected_seal = "RS1"
        elif "2RZ" in desig or "-RZ" in desig:
            detected_seal = None   # vedante sem contacto → sem atrito de vedante
        elif "2Z" in desig or "-Z" in desig:
            detected_seal = None   # escudo metálico → sem atrito de vedante
        else:
            detected_seal = None
    else:
        detected_seal = seal_type

    try:
        r = frictional_moment(
            bearing_type = "deep_groove_ball",
            designation  = str(row["designation"]),
            d            = float(row["d"]),
            D            = float(row["D"]),
            B            = float(row["B"]),
            Fr           = Fr,
            Fa           = Fa,
            n            = n,
            v            = v,
            H            = H,
            lubrication  = lubrication,
            lubricant    = lubricant,
            seal_type    = detected_seal,  # ← usa o detetado
            C0           = float(row["C0"]),
        )
        return {
            "M_rr":   r.M_rr,
            "M_sl":   r.M_sl,
            "M_drag": r.M_drag,
            "M_seal": r.M_seal,
            "M_tot":  r.M_tot,
        }
    except Exception as e:
        warnings.warn(f"Friction calc failed for {row['designation']}: {e}")
        return {"M_rr": None, "M_sl": None,
                "M_drag": None, "M_seal": None, "M_tot": None}


# ---------------------------------------------------------------------------
# Step 5 — Print table
# ---------------------------------------------------------------------------

def _print_table(df: pd.DataFrame, L10h_required: float,
                 compute_friction: bool) -> None:
    cols_life = ["designation", "d", "D", "C_kN", "C0_kN",
                 "P_N", "L10h_h", "L_skf_h", "margin", "kappa", "s0"]
    cols_fric = ["M_rr", "M_sl", "M_drag", "M_seal", "M_tot"]

    header_cols = cols_life + (cols_fric if compute_friction else [])
    present = [c for c in header_cols if c in df.columns]

    # widths
    w = {"designation": 20, "d": 5, "D": 5, "C_kN": 8, "C0_kN": 8,
         "P_N": 8, "L10h_h": 12, "L_skf_h": 12, "margin": 8,
         "kappa": 7, "s0": 6,
         "M_rr": 9, "M_sl": 9, "M_drag": 9, "M_seal": 9, "M_tot": 10}

    header = "".join(c.ljust(w.get(c, 10)) for c in present)
    sep    = "-" * len(header)
    print(f"\n  Required L10h : {L10h_required:,.0f} h")
    print(f"  Candidates    : {len(df)}\n")
    print("  " + header)
    print("  " + sep)

    fmt = {
        "designation": lambda v: str(v).ljust(20),
        "d":           lambda v: f"{v:.0f}".ljust(5),
        "D":           lambda v: f"{v:.0f}".ljust(5),
        "C_kN":        lambda v: f"{v:.1f}".ljust(8),
        "C0_kN":       lambda v: f"{v:.1f}".ljust(8),
        "P_N":         lambda v: f"{v:.0f}".ljust(8),
        "L10h_h":      lambda v: f"{v:,.0f}".ljust(12),
        "L_skf_h":     lambda v: f"{v:,.0f}".ljust(12),
        "margin":      lambda v: f"{v:.2f}".ljust(8),
        "kappa":       lambda v: f"{v:.2f}".ljust(7),
        "s0":          lambda v: f"{v:.2f}".ljust(6),
        "M_rr":        lambda v: f"{v:.1f}".ljust(9)  if v is not None else "—".ljust(9),
        "M_sl":        lambda v: f"{v:.1f}".ljust(9)  if v is not None else "—".ljust(9),
        "M_drag":      lambda v: f"{v:.1f}".ljust(9)  if v is not None else "—".ljust(9),
        "M_seal":      lambda v: f"{v:.1f}".ljust(9)  if v is not None else "—".ljust(9),
        "M_tot":       lambda v: f"{v:.1f}".ljust(10) if v is not None else "—".ljust(10),
    }

    for _, row in df.iterrows():
        line = "  " + "".join(
            fmt[c](row[c]) for c in present if c in fmt
        )
        print(line)

    print()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_bearings(
    # Operating conditions
    Fr:                  float,
    Fa:                  float,
    n:                   float,
    L10h_required:       float,
    viscosity_grade:     str   = "100",
    temperature:         float = 70.0,
    contamination:       str   = "normal_cleanliness",
    clearance:           str   = "normal",
    # Geometry filters
    d:                   Optional[float] = None,
    D:                   Optional[float] = None,
    designation_contains: Optional[str] = None,
    # Friction
    compute_friction:    bool  = True,
    v_actual:            Optional[float] = None,
    H:                   float = 0.0,
    lubrication:         LubricationType = "oil_air",
    lubricant:           str   = "mineral",
    seal_type                  = None,
    # Output
    top_n:               Optional[int]  = None,
    sort_by:             SortKey        = "L_skf",
    print_table:         bool  = True,
) -> pd.DataFrame:
    """
    Select deep groove ball bearings for given operating conditions.

    Returns
    -------
    pd.DataFrame
        One row per candidate bearing, sorted by `sort_by`.
        Columns: designation, d, D, C_kN, C0_kN, P_N, L10h_h, L_skf_h,
                 margin, kappa, eta_c, s0  [+ M_rr, M_sl, M_drag, M_seal,
                 M_tot if compute_friction=True]
    """
    # ------------------------------------------------------------------
    # 1. Required C (conservative filter)
    # ------------------------------------------------------------------
    C_req = required_C(Fr, Fa, n, L10h_required)

    # ------------------------------------------------------------------
    # 2. Load and filter database
    # ------------------------------------------------------------------
    db         = _load_db()
    candidates = _filter_db(db, C_req, d, D, designation_contains)

    if candidates.empty:
        print(f"  No candidates found (C_req = {C_req/1000:.1f} kN).")
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # 3. BearingLife for each candidate
    # ------------------------------------------------------------------
    records = []
    for _, row in candidates.iterrows():
        try:
            life = _run_life(
                row, Fr, Fa, n, viscosity_grade, temperature,
                contamination, clearance,
            )
        except Exception as e:
            warnings.warn(f"Life calc failed for {row['designation']}: {e}")
            continue

        rec = {
            "designation": row["designation"],
            "d":           float(row["d"]),
            "D":           float(row["D"]),
            "B":           float(row["B"]),
            "C_kN":        float(row["C"]) / 1000,
            "C0_kN":       float(row["C0"]) / 1000,
            "f0":          float(row["f0"]),
            "kr":          float(row["kr"]),
            "Pu":          float(row["Pu"]),
            **life,
            "P_N":         life["P"],
            "L10h_h":      life["L10h"],
            "L_skf_h":     life["L_skf"],
            "margin":      life["L_skf"] / L10h_required,
        }
        records.append(rec)

    if not records:
        print("  All candidates failed life calculation.")
        return pd.DataFrame()

    result = pd.DataFrame(records)

    # ------------------------------------------------------------------
    # 4. Friction (optional)
    # ------------------------------------------------------------------
    if compute_friction:
        vg_int = int(str(viscosity_grade).replace("VG", "").strip())
        v = v_actual if v_actual is not None else get_viscosity(vg_int, temperature)

        frictions = []
        for _, row in result.iterrows():
            db_row = candidates[candidates["designation"] == row["designation"]].iloc[0]
            fric = _run_friction(
                db_row, Fr, Fa, n, v, H, lubrication, lubricant, seal_type,
            )
            frictions.append(fric)

        fric_df = pd.DataFrame(frictions, index=result.index)
        result  = pd.concat([result, fric_df], axis=1)

    # ------------------------------------------------------------------
    # 5. Sort and trim
    # ------------------------------------------------------------------
    if sort_by in result.columns:
        ascending = sort_by == "M_tot"   # lower friction = better
        result = result.sort_values(sort_by, ascending=ascending)
    
    if top_n is not None:
        result = result.head(top_n)

    result = result.reset_index(drop=True)

    # ------------------------------------------------------------------
    # 6. Print
    # ------------------------------------------------------------------
    if print_table:
        _print_table(result, L10h_required, compute_friction)

    return result


# ---------------------------------------------------------------------------
# Quick test — mirrors the script you already had
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    df = select_bearings(
        Fr                   = 2500,        # carga radial reduzida [N]
        Fa                   = 500,
        n                    = 1500,
        L10h_required        = 10_000,      # vida reduzida [h]
        viscosity_grade      = "150",
        temperature          = 70,
        contamination        = "normal_cleanliness",
        d                    = 40,          # rolamentos com d=30mm (bastantes no CSV)
        designation_contains = None,        # sem filtro de designação
        compute_friction     = True,
        H                    = 20,
        lubrication          = "oil_air",
        lubricant            = "mineral",
        seal_type            = None,
        sort_by              = "L_skf",
    )
