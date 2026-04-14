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
    type            : str
    designation     : str
    capped_one_side : Optional[str]
    d               : float          # Bore diameter (mm)
    d1              : Optional[float]  # Inner shoulder diameter (mm)
    d2              : Optional[float]  # Inner shoulder diameter, sealed side (mm)
    D               : float          # Outer diameter (mm)
    D1              : Optional[float]  # Outer shoulder diameter (mm)
    D2              : Optional[float]  # Outer shoulder diameter, sealed side (mm)
    B               : float          # Width (mm)
    r12_min         : float          # Minimum fillet radius (mm)
    C               : float          # Dynamic load rating (kN)
    C0              : float          # Static load rating (kN)
    Pu              : float          # Fatigue load limit (kN)
    n_ref           : Optional[float]  # Reference speed (rpm)
    n_limit         : float          # Limiting speed (rpm)
    mass            : float          # Mass (kg)
    kr              : float          # Rigidity factor
    f0              : float          # Geometry factor


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

    df.columns = df.columns.str.strip()

    bearings = []
    for _, row in df.iterrows():
        bearings.append(DeepGrooveBallBearing(
            type            = row['type'].strip(),
            designation     = row['designation'].strip(),
            capped_one_side = row['capped_one_side'].strip() if pd.notna(row['capped_one_side']) else None,
            d               = float(row['d']),
            d1              = float(row['d1'])   if pd.notna(row['d1'])  else None,
            d2              = float(row['d2'])   if pd.notna(row['d2'])  else None,
            D               = float(row['D']),
            D1              = float(row['D1'])   if pd.notna(row['D1'])  else None,
            D2              = float(row['D2'])   if pd.notna(row['D2'])  else None,
            B               = float(row['B']),
            r12_min         = float(row['r12_min']),
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
        print(
            f"{b.designation:<20} "
            f"d={b.d}mm  D={b.D}mm  B={b.B}mm  "
            f"d1={b.d1}  d2={b.d2}  "
            f"D1={b.D1}  D2={b.D2}  "
            f"r12={b.r12_min}  "
            f"C={b.C}kN  n_ref={b.n_ref}  "
            f"capped={b.capped_one_side}"
        )