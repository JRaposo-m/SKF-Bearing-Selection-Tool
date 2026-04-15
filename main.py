"""
main.py
-------
SKF Bearing Selection Tool — interactive entry point.

Run from the repository root:
    python main.py

Flow
----
  1. Bearing type selection  (DGBB only in this phase)
  2. Geometry constraints    (d required; D_max, B_max optional)
  3. Operating loads         (Fr, Fa)
  4. Operating conditions    (n, L10h, T_op)
  5. Lubrication             (known VG  OR  let the tool recommend)
  6. Contamination level
  7. Candidate bearing filter from database
  8. Genetic algorithm — optimises VG, T_op, n for best bearing candidate
  9. Summary of results
"""

from __future__ import annotations

import sys
import os

# ---------------------------------------------------------------------------
# Make sure the repo root is on the path regardless of where main.py lives
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from skf_model.bearings.deep_groove_ball import load_bearings
from genetic_algorithm.fitness import VG_GRADES, evaluate
from genetic_algorithm.ga_optimizer import GeneticOptimiser
from report_generator import generate_report, open_report

# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------

_DIVIDER = "─" * 62

def _header(title: str) -> None:
    print(f"\n{_DIVIDER}")
    print(f"  {title}")
    print(_DIVIDER)


def _ask(prompt: str, cast=str, default=None, valid=None):
    """
    Ask for a single value with validation.

    Parameters
    ----------
    prompt  : question shown to the user
    cast    : type to cast the raw string to (float, int, str, …)
    default : value returned when the user presses Enter with no input
    valid   : optional callable(value) -> bool for extra validation
    """
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()

        if raw == "" and default is not None:
            return default

        if raw == "" and default is None:
            print("    ✖  This field is required. Please enter a value.")
            continue

        try:
            value = cast(raw)
        except (ValueError, TypeError):
            print(f"    ✖  Expected {cast.__name__}. Try again.")
            continue

        if valid is not None and not valid(value):
            print("    ✖  Value out of allowed range. Try again.")
            continue

        return value


def _ask_optional(prompt: str, cast=float):
    """Ask for a value that may be left blank (returns None)."""
    raw = input(f"  {prompt} [Enter to skip]: ").strip()
    if raw == "":
        return None
    try:
        return cast(raw)
    except (ValueError, TypeError):
        print("    ⚠  Could not parse — treating as empty.")
        return None


def _menu(title: str, options: list[str]) -> int:
    """Display a numbered menu and return the 1-based selection."""
    print(f"\n  {title}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        raw = input("  Select: ").strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print(f"    ✖  Enter a number between 1 and {len(options)}.")


# ---------------------------------------------------------------------------
# Step 1 — Bearing type
# ---------------------------------------------------------------------------

def step_bearing_type() -> str:
    _header("Step 1 — Bearing type")
    types = [
        "Deep Groove Ball Bearing (DGBB)",
        "Angular Contact Ball Bearing  [Phase 2 — not yet available]",
        "Cylindrical Roller Bearing    [Phase 2 — not yet available]",
    ]
    choice = _menu("Select bearing type:", types)
    if choice != 1:
        print("\n  This bearing type is not yet implemented.")
        print("  Defaulting to Deep Groove Ball Bearing for this session.\n")
    return "deep_groove_ball"


# ---------------------------------------------------------------------------
# Step 2 — Geometry constraints
# ---------------------------------------------------------------------------

def step_geometry(all_bearings: list) -> dict:
    _header("Step 2 — Geometry constraints")
    available_d = sorted({b.d for b in all_bearings})

    print("  Bore diameter d is required (defines the shaft fit).")
    print(f"  Available values in database: {available_d}\n")

    while True:
        d = _ask("Bore diameter d [mm]", cast=float, valid=lambda x: x > 0)
        if d in available_d:
            break
        # Suggest closest values
        closest = sorted(available_d, key=lambda x: abs(x - d))[:5]
        print(f"    ⚠  d = {d} mm not found in database.")
        print(f"       Nearest available values: {closest}")
        print("       Please re-enter one of the values above, or any listed value.")

    print()
    D_max = _ask_optional("Maximum outer diameter D_max [mm]  (leave blank = no limit)", cast=float)
    B_max = _ask_optional("Maximum width B_max [mm]           (leave blank = no limit)", cast=float)

    return {"d": d, "D_max": D_max, "B_max": B_max}


# ---------------------------------------------------------------------------
# Step 3 — Loads
# ---------------------------------------------------------------------------

def step_loads() -> dict:
    _header("Step 3 — Operating loads")

    modes = [
        "Enter Fr and Fa directly [N]",
        "Calculate from application (torque / power / geometry)  [coming soon]",
    ]
    mode = _menu("Load input mode:", modes)

    if mode == 2:
        print("\n  Assisted load calculation is not yet implemented.")
        print("  Switching to direct input.\n")

    print("  Enter loads as positive values.")
    print("  Fr — force perpendicular to shaft axis  [N]")
    print("  Fa — force parallel to shaft axis       [N]  (0 if purely radial)")
    Fr = _ask("Radial load Fr [N]", cast=float, valid=lambda x: x >= 0)
    Fa = _ask("Axial  load Fa [N]", cast=float, valid=lambda x: x >= 0)

    if Fr == 0 and Fa == 0:
        print("    ⚠  Both loads are zero — the bearing will still be evaluated.")

    return {"Fr": Fr, "Fa": Fa}


# ---------------------------------------------------------------------------
# Step 4 — Operating conditions
# ---------------------------------------------------------------------------

def step_operating_conditions() -> dict:
    _header("Step 4 — Operating conditions")

    print("  n     — shaft rotational speed                 [rpm]")
    print("  L10h  — required bearing life at 90% reliability [h]")
    print("          typical values: 20 000 h (industrial), 50 000 h (continuous)")
    n      = _ask("Rotational speed n [rpm]",        cast=float, valid=lambda x: x > 0)
    L10h   = _ask("Required service life L10h [h]",  cast=float, valid=lambda x: x > 0)
    print()
    print("  T_op  — bearing operating temperature (not ambient)  [°C]")
    print("          affects lubricant viscosity directly; default 70 °C")
    T_op   = _ask("Operating temperature T_op [°C]", cast=float, default=70.0,
                  valid=lambda x: -40 <= x <= 200)

    return {"n": n, "L10h_req": L10h, "T_op": T_op}


# ---------------------------------------------------------------------------
# Step 5 — Lubrication
# ---------------------------------------------------------------------------

def step_lubrication(dm: float, n: float) -> dict:
    _header("Step 5 — Lubrication")

    lube_modes = [
        "I know my lubricant — enter VG grade directly",
        "Recommend a VG grade based on operating conditions",
    ]
    mode = _menu("Lubrication input mode:", lube_modes)

    # Lubrication type
    lube_type_options = ["Grease", "Oil — oil-air / oil mist", "Oil — oil bath"]
    lt = _menu("Lubrication type:", lube_type_options)
    lubrication_map = {1: "grease", 2: "oil_air", 3: "oil_bath"}
    lubrication = lubrication_map[lt]

    lubricant_options = ["Mineral oil / grease", "Synthetic oil / grease"]
    lub = _menu("Lubricant base:", lubricant_options)
    lubricant = "mineral" if lub == 1 else "synthetic"

    H = 0.0
    if lubrication == "oil_bath":
        print("  H — oil level measured above the bearing centre [mm]")
        print("      H = 0   → only bottom of bearing submerged (oil-air / mist)")
        print("      H = D/2 → bearing centre at oil surface")
        print("      H = D   → fully submerged\n")
        H = _ask("Oil level H above bearing centre [mm]", cast=float,
                 default=0.0, valid=lambda x: x >= 0)

    if mode == 1:
        print(f"\n  ISO VG grade = nominal kinematic viscosity at 40 °C [mm²/s]")
        print(f"  e.g. VG 46 → ~46 mm²/s at 40 °C;  VG 68 → ~68 mm²/s at 40 °C")
        print(f"  Available grades: {VG_GRADES}\n")
        vg = _ask("ISO VG grade", cast=int, valid=lambda x: x in VG_GRADES)
    else:
        # Recommend using v1 from the rated-viscosity curve
        try:
            from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1
            v1 = get_v1(dm=dm, n=n)
            # Pick the first VG whose nominal viscosity at 40 °C exceeds v1
            recommended_vg = _recommend_vg(v1)
            print(f"\n  Rated viscosity v1 = {v1:.1f} mm²/s  (at dm={dm:.0f} mm, n={n:.0f} rpm)")
            print(f"  Recommended ISO VG grade: {recommended_vg}")
            vg = recommended_vg
        except Exception as exc:
            print(f"\n  ⚠  Could not compute rated viscosity ({exc}).")
            print(f"  Available ISO VG grades: {VG_GRADES}")
            vg = _ask("ISO VG grade (manual fallback)", cast=int,
                      valid=lambda x: x in VG_GRADES)

    return {
        "vg"         : vg,
        "lubrication": lubrication,
        "lubricant"  : lubricant,
        "H"          : H,
    }


def _recommend_vg(v1: float) -> int:
    """
    Return the smallest ISO VG grade whose nominal viscosity at 40 °C
    is >= v1. VG nominal viscosities at 40 °C follow the ISO 3448 series.
    """
    # Approximate nominal kinematic viscosities at 40 °C [mm²/s]
    vg_nominal = {
        10: 10, 15: 15, 22: 22, 32: 32, 46: 46,
        68: 68, 100: 100, 150: 150, 220: 220, 320: 320,
    }
    for vg in sorted(vg_nominal):
        if vg_nominal[vg] >= v1:
            return vg
    return 320  # fallback to highest available


# ---------------------------------------------------------------------------
# Step 6 — Contamination
# ---------------------------------------------------------------------------

def step_contamination() -> str:
    _header("Step 6 — Contamination / cleanliness")
    opts = [
        "High cleanliness     (filtered oil, clean room)",
        "Normal cleanliness   (typical industrial)",
        "Slight contamination (some particles)",
        "Typical contamination",
        "Severe contamination",
        "Very heavy contamination",
    ]
    keys = [
        "high_cleanliness",
        "normal_cleanliness",
        "slight_contamination",
        "typical_contamination",
        "severe_contamination",
        "very_heavy_contamination",
    ]
    choice = _menu("Select contamination level:", opts)
    return keys[choice - 1]


# ---------------------------------------------------------------------------
# Step 7 — Filter candidate bearings
# ---------------------------------------------------------------------------

def step_filter_bearings(all_bearings: list, geom: dict, Fr: float, Fa: float,
                          n: float, L10h_req: float, T_op: float,
                          contamination: str) -> list:
    _header("Step 7 — Candidate bearing selection")

    d     = geom["d"]
    D_max = geom["D_max"]
    B_max = geom["B_max"]

    candidates = [b for b in all_bearings if b.d == d]

    if D_max is not None:
        candidates = [b for b in candidates if b.D <= D_max]
    if B_max is not None:
        candidates = [b for b in candidates if b.B <= B_max]

    if not candidates:
        print(f"\n  ✖  No bearings found for d={d} mm with the given constraints.")
        print("  Try relaxing D_max or B_max.")
        sys.exit(1)

    # ---- life pre-filter ----
    print("\n  Checking life feasibility for each candidate...")
    try:
        from skf_model.common.life import BearingLife as _BL
        viable = []
        rejected = []
        for b in candidates:
            try:
                bd = {
                    "type": "deep_groove_ball",
                    "C":  b.C * 1000, "C0": b.C0 * 1000,
                    "Pu": b.Pu * 1000, "f0": b.f0,
                    "d":  b.d, "dm": 0.5*(b.d+b.D),
                    "kr": b.kr, "clearance": "normal",
                }
                life = _BL(bearing=bd, Fr=Fr, Fa=Fa, n=n,
                           viscosity_grade="68", temperature=T_op,
                           contamination=contamination)
                s = life.summary()
                if s["L_skf"] >= L10h_req:
                    viable.append((b, s["L_skf"]))
                else:
                    rejected.append((b, s["L_skf"]))
            except Exception:
                rejected.append((b, 0.0))

        if rejected:
            print(f"  ✖  {len(rejected)} bearing(s) cannot meet L10h ≥ {L10h_req:,.0f} h — excluded.")
        if not viable:
            print("\n  ✖  No candidates meet the required life.")
            print("  Suggestions: reduce L10h, increase bore size, or relax geometry constraints.")
            sys.exit(1)
        candidates = [b for b, _ in viable]
        print(f"  ✔  {len(candidates)} candidate(s) meet the life requirement.\n")
    except ImportError:
        print("  ⚠  Life pre-filter skipped (BearingLife not available).")

    print(f"  {'Designation':<18} {'d':>5} {'D':>5} {'B':>5} {'C [kN]':>8} {'C0 [kN]':>8} {'n_limit':>8}")
    print("  " + "─" * 62)
    for b in candidates:
        print(f"  {b.designation:<18} {b.d:>5.0f} {b.D:>5.0f} {b.B:>5.0f} "
              f"{b.C:>8.2f} {b.C0:>8.2f} {b.n_limit:>8.0f}")

    return candidates


# ---------------------------------------------------------------------------
# Step 7b — Select single candidate for GA
# ---------------------------------------------------------------------------

def step_select_candidate(candidates: list) -> list:
    """Ask user to pick one bearing from the candidate list, or run all."""
    print()
    opts = [f"{b.designation}  (D={b.D:.0f} mm  B={b.B:.0f} mm  C={b.C:.2f} kN  n_lim={b.n_limit:.0f} rpm)"
            for b in candidates]
    opts.append("Run GA on ALL candidates and pick best")
    choice = _menu("Select bearing to optimise:", opts)
    if choice == len(opts):
        return candidates          # all
    return [candidates[choice - 1]]


# ---------------------------------------------------------------------------
# Step 8 — Genetic algorithm
# ---------------------------------------------------------------------------

def step_genetic_optimisation(
    candidates: list,
    Fr: float,
    Fa: float,
    L10h_req: float,
    T_op: float,
    n: float,
    lube: dict,
    contamination: str,
) -> tuple:
    _header("Step 8 — Genetic algorithm optimisation")

    print("  The GA will optimise: ISO VG grade and rotational speed.")
    print(f"  Operating temperature fixed at T_op = {T_op:.1f} °C (your input).")
    print("  Objective: minimise friction (70%) + maximise life margin (30%).\n")

    best_result   = None
    best_bearing  = None
    best_fitness  = float("inf")

    n_min = max(100.0, n * 0.5)   # allow speed down to 50 % of input
    n_max = n                     # do not exceed user-specified speed

    for bearing in candidates:
        n_max_b = min(n_max, bearing.n_limit)
        if n_max_b < n_min:
            continue  # bearing cannot run in the allowed speed range

        vg_lo = 0
        vg_hi = len(VG_GRADES) - 1

        opt = GeneticOptimiser(
            fitness_fn     = evaluate,
            fitness_kwargs = dict(
                bearing       = bearing,
                Fr            = Fr,
                Fa            = Fa,
                T_op          = T_op,
                L10h_req      = L10h_req,
                contamination = contamination,
                lubrication   = lube["lubrication"],
                lubricant     = lube["lubricant"],
                H             = lube["H"],
            ),
            bounds = {
                "vg_idx": (0,     len(VG_GRADES) - 1),
                "n"     : (n_min, n_max_b),
            },
            pop_size     = 30,
            elite_frac   = 0.30,
            P_cross      = 0.90,
            P_mut        = 0.008,
            max_gen      = 100,
            lambda_init  = 10.0,
            beta1        = 1.2,
            beta2        = 1.1,
            Nf           = 20,
            seed         = 42,
            verbose      = True,
        )

        print(f"  Optimising {bearing.designation} ...", end=" ", flush=True)
        result = opt.run()
        # merit is maximised; convert to Aval for comparison (lower Aval = better)
        print(f"merit = {result['best_merit']:.4f}  |  Aval = {result['best_Aval']:.4f}")

        if result["best_Aval"] < best_fitness:
            best_fitness  = result["best_Aval"]
            best_result   = result
            best_bearing  = bearing

    return best_bearing, best_result


# ---------------------------------------------------------------------------
# Step 9 — Summary
# ---------------------------------------------------------------------------

def step_summary(
    best_bearing,
    best_result: dict,
    Fr: float,
    Fa: float,
    T_op: float,
    L10h_req: float,
    lube: dict,
    contamination: str,
) -> None:
    _header("Results — Optimal bearing and operating conditions")

    if best_bearing is None or best_result is None:
        print("\n  ✖  No feasible solution found.")
        print("  Suggestions:")
        print("    • Relax geometric constraints (D_max, B_max)")
        print("    • Reduce required life L10h")
        print("    • Check that loads Fr / Fa are within bearing capacity")
        return

    genes  = best_result["best_genes"]
    vg_val = VG_GRADES[int(genes["vg_idx"])]
    n_opt  = genes["n"]
    T_opt  = lube.get("T_op", 70.0)   # T_op was fixed by user, not a gene

    print(f"\n  Bearing selected   : {best_bearing.designation}")
    print(f"  Bore d             : {best_bearing.d:.0f} mm")
    print(f"  Outer diameter D   : {best_bearing.D:.0f} mm")
    print(f"  Width B            : {best_bearing.B:.0f} mm")
    print(f"  Dynamic rating C   : {best_bearing.C:.2f} kN")
    print(f"  Static rating C0   : {best_bearing.C0:.2f} kN")

    print(f"\n  ── Optimised operating conditions ──")
    print(f"  ISO VG grade       : VG {vg_val}")
    print(f"  Operating temp.    : {T_opt:.1f} °C")
    print(f"  Operating speed    : {n_opt:.0f} rpm")
    print(f"  Lubrication mode   : {lube['lubrication']}")
    print(f"  Lubricant base     : {lube['lubricant']}")
    print(f"  Contamination      : {contamination}")

    print(f"\n  ── Fitness ──")
    print(f"  Best merit  : {best_result['best_merit']:.6f}  (higher = better)")
    print(f"  Best Aval   : {best_result['best_Aval']:.6f}  (lower = better)")

    # Re-evaluate to recover intermediate values for display
    try:
        from genetic_algorithm.fitness import get_intermediate_values
        iv = get_intermediate_values(
            genes         = {"vg_idx": genes["vg_idx"], "n": n_opt},
            bearing       = best_bearing,
            Fr            = Fr,
            Fa            = Fa,
            T_op          = T_opt,
            L10h_req      = L10h_req,
            contamination = contamination,
            lubrication   = lube["lubrication"],
            lubricant     = lube["lubricant"],
            H             = lube["H"],
        )

        fr = iv["fr"]

        print(f"\n  ── Lubrication ──")
        print(f"  Actual viscosity v : {iv['v_act']:.2f} mm²/s  (VG {iv['vg']} at {iv['T_op']:.1f} °C)")
        print(f"  Rated viscosity v1 : {iv['v1']:.2f} mm²/s")
        print(f"  Viscosity ratio κ  : {iv['kappa']:.3f}")
        if iv["kappa"] < 1.0:
            print("  ⚠  κ < 1 — consider EP additive or higher VG grade.")

        print(f"\n  ── Life ──")
        print(f"  L_skf (modified)   : {iv['L_skf']:,.0f} h  (required: {L10h_req:,.0f} h)")
        margin = (iv["L_skf"] - L10h_req) / L10h_req * 100
        print(f"  Safety margin      : {margin:+.1f} %")

        print(f"\n  ── Frictional moment ──")
        def _fval(key):
            return fr.get(key) if isinstance(fr, dict) else getattr(fr, key, None)

        for label, key in [("M_rr  (rolling)", "M_rr"),
                            ("M_sl  (sliding)", "M_sl"),
                            ("M_drag (drag)  ", "M_drag"),
                            ("M_seal         ", "M_seal"),
                            ("M_total        ", "M_tot")]:
            val = _fval(key)
            if val is not None:
                print(f"  {label} : {val:.2f} N·mm")

    except Exception as exc:
        print(f"\n  ⚠  Could not compute detailed results: {exc}")

    print(f"\n{_DIVIDER}\n")


def _detect_seal(designation: str):
    d = designation.upper()
    if "2RSH" in d or "2RS1" in d or "RSH" in d or "RS1" in d:
        return "RSH"
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "═" * 62)
    print("  SKF Bearing Selection Tool")
    print("  Deep Groove Ball Bearing — Phase 1")
    print("═" * 62)

    # Load full bearing database
    all_bearings = load_bearings()

    # --- Input steps ---
    _          = step_bearing_type()           # type (DGBB only)
    geom       = step_geometry(all_bearings)
    loads      = step_loads()
    conditions = step_operating_conditions()
    dm_est     = geom["d"] + 10               # rough estimate before bearing is known
    lube       = step_lubrication(dm=dm_est, n=conditions["n"])
    lube["T_op"] = conditions["T_op"]
    contamination = step_contamination()

    Fr      = loads["Fr"]
    Fa      = loads["Fa"]
    n       = conditions["n"]
    L10h    = conditions["L10h_req"]
    T_op    = conditions["T_op"]

    # --- Filter ---
    candidates = step_filter_bearings(all_bearings, geom, Fr, Fa,
                                      n=n, L10h_req=L10h,
                                      T_op=T_op, contamination=contamination)

    # --- Select single candidate ---
    candidates = step_select_candidate(candidates)

    # --- Confirm before running GA ---
    print(f"\n  Ready to run genetic algorithm on {len(candidates)} candidate(s).")
    go = input("  Proceed? [Y/n]: ").strip().lower()
    if go == "n":
        print("  Aborted.\n")
        sys.exit(0)

    # --- GA ---
    best_bearing, best_result = step_genetic_optimisation(
        candidates=candidates,
        Fr=Fr, Fa=Fa,
        L10h_req=L10h,
        T_op=T_op,
        n=n,
        lube=lube,
        contamination=contamination,
    )

    # --- Summary ---
    step_summary(
        best_bearing=best_bearing,
        best_result=best_result,
        Fr=Fr, Fa=Fa,
        T_op=T_op,
        L10h_req=L10h,
        lube=lube,
        contamination=contamination,
    )

    # --- Report ---
    print()
    gen_report = input("  Generate PDF report? [Y/n]: ").strip().lower()
    if gen_report != "n":
        from genetic_algorithm.fitness import get_intermediate_values
        iv = get_intermediate_values(
            genes         = best_result["best_genes"],
            bearing       = best_bearing,
            Fr            = Fr,
            Fa            = Fa,
            T_op          = T_op,
            L10h_req      = L10h,
            contamination = contamination,
            lubrication   = lube["lubrication"],
            lubricant     = lube["lubricant"],
            H             = lube["H"],
        )
        fr = iv["fr"]
        report_data = {
            # bearing
            "bearing"       : best_bearing,
            "candidates"    : candidates,
            # inputs
            "Fr"            : Fr,
            "Fa"            : Fa,
            "n"             : n,
            "T_op"          : T_op,
            "L10h_req"      : L10h,
            "contamination" : contamination,
            "lubrication"   : lube["lubrication"],
            "lubricant"     : lube["lubricant"],
            "H"             : lube["H"],
            "vg"            : iv["vg"],
            "n_opt"         : iv["n"],
            # GA histories
            "ga_history"        : best_result["history"],
            "ga_pen_history"    : best_result["pen_history"],
            "ga_lambda_history" : best_result["lambda_history"],
            # computed results
            "v_act"  : iv["v_act"],
            "v1"     : iv["v1"],
            "kappa"  : iv["kappa"],
            "L_skf"  : iv["L_skf"],
            "L10h"   : iv["L10h"],
            "M_rr"   : fr.get("M_rr",   0.0),
            "M_sl"   : fr.get("M_sl",   0.0),
            "M_drag" : fr.get("M_drag", 0.0),
            "M_seal" : fr.get("M_seal", None),
            "M_tot"  : fr.get("M_tot",  0.0),
        }
        pdf_path = generate_report(report_data)
        open_report(pdf_path)


if __name__ == "__main__":
    main()