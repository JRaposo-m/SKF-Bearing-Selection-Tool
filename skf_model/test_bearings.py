import os
import sys
import pandas as pd

# aponta para a raiz do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skf_model.common.life import BearingLife

# --- Path ao CSV ---
csv_path = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    "skf_model", "bearings", "data", "deep_groove_ball", "deep_groove_ball.csv"
)

db = pd.read_csv(csv_path, skipinitialspace=True)

# --- Inputs operacionais ---
Fr     = 4060.11
Fa     = 0
n      = 0.255
vg     = "100"
temp   = 25
contam = "normal_cleanliness"

# --- Filtrar d=30 selados 2RS1 ---
candidates = db[(db["d"] == 45) & (db["designation"].str.contains("2RS1"))]

print(f"\n{'Designation':<20} {'C (kN)':<10} {'C0 (kN)':<10} {'L10h (h)':<14} {'L_skf (h)':<14} {'s0':<8}")
print("-" * 76)

for _, row in candidates.iterrows():
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

    try:
        bl = BearingLife(
            bearing         = bearing,
            Fr              = Fr,
            Fa              = Fa,
            n               = n,
            viscosity_grade = vg,
            temperature     = temp,
            contamination   = contam,
        )
        r = bl.summary()
        print(f"  {row['designation']:<18} {row['C']:<10.1f} {row['C0']:<10.1f} "
              f"{r['L10h']:<14.1f} {r['L_skf']:<14.1f} {r['s0']:<8.2f}")
    except Exception as e:
        print(f"  {row['designation']:<18} ERRO: {e}")