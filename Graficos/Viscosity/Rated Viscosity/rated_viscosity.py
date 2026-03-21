import os
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# n curves — digitised from SKF General Catalogue, Fig. (Rated Viscosity)
# keys: rpm value | values: csv filename (dm, v1)
# ---------------------------------------------------------------------------
n_files = {
    2:       "n_rpm_2.csv",
    5:       "n_rpm_5.csv",
    10:      "n_rpm_10.csv",
    20:      "n_rpm_20.csv",
    50:      "n_rpm_50.csv",
    100:     "n_rpm_100.csv",
    200:     "n_rpm_200.csv",
    500:     "n_rpm_500.csv",
    1000:    "n_rpm_1 000.csv",
    1500:    "n_rpm_1 500.csv",
    2000:    "n_rpm_2 000.csv",
    3000:    "n_rpm_3 000.csv",
    5000:    "n_rpm_5 000.csv",
    10000:   "n_rpm_10 000.csv",
    20000:   "n_rpm_20 000.csv",
    50000:   "n_rpm_50 000.csv",
    100000:  "n_rpm_100 000.csv",
}

# ---------------------------------------------------------------------------
# Boundary files — digitised frontier points (dm, v1)
# ---------------------------------------------------------------------------
BOUNDARY_LOW  = "low_n_dm_boundary.csv"
BOUNDARY_HIGH = "high_n_dm_boundary.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_curve(fname):
    """Load a csv with columns dm,v1 and return sorted arrays."""
    df = pd.read_csv(os.path.join(BASE_DIR, fname), sep=",", skipinitialspace=True)
    df.columns = ["dm", "v1"]
    df = df.sort_values("dm")
    return df["dm"].values, df["v1"].values


def _make_loglog_interp(dm_arr, v1_arr):
    """PCHIP interpolator in log-log space with linear extrapolation."""
    lx = np.log10(dm_arr)
    ly = np.log10(v1_arr)
    pchip = PchipInterpolator(lx, ly)

    slope_left  = (ly[1]  - ly[0])  / (lx[1]  - lx[0])
    slope_right = (ly[-1] - ly[-2]) / (lx[-1] - lx[-2])

    def f(dm_new):
        dm_new = np.asarray(dm_new, dtype=float)
        lx_new = np.log10(dm_new)
        result = np.zeros_like(lx_new)
        left  = lx_new < lx[0]
        right = lx_new > lx[-1]
        mid   = ~left & ~right
        result[mid]   = pchip(lx_new[mid])
        result[left]  = ly[0]  + slope_left  * (lx_new[left]  - lx[0])
        result[right] = ly[-1] + slope_right * (lx_new[right] - lx[-1])
        return 10 ** result

    return f


# ---------------------------------------------------------------------------
# Load all n curves at module level
# ---------------------------------------------------------------------------
_n_values = np.array(sorted(n_files.keys()), dtype=float)
_n_interps = {}

for n, fname in n_files.items():
    dm_arr, v1_arr = _load_curve(fname)
    _n_interps[n] = _make_loglog_interp(dm_arr, v1_arr)


# ---------------------------------------------------------------------------
# Load boundary curves
# ---------------------------------------------------------------------------
_dm_low,  _v1_low  = _load_curve(BOUNDARY_LOW)
_dm_high, _v1_high = _load_curve(BOUNDARY_HIGH)

_interp_low  = _make_loglog_interp(_dm_low,  _v1_low)
_interp_high = _make_loglog_interp(_dm_high, _v1_high)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_v1(dm, n):
    """
    Return the rated viscosity v1 [mm²/s] for a given bearing mean diameter
    dm [mm] and rotational speed n [rpm].

    Interpolates in log-log space across digitised n-curves.

    Parameters
    ----------
    dm : float — bearing mean diameter, dm = 0.5*(d+D) [mm], range 10–2000
    n  : float — rotational speed [rpm], range 2–100 000

    Returns
    -------
    v1 : float [mm²/s]
    """
    dm = float(dm)
    n  = float(n)

    # v1 at each reference n curve for this dm
    v1_at_n = np.array([_n_interps[nv](np.atleast_1d(dm))[0] for nv in _n_values])

    # interpolate across n in log-log space
    ln  = np.log10(_n_values)
    lv  = np.log10(v1_at_n)
    f_n = PchipInterpolator(ln, lv)

    ln_query = np.log10(n)
    # extrapolation guard (linear beyond range)
    if ln_query < ln[0]:
        slope = (lv[1] - lv[0]) / (ln[1] - ln[0])
        lv1 = lv[0] + slope * (ln_query - ln[0])
    elif ln_query > ln[-1]:
        slope = (lv[-1] - lv[-2]) / (ln[-1] - ln[-2])
        lv1 = lv[-1] + slope * (ln_query - ln[-1])
    else:
        lv1 = float(f_n(ln_query))

    return float(10 ** lv1)


def get_zone(dm, v1):
    """
    Return the operating zone for a given (dm, v1) point.

    Returns
    -------
    'low'    — Low nd_m area
    'normal' — Normal operating area
    'high'   — High nd_m area
    """
    v1_low  = float(_interp_low(np.atleast_1d(float(dm)))[0])
    v1_high = float(_interp_high(np.atleast_1d(float(dm)))[0])

    if v1 > v1_low:
        return "low"
    elif v1 < v1_high:
        return "high"
    else:
        return "normal"
    


    
def get_n(dm, v1):
    """
    Return the rotational speed n [rpm] for a given (dm, v1) pair.
    Inverse of get_v1 — interpolates in log-log space across n curves.

    Parameters
    ----------
    dm : float — bearing mean diameter [mm], range 10–2000
    v1 : float — rated viscosity [mm²/s]

    Returns
    -------
    n : float [rpm]
    """
    dm = float(dm)
    v1 = float(v1)

    # v1 at each reference n curve for this dm
    v1_at_n = np.array([_n_interps[nv](np.atleast_1d(dm))[0] for nv in _n_values])

    # interpolate inversely — v1 decreases as n increases, so flip
    ln  = np.log10(_n_values)
    lv  = np.log10(v1_at_n)

    # lv is monotonically decreasing with ln — invert by swapping axes
    f_inv = PchipInterpolator(lv[::-1], ln[::-1])

    lv_query = np.log10(v1)
    return float(10 ** f_inv(lv_query))    


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    dm_plot = np.logspace(np.log10(10), np.log10(2000), 400)

    fig, ax = plt.subplots(figsize=(10, 9))

    # --- areas ---
    dm_low_plot  = np.logspace(np.log10(_dm_low[0]),  np.log10(_dm_low[-1]),  300)
    dm_high_plot = np.logspace(np.log10(_dm_high[0]), np.log10(_dm_high[-1]), 300)

    v1_low_plot  = _interp_low(dm_low_plot)
    v1_high_plot = _interp_high(dm_high_plot)

    # Low nd_m area — above the low boundary
    ax.fill_between(dm_low_plot, v1_low_plot, 1000,
                    color="#c8d9a0", alpha=0.5, label="Low $nd_m$ area")

    # High nd_m area — below the high boundary
    ax.fill_between(dm_high_plot, 0.1, v1_high_plot,
                    color="#f5c6a0", alpha=0.5, label="High $nd_m$ area")

    # --- n curves ---
    n_labels = [2, 5, 10, 20, 50, 100, 200, 500, 1000, 1500, 2000,
                3000, 5000, 10000, 20000, 50000, 100000]

    for n in n_labels:
        v1_plot = _n_interps[n](dm_plot)
        ax.plot(dm_plot, v1_plot, color="#1a5fa8", linewidth=0.9)
        # label at right edge
        ax.text(dm_plot[-1] * 1.01, v1_plot[-1], str(n),
                fontsize=6.5, va="center", color="#1a5fa8")

    # --- formatting ---
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(10, 2000)
    ax.set_ylim(4, 1000)
    ax.set_xlabel(r"$d_m = 0.5\,(d + D)$ [mm]", fontsize=11)
    ax.set_ylabel(r"Rated viscosity $\nu_1$ [mm²/s]", fontsize=11)
    ax.set_title("Estimation of Rated Viscosity — SKF General Catalogue", fontsize=12)
    ax.grid(True, which="both", linestyle="--", linewidth=0.4, alpha=0.6)
    ax.text(0.97, 0.97, r"$n$ [r/min]", transform=ax.transAxes,
            fontsize=9, ha="right", va="top", color="#1a5fa8")
    ax.legend(loc="lower left", fontsize=9)

    plt.tight_layout()
    plt.show()

    # --- quick test ---
    print(f"get_v1(dm=100, n=925.5) = {get_v1(100, 925.5):.2f} mm²/s")
    print(f"get_zone(dm=100, v1=12) = {get_zone(100, 12)}")

    n_result = get_n(dm=100, v1=12)
    print(f"get_n(dm=100, v1=12) = {n_result:.1f} rpm")