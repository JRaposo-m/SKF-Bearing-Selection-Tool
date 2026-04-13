"""
Drag Loss Factor V_M
====================
Reads the four digitised CSV files for ball bearings and roller bearings,
combines the zoomed-in data (H/dm 0–0.2) with the full-range data (0.2–1.4),
and exposes get_Vm() for use by frictional_moment.py.

Run this file directly to plot V_M vs H/dm for both bearing types.

CSV files expected in the same directory as this script:
    ball_bearing_ampliado.csv
    ball_bearing.csv
    roller_bearing_ampliado.csv
    roller_bearing.csv

Each CSV has two columns: H/dm, Vm  (header on row 1)
"""

import pathlib
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from typing import Literal

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = pathlib.Path(__file__).parent

FILES = {
    "ball": {
        "zoomed": HERE / "ball_bearing_ampliado.csv",
        "full":   HERE / "ball_bearing.csv",
    },
    "roller": {
        "zoomed": HERE / "roller_bearing_ampliado.csv",
        "full":   HERE / "roller_bearing.csv",
    },
}

H_MAX = 1.40   # upper limit for interpolation / plot

# ---------------------------------------------------------------------------
# Helper: load one CSV -> (H_dm, Vm) arrays
# ---------------------------------------------------------------------------
def _load_csv(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(path, header=0, skipinitialspace=True)
    df = df[[c for c in df.columns if not c.startswith("Unnamed")]]
    df.columns = ["H_dm", "Vm"]
    df = df.dropna().sort_values("H_dm").reset_index(drop=True)
    return df["H_dm"].to_numpy(), df["Vm"].to_numpy()


# ---------------------------------------------------------------------------
# Helper: build a smooth combined interpolator for one bearing family
# ---------------------------------------------------------------------------
def _build_interpolator(zoomed_path: pathlib.Path,
                        full_path:   pathlib.Path,
                        cutoff: float = 0.25) -> PchipInterpolator:
    H_z, Vm_z = _load_csv(zoomed_path)
    H_f, Vm_f = _load_csv(full_path)

    # zoomed: all points; full: only above cutoff to avoid overlap / spike
    mask_f = H_f > cutoff

    H_all  = np.concatenate([H_z,       H_f[mask_f]])
    Vm_all = np.concatenate([Vm_z,      Vm_f[mask_f]])

    order = np.argsort(H_all)
    return PchipInterpolator(H_all[order], Vm_all[order])


# ---------------------------------------------------------------------------
# Build interpolators once at import time
# ---------------------------------------------------------------------------
_interp = {
    key: _build_interpolator(paths["zoomed"], paths["full"])
    for key, paths in FILES.items()
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_Vm(H_over_dm: float,
           bearing_family: Literal["ball", "roller"]) -> float:
    """
    Return the drag loss factor V_M for a given H/d_m ratio.

    Parameters
    ----------
    H_over_dm : float
        Oil level relative to bearing mean diameter H / d_m  (-).
        Capped internally at 1.2 (per catalogue: use H = 1.2*d_m when H >= 1.2*d_m).
    bearing_family : 'ball' | 'roller'

    Returns
    -------
    float
        V_M  (-)
    """
    H_capped = min(float(H_over_dm), 1.2)
    H_capped = max(H_capped, 0.0)
    return float(_interp[bearing_family](H_capped))


# ---------------------------------------------------------------------------
# Plot -- only when run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    H_plot    = np.linspace(0, H_MAX, 2000)
    Vm_ball   = _interp["ball"](H_plot)
    Vm_roller = _interp["roller"](H_plot)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(H_plot, Vm_ball,   color="#c0392b", linewidth=2, label="Ball bearings")
    ax.plot(H_plot, Vm_roller, color="#2980b9", linewidth=2, label="Roller bearings")
    ax.set_xlabel("H / $d_m$", fontsize=12)
    ax.set_ylabel("$V_M$",     fontsize=12)
    ax.set_title("Drag loss factor $V_M$", fontsize=13)
    ax.set_xlim(0, H_MAX)
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(HERE / "drag_loss_factor_Vm_plot.png", dpi=150)
    plt.show()
    print("Plot saved to drag_loss_factor_Vm_plot.png")