import os
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from skf_model.common.constants.contamination import get_eta_c
from Graficos.Bearing_life.a_SKF.Ball_Bearing.a_skf_radial_ball_bearing import get_a_skf
from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1
from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity

# ---------------------------------------------------------------------------
# Bearing configuration map
# Add new bearing types here as they are implemented.
# p : life exponent (ISO 281) — 3 for ball bearings, 10/3 for roller bearings
# ---------------------------------------------------------------------------
_BEARING_CONFIGS = {
    "deep_groove_ball": {
        "eXY_file":   "deep_groove_ball_eXY.csv",
        "eY1Y2_file": "deep_groove_ball_eY1Y2.csv",
        "p":          3,
    },
    # "angular_contact_ball": {
    #     "eXY_file":   "angular_contact_ball_eXY.csv",
    #     "eY1Y2_file": "angular_contact_ball_eY1Y2.csv",
    #     "p":          3,
    # },
    # "cylindrical_roller": {
    #     "eXY_file":   "cylindrical_roller_eXY.csv",
    #     "eY1Y2_file": None,
    #     "p":          10/3,
    # },
}

# _DATA_DIR mantém-se a apontar para data/ — continua correcto para a1_reliability.csv
_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bearings", "data")
)

# _BEARING_CONFIGS — paths agora incluem subpasta
_BEARING_CONFIGS = {
    "deep_groove_ball": {
        "eXY_file":   "deep_groove_ball/deep_groove_ball_eXY.csv",
        "eY1Y2_file": "deep_groove_ball/deep_groove_ball_eY1Y2.csv",
        "p":          3,
    },
}
# ---------------------------------------------------------------------------
# Lazy CSV loaders — only load when first requested
# ---------------------------------------------------------------------------
_loaded_eXY   = {}
_loaded_eY1Y2 = {}
_loaded_a1    = {}  


def _get_eXY_table(bearing_type: str) -> pd.DataFrame:
    if bearing_type not in _loaded_eXY:
        cfg = _BEARING_CONFIGS.get(bearing_type)
        if cfg is None:
            raise ValueError(
                f"Unknown bearing type '{bearing_type}'. "
                f"Available: {list(_BEARING_CONFIGS.keys())}"
            )
        _loaded_eXY[bearing_type] = pd.read_csv(
            os.path.join(_DATA_DIR, cfg["eXY_file"]), skipinitialspace=True
        )
    return _loaded_eXY[bearing_type]


def _get_eY1Y2_table(bearing_type: str) -> pd.DataFrame:
    if bearing_type not in _loaded_eY1Y2:
        cfg = _BEARING_CONFIGS.get(bearing_type)
        if cfg is None:
            raise ValueError(
                f"Unknown bearing type '{bearing_type}'. "
                f"Available: {list(_BEARING_CONFIGS.keys())}"
            )
        fname = cfg["eY1Y2_file"]
        if fname is None:
            raise NotImplementedError(
                f"Paired bearing factors not available for '{bearing_type}'."
            )
        _loaded_eY1Y2[bearing_type] = pd.read_csv(
            os.path.join(_DATA_DIR, fname), skipinitialspace=True
        )
    return _loaded_eY1Y2[bearing_type]


def _get_a1_table() -> pd.DataFrame:
    if "a1" not in _loaded_a1:
        _loaded_a1["a1"] = pd.read_csv(
            os.path.join(_DATA_DIR, "a1_reliability.csv"), skipinitialspace=True
        )
    return _loaded_a1["a1"]

# ---------------------------------------------------------------------------
# Interpolation functions
# ---------------------------------------------------------------------------

def _interp_eXY(f0FaC0: float, clearance: str, bearing_type: str) -> dict:
    """
    Interpolate e, X, Y from Table 9 for a given f0*Fa/C0 and clearance class.
    SKF General Catalogue 10000 EN — Table 9
    """
    df    = _get_eXY_table(bearing_type)
    col_e = f"{clearance}_e"
    col_X = f"{clearance}_X"
    col_Y = f"{clearance}_Y"

    x  = df["f0FaC0"].values
    fe = interp1d(x, df[col_e].values, kind="linear", fill_value="extrapolate")
    fX = interp1d(x, df[col_X].values, kind="linear", fill_value="extrapolate")
    fY = interp1d(x, df[col_Y].values, kind="linear", fill_value="extrapolate")

    return {
        "e": float(fe(f0FaC0)),
        "X": float(fX(f0FaC0)),
        "Y": float(fY(f0FaC0)),
    }


def _interp_eY1Y2(f0FaC0: float, bearing_type: str) -> dict:
    """
    Interpolate e, Y1, Y2 from Table 10 for back-to-back and face-to-face arrangements.
    SKF General Catalogue 10000 EN — Table 10
    """
    df  = _get_eY1Y2_table(bearing_type)
    x   = df["f0FaC0"].values
    fe  = interp1d(x, df["e"].values,  kind="linear", fill_value="extrapolate")
    fY1 = interp1d(x, df["Y1"].values, kind="linear", fill_value="extrapolate")
    fY2 = interp1d(x, df["Y2"].values, kind="linear", fill_value="extrapolate")

    return {
        "e":  float(fe(f0FaC0)),
        "Y1": float(fY1(f0FaC0)),
        "Y2": float(fY2(f0FaC0)),
    }

def _lookup_a1(reliability: float = None, failure_prob: float = None) -> float:
    """
    Return life adjustment factor a1 from Table 3 (SKF GC 10000 EN).
    Provide either reliability [%] OR failure_prob [%] — not both.
    Exact match only (table has discrete entries).
    """
    df = _get_a1_table()

    if reliability is not None and failure_prob is not None:
        raise ValueError("Provide either 'reliability' or 'failure_prob', not both.")

    if reliability is not None:
        row = df[df["reliability"] == reliability]
        key = f"reliability={reliability}%"
    elif failure_prob is not None:
        row = df[df["failure_prob"] == failure_prob]
        key = f"failure_prob={failure_prob}%"
    else:
        return 1.0   # default: 90% reliability → a1 = 1

    if row.empty:
        valid = df[["reliability", "failure_prob"]].to_string(index=False)
        raise ValueError(f"No entry found for {key}.\nValid values:\n{valid}")

    return float(row["a1"].iloc[0])

# ---------------------------------------------------------------------------
# BearingLife
# ---------------------------------------------------------------------------
class BearingLife:
    """
    SKF bearing life calculation.
    Follows the selection procedure in SKF General Catalogue 10000 EN, section 17.

    Parameters
    ----------
    bearing : dict
        Bearing data with keys:
            type      — bearing type string, e.g. 'deep_groove_ball'
            C         — dynamic load rating [N]
            C0        — static load rating [N]
            Pu        — fatigue load limit [N]
            f0        — calculation factor
            d         — bore diameter [mm]
            dm        — mean diameter, 0.5*(d+D) [mm]
            kr        — minimum load factor
            clearance — 'normal', 'C3', or 'C4'
    Fr : float
        Radial load [N]
    Fa : float
        Axial load [N]
    n : float
        Rotational speed [rpm]
    viscosity_grade : str or int
        ISO VG grade, e.g. 'VG 100', '100', or 100
    temperature : float
        Operating temperature [deg C]
    contamination : str
        Contamination condition key from Table 6, e.g. 'normal_cleanliness'.
        Valid: extreme_cleanliness, high_cleanliness, normal_cleanliness,
        slight_contamination, typical_contamination, severe_contamination,
        very_severe_contamination.
    arrangement : str
        Bearing arrangement: 'single', 'tandem', 'back_to_back', 'face_to_face'.
        Default: 'single'.
    eta_c : float or None
        If provided, overrides the Table 6 range and uses this value directly.
    """

    def __init__(
        self,
        bearing: dict,
        Fr: float,
        Fa: float,
        n: float,
        viscosity_grade,
        temperature: float,
        contamination: str,
        arrangement: str = "single",
        eta_c: float = None,
        reliability: float = None,      
        failure_prob: float = None,  
    ):
        self.bearing         = bearing
        self.Fr              = float(Fr)
        self.Fa              = float(Fa)
        self.n               = float(n)
        self.viscosity_grade = str(viscosity_grade).replace("VG", "").strip()
        self.temperature     = float(temperature)
        self.contamination   = contamination
        self.arrangement     = arrangement
        self._eta_c_override = eta_c
        self._cache          = {}
        self._reliability  = reliability
        self._failure_prob = failure_prob
        self._apply_matched_pair_ratings()

        if bearing.get("type") not in _BEARING_CONFIGS:
            raise ValueError(
                f"Unknown bearing type '{bearing.get('type')}'. "
                f"Available: {list(_BEARING_CONFIGS.keys())}"
            )

    # -----------------------------------------------------------------------
    # Admissibility checks
    # -----------------------------------------------------------------------

    def check_minimum_load(self) -> dict:
        """
        Minimum load check.
        F_rm = kr * (v*n/1000)^(2/3) * (dm/100)^2
        If Fr < F_rm, preloading should be considered.
        SKF General Catalogue 10000 EN — section 17
        """
        kr   = self.bearing["kr"]
        v    = self._cache.get("v") or get_viscosity(int(self.viscosity_grade), self.temperature)
        dm   = self.bearing["dm"]
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
        Pure axial load : Fa <= 0.5 * C0
        Small bearings (d <= 12 mm) and light series: Fa <= 0.25 * C0
        SKF General Catalogue 10000 EN — section 17

        Note: light series (diameter series 8, 9, 0, 1) identification
        from designation not yet implemented — verify manually for those cases.
        """
        d  = self.bearing["d"]
        C0 = self.bearing["C0"]

        if d <= 12:
            fa_limit  = 0.25 * C0
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
            "Fa":        self.Fa,
            "fa_limit":  fa_limit,
            "adequate":  self.Fa <= fa_limit,
            "condition": condition,
            "note":      None if self.Fa <= fa_limit else "Fa exceeds admissible axial load — bearing not suitable",
        }

    # -----------------------------------------------------------------------
    # Private — intermediate calculations
    # -----------------------------------------------------------------------

    def _get_eXY(self) -> dict:
        """
        Interpolate load factors from Table 9 (single/tandem) or Table 10
        (back_to_back/face_to_face) based on f0*Fa/C0.
        SKF General Catalogue 10000 EN — Table 9, Table 10
        """
        if "eXY" not in self._cache:
            f0FaC0 = self.bearing["f0"] * self.Fa / self.bearing["C0"]
            self._cache["f0FaC0"] = f0FaC0
            btype  = self.bearing["type"]

            if self.arrangement in ("single", "tandem"):
                self._cache["eXY"] = _interp_eXY(f0FaC0, self.bearing["clearance"], btype)
            elif self.arrangement in ("back_to_back", "face_to_face"):
                self._cache["eXY"] = _interp_eY1Y2(f0FaC0, btype)
            else:
                raise ValueError(
                    f"Unknown arrangement '{self.arrangement}'. "
                    f"Valid: single, tandem, back_to_back, face_to_face"
                )
        return self._cache["eXY"]
    
    def _apply_matched_pair_ratings(self) -> None:
        """
        For matched bearing pairs (back_to_back or face_to_face), adjust load
        ratings to pair values per SKF General Catalogue 10000 EN — section 17:
            C   = 1.62 * C_single
            C0  = 2    * C0_single
            Pu  = 2    * Pu_single
        Only applied once — skipped for single and tandem arrangements.
        """
        if self.arrangement in ("back_to_back", "face_to_face"):
            if not self._cache.get("pair_ratings_applied"):
                self.bearing = dict(self.bearing)   # avoid mutating the original dict
                self.bearing["C"]  = 1.62 * self.bearing["C"]
                self.bearing["C0"] = 2.0  * self.bearing["C0"]
                self.bearing["Pu"] = 2.0  * self.bearing["Pu"]
                self._cache["pair_ratings_applied"] = True

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
            eXY   = self._get_eXY()
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

        Single and tandem:
            P0 = 0.6*Fr + 0.5*Fa
            P0 = Fr                if the above is less than Fr

        Back-to-back and face-to-face:
            P0 = Fr + 1.7*Fa

        SKF General Catalogue 10000 EN — section 17
        """
        if "P0" not in self._cache:
            if self.arrangement in ("single", "tandem"):
                P0 = max(0.6 * self.Fr + 0.5 * self.Fa, self.Fr)
            elif self.arrangement in ("back_to_back", "face_to_face"):
                P0 = self.Fr + 1.7 * self.Fa
            self._cache["P0"] = P0
        return self._cache["P0"]

    def _kappa(self) -> float:
        """
        Viscosity ratio kappa = v / v1.
        v  — actual kinematic viscosity at operating temperature [mm^2/s]
        v1 — reference viscosity from rated viscosity chart [mm^2/s]
        SKF General Catalogue 10000 EN — section 17
        """
        if "kappa" not in self._cache:
            v  = get_viscosity(int(self.viscosity_grade), self.temperature)
            v1 = get_v1(dm=self.bearing["dm"], n=self.n)
            self._cache["v"]     = v
            self._cache["v1"]    = v1
            self._cache["kappa"] = v / v1
        return self._cache["kappa"]

    def _eta_c(self) -> float:
        """
        Contamination factor eta_c.
        If eta_c was provided at init, uses it directly.
        Otherwise returns the midpoint of the Table 6 range.
        SKF General Catalogue 10000 EN — Table 6
        """
        if "eta_c" not in self._cache:
            if self._eta_c_override is not None:
                self._cache["eta_c"] = float(self._eta_c_override)
            else:
                lo, hi = get_eta_c(self.contamination, self.bearing["dm"])
                self._cache["eta_c"] = (lo + hi) / 2 # midpoint of the range 
        return self._cache["eta_c"]

    def _x_factor(self) -> float:
        """
        Contamination-corrected load parameter for a_SKF lookup.
        x = eta_c * Pu / P
        SKF General Catalogue 10000 EN — section 17
        """
        if "x" not in self._cache:
            self._cache["x"] = self._eta_c() * self.bearing["Pu"] / self._equivalent_load()
        return self._cache["x"]
    
    def _a1(self) -> float:
        """
        Life adjustment factor for reliability a1 (Table 3).
        Defaults to 1.0 (90% reliability) if neither reliability nor failure_prob
        was specified at init.
        SKF General Catalogue 10000 EN — Table 3
        """
        if "a1" not in self._cache:
            self._cache["a1"] = _lookup_a1(
                reliability  = self._reliability,
                failure_prob = self._failure_prob,
            )
        return self._cache["a1"]

    # -----------------------------------------------------------------------
    # Public — results
    # -----------------------------------------------------------------------

    def L10(self) -> float:
        """
        Basic rating life L10 [million revolutions].
        L10 = (C / P)^p
        p = 3 for ball bearings, 10/3 for roller bearings (ISO 281)
        """
        p = _BEARING_CONFIGS[self.bearing["type"]]["p"]
        return (self.bearing["C"] / self._equivalent_load()) ** p

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
    
    def L_skfn(self) -> float:
        """
        SKF rating life adjusted for reliability L_SKFn [hours].
        L_SKFn = a1 * a_SKF * L10h
        SKF General Catalogue 10000 EN — section 17
        """
        return self._a1() * self.L_skf()

    def static_check(self) -> dict:
        """
        Static load safety factor s0 = C0 / P0.
        Recommended minimum values (SKF General Catalogue):
            s0 >= 1.0 for normal conditions
            s0 >= 0.5 for smooth, vibration-free operation
            s0 >= 1.5 for shock loads or high accuracy requirements
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
        """
        static = self.static_check()
        eXY    = self._get_eXY()
        kappa  = self._kappa()

        return {
            # bearing
            "type":         self.bearing["type"],
            "arrangement":  self.arrangement,
            # loads
            "Fr":           self.Fr,
            "Fa":           self.Fa,
            "f0*Fa/C0":     self._cache.get("f0FaC0"),
            "P":            self._equivalent_load(),
            "P0":           static["P0"],
            # table 9 / 10
            "e":            eXY["e"],
            "X":            eXY.get("X"),
            "Y":            eXY.get("Y"),
            "Y1":           eXY.get("Y1"),
            "Y2":           eXY.get("Y2"),
            # lubrication
            "v":            self._cache.get("v"),
            "v1":           self._cache.get("v1"),
            "kappa":        kappa,
            # contamination
            "eta_c":        self._eta_c(),
            "eta_c*Pu/P":   self._x_factor(),
            # life
            "L10":          self.L10(),
            "L10h":         self.L10h(),
            "a_skf":        self.a_skf(),
            "L_skf":        self.L_skf(),
            "a1":           self._a1(),
            "L_skfn":       self.L_skfn(),
            # static
            "C0":           static["C0"],
            "s0":           static["s0"],
        }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

    db = pd.read_csv(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bearings", "data", "deep_groove_ball", "deep_groove_ball.csv")),
        skipinitialspace=True,
    )

    row = db[db["designation"] == "61906"].iloc[0]

    bearing = {
        "type":      "deep_groove_ball",
        "C":         row["C"]  * 1000,
        "C0":        row["C0"] * 1000,
        "Pu":        row["Pu"] * 1000,
        "f0":        row["f0"],
        "d":         row["d"],
        "dm":        0.5 * (row["d"] + row["D"]),
        "kr":        row["kr"],
        "clearance": "normal",
    }

    for label, kwargs in [
        ("90% reliability (default)", {}),
        ("95% reliability",           {"reliability": 95}),
        ("99% reliability",           {"reliability": 99}),
        ("failure_prob=2%",           {"failure_prob": 2}),
    ]:
        bl = BearingLife(
            bearing         = bearing,
            Fr              = 1000,
            Fa              = 100,
            n               = 1500,
            viscosity_grade = "150",
            temperature     = 70,
            contamination   = "normal_cleanliness",
            **kwargs,
        )

        print(f"\n--- {label} ---")
        result = bl.summary()
        for k, v in result.items():
            print(f"  {k:<15} {v:.4f}" if isinstance(v, float) else f"  {k:<15} {v}")