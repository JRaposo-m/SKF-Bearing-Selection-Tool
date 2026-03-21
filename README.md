# skf-bearing-model

Python implementation of the SKF bearing selection procedure, following the sequence described in the SKF General Catalogue (10000 EN). The project is under active development.

---

## Background

The SKF online selection tools do not expose intermediate values — viscosity ratio, equivalent load, or the a_SKF factor used — making it impossible to audit a result or integrate the calculation into a larger workflow. This library implements the same procedure with every intermediate value accessible and every formula referenced to the catalogue page it comes from.

The scope extends in two directions that the SKF tools do not cover: given a bearing designation and operating speed, the library returns the ideal operating conditions (reverse lookup); and given vibration data or detected misalignment, it corrects the life estimate and identifies fault frequencies.

---

## Status

The project is at the end of Phase 1. Deep groove ball bearing (DGBB) selection is the current focus.

**Phase 1 — in progress**

- L10 basic rating life per ISO 281
- a_SKF correction factor: catalogue curves digitised with WebPlotDigitizer, stored as CSV per kappa value, interpolated in Python
- Equivalent dynamic load P with axial load factors e and Y from the catalogue tables
- `selector.py`: given (Fr, Fa, n, L10h), returns a ranked list of bearings with estimated life and safety margin
- Validation against the SKF Bearing Calculator on a set of reference cases

**Phase 2 — planned**

- Reference viscosity v1 from bearing mean diameter and speed
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
skf-bearing-model/
|
+-- bearings/
|   +-- deep_groove_ball.py        # load ratings, geometry, speed limits
|   +-- angular_contact_ball.py    # Phase 2
|   +-- cylindrical_roller.py      # Phase 2
|   +-- data/
|       +-- deep_groove_ball.csv   # C, C0, dimensions, speed limits
|
+-- catalogue/
|   +-- a_SKF/
|   |   +-- k_0.15.csv             # digitised curve, kappa = 0.15
|   |   +-- k_0.2.csv
|   |   +-- k_0.3.csv
|   |   +-- ...
|   |   +-- k_4.csv
|   +-- viscosity/
|       +-- VG_10.csv              # viscosity-temperature curve, ISO VG 10
|       +-- VG_100.csv
|       +-- ...
|
+-- common/
|   +-- life.py                    # L10 and a_SKF rating life
|   +-- load.py                    # equivalent dynamic and static load
|   +-- lubrication.py             # v1, kappa (Phase 2)
|   +-- misalignment.py            # load correction factor (Phase 3)
|
+-- diagnostics/                   # Phase 3
|   +-- vibration.py               # BPFO, BPFI, BSF, FTF
|   +-- fault_freq.py              # misalignment and imbalance pattern identification
|   +-- severity.py                # misalignment severity estimation
|
+-- selector.py                    # operating conditions -> bearing selection
+-- advisor.py                     # bearing -> ideal operating conditions (Phase 2)
+-- main.py                        # worked examples
+-- tests/
    +-- test_life.py
```

---

## Installation

Requires Python 3.9 or later.

```bash
git clone https://github.com/<username>/skf-bearing-model.git
cd skf-bearing-model
pip install numpy pandas scipy
```

---

## Usage

### Bearing selection

```python
from selector import select_bearing

results = select_bearing(
    Fr   = 5000,    # radial load, N
    Fa   = 1000,    # axial load, N
    n    = 1500,    # rotational speed, rpm
    L10h = 20000,   # required service life, hours
)
```

Returns a ranked DataFrame with bearing designation, dynamic load rating C, estimated L10h, and margin over the required life.

### Operating condition advisor (Phase 2)

```python
from advisor import get_operating_conditions

conditions = get_operating_conditions(
    bearing = '6308',
    n       = 1500,   # rpm
)
```

Returns reference viscosity v1, viscosity ratio kappa, static safety factor C0/P0, and maximum admissible axial load.

---

## Catalogue curves

The a_SKF factor and viscosity-temperature curves are taken from the SKF General Catalogue and digitised using WebPlotDigitizer. Each curve is stored as a CSV file with the raw digitised points. The Python scripts that read and interpolate these files are in the same directory. This keeps the source data visible and independently verifiable.

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
