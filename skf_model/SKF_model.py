
import numpy as np
import matplotlib.pyplot as plt

class SKFFrictionModel:
    def __init__(self, d, D, B, Fr, Fa, n, nu):
        
        self.d = d
        self.D = D
        self.dm = 0.5 * (d + D)
        self.Fr = Fr
        self.Fa = Fa
        self.n = n
        self.nu = nu
        self.B = B

        self.H = 1 * self.dm

       
        self.R1 = 1.12e-7
        self.S1 = 0.17
        self.S2 = 0.0015

        self.Kz = 5.1
        self.Krs = 3 * 10**(-8)
        self.KL = 0.65

    def rolling_friction(self):
        # M_rr = f_ish * f_rs * G_rr * (nu * n)^0.6
        f_ish = 1 / (1 + 1.84e-9 * (self.n * self.dm)**1.28 * self.nu**0.64)

        f_rs = 1 / (2.718**(self.Krs*self.nu*self.n*(self.d + self.D)*np.sqrt(self.Kz/(2 * (self.D - self.d)))))

        G_rr = self.R1 * (self.dm**2.41) * (self.Fr**0.31)
        return f_ish * f_rs * G_rr * (self.nu * self.n)**0.6

    def sliding_friction(self):
        # M_sl = G_sl * mu_sl
        G_sl = self.S1 * (self.dm**0.9)*self.Fa + self.S2 * self.dm * self.Fr
        fi_bl = 1 / (2.718**(2.6*10**(-8) * (self.n*self.nu)**1.4 * self.dm)) 
        mu_EHL = 0.02
        mu_bl = 0.12 # n != 0
        mu_sl = fi_bl * mu_bl + (1 - fi_bl) * mu_EHL
        return G_sl * mu_sl

    def drag_friction(self):
        
        fA = 0.05 * (self.Kz * (self.D + self.d)) / (self.D - self.d)
        t = 2 * np.arccos((0.6 * self.dm - self.H) / (0.6 * self.dm))
        Rs = 0.36 * self.dm**2 * (t - np.sin(t)) * fA
        
        if (t >= 0 and t <= 3.1416):
            ft = np.sin(0.5 * t)
        else:
            ft = 1
        l_D = 5 * self.KL * self.B / self.dm
        Cw = (2.789 * 10**-10) * l_D**3 - (2.786 * 10 **-4) * l_D**2 + 0.0195 * l_D + 0.6439
        K_roll = ((self.KL * self.Kz * (self.d + self.D)) / (self.D - self.d)) * 10 **-12
        V_M = 0.0012

       
        M_drag = 4 * V_M * K_roll * Cw * self.B * self.dm**4 * self.n**2 + \
                 (1.093*10**-7) * self.n**2 * self.dm**3 * (((self.n*(self.dm**2) * ft)/self.nu)**-1.379) * Rs
        return M_drag

    def total_friction(self):
        return self.rolling_friction() + self.sliding_friction() + self.drag_friction()


def plot_M_variation(model: SKFFrictionModel,
                    param_name: str,
                    values: np.ndarray,
                    show_components: bool = True,
                    figsize=(8, 5)):
    """
    Plota o momento de fricção (M) variando um parâmetro ao longo de um vetor.
    - model: instância do teu SKFFrictionModel (com fórmulas/constantes tal como estão)
    - param_name: nome do atributo a variar ('n', 'Fr', 'Fa', 'nu', 'H', etc.)
    - values: vetor de valores para esse parâmetro
    - show_components: se True, plota M_rr, M_sl, M_drag além de M_total
    """
    # Verificação básica
    if not hasattr(model, param_name):
        raise AttributeError(f"O modelo não tem o atributo '{param_name}' para variar.")

    M_total_list = []
    M_rr_list = []
    M_sl_list = []
    M_drag_list = []

    # Guardar valor original para repor no fim
    original_value = getattr(model, param_name)

    for v in values:
        setattr(model, param_name, v)
        M_rr = model.rolling_friction()
        M_sl = model.sliding_friction()
        M_drag = model.drag_friction()
        M_total = M_rr + M_sl + M_drag

        M_total_list.append(M_total)
        M_rr_list.append(M_rr)
        M_sl_list.append(M_sl)
        M_drag_list.append(M_drag)

    # Repor valor original
    setattr(model, param_name, original_value)

    
    # Plot
    plt.figure(figsize=figsize)
    plt.plot(values, M_total_list, label="Total friction moment", color="black", linewidth=2)
    if show_components:
        plt.plot(values, M_rr_list, label="Rolling friction (M_rr)", linestyle="--")
        plt.plot(values, M_sl_list, label="Sliding friction (M_sl)", linestyle="--")
        plt.plot(values, M_drag_list, label="Drag friction (M_drag)", linestyle="--")
    plt.xlabel(param_label(param_name))
    plt.ylabel("Friction moment M (N·mm)")
    plt.title(f"Variation of M vs {param_label(param_name)}")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def param_label(name: str) -> str:
    """Axis labels in English."""
    labels = {
        "n": "Speed (rpm)",
        "Fr": "Radial load Fr (N)",
        "Fa": "Axial load Fa (N)",
        "nu": "Lubricant viscosity ν (mm²/s)",
        "H": "Oil level H (mm)",
        "B": "Width B (mm)",
        "dm": "Mean diameter dm (mm)",
    }
    return labels.get(name, name)



    
# Criar modelo com parâmetros base (ajusta conforme o teu caso)
model = SKFFrictionModel(d=40, D=68, B=15, Fr=4450, Fa=0, n=50, nu=70)

# i) M vs velocidade (n)
n_vals = np.linspace(10, 150, 12)
plot_M_variation(model, param_name="n", values=n_vals, show_components=True)

# ii) M vs carga radial (Fr)
Fr_vals = np.linspace(2000, 5000, 12)
plot_M_variation(model, param_name="Fr", values=Fr_vals, show_components=True)

# iii) M vs viscosidade (nu)
nu_vals = np.linspace(10, 200, 12)
plot_M_variation(model, param_name="nu", values=nu_vals, show_components=True)


def sliding_mu(model):
    # usa o método sliding_friction para obter G_sl e recomputa mu_sl como no teu método
    G_sl = model.S1 * (model.dm**0.9)*model.Fa + model.S2 * model.dm * model.Fr
    fi_bl = 1 / (2.718**(2.6e-8 * (model.n * model.nu)**1.4 * model.dm))
    mu_EHL = 0.02
    mu_bl = 0.12
    mu_sl = fi_bl * mu_bl + (1 - fi_bl) * mu_EHL
    return mu_sl

def stribeck_param(model):
    # S = U * nu * F^{-1/2}, com U = 2*pi*n*R e R ~ dm/2
    R = model.dm / 2.0
    U = 2*np.pi * (model.n/60.0) * R  # [m/s] se dm estiver em mm ajusta unidades
    # ATENÇÃO ÀS UNIDADES: se dm está em mm, converte: R_mm -> R_m
    R_m = (model.dm / 2.0) / 1000.0
    U = 2*np.pi * (model.n/60.0) * R_m  # m/s
    S = U * (model.nu * 1e-6) * (model.Fr ** -0.5)  # nu [mm^2/s] -> [m^2/s]
    return S

# variação de n mantendo Fr e nu fixos (exemplo)
n_vals = np.linspace(20, 150, 30)
mu_vals = []
S_vals = []
Fr_fixed = 4450
nu_fixed = 70

for n in n_vals:
    model.n = n
    model.Fr = Fr_fixed
    model.nu = nu_fixed
    mu_vals.append(sliding_mu(model))
    S_vals.append(stribeck_param(model))

plt.figure(figsize=(7,5))
plt.plot(S_vals, mu_vals, 'o-', color='tab:blue', label='Model (SKF μ_sl)')
plt.xscale('log')
plt.xlabel(r'Stribeck parameter $S = U\,\nu\,F^{-1/2}$')
plt.ylabel(r'Sliding friction coefficient $\mu_{\mathrm{sl}}$')
plt.title('Stribeck-like curve from SKF sliding friction model')
plt.grid(True, which='both', ls='--', alpha=0.4)
plt.legend()
plt.tight_layout()
plt.show()
