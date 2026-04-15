"""
fitness.py  —  evaluation function for the SKF bearing GA.

Hadj-Alouane & Bean:
    Aval(x) = f(x) + lambda * sum( u_j(x)^2 )
    Merit    = C_MAX - Aval(x)

Gene (1 gene only)
    vg_idx : int    index into VG_GRADES  [0..9]

Fixed inputs (not genes — set by the user)
    n      : float  rotational speed [rpm]
    T_op   : float  operating temperature [°C]

Constraints (normalised, g_j <= 0 is feasible)
    C1  kappa >= 0.1              → g = 0.1/kappa - 1
    C2  L_skf >= L10h_req         → g = L10h_req/L_skf - 1
"""
from __future__ import annotations

VG_GRADES = [10, 15, 22, 32, 46, 68, 100, 150, 220, 320]
_M_REF    = 5_000.0
C_MAX     = 100.0


def evaluate(
    genes: dict,
    bearing,
    Fr: float,
    Fa: float,
    n: float,
    T_op: float,
    L10h_req: float,
    contamination: str,
    lubrication: str,
    lubricant: str,
    H: float,
    lam: float = 10.0,
) -> tuple:
    """
    Returns (Aval, pen_sum).

    genes keys : {"vg_idx": int}   — only 1 gene
    n, T_op    : fixed user inputs, NOT genes
    """
    vg_idx = int(round(genes["vg_idx"]))
    vg_idx = max(0, min(vg_idx, len(VG_GRADES) - 1))
    vg     = VG_GRADES[vg_idx]

    try:
        from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity as _gv
        from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1 as _gv1
        from skf_model.common.frictional_moment import frictional_moment as _fric
        from skf_model.common.life import BearingLife as _BL
    except ImportError as exc:
        raise ImportError(f"fitness.py: run from repo root.\n{exc}")

    _BAD = (C_MAX - 1e-6, 1e6)

    # ---- viscosity ----
    try:
        v_act = _gv(vg=vg, temperature=T_op)
    except Exception:
        return _BAD
    if not v_act or v_act <= 0:
        return _BAD

    dm = 0.5 * (bearing.d + bearing.D)
    try:
        v1 = _gv1(dm=dm, n=n)
    except Exception:
        return _BAD
    if not v1 or v1 <= 0:
        return _BAD

    kappa = v_act / v1

    # ---- life ----
    bearing_dict = {
        "type":      "deep_groove_ball",
        "C":         bearing.C * 1000,
        "C0":        bearing.C0 * 1000,
        "Pu":        bearing.Pu * 1000,
        "f0":        bearing.f0,
        "d":         bearing.d,
        "dm":        dm,
        "kr":        bearing.kr,
        "clearance": "normal",
    }
    try:
        life    = _BL(
            bearing         = bearing_dict,
            Fr              = Fr,
            Fa              = Fa,
            n               = n,
            viscosity_grade = str(vg),
            temperature     = T_op,
            contamination   = contamination,
        )
        summary = life.summary()
        L_skf   = summary["L_skf"]
    except Exception:
        return _BAD
    if L_skf is None or L_skf <= 0:
        return _BAD

    # ---- friction ----
    d1 = getattr(bearing, 'd1', None)
    d2 = getattr(bearing, 'd2', None)
    try:
        fr    = _fric(
            bearing_type = "deep_groove_ball",
            designation  = bearing.designation,
            d=bearing.d, D=bearing.D, B=bearing.B,
            Fr=Fr, Fa=Fa, n=n, v=v_act, H=H,
            lubrication=lubrication, lubricant=lubricant,
            seal_type=_detect_seal(bearing.designation),
            subtype=getattr(bearing, 'type', None),
            C0=bearing.C0 * 1000, irw=False,
            d1=d1, d2=d2,
        )
        M_tot = fr.M_tot
    except Exception:
        return _BAD
    if M_tot is None or M_tot < 0:
        return _BAD

    # ---- objective ----
    f_obj = 0.70 * (M_tot / _M_REF) + 0.30 * (L10h_req / max(L_skf, 1.0))

    # ---- normalised constraints ----
    g = [
        0.1 / max(kappa, 1e-9) - 1.0,          # C1 kappa >= 0.1
        L10h_req / max(L_skf, 1.0) - 1.0,       # C2 life
    ]

    pen_sum = sum(max(0.0, gi) ** 2 for gi in g)
    Aval    = f_obj + lam * pen_sum
    Aval    = min(Aval, C_MAX - 1e-6)

    return Aval, pen_sum


def get_intermediate_values(genes, bearing, Fr, Fa, n, T_op, L10h_req,
                             contamination, lubrication, lubricant, H):
    """Re-evaluate and return all intermediate values for the summary display."""
    from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity as _gv
    from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1 as _gv1
    from skf_model.common.frictional_moment import frictional_moment as _fric
    from skf_model.common.life import BearingLife as _BL

    vg_idx = int(round(genes["vg_idx"]))
    vg_idx = max(0, min(vg_idx, len(VG_GRADES) - 1))
    vg     = VG_GRADES[vg_idx]

    v_act  = _gv(vg=vg, temperature=T_op)
    dm     = 0.5 * (bearing.d + bearing.D)
    v1     = _gv1(dm=dm, n=n)
    kappa  = v_act / v1 if v1 > 0 else 0.0

    bearing_dict = {
        "type":      "deep_groove_ball",
        "C":         bearing.C * 1000,
        "C0":        bearing.C0 * 1000,
        "Pu":        bearing.Pu * 1000,
        "f0":        bearing.f0,
        "d":         bearing.d,
        "dm":        dm,
        "kr":        bearing.kr,
        "clearance": "normal",
    }
    life   = _BL(bearing=bearing_dict, Fr=Fr, Fa=Fa, n=n,
                 viscosity_grade=str(vg), temperature=T_op,
                 contamination=contamination)
    s      = life.summary()
    L_skf  = s["L_skf"]
    L10h_b = s["L10h"]

    d1 = getattr(bearing, 'd1', None)
    d2 = getattr(bearing, 'd2', None)

    fr = _fric(
        bearing_type="deep_groove_ball",
        designation=bearing.designation,
        d=bearing.d, D=bearing.D, B=bearing.B,
        Fr=Fr, Fa=Fa, n=n, v=v_act, H=H,
        lubrication=lubrication, lubricant=lubricant,
        seal_type=_detect_seal(bearing.designation),
        subtype=getattr(bearing, 'type', None),
        C0=bearing.C0 * 1000, irw=False,
        d1=d1, d2=d2,
    )

    return {
        "vg"   : vg,
        "n"    : n,
        "T_op" : T_op,
        "v_act": v_act,
        "v1"   : v1,
        "kappa": kappa,
        "L_skf": L_skf,
        "L10h" : L10h_b,
        "fr"   : vars(fr),
    }


def _detect_seal(designation: str):
    d = designation.upper()
    if "2RSH" in d or "2RS1" in d or "RSH" in d or "RS1" in d:
        return "RSH"
    return None