"""
Generador y Ejecutor del Cuaderno Interactivo para Google Colab:
  - Simulacion_Colas_Banco_Colab.ipynb

Cuaderno 100% autocontenido (no requiere archivos externos), sincronizado exactamente
con los parámetros de las Tablas 1 y 2, la semilla base (seed = 42), intervalos t de Student,
cálculo iterativo del número de réplicas n*, enrutamiento JSQ no clarividente y resultados
completos de 'bank_queue', pre-ejecutado mediante jupyter_client para renderizado inmediato.
"""

import json
import queue
import sys
import jupyter_client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def md_cell(text: str) -> dict:
    lines = text.splitlines(keepends=True)
    return {"cell_type": "markdown", "metadata": {}, "source": lines}


def code_cell(code: str) -> dict:
    lines = code.strip("\n").splitlines(keepends=True)
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines,
    }


cells = [
    md_cell(
        """# Simulación de Colas Independientes M/M/1 — Solución del Problema Bancario (Banco de Colombia)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-Alberto-Palacio/Simulacion-Colas-Banco-MM1/blob/main/Simulacion_Colas_Banco_Colab.ipynb)

---
### Institución Universitaria Digital de Antioquia (IU Digital)
* **Facultad:** Facultad de Ingeniería — Ingeniería de Software y Datos
* **Asignatura:** Simulación — `PREICA2602B020045` (Módulo 2 — Actividad Didáctica 2-M3)
* **Docente:** Dr. Julián Andrés Loaiza López
* **Grupo:** 25 · **Sede:** Medellín, Antioquia · **Fecha:** Noviembre de 2026

#### Integrantes del Equipo:
1. **Adriana Andrea Agudelo Agudelo**
2. **Camilo Alberto Palacios Turriago**
3. **Juan Daniel Pulgarin García**
4. **Ruben Dario Jaramillo Cervantes**

---"""
    ),
    md_cell(
        r"""## 1. Planteamiento del Problema y Formulación Matemática M/M/1 y M/G/1

El **Banco de Colombia** busca evaluar el desempeño operativo de sus **3 cajas de atención presencial** (sin cajeros electrónicos inicialmente) durante una jornada diaria de **8 horas ($480\text{ minutos}$)** para decidir si debe especializar cajeros (**1 retiro + 2 pagos**, **2 retiros + 1 pago**), mantener **3 cajas mixtas**, o **incorporar un 4.º cajero físico o electrónico**.

Cada cajero opera como una cola independiente **$M/M/1$** bajo disciplina **FCFS** (*First-Come, First-Served*), donde:
* El **70 %** de los usuarios realiza **Retiros** y el **30 %** realiza **Consignaciones o pagos**.
* Las llegadas y tiempos de servicio siguen distribuciones **Exponenciales** parametrizadas por perfil de velocidad (**Rápido, Normal, Lento, Muy lento**) según las Tablas 1 y 2.

Para cada servidor independiente con tasa de llegada $\lambda_c$ y tasa de servicio $\mu_c$, la estabilidad exige $\rho_c = \lambda_c / \mu_c < 1$, aplicándose la **Ley de Little** y la extensión **Pollaczek–Khinchine M/G/1** (debido a la hiperexponencialidad de la mezcla):
$$L_q = \frac{\rho^2}{1 - \rho}, \qquad W_q^{\text{M/M/1}} = \frac{L_q}{\lambda_c} = \frac{\rho}{\mu_c(1 - \rho)}, \qquad W = W_q + \frac{1}{\mu_c}, \qquad W_q^{\text{M/G/1}} = \frac{\lambda_c\,\mathbb{E}[S^2]}{2(1 - \rho)}$$"""
    ),
    code_cell(
        """from collections import deque
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["figure.figsize"] = (13.2, 5.2)
plt.rcParams["font.size"] = 10
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.linestyle"] = ":"
plt.rcParams["grid.alpha"] = 0.6

BANK_MINUTES = 480.0
ACTION_PROBS = {"Retiro": 0.70, "Pago": 0.30}
USER_TYPES = ["Rápido", "Normal", "Lento", "Muy lento"]

SERVICE_MEANS = {
    "Retiro": {"Rápido": 1.0, "Normal": 2.0, "Lento": 3.0, "Muy lento": 4.0},
    "Pago":   {"Rápido": 3.0, "Normal": 3.0, "Lento": 5.0, "Muy lento": 7.0},
}
ARRIVAL_MEANS = {
    "Retiro": {"Rápido": 1.0, "Normal": 2.0, "Lento": 3.0, "Muy lento": 3.0},
    "Pago":   {"Rápido": 1.0, "Normal": 2.0, "Lento": 3.0, "Muy lento": 4.0},
}
USER_TYPE_PROBS = {
    "Retiro": {"Rápido": 0.23, "Normal": 0.40, "Lento": 0.17, "Muy lento": 0.20},
    "Pago":   {"Rápido": 0.10, "Normal": 0.20, "Lento": 0.30, "Muy lento": 0.40},
}

SCENARIOS = {
    "E1_3_Mixtas": ("3 Mixtas", [("Cajero 1", "Mixto"), ("Cajero 2", "Mixto"), ("Cajero 3", "Mixto")]),
    "E2_1R_2P":    ("1R + 2P",  [("Cajero 1 (Retiro)", "Retiro"), ("Cajero 2 (Pago)", "Pago"), ("Cajero 3 (Pago)", "Pago")]),
    "E3_2R_1P":    ("2R + 1P",  [("Cajero 1 (Retiro)", "Retiro"), ("Cajero 2 (Retiro)", "Retiro"), ("Cajero 3 (Pago)", "Pago")]),
    "E4a_4_Mixtas":("4 Mixtas", [("Cajero 1", "Mixto"), ("Cajero 2", "Mixto"), ("Cajero 3", "Mixto"), ("Cajero 4", "Mixto")]),
    "E4b_2R_2P":   ("2R + 2P",  [("Cajero 1 (Retiro)", "Retiro"), ("Cajero 2 (Retiro)", "Retiro"), ("Cajero 3 (Pago)", "Pago"), ("Cajero 4 (Pago)", "Pago")]),
}

def expected_service_moments(role: str):
    if role == "Mixto":
        e1 = sum(ACTION_PROBS[a] * sum(USER_TYPE_PROBS[a][u] * SERVICE_MEANS[a][u] for u in USER_TYPES) for a in ACTION_PROBS)
        e2 = sum(ACTION_PROBS[a] * sum(USER_TYPE_PROBS[a][u] * 2.0 * (SERVICE_MEANS[a][u] ** 2) for u in USER_TYPES) for a in ACTION_PROBS)
        return e1, e2
    e1 = sum(USER_TYPE_PROBS[role][u] * SERVICE_MEANS[role][u] for u in USER_TYPES)
    e2 = sum(USER_TYPE_PROBS[role][u] * 2.0 * (SERVICE_MEANS[role][u] ** 2) for u in USER_TYPES)
    return e1, e2

def theoretical_scenario_wq(cajeros_cfg):
    e_ia = sum(ACTION_PROBS[a] * sum(USER_TYPE_PROBS[a][u] * ARRIVAL_MEANS[a][u] for u in USER_TYPES) for a in ACTION_PROBS)
    lam_tot = 1.0 / e_ia
    counts = {}
    for _, r in cajeros_cfg:
        counts[r] = counts.get(r, 0) + 1
    wq_mm1, wq_mg1, total_l = 0.0, 0.0, 0.0
    for _, role in cajeros_cfg:
        lam_c = (lam_tot if role == "Mixto" else lam_tot * ACTION_PROBS[role]) / counts[role]
        es, es2 = expected_service_moments(role)
        mu_c = 1.0 / es
        rho = lam_c / mu_c
        w_frac = lam_c / lam_tot
        wq_mm1 += w_frac * (rho / (mu_c * (1.0 - rho)))
        wq_mg1 += w_frac * ((lam_c * es2) / (2.0 * (1.0 - rho)))
        total_l += lam_c
    return wq_mm1, wq_mg1

e_ia = sum(ACTION_PROBS[a] * sum(USER_TYPE_PROBS[a][u] * ARRIVAL_MEANS[a][u] for u in USER_TYPES) for a in ACTION_PROBS)
lam_total = 1.0 / e_ia
print(f"E[IA] = {e_ia:.3f} min | λ_global = {lam_total:.4f} cli/min (~{lam_total*BANK_MINUTES:.1f} usuarios/8h)")
print(f"E[S_Retiro] = {expected_service_moments('Retiro')[0]:.2f} min | E[S_Pago] = {expected_service_moments('Pago')[0]:.2f} min | E[S_Mix] = {expected_service_moments('Mixto')[0]:.3f} min")"""
    ),
    md_cell(
        """## 2. Motor DES (M/M/1 Independiente, JSQ No Clarividente e IC95% exacto *t* de Student)

Implementamos:
* **Generación reproducible** (`PCG64`, semilla base `42`, jornadas de `480 min`) con **Números Aleatorios Comunes (CRN)** entre escenarios.
* **Descomposición equiprobable de Poisson (`1/k`)** (`random_mm1`) para preservar cajeros independientes M/M/1, frente a **Join-the-Shortest-Queue (`shortest_queue`) no clarividente** (el usuario observa únicamente el número de personas presentes en fila o servicio sin conocer tiempos futuros de atención).
* **Cuantiles exactos de la distribución *t* de Student** (sin aproximaciones asintóticas de `1.96`) para intervalos de confianza al 95 % y cálculo iterativo del tamaño muestral requerido ($n^*$)."""
    ),
    code_cell(
        """def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) >= 1e-300 else 1e-300)
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) >= 1e-300 else 1e-300)
            c = 1.0 + aa / (c if abs(c) >= 1e-300 else 1e-300)
            c = c if abs(c) >= 1e-300 else 1e-300
            h *= d * c
            if m > 1 and abs(d * c - 1.0) < 3e-14:
                return h
    return h

def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x))
    return (bt * _betacf(a, b, x) / a) if x < (a + 1.0) / (a + b + 2.0) else (1.0 - bt * _betacf(b, a, 1.0 - x) / b)

def t_crit_95(df: int) -> float:
    target, lo, hi = 0.05, 0.0, 20.0
    while _betainc(0.5 * df, 0.5, df / (df + hi * hi)) > target:
        hi *= 2.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if _betainc(0.5 * df, 0.5, df / (df + mid * mid)) > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def ci95_student_t(values):
    arr = np.asarray([float(v) for v in values if not np.isnan(v)], dtype=float)
    n = len(arr)
    m = float(np.mean(arr))
    if n <= 1: return m, 0.0, m, m
    sd = float(np.std(arr, ddof=1))
    half = t_crit_95(n - 1) * sd / np.sqrt(n)
    return m, sd, m - half, m + half

def generate_day_arrivals(seed: int):
    rng = np.random.default_rng(seed)
    actions = list(ACTION_PROBS.keys())
    act_p = [ACTION_PROBS[a] for a in actions]
    utype_p = {a: [USER_TYPE_PROBS[a][u] for u in USER_TYPES] for a in actions}
    arrivals, t = [], 0.0
    while True:
        act = str(rng.choice(actions, p=act_p))
        ut = str(rng.choice(USER_TYPES, p=utype_p[act]))
        t += float(rng.exponential(ARRIVAL_MEANS[act][ut]))
        if t > BANK_MINUTES:
            break
        srv = float(rng.exponential(SERVICE_MEANS[act][ut]))
        arrivals.append((t, act, ut, srv))
    return arrivals

def simulate_scenario_replica(cajeros_cfg, arrivals, routing_seed: int, routing_mode: str = "random_mm1"):
    rng = np.random.default_rng(routing_seed)
    k = len(cajeros_cfg)
    queues = [[] for _ in range(k)]
    dep_q = [deque() for _ in range(k)]
    free_t = [0.0 for _ in range(k)]
    elig_map = {a: [i for i, (_, r) in enumerate(cajeros_cfg) if r == "Mixto" or r == a] for a in ACTION_PROBS}

    for t_arr, act, ut, srv in arrivals:
        elig = elig_map[act]
        if len(elig) == 1:
            idx = elig[0]
        elif routing_mode == "random_mm1":
            idx = elig[int(rng.integers(0, len(elig)))]
        elif routing_mode == "shortest_queue":
            for i in elig:
                while dep_q[i] and dep_q[i][0] <= t_arr:
                    dep_q[i].popleft()
            min_len = min(len(dep_q[i]) for i in elig)
            tied = [i for i in elig if len(dep_q[i]) == min_len]
            idx = tied[0] if len(tied) == 1 else tied[int(rng.integers(0, len(tied)))]
        else:
            raise ValueError(routing_mode)
        queues[idx].append((t_arr, act, ut, srv))
        end_t = max(t_arr, free_t[idx]) + srv
        free_t[idx] = end_t
        dep_q[idx].append(end_t)

    cashier_stats = {}
    all_w, all_s, all_sys = [], [], []
    w_by_act = {a: [] for a in ACTION_PROBS}
    w_by_typ = {u: [] for u in USER_TYPES}
    counts_u = {u: 0 for u in USER_TYPES}
    counts_in_turn = {u: 0 for u in USER_TYPES}
    completed_turn = 0

    for idx, (cname, role) in enumerate(cajeros_cfg):
        ft = 0.0
        ws, ss, syss = [], [], []
        cu = {u: 0 for u in USER_TYPES}
        for t_arr, act, ut, srv in queues[idx]:
            st = max(t_arr, ft)
            wt = st - t_arr
            ft = st + srv
            ws.append(wt); ss.append(srv); syss.append(wt + srv)
            all_w.append(wt); all_s.append(srv); all_sys.append(wt + srv)
            w_by_act[act].append(wt); w_by_typ[ut].append(wt)
            cu[ut] += 1; counts_u[ut] += 1
            if ft <= BANK_MINUTES:
                completed_turn += 1
                counts_in_turn[ut] += 1
        heff = max(BANK_MINUTES, ft)
        cashier_stats[cname] = {
            "rol": role, "usuarios": len(queues[idx]),
            "mean_s": float(np.mean(ss)) if ss else 0.0,
            "mean_wq": float(np.mean(ws)) if ws else 0.0,
            "mean_w": float(np.mean(syss)) if syss else 0.0,
            "rho": float(np.sum(ss) / heff),
            "prob_gt5": float(np.mean(np.asarray(ws) > 5.0) * 100.0) if ws else 0.0,
            "counts_u": cu,
        }
    return {
        "total_usuarios": len(arrivals), "atendidos_turno": completed_turn,
        "counts_u": counts_u, "counts_in_turn": counts_in_turn,
        "mean_wq": float(np.mean(all_w)), "mean_s": float(np.mean(all_s)), "mean_w": float(np.mean(all_sys)),
        "prob_gt5": float(np.mean(np.asarray(all_w) > 5.0) * 100.0),
        "wq_retiro": float(np.mean(w_by_act["Retiro"])), "wq_pago": float(np.mean(w_by_act["Pago"])),
        "wq_rapido": float(np.mean(w_by_typ["Rápido"])), "wq_normal": float(np.mean(w_by_typ["Normal"])),
        "wq_lento": float(np.mean(w_by_typ["Lento"])), "wq_muy_lento": float(np.mean(w_by_typ["Muy lento"])),
        "peor_wq": max(v["mean_wq"] for v in cashier_stats.values()),
        "peor_prob_gt5": max(v["prob_gt5"] for v in cashier_stats.values()),
        "rho_med": float(np.mean([v["rho"] for v in cashier_stats.values()])),
        "rho_max": float(np.max([v["rho"] for v in cashier_stats.values()])),
        "cashiers": cashier_stats,
    }

def run_experiment(num_replicas: int = 10, base_seed: int = 42, routing_mode: str = "random_mm1"):
    shared_arr = {r: generate_day_arrivals(base_seed + r) for r in range(1, num_replicas + 1)}
    rep_rows, caj_rows, prof_rows = [], [], []
    for s_idx, (skey, (short_name, cfg)) in enumerate(SCENARIOS.items()):
        for r in range(1, num_replicas + 1):
            arr = shared_arr[r]
            res = simulate_scenario_replica(cfg, arr, base_seed * 100 + s_idx * 1000 + r, routing_mode)
            rep_rows.append({
                "escenario": skey, "nombre": short_name, "replica": r,
                "total": res["total_usuarios"], "en_turno": res["atendidos_turno"],
                "Rápido": res["counts_u"]["Rápido"], "Normal": res["counts_u"]["Normal"],
                "Lento": res["counts_u"]["Lento"], "Muy lento": res["counts_u"]["Muy lento"],
                "Rápido_turno": res["counts_in_turn"]["Rápido"], "Normal_turno": res["counts_in_turn"]["Normal"],
                "Lento_turno": res["counts_in_turn"]["Lento"], "Muy lento_turno": res["counts_in_turn"]["Muy lento"],
                "Wq": res["mean_wq"], "Wq_Retiro": res["wq_retiro"], "Wq_Pago": res["wq_pago"],
                "Wq_Rápido": res["wq_rapido"], "Wq_Normal": res["wq_normal"],
                "Wq_Lento": res["wq_lento"], "Wq_Muy_lento": res["wq_muy_lento"],
                "S": res["mean_s"], "W": res["mean_w"], "Peor_Wq": res["peor_wq"],
                "Prob_gt5_Global": res["prob_gt5"], "Prob_gt5_Peor": res["peor_prob_gt5"],
                "rho_med": res["rho_med"], "rho_max": res["rho_max"],
            })
            for cname, cv in res["cashiers"].items():
                caj_rows.append({
                    "escenario": skey, "nombre": short_name, "replica": r,
                    "cajero": cname, "rol": cv["rol"], "usuarios": cv["usuarios"],
                    "S": cv["mean_s"], "Wq": cv["mean_wq"], "W": cv["mean_w"], "rho": cv["rho"],
                    "prob_gt5": cv["prob_gt5"],
                    "Rápido": cv["counts_u"]["Rápido"], "Normal": cv["counts_u"]["Normal"],
                    "Lento": cv["counts_u"]["Lento"], "Muy lento": cv["counts_u"]["Muy lento"],
                })
            if skey == "E1_3_Mixtas":
                c8 = {(a, u): 0 for a in ACTION_PROBS for u in USER_TYPES}
                for _, act, ut, _ in arr:
                    c8[(act, ut)] += 1
                for (a, u), cnt in c8.items():
                    prof_rows.append({"replica": r, "accion": a, "tipo": u, "cantidad": cnt, "prop": cnt / len(arr)})
    return pd.DataFrame(rep_rows), pd.DataFrame(caj_rows), pd.DataFrame(prof_rows)

df_rep10, df_caj10, df_prof10 = run_experiment(num_replicas=10, base_seed=42)
print("Ejecución de 10 réplicas oficiales completada (t_0.975,9 =", round(t_crit_95(9), 4), ").")"""
    ),
    md_cell(
        """## 3. Resultados de los Puntos 1, 2, 3 y Tamaño Muestral ($n^*$) sobre 10 Réplicas"""
    ),
    code_cell(
        """# Punto 1: Cajero con menor y mayor tiempo promedio de atención en el escenario base (3 Mixtas)
base_caj = df_caj10[df_caj10["escenario"] == "E1_3_Mixtas"].groupby("cajero", sort=False).agg(
    Usuarios_Prom=("usuarios", "mean"),
    Servicio_S_min=("S", "mean"),
    Espera_Wq_min=("Wq", "mean"),
    Atencion_W_min=("W", "mean"),
    Utilizacion_rho=("rho", "mean"),
).round(3)
print("=== PUNTO 1: DESEMPEÑO POR CAJERO (ESCENARIO BASE 3 MIXTAS, 10 RÉPLICAS) ===")
display(base_caj)

# Punto 2: Promedio en totalidad de cajeros, por cajero y los 8 subperfiles
base_rep = df_rep10[df_rep10["escenario"] == "E1_3_Mixtas"][["replica", "total", "en_turno", "Rápido", "Normal", "Lento", "Muy lento", "Wq", "W"]].copy()
print("\\n=== PUNTO 2: PROMEDIO DIARIO POR TIPO EN LA SUCURSAL Y POR CAJERO ===")
pts2_df = pd.DataFrame({
    "Sucursal_Total_Prom": base_rep[["Rápido", "Normal", "Lento", "Muy lento"]].mean(),
    "DE_10_Replicas": base_rep[["Rápido", "Normal", "Lento", "Muy lento"]].std(ddof=1),
    "Promedio_Por_Cajero": base_rep[["Rápido", "Normal", "Lento", "Muy lento"]].mean() / 3.0,
}).round(2)
display(pts2_df)

prof_summary = df_prof10.groupby(["accion", "tipo"], sort=False).agg(
    Total_10R=("cantidad", "sum"),
    Prom_Dia=("cantidad", "mean"),
    Prop_Emp_pct=("prop", lambda s: s.mean() * 100),
).round(2)
prof_summary["Prop_Teor_pct"] = [ACTION_PROBS[a] * USER_TYPE_PROBS[a][u] * 100 for a, u in prof_summary.index]
print("Desglose de los 8 perfiles (Acción × Tipo):")
display(prof_summary.round(2))

# Punto 3: Detalle por réplica, mínimos por tipo y modelo con menor atención en turno de 480 min
print("\\n=== PUNTO 3: TOTAL POR RÉPLICA, MÍNIMOS Y MODELO CON MENOR ATENCIÓN ===")
display(base_rep.round(2))
for u in USER_TYPES:
    idx_min = base_rep[u].idxmin()
    print(f"  - Mínimo en réplicas ({u:10s}): {int(base_rep.loc[idx_min, u])} usuarios en Réplica {int(base_rep.loc[idx_min, 'replica'])}")

turn_cols = ["en_turno", "Rápido_turno", "Normal_turno", "Lento_turno", "Muy lento_turno"]
turn_by_model = df_rep10.groupby("nombre", sort=False)[turn_cols].sum()
print("\\nTotal completados dentro del turno de 480 min por modelo (suma 10 réplicas):")
display(turn_by_model)

# Tamaño muestral requerido (n*) desde piloto n0 = 10
req_rows = []
for skey, (short_n, _) in SCENARIOS.items():
    sub = df_rep10[df_rep10["escenario"] == skey]
    wqm, wqsd, wql, wqu = ci95_student_t(sub["Wq"])
    wm, wsd, _, _ = ci95_student_t(sub["W"])
    um, usd, _, _ = ci95_student_t(sub["total"])
    def req_n(s, tol):
        n = max(2, math.ceil((t_crit_95(9) * s / tol) ** 2))
        for _ in range(30):
            nn = max(2, math.ceil((t_crit_95(n - 1) * s / tol) ** 2))
            if nn == n: break
            n = nn
        return n
    req_rows.append({
        "Escenario": short_n, "Semiamp_Wq_n10": round(0.5*(wqu - wql), 2), "DE_Wq": round(wqsd, 2),
        "n_req_Wq_050m": req_n(wqsd, 0.50), "n_req_W_5pct": req_n(wsd, 0.05 * wm), "n_req_Usr_5": req_n(usd, 5.0),
    })
print("\\n=== CÁLCULO ITERATIVO DE RÉPLICAS NECESARIAS (n*, 95% t DE STUDENT) ===")
display(pd.DataFrame(req_rows).set_index("Escenario"))"""
    ),
    md_cell(
        """## 4. Comparativa de Escenarios, Todos los Criterios de Espera y Validación Monte Carlo (100 Réplicas)"""
    ),
    code_cell(
        """df_rep100, df_caj100, _ = run_experiment(num_replicas=100, base_seed=42, routing_mode="random_mm1")
df_jsq100, _, _ = run_experiment(num_replicas=100, base_seed=42, routing_mode="shortest_queue")

sum_rows = []
for skey, (short_n, cfg) in SCENARIOS.items():
    sub = df_rep100[df_rep100["escenario"] == skey]
    sub_jsq = df_jsq100[df_jsq100["escenario"] == skey]
    wqm, wqsd, wql, wqu = ci95_student_t(sub["Wq"])
    wm, _, _, _ = ci95_student_t(sub["W"])
    mm1_wq, mg1_wq = theoretical_scenario_wq(cfg)
    sum_rows.append({
        "Escenario": short_n,
        "Wq_Global": wqm, "Wq_IC95_Inf": wql, "Wq_IC95_Sup": wqu,
        "Wq_Retiro": float(sub["Wq_Retiro"].mean()), "Wq_Pago": float(sub["Wq_Pago"].mean()),
        "Peor_Cajero_Wq": float(sub["Peor_Wq"].mean()),
        "Sistema_W": wm, "MM1_Teor": mm1_wq, "MG1_PK": mg1_wq,
        "Wq_JSQ": float(sub_jsq["Wq"].mean()),
        "Rho_Med_pct": float(sub["rho_med"].mean() * 100),
        "Rho_Max_pct": float(sub["rho_max"].mean() * 100),
    })
summary = pd.DataFrame(sum_rows).set_index("Escenario").round(2)
print("=== RESUMEN COMPARATIVO MULTI-CRITERIO (100 RÉPLICAS MONTE CARLO) ===")
display(summary)

crit_typ = df_rep100.groupby("nombre", sort=False)[["Wq_Rápido", "Wq_Normal", "Wq_Lento", "Wq_Muy_lento"]].mean().round(2)
print("\\nDesagregación adicional de Wq por velocidad de usuario (min):")
display(crit_typ)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.0))
x = np.arange(len(summary))
ax1.bar(x - 0.25, summary["Wq_Global"], width=0.25, color="#2563EB", label="Wq Global (Indep. M/M/1)")
ax1.bar(x,        summary["Peor_Cajero_Wq"], width=0.25, color="#DC2626", label="Peor Cajero (Cuello de Botella)")
ax1.bar(x + 0.25, summary["Wq_JSQ"], width=0.25, color="#F59E0B", label="JSQ Observable (Cola Más Corta)")
ax1.axhline(5.0, color="#0F766E", linestyle="--", label="Umbral 5.0 min")
ax1.set_xticks(x); ax1.set_xticklabels(summary.index, fontweight="bold")
ax1.set_ylabel("Tiempo de espera Wq (min)")
ax1.set_title("Espera Global vs. Cuello de Botella vs. JSQ (100 Réplicas)")
ax1.legend(fontsize=8.5)

c_min, c_max = float("inf"), float("-inf")
for skey, (short_n, _) in SCENARIOS.items():
    sub = df_rep100[df_rep100["escenario"] == skey].sort_values("replica")
    cm = sub["Wq"].expanding().mean()
    c_min, c_max = min(c_min, float(cm.min())), max(c_max, float(cm.max()))
    ax2.plot(sub["replica"], cm, linewidth=2.0, label=f"{short_n} ({cm.iloc[-1]:.2f}m)")
ax2.axvline(10, color="#475569", linestyle="--", label="10 réplicas piloto")
pad = max(0.35, (c_max - c_min) * 0.15)
ax2.set_ylim(max(0.0, c_min - pad), c_max + pad * 2.1)
ax2.set_xlabel("Réplicas Monte Carlo")
ax2.set_ylabel("Wq acumulado (min)")
ax2.set_title("Convergencia Estocástica de Wq (1 a 100 Réplicas)")
ax2.legend(fontsize=8.5)
plt.tight_layout()
plt.show()"""
    ),
    md_cell(
        """## 5. Diagnóstico AAA / Semana 7: Error Relativo ($ER\\%$), Estado Estable (*Warm-up*), Protocolo V&V y Valores Críticos

Complementamos el análisis con las herramientas de estimación estadística y validación del curso:
1. **Algoritmo de 8 pasos ($ER\\%$):** comparación del Error Relativo porcentual $ER = (ME / \\bar{Y}) \\times 100\\%$ entre $n_0=10$ y $n=100$ réplicas y cálculo de $n_{\\text{prof}} = \\lceil n_0 (ER_0 / 10\\%)^2 \\rceil$.
2. **Eliminación del período transitorio (*warm-up*):** promedio móvil ($\\text{ventana} = 15$) y mínima varianza local sobre la espera por orden de llegada en `E1: 3 Mixtas`.
3. **Validación *t* de Student frente a Pollaczek–Khinchine $M/G/1$ y matriz de valores críticos** ($P(W_q > 5\\text{ min})$ y regímenes de utilización $\\rho$)."""
    ),
    code_cell(
        """# 1. Error Relativo ER% (n0=10 vs n=100) y Matriz V&V + Valores Críticos
vv_rows = []
for skey, (short_n, cfg) in SCENARIOS.items():
    sub10 = df_rep10[df_rep10["escenario"] == skey]
    sub100 = df_rep100[df_rep100["escenario"] == skey]
    m10, _, l10, u10 = ci95_student_t(sub10["Wq"])
    er10 = (0.5 * (u10 - l10)) / m10 * 100.0
    n_prof = math.ceil(10 * (er10 / 10.0) ** 2)

    m100, sd100, l100, u100 = ci95_student_t(sub100["Wq"])
    er100 = (0.5 * (u100 - l100)) / m100 * 100.0
    wm100, _, wl100, wu100 = ci95_student_t(sub100["W"])
    er_w100 = (0.5 * (wu100 - wl100)) / wm100 * 100.0

    _, mg1_wq = theoretical_scenario_wq(cfg)
    se100 = sd100 / np.sqrt(100)
    caj100_s = df_caj100[df_caj100["escenario"] == skey]
    prob_gt5_peor = float(caj100_s.groupby("cajero")["prob_gt5"].mean().max())
    vv_rows.append({
        "Escenario": short_n,
        "ER10_Wq_pct": round(er10, 1),
        "n_prof_ER10": n_prof,
        "ER100_Wq_pct": round(er100, 1),
        "ER100_W_pct": round(er_w100, 2),
        "Wq_100": round(m100, 2),
        "MG1_Teor": round(mg1_wq, 2),
        "Prob_gt5m_Global_pct": round(float(sub100["Prob_gt5_Global"].mean()), 1),
        "Prob_gt5m_Peor_pct": round(prob_gt5_peor, 1),
        "Peor_Wq": round(float(sub100["Peor_Wq"].mean()), 2),
    })

df_vv_colab = pd.DataFrame(vv_rows).set_index("Escenario")
print("=== ALGORITMO DE ERROR RELATIVO ER% Y MATRIZ DE VALORES CRÍTICOS ===")
display(df_vv_colab)

# 2. Detección de calentamiento (warm-up) en 3 Cajas Mixtas (100 réplicas)
k_hor = 160
shared_100 = {r: generate_day_arrivals(42 + r) for r in range(1, 101)}
cfg_e1 = SCENARIOS["E1_3_Mixtas"][1]
mat_wq = np.full((100, k_hor), np.nan)
seq_all_reps = []
for r in range(1, 101):
    arr = shared_100[r]
    rng = np.random.default_rng(4200 + r)
    free_t = [0.0, 0.0, 0.0]
    waits_seq = []
    for t_arr, act, ut, srv in arr:
        c = int(rng.integers(0, 3))
        wt = max(0.0, free_t[c] - t_arr)
        free_t[c] = max(t_arr, free_t[c]) + srv
        waits_seq.append(wt)
    seq_all_reps.append(waits_seq)
    for k_i in range(min(k_hor, len(waits_seq))):
        mat_wq[r - 1, k_i] = waits_seq[k_i]

wq_cross = np.nanmean(mat_wq, axis=0)
win = 15
ma_vals = np.array([float(np.mean(wq_cross[max(0, i - win + 1):i + 1])) for i in range(k_hor)])
mov_full = [float(np.mean(wq_cross[i:i + win])) for i in range(k_hor - win + 1)]
cand_k = [i + win for i in range(max(0, 20 - win), min(len(mov_full) - win + 1, 66 - win + 1)) if 20 <= i + win <= 65]
cand_v = [float(np.var(mov_full[k - win:k])) for k in cand_k]
k_cut = cand_k[int(np.argmin(cand_v))]

wq_trans = float(np.mean([np.mean(s) for s in seq_all_reps]))
wq_est = float(np.mean([np.mean(s[k_cut - 1:]) for s in seq_all_reps if len(s) >= k_cut]))
se_est = float(np.std([np.mean(s[k_cut - 1:]) for s in seq_all_reps if len(s) >= k_cut], ddof=1) / np.sqrt(100))
mg1_e1 = theoretical_scenario_wq(cfg_e1)[1]
t_val = (wq_est - mg1_e1) / se_est
p_mg1 = _betainc(0.5 * 99, 0.5, 99.0 / (99.0 + t_val * t_val))
print(f"Warm-up 3 Mixtas: k* = {k_cut} clientes | Wq con transitorio = {wq_trans:.2f} m -> Estado estable = {wq_est:.2f} m (M/G/1 = {mg1_e1:.2f} m, p = {p_mg1:.3f})")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 4.9))
ks = np.arange(1, k_hor + 1)
ax1.axvspan(1, k_cut, color="#FEF3C7", alpha=0.55, label=f"Transitorio L(0)=0 (1–{k_cut})")
ax1.axvspan(k_cut, k_hor, color="#DCFCE7", alpha=0.35, label="Estado estable")
ax1.plot(ks, wq_cross, color="#94A3B8", linewidth=1.0, label="Wq transversal")
ax1.plot(ks, ma_vals, color="#0F172A", linewidth=2.1, label="Media móvil (w=15)")
ax1.axvline(k_cut, color="#DC2626", linestyle="--", linewidth=1.5, label=f"Corte k*={k_cut}")
ax1.axhline(wq_est, color="#0F766E", linestyle="-.", linewidth=1.5, label=f"Estable={wq_est:.2f}m")
ax1.set_title("Eliminación del Estado Transitorio (3 Cajas Mixtas)")
ax1.set_xlabel("Orden de llegada k"); ax1.set_ylabel("Wq (min)")
ax1.set_ylim(0, max(wq_cross) * 1.45); ax1.legend(fontsize=7.8, ncol=2)

x = np.arange(len(df_vv_colab))
ax2.bar(x - 0.17, df_vv_colab["ER10_Wq_pct"], width=0.34, color="#F59E0B", label="ER% Piloto n0=10")
ax2.bar(x + 0.17, df_vv_colab["ER100_Wq_pct"], width=0.34, color="#2563EB", label="ER% Monte Carlo n=100")
ax2.axhline(10.0, color="#0F766E", linestyle="--", label="Meta ER ≤ 10%")
ax2.set_xticks(x); ax2.set_xticklabels(df_vv_colab.index, fontweight="bold")
ax2.set_title("Reducción del Error Relativo ER(Wq) %")
ax2.set_ylabel("Error Relativo (%)"); ax2.legend(fontsize=8.2)
plt.tight_layout(); plt.show()"""
    ),
    md_cell(
        """## 6. Conclusiones Ejecutivas y Uso Ético de IA (Usa–Modifica–Crea)"""
    ),
    md_cell(
        """1. **Cajero con menor y mayor atención (Base 3 Mixtas, 10 réplicas):** El **Cajero 2** registró el menor tiempo medio (`S = 2.882 min`, `W = 6.217 min`), mientras que el **Cajero 1** registró el mayor (`S = 3.226 min`, `W = 7.490 min`), debido a la varianza natural de las colas M/M/1 independientes.
2. **Suficiencia de réplicas ($n^*$ y Error Relativo $ER\\%$):** Con $n_0=10$, el Error Relativo sobre $W_q$ alcanza `33.3%` en `3 Mixtas` (`n_prof = 111` para $ER \\le 10\\%$). Al simular `100` réplicas, $ER(W_q)$ baja a **`8.8%`** ($< 10\\%$) y $ER(W)$ a **`5.03%`**.
3. **Estado estable y validación V&V:** Eliminando el período transitorio ($k^* = 26$ arribos), la espera estacionaria de `3 Mixtas` converge a **`3.35 min`**, concordando estadísticamente con Pollaczek–Khinchine $M/G/1$ (`3.39 min`, $p = 0.794 > 0.05$). En riesgo operativo bajo cola aleatoria $M/M/1$, `3 Mixtas` presenta $P(W_q > 5\\text{ min}) = 20.9\\%$ global (`21.3%` en cajero pico), brecha mitigable con selección observable JSQ (`Wq = 0.74 min`).
4. **Necesidad de un 4.º cajero físico o electrónico:** **No es necesario** ampliar a 4 posiciones manteniendo `3 cajas mixtas` (`Wq_Global = 3.24 min`, `ER = 8.8%`, `JSQ = 0.74 min`, uso `43.7%`). Un 4.º cajero desploma la ocupación a `32.9%` (`67.1%` ocio) por un ahorro de apenas `1.24 min`.
5. **Asignación óptima de cajas exclusivas (Pagos vs. Retiros):** **3 cajas mixtas (`0 exclusivos de retiro` / `0 exclusivos de pago`)**. Bajo especialización rígida, `1R + 2P` sobrecarga retiros (`5.91 min`; `37.7%` con espera $> 5\\text{ min}$) y `2R + 1P` colapsa el único cajero de pagos hasta **`9.08 min`** (`43.6%` de clientes esperan $> 5\\text{ min}$).
6. **Bitácora ética Usa–Modifica–Crea:** El equipo utilizó asistencia computacional verificable auditando cada supuesto: corrección de JSQ no clarividente, uso de cuantiles exactos *t* de Student, extensión analítica hiperexponencial $M/G/1$, filtro de calentamiento y verificación automática mediante 14 pruebas unitarias."""
    ),
]


def execute_notebook_cells(cell_list: list) -> None:
    """Ejecuta todas las celdas de código en un kernel Python real y captura sus salidas."""
    km = jupyter_client.KernelManager(kernel_name="python3")
    km.start_kernel()
    kc = km.client()
    kc.start_channels()
    kc.wait_for_ready(timeout=30)

    exec_count = 1
    try:
        for cell in cell_list:
            if cell["cell_type"] != "code":
                continue
            code = "".join(cell["source"])
            msg_id = kc.execute(code)
            outputs = []
            cell["execution_count"] = exec_count
            exec_count += 1

            while True:
                try:
                    msg = kc.get_iopub_msg(timeout=90)
                except queue.Empty:
                    raise RuntimeError("Timeout ejecutando celda del notebook")

                if msg["parent_header"].get("msg_id") != msg_id:
                    continue

                msg_type = msg["msg_type"]
                content = msg["content"]

                if msg_type == "status" and content.get("execution_state") == "idle":
                    break
                elif msg_type == "stream":
                    outputs.append({
                        "output_type": "stream",
                        "name": content["name"],
                        "text": content["text"].splitlines(keepends=True),
                    })
                elif msg_type == "display_data":
                    outputs.append({
                        "output_type": "display_data",
                        "data": content["data"],
                        "metadata": content.get("metadata", {}),
                    })
                elif msg_type == "execute_result":
                    outputs.append({
                        "output_type": "execute_result",
                        "execution_count": cell["execution_count"],
                        "data": content["data"],
                        "metadata": content.get("metadata", {}),
                    })
                elif msg_type == "error":
                    tb = "\n".join(content.get("traceback", []))
                    raise RuntimeError(f"Error ejecutando celda:\n{tb}")

            cell["outputs"] = outputs
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


if __name__ == "__main__":
    print("Ejecutando celdas del cuaderno Google Colab para incrustar salidas y figuras...")
    execute_notebook_cells(cells)

    colab_notebook = {
        "cells": cells,
        "metadata": {
            "colab": {
                "name": "Simulacion_Colas_Banco_Colab.ipynb",
                "provenance": [],
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.13",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    out_name = "Simulacion_Colas_Banco_Colab.ipynb"
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump(colab_notebook, f, indent=2, ensure_ascii=False)
    print(f"[OK] Cuaderno generado y pre-ejecutado: {out_name}")
