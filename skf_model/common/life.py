import os
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

# ---------------------------------------------------------------------------
# Internal imports — adjust paths to match your project structure
# ---------------------------------------------------------------------------
from skf_model.common.constants.contamination import get_eta_c

# Catalogue curve interpolators
from Graficos.Bearing_life.a_SKF.Ball_Bearing.a_skf_radial_ball_bearing import get_a_skf
from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1
from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity

# ---------------------------------------------------------------------------
# Load Tabela 9 — e, X, Y factors for deep groove ball bearings
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "bearings", "data"))

_eXY = pd.read_csv(
    os.path.join(_DATA_DIR, "deep_groove_ball_eXY.csv"),
    skipinitialspace=True,
)

def _interp_eXY(f0FaC0: float, clearance: str) -> dict:
    """
    Interpolate e, X, Y from Table 9 for a given f0*Fa/C0 and clearance class.
    Reads X from CSV — no hardcoded values.
    SKF General Catalogue 10000 EN — Table 9
    """
    col_e = f"{clearance}_e"
    col_X = f"{clearance}_X"
    col_Y = f"{clearance}_Y"

    x  = _eXY["f0FaC0"].values
    fe = interp1d(x, _eXY[col_e].values, kind="linear", fill_value="extrapolate")
    fX = interp1d(x, _eXY[col_X].values, kind="linear", fill_value="extrapolate")
    fY = interp1d(x, _eXY[col_Y].values, kind="linear", fill_value="extrapolate")

    return {
        "e": float(fe(f0FaC0)),
        "X": float(fX(f0FaC0)),
        "Y": float(fY(f0FaC0)),
    }

# Load Tabela 10 — paired bearings back-to-back and face-to-face
_eY1Y2 = pd.read_csv(
    os.path.join(_DATA_DIR, "deep_groove_ball_eY1Y2.csv"),
    skipinitialspace=True,
)

def _interp_eY1Y2(f0FaC0: float) -> dict:
    """
    Interpolate e, Y1, Y2 from Table 10 for back-to-back and face-to-face arrangements.
    SKF General Catalogue 10000 EN — Table 10
    """
    x   = _eY1Y2["f0FaC0"].values
    fe  = interp1d(x, _eY1Y2["e"].values,  kind="linear", fill_value="extrapolate")
    fY1 = interp1d(x, _eY1Y2["Y1"].values, kind="linear", fill_value="extrapolate")
    fY2 = interp1d(x, _eY1Y2["Y2"].values, kind="linear", fill_value="extrapolate")

    return {
        "e":  float(fe(f0FaC0)),
        "Y1": float(fY1(f0FaC0)),
        "Y2": float(fY2(f0FaC0)),
    }

# ---------------------------------------------------------------------------
# BearingLife
# ---------------------------------------------------------------------------
class BearingLife:
    """
    SKF bearing life calculation for deep groove ball bearings.
    Follows the selection procedure in SKF General Catalogue 10000 EN, section 17.

    Parameters
    ----------
    bearing : dict
        Bearing data with keys:
            C       — dynamic load rating [N]
            C0      — static load rating [N]
            Pu      — fatigue load limit [N]
            f0      — calculation factor (from bearing tables)
            dm      — mean diameter, 0.5*(d+D) [mm]
            clearance — 'normal', 'C3', or 'C4'
    Fr : float
        Radial load [N]
    Fa : float
        Axial load [N]
    n : float
        Rotational speed [rpm]
    viscosity_grade : str
        ISO VG grade of the lubricant, e.g. 'VG 100'
    temperature : float
        Operating temperature [°C]
    contamination : str
        Contamination condition key from Table 6, e.g. 'normal_cleanliness'.
        Valid options: extreme_cleanliness, high_cleanliness, normal_cleanliness,
        slight_contamination, typical_contamination, severe_contamination,
        very_severe_contamination.
    eta_c : float or None
        If provided, overrides the Table 6 range and uses this value directly.
        Use this when you know the exact eta_c for your application.
    """

    def __init__(
        self,
        bearing: dict,
        Fr: float,
        Fa: float,
        n: float,
        viscosity_grade: str,
        temperature: float,
        contamination: str,
        arrangement: str = "single",
        eta_c: float = None,
    ):
        self.bearing       = bearing
        self.Fr            = float(Fr)
        self.Fa            = float(Fa)
        self.n             = float(n)
        self.viscosity_grade = viscosity_grade
        self.temperature   = float(temperature)
        self.contamination = contamination
        self.arrangement = arrangement
        self._eta_c_override = eta_c

        # cached intermediate results
        self._cache = {}

    # -----------------------------------------------------------------------
    # Private — intermediate calculations
    # -----------------------------------------------------------------------

    def check_minimum_load(self) -> dict:
        """
        Minimum load check for single row deep groove ball bearings.
        F_rm = kr * (v*n/1000)^(2/3) * (dm/100)^2
        If Fr < F_rm, preloading should be considered.
        SKF General Catalogue 10000 EN — section 17
        """
        kr = self.bearing["kr"]
        v  = self._cache.get("v") or get_viscosity(
            int(str(self.viscosity_grade).replace("VG", "").strip()),
            self.temperature
        )
        dm  = self.bearing["dm"]
        F_rm = kr * ((v * self.n / 1000) ** (2/3)) * ((dm / 100) ** 2)

        return {
            "F_rm":     F_rm,
            "Fr":       self.Fr,
            "adequate": self.Fr >= F_rm,
            "note":     None if self.Fr >= F_rm else "Fr < F_rm — consider preloading",
        }

    def check_axial_load(self) -> dict:
        """
        Axial load carrying capacity check.
        Pure axial load: Fa <= 0.5 * C0
        Small bearings (d <= 12 mm) and light series: Fa <= 0.25 * C0
        SKF General Catalogue 10000 EN — section 17

        Note: light series (diameter series 8, 9, 0, 1) identification
        from designation not yet implemented — verify manually for those cases.
        """
        d  = self.bearing["d"]
        C0 = self.bearing["C0"]

        if d <= 12:
            fa_limit = 0.25 * C0
            condition = "small bearing (d <= 12 mm): Fa <= 0.25*C0"
        else:
            '''
            TODO: check for light series (diameter series 8, 9, 0, 1)
            and apply Fa <= 0.25 * C0 if applicable.
            For now, general limit applied.
            '''
            fa_limit  = 0.5 * C0
            condition = "general: Fa <= 0.5*C0"

        return {
            "Fa":       self.Fa,
            "fa_limit": fa_limit,
            "adequate": self.Fa <= fa_limit,
            "condition": condition,
            "note":     None if self.Fa <= fa_limit else "Fa exceeds admissible axial load — bearing not suitable",
        }      
    
    def _get_eXY(self) -> dict:
        """
        Interpolate load factors from Table 9 (single/tandem) or Table 10
        (back_to_back/face_to_face) based on f0*Fa/C0.
        SKF General Catalogue 10000 EN — Table 9, Table 10
        """
        if "eXY" not in self._cache:
            f0FaC0 = self.bearing["f0"] * self.Fa / self.bearing["C0"]
            self._cache["f0FaC0"] = f0FaC0

            if self.arrangement in ("single", "tandem"):
                self._cache["eXY"] = _interp_eXY(f0FaC0, self.bearing["clearance"])
            elif self.arrangement in ("back_to_back", "face_to_face"):
                self._cache["eXY"] = _interp_eY1Y2(f0FaC0)
            else:
                raise ValueError(
                    f"Unknown arrangement '{self.arrangement}'. "
                    f"Valid options: single, tandem, back_to_back, face_to_face"
                )
        return self._cache["eXY"]

    def _equivalent_load(self) -> float:
        """
        Equivalent dynamic bearing load P [N].

        Single and tandem:
            Fa/Fr <= e  ->  P = Fr
            Fa/Fr >  e  ->  P = X*Fr + Y*Fa
        Back-to-back and face-to-face:
            Fa/Fr <= e  ->  P = Fr + Y1*Fa
            Fa/Fr >  e  ->  P = 0.75*Fr + Y2*Fa

        SKF General Catalogue 10000 EN — section 17
        """
        if "P" not in self._cache:
            eXY  = self._get_eXY()
            ratio = self.Fa / self.Fr

            if self.arrangement in ("single", "tandem"):
                if ratio <= eXY["e"]:
                    P = self.Fr
                else:
                    P = eXY["X"] * self.Fr + eXY["Y"] * self.Fa

            elif self.arrangement in ("back_to_back", "face_to_face"):
                if ratio <= eXY["e"]:
                    P = self.Fr + eXY["Y1"] * self.Fa
                else:
                    P = 0.75 * self.Fr + eXY["Y2"] * self.Fa

            self._cache["P"] = P
        return self._cache["P"]

    def _static_load(self) -> float:
        """
        Equivalent static bearing load P0 [N].
        P0 = 0.6*Fr + 0.5*Fa    (deep groove ball bearings)
        P0 = Fr                 if the above is less than Fr
        SKF General Catalogue 10000 EN — section 17
        """
        if "P0" not in self._cache:
            P0 = max(0.6 * self.Fr + 0.5 * self.Fa, self.Fr)
            self._cache["P0"] = P0
        return self._cache["P0"]

    def _kappa(self) -> float:
        """
        Viscosity ratio kappa = v / v1.
        v  — actual kinematic viscosity at operating temperature [mm²/s]
        v1 — reference viscosity from rated viscosity chart [mm²/s]
        SKF General Catalogue 10000 EN — section 17
        """
        if "kappa" not in self._cache:
            v  = get_viscosity(self.viscosity_grade, self.temperature)
            v1 = get_v1(dm=self.bearing["dm"], n=self.n)
            self._cache["v"]     = v
            self._cache["v1"]    = v1
            self._cache["kappa"] = v / v1
        return self._cache["kappa"]

    def _eta_c(self) -> float:
        """
        Contamination factor eta_c.
        If eta_c was provided at init, use it directly.
        Otherwise returns the midpoint of the Table 6 range for the given condition.
        SKF General Catalogue 10000 EN — Table 6
        """
        if "eta_c" not in self._cache:
            if self._eta_c_override is not None:
                self._cache["eta_c"] = float(self._eta_c_override)
            else:
                lo, hi = get_eta_c(self.contamination, self.bearing["dm"])
                self._cache["eta_c"] = (lo + hi) / 2
        return self._cache["eta_c"]

    def _x_factor(self) -> float:
        """
        Contamination-corrected load parameter for a_SKF lookup.
        x = eta_c * Pu / P
        SKF General Catalogue 10000 EN — section 17
        """
        if "x" not in self._cache:
            eta_c = self._eta_c()
            Pu    = self.bearing["Pu"]
            P     = self._equivalent_load()
            self._cache["x"] = eta_c * Pu / P
        return self._cache["x"]

    # -----------------------------------------------------------------------
    # Public — results
    # -----------------------------------------------------------------------

    def L10(self) -> float:
        """
        Basic rating life L10 [million revolutions].
        L10 = (C / P)^p   where p = 3 for ball bearings
        ISO 281:2007 — eq. (1)
        SKF General Catalogue 10000 EN — section 17
        """
        C = self.bearing["C"]
        P = self._equivalent_load()
        return (C / P) ** 3

    def L10h(self) -> float:
        """
        Basic rating life L10h [hours].
        L10h = (10^6 / (60 * n)) * L10
        ISO 281:2007
        """
        return (1e6 / (60 * self.n)) * self.L10()

    def a_skf(self) -> float:
        """
        SKF life modification factor a_SKF.
        Depends on viscosity ratio kappa and contamination-corrected load x.
        SKF General Catalogue 10000 EN — Fig. 1 (ball bearings)
        """
        return get_a_skf(x=self._x_factor(), k=self._kappa())

    def L_skf(self) -> float:
        """
        SKF rating life L_SKF [hours].
        L_SKF = a_SKF * L10h
        SKF General Catalogue 10000 EN — section 17, eq. (3)
        """
        return self.a_skf() * self.L10h()

    def static_check(self) -> dict:
        """
        Static load safety factor s0 = C0 / P0.
        Recommended minimum values (SKF General Catalogue):
            s0 >= 1.0  for normal operating conditions
            s0 >= 0.5  for smooth, vibration-free operation
            s0 >= 1.5  for shock loads or high requirements on running accuracy

        Returns
        -------
        dict with keys: P0, s0, C0
        """
        P0 = self._static_load()
        C0 = self.bearing["C0"]
        return {
            "P0": P0,
            "C0": C0,
            "s0": C0 / P0,
        }

    def summary(self) -> dict:
        """
        Return all intermediate and final results in a single dict.
        Useful for inspection and debugging.
        """
        static = self.static_check()
        eXY    = self._get_eXY()
        kappa  = self._kappa()
        return {
            # loads
            "Fr":      self.Fr,
            "Fa":      self.Fa,
            "P":       self._equivalent_load(),
            "P0":      static["P0"],
            # table 9
            "e":       eXY["e"],
            "X":       eXY["X"],
            "Y":       eXY["Y"],
            # lubrication
            "v":       self._cache.get("v"),
            "v1":      self._cache.get("v1"),
            "kappa":   kappa,
            # contamination
            "eta_c":   self._eta_c(),
            "x":       self._x_factor(),
            # life
            "L10":     self.L10(),
            "L10h":    self.L10h(),
            "a_skf":   self.a_skf(),
            "L_skf":   self.L_skf(),
            # static
            "C0":      static["C0"],
            "s0":      static["s0"],
        }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

    # Load bearing database
    db = pd.read_csv(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bearings", "data", "deep_groove_ball.csv")),
        skipinitialspace=True,
    )

    # Select bearing by designation
    row = db[db["designation"] == "609"].iloc[0]

    bearing = {
        "C":         row["C"] * 1000,        # kN -> N
        "C0":        row["C0"] * 1000,       # kN -> N
        "Pu":        row["Pu"] * 1000,       # kN -> N
        "f0":        row["f0"],
        "dm":        0.5 * (row["d"] + row["D"]),
        "d":  row["d"],
        "kr": row["kr"],
        "clearance": "normal",
    }

    bl = BearingLife(
        bearing         = bearing,
        Fr              = 2000,
        Fa              = 1000,
        n               = 1500,
        viscosity_grade = "100",
        temperature     = 70,
        contamination   = "normal_cleanliness",
    )

    result = bl.summary()
    for k, v in result.items():
        print(f"  {k:<10} {v:.4f}" if isinstance(v, float) else f"  {k:<10} {v}")