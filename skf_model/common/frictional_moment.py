"""
frictional_moment.py
====================
Total frictional moment for rolling bearings following the SKF friction model
described in the SKF General Catalogue 10000 EN.

Components
----------
    M_rr   — rolling frictional moment          [N·mm]
    M_sl   — sliding frictional moment          [N·mm]
    M_drag — drag / churning frictional moment  [N·mm]
    M_seal — seal frictional moment             [N·mm]
    M_tot  — total frictional moment            [N·mm]

References
----------
    SKF General Catalogue 10000 EN, section on frictional moment (friction model)
    Formulae, diagram references and variable definitions follow the catalogue
    page numbers where they appear.

Dependencies (same package)
---------------------------
    friction_constants/rs_constants.py        → get_RS_constants()
    seal_friction/friction_seal_constants.py  → get_seal_constants()
    drag_friction/drag_loss_constants.py      → get_drag_constants()
    drag_friction/drag_loss_factor_Vm.py      → get_Vm()
    common/geometry_variables.py             → get_G()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Local imports — adjust relative paths if the module is used outside the
# skf_model package.
# ---------------------------------------------------------------------------
import sys, pathlib

_ROOT           = pathlib.Path(__file__).resolve().parent.parent.parent  # repo root
_COMMON         = _ROOT / "skf_model" / "common"
_FRICTION_MODEL = _ROOT / "skf_model" / "friction_model"
_DRAG_VM        = (_ROOT / "Graficos" / "Friction Moments" /
                   "Drag Moment" / "Drag Loss Factor Vm")

for _p in (
    _COMMON,
    _FRICTION_MODEL / "friction_constants",
    _FRICTION_MODEL / "seal_friction",
    _FRICTION_MODEL / "drag_friction",
    _DRAG_VM,
):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

from rs_constants            import get_RS_constants
from friction_seal_constants import get_seal_constants
from drag_loss_constants     import get_drag_constants
from drag_loss_factor_Vm     import get_Vm
from geometry_variables      import get_G

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
BearingFamily  = Literal["ball", "roller"]
LubricationType = Literal[
    "oil_bath",          # low-level oil bath or oil jet
    "oil_air",           # oil-air lubrication / grease
]
SealType = Literal["RSL", "RSH", "RS1", "LS", "CS_CS2_CS5", None]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class FrictionResult:
    """All intermediate values and the four moment components."""

    # Inputs
    bearing_type:     str
    designation:      str
    d:   float   # bore diameter          [mm]
    D:   float   # outside diameter       [mm]
    B:   float   # width                  [mm]
    Fr:  float   # radial load            [N]
    Fa:  float   # axial load             [N]
    n:   float   # rotational speed       [r/min]
    v:   float   # actual viscosity       [mm²/s]
    H:   float   # oil level              [mm]
    lubrication: LubricationType

    # Intermediate
    dm:    float = field(init=False)   # mean diameter  [mm]
    phi_ish: float = field(init=False) # inlet shear heating reduction factor
    phi_rs:  float = field(init=False) # kinematic replenishment/starvation factor
    G_rr:    float = field(init=False) # rolling geometry variable
    G_sl:    float = field(init=False) # sliding geometry variable
    mu_sl:   float = field(init=False) # sliding friction coefficient
    phi_bl:  float = field(init=False) # sliding friction weighting factor

    # Moment components  [N·mm]
    M_rr:   float = field(init=False)
    M_sl:   float = field(init=False)
    M_drag: float = field(init=False)
    M_seal: float = field(init=False)
    M_tot:  float = field(init=False)

    def __post_init__(self):
        self.dm = 0.5 * (self.d + self.D)

    def __str__(self) -> str:
        lines = [
            f"Bearing : {self.designation}  ({self.bearing_type})",
            f"  d={self.d} mm  D={self.D} mm  B={self.B} mm  dm={self.dm:.1f} mm",
            f"  Fr={self.Fr} N  Fa={self.Fa} N  n={self.n} r/min  v={self.v} mm²/s",
            "",
            f"  phi_ish = {self.phi_ish:.4f}   (inlet shear heating reduction)",
            f"  phi_rs  = {self.phi_rs:.4f}   (replenishment/starvation)",
            f"  phi_bl  = {self.phi_bl:.4f}   (sliding weighting factor)",
            f"  mu_sl   = {self.mu_sl:.4f}   (sliding friction coefficient)",
            "",
            f"  M_rr    = {self.M_rr:.3f} N·mm",
            f"  M_sl    = {self.M_sl:.3f} N·mm",
            f"  M_drag  = {self.M_drag:.3f} N·mm",
            f"  M_seal  = {self.M_seal:.3f} N·mm",
            f"  ─────────────────────────",
            f"  M_tot   = {self.M_tot:.3f} N·mm",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper — safe power (avoids domain errors for zero values)
# ---------------------------------------------------------------------------
def _pow(base: float, exp: float) -> float:
    if base <= 0:
        return 0.0
    return base ** exp


# ---------------------------------------------------------------------------
# φ_ish  — inlet shear heating reduction factor  (Diagram 2 / formula)
# Catalogue formula:
#   phi_ish = 1 / (1 + 1.84e-9 * (n * dm)^1.28 * v^0.64)
# ---------------------------------------------------------------------------
def _phi_ish(n: float, dm: float, v: float) -> float:
    """Inlet shear heating reduction factor (–)."""
    return 1.0 / (1.0 + 1.84e-9 * _pow(n * dm, 1.28) * _pow(v, 0.64))


# ---------------------------------------------------------------------------
# φ_rs  — kinematic replenishment/starvation reduction factor
# Catalogue formula:
#   phi_rs = 1 / exp( K_rs * v * n * (d + D) * sqrt(K_z / (2*(D - d))) )
#
# K_rs: replenishment/starvation constant
#   = 3e-8  for oil bath / oil jet
#   = 6e-8  for grease / oil-air
# K_z : bearing type related geometric constant (Table 4)
# ---------------------------------------------------------------------------
def _phi_rs(n: float, v: float, d: float, D: float, Kz: float,
            lubrication: LubricationType) -> float:
    """Kinematic replenishment/starvation reduction factor (–)."""
    K_rs = 3e-8 if lubrication == "oil_bath" else 6e-8
    exponent = K_rs * v * n * (d + D) * math.sqrt(Kz / (2.0 * (D - d)))
    return 1.0 / math.exp(exponent)


# ---------------------------------------------------------------------------
# φ_bl  — weighting factor for the sliding friction coefficient (Diagram 3)
# Analytical formula:
#   phi_bl = 1 / exp(2.6e-8 * (n*v)^1.4 * dm)
# ---------------------------------------------------------------------------
def _phi_bl(n: float, v: float, dm: float) -> float:
    """Sliding friction weighting factor (–)."""
    return 1.0 / math.exp(2.6e-8 * _pow(n * v, 1.4) * dm)


# ---------------------------------------------------------------------------
# μ_sl  — sliding friction coefficient
# μ_sl = φ_bl * μ_bl + (1 - φ_bl) * μ_EHL
#
# μ_bl  = 0.12 (n > 0) or 0.15 (starting torque, n = 0)
# μ_EHL: full-film value depending on bearing type and lubricant
# ---------------------------------------------------------------------------
_MU_EHL_BY_TYPE: dict[str, float] = {
    # Cylindrical and tapered roller bearings
    "cylindrical_roller":         0.02,
    "tapered_roller":             0.002,
    # All other bearings — default by lubricant (see below)
}

def _mu_sl(bearing_type: str, phi_bl: float,
           lubricant: Literal["mineral", "synthetic", "transmission"],
           n: float) -> float:
    """
    Sliding friction coefficient (–).

    Parameters
    ----------
    lubricant : 'mineral' | 'synthetic' | 'transmission'
        Type of lubricant, used for μ_EHL when the bearing type does not have
        a specific value.
    n : rotational speed [r/min]. Use 0 for starting torque (μ_bl = 0.15).
    """
    mu_bl = 0.15 if n == 0 else 0.12

    if bearing_type in _MU_EHL_BY_TYPE:
        mu_EHL = _MU_EHL_BY_TYPE[bearing_type]
    else:
        mu_EHL = {"mineral": 0.05, "synthetic": 0.04,
                  "transmission": 0.1}.get(lubricant, 0.05)

    return phi_bl * mu_bl + (1.0 - phi_bl) * mu_EHL


# G_rr and G_sl are now computed by geometry_variables.get_G()


# ---------------------------------------------------------------------------
# Drag loss moment — M_drag
#
# Ball bearings:
#   M_drag = 0.4 * Vm * K_ball * dm^5 * n^2
#           + 1.093e-7 * n^2 * dm^3 * (n*dm^2*ft / v)^-1.379 * Rs
#
# Roller bearings:
#   M_drag = 4 * Vm * K_roll * Cw * B * dm^4 * n^2
#           + 1.093e-7 * n^2 * dm^3 * (n*dm^2*ft / v)^-1.379 * Rs
#
# with:
#   K_ball  = irw * Kz * (d+D) / (D-d) * 1e-12
#   K_roll  = KL  * Kz * (d+D) / (D-d) * 1e-12
#   Cw      = 2.789e-10*lD^3 - 2.786e-4*lD^2 + 0.0195*lD + 0.6439
#   lD      = 5 * B / dm
#   ft      = sin(0.5*t)   0 ≤ t ≤ π ;  1   π < t < 2π
#   Rs      = 0.36 * dm^2 * (t - sin(t)) * fA
#   t       = 2 * arccos( (0.6*dm - H) / (0.6*dm) )  capped at H = 1.2*dm
#   fA      = 0.05 * Kz * (D+d) / (D-d)
#   irw     = number of ball rows (default 1)
# ---------------------------------------------------------------------------

def _drag_moment(bearing_family: BearingFamily,
                 bearing_type:   str,
                 d: float, D: float, B: float,
                 dm: float, n: float, v: float, H: float,
                 Kz: float, KL: float | None,
                 irw: int = 1) -> float:
    """Frictional moment of drag losses [N·mm]."""

    if n <= 0:
        return 0.0

    # --- oil level geometry -----------------------------------------------
    H_eff = min(H, 1.2 * dm)
    cos_arg = max(-1.0, min(1.0, (0.6 * dm - H_eff) / (0.6 * dm)))
    t = 2.0 * math.acos(cos_arg)          # [rad]

    ft = math.sin(0.5 * t) if t <= math.pi else 1.0
    fA = 0.05 * Kz * (D + d) / (D - d)
    Rs = 0.36 * dm**2 * (t - math.sin(t)) * fA

    # --- Vm from digitised curves -----------------------------------------
    Vm = get_Vm(H_eff / dm, bearing_family)

    # --- second term (same for ball and roller) ----------------------------
    # second term: only active when Rs > 0 (oil present) and ft > 0
    if Rs <= 0.0 or ft <= 0.0 or v <= 0.0:
        second = 0.0
    else:
        inner  = (n * dm**2 * ft) / v
        second = 1.093e-7 * n**2 * dm**3 * _pow(inner, -1.379) * Rs

    # --- first term --------------------------------------------------------
    if bearing_family == "ball":
        K_ball = irw * Kz * (d + D) / (D - d) * 1e-12
        first  = 0.4 * Vm * K_ball * dm**5 * n**2

    else:  # roller
        if KL is None:
            raise ValueError(f"KL is required for roller bearing drag loss "
                             f"(bearing_type='{bearing_type}').")
        K_roll = KL * Kz * (d + D) / (D - d) * 1e-12
        lD     = 5.0 * B / dm
        Cw     = 2.789e-10 * lD**3 - 2.786e-4 * lD**2 + 0.0195 * lD + 0.6439
        first  = 4.0 * Vm * K_roll * Cw * B * dm**4 * n**2

    return first + second


# ---------------------------------------------------------------------------
# Seal moment — M_seal
# M_seal = KS1 * ds^beta + KS2
# ds is chosen from bearing geometry: d1 = bore seal dia, d2 = OD seal dia, E
# For simplicity we pass the relevant diameter directly.
# ---------------------------------------------------------------------------

def _seal_moment(seal_type: SealType, bearing_type: str,
                 D: float, d: float,
                 d1: float | None = None,
                 d2: float | None = None) -> float:
    if seal_type is None:
        return 0.0

    sc = get_seal_constants(seal_type, bearing_type, D)
    beta      = sc["beta"]
    KS1       = sc["KS1"]
    KS2       = sc["KS2"]
    ds_labels = sc["ds"]

    _dia = {
        "d1": d1,
        "d2": d2,
        "E" : D,
    }

    # Use catalogue-preferred label; fall back to sibling seal diameter
    # if the preferred one is absent from the database entry (d1 ↔ d2).
    _fallback = {"d1": "d2", "d2": "d1"}
    ds_values = []
    for label in ds_labels:
        val = _dia.get(label)
        if val is not None:
            ds_values.append(val)
        else:
            fb = _fallback.get(label)
            if fb and _dia.get(fb) is not None:
                ds_values.append(_dia[fb])

    if not ds_values:
        return 0.0

    M = KS2
    for ds in ds_values:
        M += KS1 * _pow(ds, beta)

    return M


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def bearing_family(bearing_type: str) -> BearingFamily:
    """Return 'ball' or 'roller' for a given bearing_type string."""
    _roller_types = {
        "cylindrical_roller", "tapered_roller", "spherical_roller",
        "carb_toroidal_roller", "cylindrical_roller_thrust",
        "spherical_roller_thrust",
    }
    return "roller" if bearing_type in _roller_types else "ball"


def frictional_moment(
    bearing_type:   str,
    designation:    str,
    d:  float,
    D:  float,
    B:  float,
    Fr: float,
    Fa: float,
    n:  float,
    v:  float,
    H:  float,
    lubrication:    LubricationType = "oil_bath",
    lubricant:      Literal["mineral", "synthetic", "transmission"] = "mineral",
    seal_type:      SealType = None,
    subtype:        str = "",
    C0:             float = None,
    irw:            int = 1,
    d1:             float | None = None,   # ← novo
    d2:             float | None = None,   # ← novo    
) -> FrictionResult:
    """
    Calculate the total frictional moment for a rolling bearing.

    Parameters
    ----------
    bearing_type : str
        SKF type key, e.g. 'deep_groove_ball', 'cylindrical_roller'.
    designation : str
        Full bearing designation, e.g. '6206-2RS1'.
    d : float
        Bearing bore diameter [mm].
    D : float
        Bearing outside diameter [mm].
    B : float
        Bearing width [mm].
    Fr : float
        Radial load [N].
    Fa : float
        Axial load [N].
    n : float
        Rotational speed [r/min].
    v : float
        Actual operating viscosity of the oil or base oil of the grease [mm²/s].
    H : float
        Oil level height from the bearing centre [mm]  (→ Fig. 2, page 14).
        For grease / oil-air, set H = 0.
    lubrication : 'oil_bath' | 'oil_air'
        Lubrication method.  Affects K_rs in φ_rs.
    lubricant : 'mineral' | 'synthetic' | 'transmission'
        Lubricant type.  Affects μ_EHL for bearing types without a specific value.
    seal_type : str or None
        Seal type if the bearing has contact seals: 'RSL', 'RSH', 'RS1',
        'LS', 'CS_CS2_CS5'.  Pass None for open or shielded bearings.
    subtype : str
        Bearing subtype for drag constants, required for angular_contact_ball
        ('single_row', 'double_row', 'four_point'), cylindrical_roller and
        carb_toroidal_roller ('with_cage', 'full_complement').
    C0 : float, optional
        Static load rating [N]. Required for deep groove ball bearings with
        axial load (Fa > 0), used to compute the pressure angle α_F.
    irw : int
        Number of ball rows (used in K_ball for drag loss).  Default 1.

    Returns
    -------
    FrictionResult
        Dataclass with all intermediate values and moment components [N·mm].
    """
    dm = 0.5 * (d + D)

    # --- RS constants ------------------------------------------------------
    rs     = get_RS_constants(bearing_type, designation)

    # --- Drag constants (Kz, KL) -------------------------------------------
    dc     = get_drag_constants(bearing_type, subtype=subtype)
    Kz     = dc["KZ"]
    KL     = dc.get("KL")          # None for ball bearings

    # --- Reduction factors -------------------------------------------------
    phi_ish = _phi_ish(n, dm, v)
    phi_rs  = _phi_rs(n, v, d, D, Kz, lubrication)
    phi_bl  = _phi_bl(n, v, dm)

    # --- Sliding friction coefficient --------------------------------------
    mu_sl_val = _mu_sl(bearing_type, phi_bl, lubricant, n)

    # --- Geometry variables (Table 1a / 1b) --------------------------------
    _G   = get_G(bearing_type, rs, dm, Fr, Fa, n=n, v=v, C0=C0)
    G_rr = _G["G_rr"]
    G_sl = _G["G_sl"]


    # --- Rolling moment  (SKF catalogue, eq. rolling)
    #   M_rr = phi_ish * phi_rs * G_rr * (v*n)^0.6
    M_rr = phi_ish * phi_rs * G_rr * _pow(v * n, 0.6)

    # --- Sliding moment
    #   M_sl = G_sl * mu_sl
    M_sl = G_sl * mu_sl_val

    # --- Drag moment -------------------------------------------------------
    fam    = bearing_family(bearing_type)
    M_drag = _drag_moment(fam, bearing_type, d, D, B, dm, n, v, H, Kz, KL, irw)

    # --- Seal moment -------------------------------------------------------
    M_seal = _seal_moment(seal_type, bearing_type, D, d, d1=d1, d2=d2)

    # --- Assemble result ---------------------------------------------------
    result             = FrictionResult(
        bearing_type   = bearing_type,
        designation    = designation,
        d=d, D=D, B=B, Fr=Fr, Fa=Fa, n=n, v=v, H=H,
        lubrication    = lubrication,
    )
    result.phi_ish = phi_ish
    result.phi_rs  = phi_rs
    result.phi_bl  = phi_bl
    result.G_rr    = G_rr
    result.G_sl    = G_sl
    result.mu_sl   = mu_sl_val
    result.M_rr    = M_rr
    result.M_sl    = M_sl
    result.M_drag  = M_drag
    result.M_seal  = M_seal
    result.M_tot   = M_rr + M_sl + M_drag + M_seal

    return result


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(_ROOT))

    from skf_model.bearings.deep_groove_ball import load_bearings

    bearings = {b.designation: b for b in load_bearings()}
    b = bearings["6208-2RSH"]

    r = frictional_moment(
            bearing_type = "deep_groove_ball",
            designation  = b.designation,
            d   = b.d,   D   = b.D,   B  = b.B,
            Fr  = 1500,  Fa  = 500,   n  = 1500,
            v   = 32,
            H   = 20,
            lubrication  = "oil_air",
            lubricant    = "mineral",
            seal_type    = "RSH",
            C0           = b.C0 * 1000,
            d1           = b.d1,
            d2           = b.d2,
        )
    print(r)
    print(f"  G_rr = {r.G_rr:.6f}")
    print(f"  G_sl = {r.G_sl:.6f}")