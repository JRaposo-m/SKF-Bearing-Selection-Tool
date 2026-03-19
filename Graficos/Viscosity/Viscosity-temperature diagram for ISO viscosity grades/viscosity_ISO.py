import os
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VG_FILES = {
    10:   "VG 10.csv",
    15:   "VG 15.csv",
    22:   "VG 22.csv",
    32:   "VG 32.csv",
    46:   "VG 46.csv",
    68:   "VG 68.csv",
    100:  "VG 100.csv",
    150:  "VG 150.csv",
    220:  "VG 220.csv",
    320:  "VG 320.csv",
    460:  "VG 460.csv",
    680:  "VG 680.csv",
    1000: "VG 1000.csv",
    1500: "VG 1500.csv",
}


def _read_vg_csv(filepath):
    """Lê um CSV de viscosidade, lida com separadores e valores corrompidos.
    Devolve (x, y) arrays numpy com os pontos originais do CSV, ordenados por x."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
    sep = ";" if ";" in first_line else ","

    df = pd.read_csv(filepath, sep=sep, header=0, skipinitialspace=True)
    df.columns = df.columns.str.strip()

    x = pd.to_numeric(df.iloc[:, 0].astype(str).str.strip(), errors="coerce")
    y = pd.to_numeric(df.iloc[:, 1].astype(str).str.strip(), errors="coerce")

    mask = x.notna() & y.notna() & (y > 0)
    x = x[mask].values
    y = y[mask].values

    order = np.argsort(x)
    return x[order], y[order]


# Carrega todos os CSVs — guarda os pontos raw e um interpolador só para get_viscosity
_raw = {}      # {vg: (x_array, y_array)}  — usado no plot, pontos originais
_interps = {}  # {vg: callable}            — usado em get_viscosity

for vg, fname in VG_FILES.items():
    filepath = os.path.join(BASE_DIR, fname)
    if not os.path.exists(filepath):
        print(f"[viscosity] Ficheiro não encontrado: {filepath}")
        continue
    try:
        x, y = _read_vg_csv(filepath)
        _raw[vg] = (x, y)
        _interps[vg] = PchipInterpolator(x, y)
    except Exception as e:
        print(f"[viscosity] Erro ao ler {fname}: {e}")


def get_viscosity(vg, temperature):
    """
    Retorna a viscosidade cinemática [mm²/s] para um dado grau ISO VG e temperatura [°C].

    Parâmetros
    ----------
    vg : int ou float
        Grau de viscosidade ISO VG (ex: 46, 100, 320).
        Tem de corresponder a um dos VGs disponíveis nos CSVs.
    temperature : float
        Temperatura de operação em °C.

    Retorna
    -------
    float : viscosidade em mm²/s
    """
    vg = int(vg)
    temperature = float(temperature)

    if vg not in _interps:
        available = sorted(_interps.keys())
        raise ValueError(f"VG {vg} não disponível. VGs carregados: {available}")

    return float(_interps[vg](temperature))


def plot_viscosity():
    """Plota o diagrama viscosidade-temperatura usando os pontos originais dos CSVs."""
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    fig, ax = plt.subplots(figsize=(10, 8))

    for vg in sorted(_raw.keys()):
        x, y = _raw[vg]
        ax.plot(x, y, linewidth=1.2, label=f"VG {vg}")
        ax.annotate(
            str(vg),
            xy=(x[-1], y[-1]),
            xytext=(3, 0),
            textcoords="offset points",
            fontsize=7,
            va="center",
        )

    ax.set_yscale("log")
    ax.set_xlabel("Operating temperature [°C]", fontsize=11)
    ax.set_ylabel("Viscosity [mm²/s]", fontsize=11)
    ax.set_title("Viscosity-temperature diagram for ISO viscosity grades", fontsize=12)
    ax.set_xlim(20, 120)
    ax.set_ylim(5, 2000)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", " ")))
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())
    ax.set_xticks(range(20, 130, 10))
    ax.grid(True, which="both", linestyle="--", linewidth=0.4, alpha=0.6)
    ax.legend(loc="upper right", fontsize=7, ncol=2, framealpha=0.7)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    for vg in [46, 100, 320]:
        for temp in [40, 70, 100]:
            v = get_viscosity(vg, temp)
            print(f"  VG {vg:4d} @ {temp}°C  →  {v:.2f} mm²/s")

    plot_viscosity()