# SKF-Bearing-Selection-Tool

Python implementation of the SKF bearing selection procedure, following the sequence described in the SKF General Catalogue (10000 EN). The project is under active development.

---

## Background

The SKF online selection tools do not expose intermediate values — viscosity ratio, equivalent load, or the a_SKF factor used — making it impossible to audit a result or integrate the calculation into a larger workflow. This library implements the same procedure with every intermediate value accessible and every formula referenced to the catalogue page it comes from.

The scope extends in two directions that the SKF tools do not cover: given a bearing designation and operating speed, the library returns the ideal operating conditions (reverse lookup); and given vibration data or detected misalignment, it corrects the life estimate and identifies fault frequencies.

---

## Status

The project is in active development. The current focus is deep groove ball bearing (DGBB) selection and lubrication assessment.

**Phase 1 — in progress**

- L10 basic rating life per ISO 281
- a_SKF correction factor: catalogue curves digitised with WebPlotDigitizer, stored as CSV per kappa value, interpolated in Python
- Equivalent dynamic load P with axial load factors e and Y from the catalogue tables
- `selector.py`: given (Fr, Fa, n, L10h), returns a ranked list of bearings with estimated life, safety margin, and total frictional moment
- Friction model: M_rr, M_sl, M_drag, M_seal and M_total for all bearing types (Table 1a / 1b)
  - `geometry_variables.py`: G_rr and G_sl per bearing type, exact catalogue formulas
  - `frictional_moment.py`: φ_ish, φ_rs, φ_bl, μ_sl, drag loss, seal moment
  - Drag loss factor V_M digitised for ball and roller bearings, combined interpolation from zoomed and full-range curves
  - Seal moment using real catalogue dimensions d1 and d2 where available; automatic seal type detection from bearing designation
- Bearing database extended with abutment dimensions d1, d2, D1, D2 and fillet radius r1,2 for all DGBB entries (SKF General Catalogue, sourced per bearing)
- Validation against the SKF Bearing Calculator on a set of reference cases

**Phase 2 — planned**

- Viscosity ratio kappa = v / v1 and lubrication condition assessment
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
+-- Graficos/
|   +-- Bearing life/
|   |   +-- a_SKF/
|   |       +-- Ball Bearing/
|   |           +-- k_0.15.csv             # digitised curve, kappa = 0.15
|   |           +-- k_0.2.csv
|   |           +-- ...
|   |           +-- k_4.csv
|   |           +-- a_skf_radial_ball_bearing.py
|   +-- Friction Moments/
|   |   +-- Drag Moment/
|   |       +-- Drag Loss Factor Vm/
|   |           +-- ball_bearing_ampliado.csv      # digitised V_M curve, ball, H/dm 0–0.2
|   |           +-- ball_bearing.csv               # digitised V_M curve, ball, full range
|   |           +-- roller_bearing_ampliado.csv    # digitised V_M curve, roller, H/dm 0–0.2
|   |           +-- roller_bearing.csv             # digitised V_M curve, roller, full range
|   |           +-- drag_loss_factor_Vm.py         # interpolator + get_Vm() + plot
|   +-- Viscosity/
|       +-- Rated Viscosity/
|       |   +-- n_rpm_2.csv                # digitised rated viscosity curve, n = 2 rpm
|       |   +-- n_rpm_5.csv
|       |   +-- ...
|       |   +-- n_rpm_100 000.csv
|       |   +-- low_n_dm_boundary.csv      # low nd_m area boundary
|       |   +-- high_n_dm_boundary.csv     # high nd_m area boundary
|       |   +-- rated_viscosity.py
|       +-- Viscosity-temperature diagram/
|           +-- VG 10.csv                  # viscosity-temperature curve, ISO VG 10
|           +-- VG 100.csv
|           +-- ...
|           +-- viscosity_ISO.py
|
+-- skf_model/
    +-- bearings/
    |   +-- data/
    |   |   +-- deep_groove_ball.csv       # C, C0, dimensions, abutment dims, speed limits
    |   |   +-- deep_groove_ball.py        # dataclass + loader
    |   +-- angular_contact_ball.py        # Phase 2
    |   +-- cylindrical_roller.py          # Phase 2
    +-- common/
    |   +-- __pycache__/
    |   +-- constants/
    |   +-- frictional_moment.py           # total frictional moment (M_rr, M_sl, M_drag, M_seal)
    |   +-- geometry_variables.py          # G_rr and G_sl per bearing type (Table 1a / 1b)
    |   +-- life.py                        # L10 and a_SKF rating life
    |   +-- lubrication.py                 # v1, kappa (Phase 2)
    |   +-- misalignment.py                # load correction factor (Phase 3)
    +-- diagnostics/
    +-- friction_model/
        +-- drag_friction/
        |   +-- drag_loss_constants.csv    # geometric constants Kz and KL per bearing type (Table 4)
        |   +-- drag_loss_constants.py
        +-- friction_constants/
        |   +-- friction_RS_constants.csv  # friction constants for RS-sealed bearings
        |   +-- rs_constants.py
        +-- seal_friction/
        |   +-- friction_seal_constants.py
        |   +-- seal_frictional_moment.csv # seal frictional moment constants (KS1, KS2, beta, ds)
```

---

## Installation

Requires Python 3.9 or later.

```bash
git clone https://github.com/<username>/SKF-Bearing-Selection-Tool.git
cd SKF-Bearing-Selection-Tool
pip install numpy pandas scipy
```

---

## Usage

### Rated viscosity

```python
from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1, get_n, get_zone

v1 = get_v1(dm=100, n=1500)     # rated viscosity for dm=100 mm, n=1500 rpm
n  = get_n(dm=100, v1=12)       # speed for dm=100 mm, v1=12 mm²/s
z  = get_zone(dm=100, v1=12)    # 'low', 'normal', or 'high'
```

### Bearing life modification factor

```python
from Graficos.Bearing_life.a_SKF.Ball_Bearing.a_skf_radial_ball_bearing import get_a_skf

a = get_a_skf(x=0.5, k=0.25)   # a_SKF for given contamination factor x and viscosity ratio k
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
    d   = b.d,        # bore diameter [mm]
    D   = b.D,        # outside diameter [mm]
    B   = b.B,        # width [mm]
    Fr  = 3000,       # radial load [N]
    Fa  = 500,        # axial load [N]
    n   = 1500,       # rotational speed [r/min]
    v   = 32,         # actual viscosity [mm²/s]
    H   = 0,          # oil level [mm] — 0 for grease / oil-air
    lubrication = "oil_air",
    lubricant   = "mineral",
    seal_type   = "RSH",   # None for open/shielded, auto-detected in selector
    C0          = b.C0 * 1000,   # static load rating [N]
    d1          = b.d1,   # inner seal diameter from catalogue [mm]
    d2          = b.d2,   # outer seal diameter from catalogue [mm]
)
print(r)           # M_rr, M_sl, M_drag, M_seal, M_tot  [N·mm]
```

### Drag loss factor V_M

```python
from drag_loss_factor_Vm import get_Vm

Vm = get_Vm(H_over_dm=0.5, bearing_family="ball")   # V_M at H/dm = 0.5
```

### Bearing selection

```python
from skf_model.selector import select_bearings

df = select_bearings(
    Fr              = 5000,     # radial load [N]
    Fa              = 1000,     # axial load [N]
    n               = 1500,     # rotational speed [rpm]
    L10h_required   = 20000,    # required service life [h]
    viscosity_grade = "100",    # ISO VG grade
    temperature     = 70,       # operating temperature [°C]
    contamination   = "normal_cleanliness",
    d               = None,     # fix bore diameter [mm] — None for all
    compute_friction = True,
    H               = 0,        # oil level [mm]
    lubrication     = "oil_air",
    sort_by         = "L_skf",
)
```

---

## Catalogue curves

All curves are taken from the SKF General Catalogue and digitised using WebPlotDigitizer. Each curve is stored as a CSV file with the raw digitised points alongside the Python script that reads and interpolates it. This keeps the source data visible and independently verifiable.

Current coverage:

- a_SKF factor — ball bearings, kappa = 0.15 to 4.0 (13 curves)
- Rated viscosity v1 — n = 2 to 100 000 rpm (17 curves), with operating zone boundaries
- Viscosity-temperature — ISO VG grades 10 to 1000
- Drag constants Kz and KL — all bearing types per SKF General Catalogue Table 4, stored in `drag_friction/drag_loss_constants.csv`
- Drag loss factor V_M — ball and roller bearings, H/dm = 0 to 1.4 (4 curves, zoomed + full range combined)

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
Operating conditions: Fr, Fa, n, lubricant viscosity, required L10h
    |
    +-- 1. Bearing type      load direction, space, misalignment tolerance
    +-- 2. Bearing size      required C from L10 equation, selection from database
    +-- 3. a_SKF factor      kappa from viscosity, a_SKF from digitised catalogue curve
    +-- 4. Lubrication       v1, kappa, relubrication interval
    +-- 5. Friction          drag loss, seal friction, frictional moment
    +-- 6. Diagnostics       fault frequencies, misalignment correction
    |
    v
Bearing designation + operating recommendations
```

All formula references in the source code include the catalogue section and page number as comments.

---

## References

- SKF General Catalogue 10000 EN
- ISO 281:2007 — Rolling bearings: Dynamic load ratings and rating life
- ISO/TS 16281:2008 — Methods for calculating the modified reference rating life
- SKF Engineering Handbook