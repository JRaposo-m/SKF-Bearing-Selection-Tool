# SKF Bearing Model

An open-source Python tool for SKF bearing selection, performance evaluation and fault diagnostics — built on the official SKF catalogue formulas.

> **Status:** 🚧 Active development  
> **Current phase:** Week 1 — Core selection (deep groove ball bearings)

---

## What this does

Most bearing tools are black boxes. This project exposes every formula with its exact catalogue reference, and extends the standard selection workflow in two directions the SKF online tools don't cover:

- **Bidirectional:** given a bearing → returns ideal operating conditions (not just the other way around)
- **Diagnostics:** given vibration data or misalignment → corrects life estimation and identifies fault frequencies

---

## Roadmap

### ✅ Week 1 — Core selection *(in progress)*
- [ ] Deep groove ball bearing database (CSV)
- [ ] L10 basic rating life
- [ ] SKF rating life (a_SKF factor)
- [ ] `selector.py` — operating conditions → ranked bearing list
- [ ] Results validated against SKF Bearing Calculator
- [ ] README with usage examples

### 🔲 Month 1 — Lubrication + multi-type
- [ ] Reference viscosity ν₁ and viscosity ratio κ
- [ ] Lubrication condition assessment
- [ ] `advisor.py` — given bearing → ideal operating conditions
- [ ] Extended database: angular contact + cylindrical roller bearings
- [ ] Unit tests for all core formulas

### 🔲 Semester — Diagnostics + misalignment
- [ ] Bearing fault frequencies (BPFO, BPFI, BSF, FTF)
- [ ] Misalignment detection from vibration signature (1×, 2× harmonics)
- [ ] Life correction factor based on detected misalignment
- [ ] Severity estimation module
- [ ] Full system: selection + lubrication + diagnostics in one workflow

---

## Project Structure

```
skf_model/
│
├── bearings/
│   ├── deep_groove_ball.py       # Deep groove ball bearings
│   ├── angular_contact_ball.py   # Angular contact ball bearings
│   ├── cylindrical_roller.py     # Cylindrical roller bearings
│   ├── tapered_roller.py         # Tapered roller bearings
│   ├── spherical_roller.py       # Spherical roller bearings
│   └── data/
│       └── deep_groove_ball.csv  # Bearing database (C, C0, speed limits, dimensions)
│
├── common/
│   ├── life.py                   # L10 and SKF rating life formulas
│   ├── lubrication.py            # Reference viscosity, κ ratio (Month 1)
│   ├── load.py                   # Equivalent dynamic/static load
│   └── misalignment.py           # Load correction for misalignment (Semester)
│
├── diagnostics/                  # (Semester)
│   ├── vibration.py              # Fault frequency calculation (BPFO, BPFI, BSF, FTF)
│   ├── fault_freq.py             # Misalignment/imbalance pattern identification
│   └── severity.py               # Misalignment severity estimation
│
├── selector.py                   # Operating conditions → bearing selection
├── advisor.py                    # Given bearing → ideal operating conditions (Month 1)
├── main.py                       # Entry point with usage examples
└── tests/
    └── test_life.py              # Unit tests (Month 1)
```

---

## How to Run

### Requirements

- Python 3.9 or later
- `numpy`, `pandas`

```bash
pip install numpy pandas
```

### Basic usage — Bearing selection

```python
from selector import select_bearing

results = select_bearing(
    Fr      = 5000,    # Radial load (N)
    Fa      = 1000,    # Axial load (N)
    n       = 1500,    # Rotational speed (rpm)
    L10h    = 20000,   # Required bearing life (hours)
)

print(results)
# Returns a ranked list of bearings with estimated life and safety margin
```

### Basic usage — Advisor *(Month 1)*

```python
from advisor import get_operating_conditions

conditions = get_operating_conditions(
    bearing = '6205',   # SKF bearing designation
    n       = 1500,     # Rotational speed (rpm)
)

print(conditions)
# Returns ideal viscosity, load limits, temperature range, etc.
```

---

## Methodology

This tool follows the official SKF bearing selection process:

```
Operating conditions
        │
        ├── Bearing type   (space, load, speed, misalignment)
        ├── Bearing size   (dynamic load, required life, viscosity)
        ├── Lubrication    (viscosity ratio κ, relubrication interval)
        └── Diagnostics    (fault frequencies, misalignment correction)
                │
                ▼
        Bearing solution
```

All formulas reference the **SKF General Catalogue (10000 EN)** with explicit page numbers in the source code comments.

---

## Why this exists

| | SKF online tools | This project |
|---|---|---|
| Formulas visible | ❌ Black box | ✅ Fully documented |
| Bidirectional | ❌ Conditions → bearing only | ✅ Both directions |
| Misalignment impact on life | ❌ | ✅ *(Semester)* |
| Fault frequency diagnostics | ❌ | ✅ *(Semester)* |
| Integrates into Python workflows | ❌ | ✅ |
| Open source | ❌ | ✅ |

---

## References

1. SKF General Catalogue 10000 EN
2. ISO 281 — Rolling bearings: Dynamic load ratings and rating life
3. ISO/TS 16281 — Methods for calculating the modified reference rating life
4. SKF Engineering Handbook
