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
- `selector.py`: given (Fr, Fa, n, L10h), returns a ranked list of bearings with estimated life and safety margin
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
    |   |   +-- deep_groove_ball.csv       # C, C0, dimensions, speed limits
    |   |   +-- deep_groove_ball.py
    |   +-- angular_contact_ball.py        # Phase 2
    |   +-- cylindrical_roller.py          # Phase 2
    +-- common/
        +-- life.py                        # L10 and a_SKF rating life
        +-- load.py                        # equivalent dynamic and static load
        +-- lubrication.py                 # v1, kappa (Phase 2)
        +-- misalignment.py                # load correction factor (Phase 3)
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

### Bearing selection (in progress)

```python
from skf_model.selector import select_bearing

results = select_bearing(
    Fr   = 5000,    # radial load, N
    Fa   = 1000,    # axial load, N
    n    = 1500,    # rotational speed, rpm
    L10h = 20000,   # required service life, hours
)
```

---

## Catalogue curves

All curves are taken from the SKF General Catalogue and digitised using WebPlotDigitizer. Each curve is stored as a CSV file with the raw digitised points alongside the Python script that reads and interpolates it. This keeps the source data visible and independently verifiable.

Current coverage:

- a_SKF factor — ball bearings, kappa = 0.15 to 4.0 (13 curves)
- Rated viscosity v1 — n = 2 to 100 000 rpm (17 curves), with operating zone boundaries
- Viscosity-temperature — ISO VG grades 10 to 1000

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
    +-- 5. Diagnostics       fault frequencies, misalignment correction
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
