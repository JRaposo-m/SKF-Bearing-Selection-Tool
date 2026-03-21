import os
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

k_files = {
    0.1:  None,
    0.15: "k_0.15.csv",
    0.2:  "k_0.2.csv",
    0.3:  "k_0.3.csv",
    0.4:  "k_0.4.csv",
    0.5:  "k_0.5.csv",
    0.6:  "k_0.6.csv",
    0.8:  "k_0.8.csv",
    1.0:  "k_1.csv",
    1.5:  "k_1.5.csv",
    2.0:  "k_2.csv",
    3.0:  "k_3.csv",
    4.0:  "k_4.csv",
}

def make_interp(df):
    x = df["x"].values
    y = df["y"].values
    pchip = PchipInterpolator(x, y)
    slope_left  = (y[1]  - y[0])  / (x[1]  - x[0])
    slope_right = (y[-1] - y[-2]) / (x[-1] - x[-2])

    def f(x_new):
        x_new = np.asarray(x_new, dtype=float)
        result = np.zeros_like(x_new)
        left  = x_new < x[0]
        right = x_new > x[-1]
        mid   = ~left & ~right
        result[mid]   = pchip(x_new[mid])
        result[left]  = y[0]  + slope_left  * (x_new[left]  - x[0])
        result[right] = y[-1] + slope_right * (x_new[right] - x[-1])
        return result

    return f

_k_values = np.array(sorted(k_files.keys()))
_interps = {}
for k, fname in k_files.items():
    if fname is None:
        _interps[k] = lambda x_new, _k=k: np.full_like(np.asarray(x_new, dtype=float), 0.1)
    else:
        df = pd.read_csv(os.path.join(BASE_DIR, fname), sep=",", skipinitialspace=True)
        df.columns = ["x", "y"]
        _interps[k] = make_interp(df)

def get_a_skf(x, k):
    """Retorna a_SKF para um dado x e k (interpolação log-log em ambos os eixos)."""
    y_at_k = np.array([_interps[kv](np.atleast_1d(float(x)))[0] for kv in _k_values])
    lk = np.log10(_k_values)
    ly = np.log10(y_at_k)
    f_k = PchipInterpolator(lk, ly)
    a = float(10 ** f_k(np.log10(k)))
    return min(a, 50.0)


if __name__ == "__main__":
    # teste
    a = get_a_skf(x=0.5, k=0.25)
    print(f"a_SKF(x=0.5, k=0.25) = {a:.4f}")

    import matplotlib.pyplot as plt

    x_plot = np.logspace(np.log10(0.005), np.log10(5), 500)

    plt.figure(figsize=(10, 8))
    for k in _k_values:
        y = [get_a_skf(xi, k) for xi in x_plot]
        plt.plot(x_plot, y, label=f"k={k}")

    plt.xscale("log")
    plt.yscale("log")
    plt.xlim(right=5)
    plt.ylim(top=50)
    plt.xlabel("$n_c \\cdot P_u / P$")
    plt.ylabel("$a_{SKF}$")
    plt.title("SKF Life Modification Factor $a_{SKF}$")
    plt.legend(title="k", loc="upper left")
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.show()

