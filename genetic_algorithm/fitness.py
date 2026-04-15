"""
fitness.py  —  evaluation function for the SKF bearing GA.

Hadj-Alouane & Bean:
    Aval(x) = f(x) + lambda * sum( u_j(x)^2 )
    Merit    = C_MAX - Aval(x)

Genes (2 genes only — T_op is fixed by user input)
    vg_idx : int    index into VG_GRADES  [0..9]
    n      : float  [rpm]

Constraints (normalised, g_j <= 0 is feasible)
    C1  n     <= n_limit          → g = n/n_limit - 1
    C2  kappa >= 0.1              → g = 0.1/kappa - 1
    C3  L_skf >= L10h_req         → g = L10h_req/L_skf - 1
"""
from __future__ import annotations

VG_GRADES = [10, 15, 22, 32, 46, 68, 100, 150, 220, 320]
_M_REF    = 5_000.0
C_MAX     = 100.0
_DEBUG    = False


def evaluate(
    genes: dict,
    bearing,
    Fr: float,
    Fa: float,
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
    genes keys: "vg_idx" (int index), "n" (float rpm)
    T_op is fixed — passed as a constant, NOT a gene.
    """
    vg_idx = int(round(genes["vg_idx"]))
    vg_idx = max(0, min(vg_idx, len(VG_GRADES) - 1))
    vg     = VG_GRADES[vg_idx]
    n      = float(genes["n"])

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
    except Exception as _e:
        if _DEBUG: print(f"      [fit] viscosity failed: {_e}")
        return _BAD
    if not v_act or v_act <= 0:
        if _DEBUG: print(f"      [fit] v_act invalid: {v_act}")
        return _BAD

    dm = 0.5 * (bearing.d + bearing.D)
    try:
        v1 = _gv1(dm=dm, n=n)
    except Exception as _e:
        if _DEBUG: print(f"      [fit] v1 failed: {_e}")
        return _BAD
    if not v1 or v1 <= 0:
        if _DEBUG: print(f"      [fit] v1 invalid: {v1}")
        return _BAD

    kappa = v_act / v1

    # ---- life ----
    # BearingLife expects a dict, not the dataclass object
    bearing_dict = {
        "type":      "deep_groove_ball",
        "C":         bearing.C * 1000,    # dataclass stores kN → convert to N
        "C0":        bearing.C0 * 1000,
        "Pu":        bearing.Pu * 1000,
        "f0":        bearing.f0,
        "d":         bearing.d,
        "dm":        0.5 * (bearing.d + bearing.D),
        "kr":        bearing.kr,
        "clearance": "normal",
    }
    try:
        life  = _BL(
            bearing         = bearing_dict,
            Fr              = Fr,
            Fa              = Fa,
            n               = n,
            viscosity_grade = str(vg),
            temperature     = T_op,
            contamination   = contamination,
        )
        summary = life.summary()
        L_skf   = summary["L_skf"]   # [h]
    except Exception as _e:
        if _DEBUG: print(f"      [fit] life failed: {_e}")
        return _BAD
    if L_skf is None or L_skf <= 0:
        if _DEBUG: print(f"      [fit] L_skf invalid: {L_skf}")
        return _BAD

    # ---- friction ----
    # d1/d2 may be None in the database — pass only when available
    d1 = getattr(bearing, 'd1', None)
    d2 = getattr(bearing, 'd2', None)

    try:
        fr = _fric(
            bearing_type = "deep_groove_ball",
            designation  = bearing.designation,
            d            = bearing.d,
            D            = bearing.D,
            B            = bearing.B,
            Fr           = Fr,
            Fa           = Fa,
            n            = n,
            v            = v_act,
            H            = H,
            lubrication  = lubrication,
            lubricant    = lubricant,
            seal_type    = _detect_seal(bearing.designation),
            subtype      = getattr(bearing, 'type', None),
            C0           = bearing.C0 * 1000,
            irw          = False,
            d1           = d1,
            d2           = d2,
        )
        # frictional_moment returns FrictionResult dataclass
        M_tot = fr.M_tot
    except Exception as _e:
        if _DEBUG: print(f"      [fit] friction failed: {_e}")
        return _BAD

    if M_tot is None or M_tot < 0:
        if _DEBUG: print(f"      [fit] M_tot invalid: {M_tot}")
        return _BAD

    # ---- objective ----
    f_obj = 0.70 * (M_tot / _M_REF) + 0.30 * (L10h_req / max(L_skf, 1.0))

    # ---- normalised constraints ----
    g = [
        n / max(bearing.n_limit, 1.0) - 1.0,
        0.1 / max(kappa, 1e-9)        - 1.0,
        L10h_req / max(L_skf, 1.0)    - 1.0,
    ]

    pen_sum = sum(max(0.0, gi) ** 2 for gi in g)
    Aval    = f_obj + lam * pen_sum
    Aval    = min(Aval, C_MAX - 1e-6)

    return Aval, pen_sum


def get_intermediate_values(genes, bearing, Fr, Fa, T_op, L10h_req,
                             contamination, lubrication, lubricant, H):
    """Re-evaluate and return all intermediate values for the summary display."""
    from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity as _gv
    from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1 as _gv1
    from skf_model.common.frictional_moment import frictional_moment as _fric
    from skf_model.common.life import BearingLife as _BL

    vg_idx = int(round(genes["vg_idx"]))
    vg_idx = max(0, min(vg_idx, len(VG_GRADES) - 1))
    vg     = VG_GRADES[vg_idx]
    n      = float(genes["n"])

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
        "dm":        0.5 * (bearing.d + bearing.D),
        "kr":        bearing.kr,
        "clearance": "normal",
    }
    life   = _BL(bearing=bearing_dict, Fr=Fr, Fa=Fa, n=n,
                 viscosity_grade=str(vg), temperature=T_op,
                 contamination=contamination)
    s      = life.summary()
    L_skf  = s["L_skf"]    # [h]
    L10h_b = s["L10h"]     # [h]

    d1 = getattr(bearing, 'd1', None)
    d2 = getattr(bearing, 'd2', None)

    fr = _fric(
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

    # FrictionResult is a dataclass — convert to dict for easy access
    fr_dict = vars(fr)

    return {
        "vg"    : vg,
        "n"     : n,
        "T_op"  : T_op,
        "v_act" : v_act,
        "v1"    : v1,
        "kappa" : kappa,
        "L_skf" : L_skf,
        "L10h"  : L10h_b,
        "fr"    : fr_dict,
    }


def _detect_seal(designation: str):
    d = designation.upper()
    if "2RSH" in d or "2RS1" in d or "RSH" in d or "RS1" in d:
        return "RSH"
    return None