# SKF-Bearing-Selection-Tool

Python implementation of the SKF bearing selection procedure, following the sequence described in the SKF General Catalogue (10000 EN). The project is under active development.

---

## Background

The SKF online selection tools do not expose intermediate values — viscosity ratio, equivalent load, or the a_SKF factor used — making it impossible to audit a result or integrate the calculation into a larger workflow. This library implements the same procedure with every intermediate value accessible and every formula referenced to the catalogue page it comes from.

The scope extends in two directions that the SKF tools do not cover: given a bearing designation and operating speed, the library returns the ideal operating conditions (reverse lookup); and given vibration data or detected misalignment, it corrects the life estimate and identifies fault frequencies.

---

## Status

**Phase 1 — complete**

- L10 basic rating life per ISO 281
- a_SKF correction factor: catalogue curves digitised with WebPlotDigitizer, stored as CSV per kappa value, interpolated in Python
- Equivalent dynamic load P with axial load factors e and Y from the catalogue tables
- `selector.py`: given (Fr, Fa, n, L10h), returns a ranked list of bearings with estimated life, safety margin, and total frictional moment
- Friction model: M_rr, M_sl, M_drag, M_seal and M_total for all bearing types (Table 1a / 1b)
  - `geometry_variables.py`: G_rr and G_sl per bearing type, exact catalogue formulas
  - `frictional_moment.py`: φ_ish, φ_rs, φ_bl, μ_sl, drag loss, seal moment — returns `FrictionResult` dataclass
  - Drag loss factor V_M digitised for ball and roller bearings, combined interpolation from zoomed and full-range curves
  - Seal moment using real catalogue dimensions d1 and d2 where available; automatic seal type detection from bearing designation
- Bearing database extended with abutment dimensions d1, d2, D1, D2 and fillet radius r1,2 for all DGBB entries (SKF General Catalogue, sourced per bearing)
- Validation against the SKF Bearing Calculator on a set of reference cases
- `main.py`: interactive console entry point — guided input flow, life pre-filter, bearing selection, genetic algorithm optimisation, and optional PDF report generation
- `genetic_algorithm/`: binary-coded single-objective GA (Hadj-Alouane & Bean adaptive penalty, SUS selection, uniform crossover, flip-bit mutation) — optimises ISO VG grade and operating speed for minimum friction subject to life and lubrication constraints
- `report_generator.py`: generates a professional multi-page PDF report with tables, viscosity curves, GA convergence plot, and friction breakdown chart — saved to `reports/`

**Phase 2 — planned**

- `advisor.py`: given bearing designation and speed, returns ideal viscosity, load limits, relubrication interval
- Database extended to angular contact ball and cylindrical roller bearings
- Unit tests for all core formulas

**Phase 3 — planned**

- Bearing fault frequencies: BPFO, BPFI, BSF, FTF from bearing geometry
- Misalignment detection from vibration signature (1x, 2x harmonics)
- Life correction factor based on detected misalignment severity
- Full workflow: selection, lubrication assessment, and diagnostics in sequence

---

## Repository structure

```
SKF-Bearing-Selection-Tool/
|
+-- main.py                            # interactive entry point — run this
+-- report_generator.py                # PDF report builder (reportlab + matplotlib)
+-- selector.py                        # programmatic bearing selector (returns DataFrame)
|
+-- genetic_algorithm/
|   +-- __init__.py
|   +-- fitness.py                     # Aval(x) = f(x) + λ·Σu², returns (Aval, pen_sum)
|   +-- ga_optimizer.py                # binary GA: SUS, uniform crossover, flip-bit, H-A&B
|
+-- reports/                           # auto-created — PDF reports saved here
|
+-- Graficos/
|   +-- Bearing_life/
|   |   +-- a_SKF/
|   |       +-- Ball_Bearing/
|   |           +-- k_0.15.csv         # digitised curve, kappa = 0.15
|   |           +-- k_0.2.csv
|   |           +-- ...
|   |           +-- k_4.csv
|   |           +-- a_skf_radial_ball_bearing.py
|   +-- Friction Moments/
|   |   +-- Drag Moment/
|   |       +-- Drag Loss Factor Vm/
|   |           +-- ball_bearing_ampliado.csv      # V_M curve, ball, H/dm 0–0.2
|   |           +-- ball_bearing.csv               # V_M curve, ball, full range
|   |           +-- roller_bearing_ampliado.csv    # V_M curve, roller, H/dm 0–0.2
|   |           +-- roller_bearing.csv             # V_M curve, roller, full range
|   |           +-- drag_loss_factor_Vm.py
|   +-- Viscosity/
|       +-- Rated_Viscosity/
|       |   +-- n_rpm_2.csv            # digitised rated viscosity curve, n = 2 rpm
|       |   +-- ...
|       |   +-- n_rpm_100 000.csv
|       |   +-- low_n_dm_boundary.csv
|       |   +-- high_n_dm_boundary.csv
|       |   +-- rated_viscosity.py
|       +-- Viscosity_temperature_diagram_for_ISO_viscosity_grades/
|           +-- VG 10.csv              # viscosity-temperature curve, ISO VG 10
|           +-- VG 100.csv
|           +-- ...
|           +-- viscosity_ISO.py
|
+-- skf_model/
    +-- bearings/
    |   +-- data/
    |   |   +-- deep_groove_ball.csv   # C, C0, dimensions, abutment dims, speed limits
    |   |   +-- deep_groove_ball.py    # dataclass + loader
    |   +-- angular_contact_ball.py    # Phase 2
    |   +-- cylindrical_roller.py      # Phase 2
    +-- common/
    |   +-- constants/
    |   +-- frictional_moment.py       # M_rr, M_sl, M_drag, M_seal → FrictionResult
    |   +-- geometry_variables.py      # G_rr and G_sl per bearing type (Table 1a/1b)
    |   +-- life.py                    # BearingLife class — L10, a_SKF, L_skf, summary()
    |   +-- lubrication.py             # v1, kappa (Phase 2)
    |   +-- misalignment.py            # load correction factor (Phase 3)
    +-- diagnostics/
    +-- friction_model/
        +-- drag_friction/
        |   +-- drag_loss_constants.csv
        |   +-- drag_loss_constants.py
        +-- friction_constants/
        |   +-- friction_RS_constants.csv
        |   +-- rs_constants.py
        +-- seal_friction/
            +-- friction_seal_constants.py
            +-- seal_frictional_moment.csv  # KS1, KS2, beta, ds per seal type
```

---

## Installation

Requires Python 3.9 or later.

```bash
git clone https://github.com/<username>/SKF-Bearing-Selection-Tool.git
cd SKF-Bearing-Selection-Tool
pip install numpy pandas scipy matplotlib reportlab
```

---

## Quick start — interactive tool

Run from the repository root:

```bash
python main.py
```

The tool guides you through 8 steps:

1. **Bearing type** — DGBB (Phase 1); angular contact and roller in Phase 2
2. **Geometry constraints** — bore diameter d (required); D_max and B_max optional
3. **Operating loads** — Fr and Fa in N (direct input; assisted calculation coming)
4. **Operating conditions** — speed n [rpm], required life L10h [h], temperature T_op [°C]
5. **Lubrication** — enter ISO VG grade directly, or let the tool recommend based on v1
6. **Contamination** — six levels from high cleanliness to very heavy contamination
7. **Candidate selection** — bearings that fail the life requirement are excluded; pick one or run all
8. **Genetic algorithm** — optimises ISO VG grade and speed for minimum friction subject to life and κ constraints; results printed to console

At the end you are asked whether to generate a PDF report. If yes, the report is saved to `reports/` and opened automatically.

---

## Usage — library API

### Rated viscosity

```python
from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1, get_n, get_zone

v1 = get_v1(dm=100, n=1500)     # rated viscosity [mm²/s] for dm=100 mm, n=1500 rpm
n  = get_n(dm=100, v1=12)       # speed [rpm] for dm=100 mm, v1=12 mm²/s
z  = get_zone(dm=100, v1=12)    # 'low', 'normal', or 'high'
```

### Bearing life modification factor

```python
from Graficos.Bearing_life.a_SKF.Ball_Bearing.a_skf_radial_ball_bearing import get_a_skf

a = get_a_skf(x=0.5, k=0.25)   # a_SKF for contamination factor x and viscosity ratio k
```

### Frictional moment

```python
from skf_model.common.frictional_moment import frictional_moment
from skf_model.bearings.deep_groove_ball import load_bearings

bearings = {b.designation: b for b in load_bearings()}
b = bearings["6208-2RSH"]

r = frictional_moment(
    bearing_type = "deep_groove_ball",
    designation  = b.designation,
    d            = b.d,         # bore diameter [mm]
    D            = b.D,         # outside diameter [mm]
    B            = b.B,         # width [mm]
    Fr           = 3000,        # radial load [N]
    Fa           = 500,         # axial load [N]
    n            = 1500,        # rotational speed [rpm]
    v            = 32,          # actual kinematic viscosity [mm²/s]
    H            = 0,           # oil level [mm] — 0 for grease / oil-air
    lubrication  = "oil_air",
    lubricant    = "mineral",
    seal_type    = "RSH",       # None for open/shielded
    subtype      = b.type,
    C0           = b.C0 * 1000, # static load rating [N]
    irw          = False,
    d1           = b.d1,        # inner seal diameter [mm] — None if not in catalogue
    d2           = b.d2,        # outer seal diameter [mm] — None if not in catalogue
)
# r is a FrictionResult dataclass
print(r.M_rr, r.M_sl, r.M_drag, r.M_seal, r.M_tot)   # all in [N·mm]
```

### Bearing selection (programmatic)

```python
from selector import select_bearings

df = select_bearings(
    Fr               = 5000,              # radial load [N]
    Fa               = 1000,              # axial load [N]
    n                = 1500,              # rotational speed [rpm]
    L10h_required    = 20000,             # required service life [h]
    viscosity_grade  = "100",             # ISO VG grade
    temperature      = 70,               # operating temperature [°C]
    contamination    = "normal_cleanliness",
    d                = None,              # fix bore diameter [mm] — None for all
    compute_friction = True,
    H                = 0,                # oil level [mm]
    lubrication      = "oil_air",
    sort_by          = "L_skf",
)
```

### Genetic algorithm (standalone)

```python
from genetic_algorithm.fitness import evaluate, VG_GRADES
from genetic_algorithm.ga_optimizer import GeneticOptimiser
from skf_model.bearings.deep_groove_ball import load_bearings

bearings = {b.designation: b for b in load_bearings()}
b = bearings["6305"]

opt = GeneticOptimiser(
    fitness_fn     = evaluate,
    fitness_kwargs = dict(
        bearing       = b,
        Fr            = 3000,
        Fa            = 500,
        T_op          = 70.0,
        L10h_req      = 20000,
        contamination = "normal_cleanliness",
        lubrication   = "grease",
        lubricant     = "mineral",
        H             = 0.0,
    ),
    bounds       = {"vg_idx": (0, 9), "n": (500.0, 1500.0)},
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

result = opt.run()
# result keys: best_genes, best_Aval, best_merit, history, pen_history, lambda_history
print(f"VG {VG_GRADES[result['best_genes']['vg_idx']]}  "
      f"n = {result['best_genes']['n']:.0f} rpm  "
      f"merit = {result['best_merit']:.4f}")
```

### PDF report (standalone)

```python
from report_generator import generate_report, open_report

# report_data must contain all keys listed in report_generator.py module docstring
pdf_path = generate_report(report_data)
open_report(pdf_path)
```

---

## Genetic algorithm — design notes

The GA optimises two variables for a given bearing and fixed operating temperature:

| Gene | Type | Search space |
|---|---|---|
| ISO VG grade index | discrete (4 bits) | VG 10, 15, 22, 32, 46, 68, 100, 150, 220, 320 |
| Rotational speed n | continuous (17 bits) | [n_min, n_limit] of the selected bearing |

The chromosome is 21 bits total (2 decimal places precision for n). Operators mirror the MATLAB implementation used in prior work: SUS selection with parent shuffle before pairing, uniform crossover with binary mask, flip-bit mutation at P_mut = 0.008 per bit. Elitism preserves the top 30 % of the population. The penalty function follows Hadj-Alouane & Bean with adaptive λ: λ increases when the best individual is infeasible for Nf consecutive generations, and decreases when it is feasible for Nf consecutive generations.

**Fitness function:**

```
f(x)    = 0.70 · (M_tot / M_ref) + 0.30 · (L10h_req / L_skf)
Aval(x) = f(x) + λ · Σ u_j(x)²
Merit   = C_max − Aval(x)                    (higher = better)
```

Hard constraints (normalised, g_j ≤ 0 is feasible):

| Constraint | Expression |
|---|---|
| Speed limit | n / n_limit − 1 ≤ 0 |
| Minimum lubrication film | 0.1 / κ − 1 ≤ 0  (κ ≥ 0.1) |
| Minimum life | L10h_req / L_skf − 1 ≤ 0 |

---

## Catalogue curves

All curves are taken from the SKF General Catalogue and digitised using WebPlotDigitizer. Each curve is stored as a CSV file alongside the Python script that reads and interpolates it.

Current coverage:

- a_SKF factor — ball bearings, kappa = 0.15 to 4.0 (13 curves)
- Rated viscosity v1 — n = 2 to 100 000 rpm (17 curves), with operating zone boundaries
- Viscosity-temperature — ISO VG grades 10 to 1000
- Drag constants Kz and KL — all bearing types per SKF General Catalogue Table 4
- Drag loss factor V_M — ball and roller bearings, H/dm = 0 to 1.4 (4 curves)

---

## Bearing database

The DGBB database (`deep_groove_ball.csv`) covers all single-row deep groove ball bearings from the SKF General Catalogue, including:

- Dynamic load rating C, static load rating C0, fatigue load limit Pu
- Bore d, outside diameter D, width B
- Abutment and fillet dimensions: d1, d2, D1, D2, r1,2_min
- Reference speed n_ref and limiting speed n_limit
- Calculation factors kr and f0

Seal dimensions d1 and d2 are used directly in the seal frictional moment calculation where available. When a dimension is not listed in the catalogue for a given variant, it is not used — no estimates are substituted.

---

## Calculation procedure

The selection sequence follows SKF General Catalogue section 17:

```
Operating conditions: Fr, Fa, n, T_op, required L10h
    |
    +-- 1. Bearing type       load direction, space constraints
    +-- 2. Life pre-filter    exclude bearings that cannot meet L10h_req
    +-- 3. Bearing selection  user picks one candidate (or runs GA on all)
    +-- 4. GA optimisation    optimise VG grade and speed → minimum friction
    +-- 5. Results summary    L_skf, kappa, M_tot, power loss
    +-- 6. PDF report         optional — saved to reports/
    |
    v
Bearing designation + optimised operating conditions + technical report
```

All formula references in the source code include the catalogue section and page number as comments.

---

## References

- SKF General Catalogue 10000 EN
- ISO 281:2007 — Rolling bearings: Dynamic load ratings and rating life
- ISO/TS 16281:2008 — Methods for calculating the modified reference rating life
- SKF Engineering Handbook
- Hadj-Alouane, A. B. & Bean, J. C. (1995) — A genetic algorithm for the multiple-choice integer program. *Computers & Operations Research*, 22(1), 57–67