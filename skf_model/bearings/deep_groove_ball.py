# bearings/deep_groove_ball.py

import os
import pandas as pd
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeepGrooveBallBearing:
    """
    Represents a single SKF deep groove ball bearing.
    Data sourced from SKF General Catalogue 10000 EN.
    """
    type            : str            # Bearing type (s_row = single row)
    designation     : str            # SKF designation (e.g. 6205, 623-2RS1)
    capped_one_side : Optional[str]  # Designation capped on one side (e.g. 623-RS1)
    d               : float          # Bore diameter (mm)
    D               : float          # Outer diameter (mm)
    B               : float          # Width (mm)
    C               : float          # Dynamic load rating (kN)
    C0              : float          # Static load rating (kN)
    Pu              : float          # Fatigue load limit (kN)
    n_ref           : Optional[float]  # Reference speed (rpm) — None se não aplicável
    n_limit         : float          # Limiting speed (rpm)
    mass            : float          # Mass (kg)
    kr              : float          # Rigidity factor — used for misalignment (Semester)
    f0              : float          # Geometry factor — used for axial load calculation


def load_bearings(csv_path: str = None) -> list[DeepGrooveBallBearing]:
    """
    Loads all bearings from the CSV database.
    Returns a list of DeepGrooveBallBearing objects.
    """
    if csv_path is None:
        base_dir = os.path.dirname(__file__)
        csv_path = os.path.join(base_dir, "data", "deep_groove_ball", "deep_groove_ball.csv")

    df = pd.read_csv(
        csv_path,
        dtype     = {'designation': str, 'capped_one_side': str, 'type': str},
        na_values = ['', ' ']
    )

    # Limpar espaços nos nomes das colunas
    df.columns = df.columns.str.strip()

    bearings = []
    for _, row in df.iterrows():
        bearings.append(DeepGrooveBallBearing(
            type            = row['type'].strip(),
            designation     = row['designation'].strip(),
            capped_one_side = row['capped_one_side'].strip() if pd.notna(row['capped_one_side']) else None,
            d               = float(row['d']),
            D               = float(row['D']),
            B               = float(row['B']),
            C               = float(row['C']),
            C0              = float(row['C0']),
            Pu              = float(row['Pu']),
            n_ref           = float(row['n_ref']) if pd.notna(row['n_ref']) else None,
            n_limit         = float(row['n_limit']),
            mass            = float(row['mass']),
            kr              = float(row['kr']),
            f0              = float(row['f0']),
        ))
    return bearings


if __name__ == "__main__":
    bearings = load_bearings()
    print(f"Loaded {len(bearings)} bearings:\n")
    for b in bearings:
        print(f"{b.designation:<20} C={b.C} kN  d={b.d}mm  n_ref={b.n_ref}  capped={b.capped_one_side}")