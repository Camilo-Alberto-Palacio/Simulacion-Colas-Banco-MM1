"""
Módulo de Visualizaciones Científicas para la Simulación Bancaria M/M/1.
Genera 6 figuras de alta resolución (300 DPI) con estética editorial sobria
y sin solapamiento de etiquetas.
"""

import os
from typing import Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch

from .model import BankQueuingModel, SCENARIO_DEFINITIONS, USER_TYPES


class BankVisualizer:
    """Generador de gráficas científicas a 300 DPI para el caso Banco de Colombia."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        plt.rcParams["font.family"] = "DejaVu Sans"
        plt.rcParams["axes.edgecolor"] = "#CBD5E1"
        plt.rcParams["axes.linewidth"] = 0.8

        self.palette = {
            "navy": "#1E3A8A",
            "blue": "#2563EB",
            "teal": "#0F766E",
            "amber": "#D97706",
            "red": "#DC2626",
            "slate": "#475569",
            "light_bg": "#F8FAFC",
        }
        self.user_colors = {
            "Rápido": "#16A34A",
            "Normal": "#2563EB",
            "Lento": "#D97706",
            "Muy lento": "#DC2626",
        }

    def plot_queue_architecture(
        self,
        model: BankQueuingModel,
        filename: str = "fig1_arquitectura_colas_mm1.png",
    ) -> str:
        """Dibuja el diagrama de flujo y topología M/M/1 de las configuraciones evaluadas."""
        fig, ax = plt.subplots(figsize=(13.5, 7.6), dpi=300)
        ax.set_xlim(0, 13.5)
        ax.set_ylim(0, 7.8)
        ax.axis("off")

        ax.text(
            6.75, 7.42,
            "Arquitectura de Colas Independientes M/M/1 — Banco de Colombia (Jornada 8h = 480 min)",
            ha="center", va="center", fontsize=13, fontweight="bold", color="#0F172A",
        )
        ax.text(
            6.75, 7.05,
            "Comparación estructural entre operación mixta, especialización asimétrica y ampliación a 4 cajeros",
            ha="center", va="center", fontsize=9.5, color="#475569",
        )

        # Bloque de llegada global
        lam_tot = model.branch_arrival_rate("Mixto")
        arr_box = FancyBboxPatch(
            (0.4, 2.3), 2.7, 3.8,
            boxstyle="round,pad=0.12,rounding_size=0.2",
            facecolor="#EFF6FF", edgecolor="#1E3A8A", linewidth=1.8,
        )
        ax.add_patch(arr_box)
        ax.text(1.75, 5.65, "Flujo de Llegadas", ha="center", va="center", fontsize=10.5, fontweight="bold", color="#1E3A8A")
        ax.text(
            1.75, 4.35,
            f"λ_total = {lam_tot:.4f} cli/min\n"
            f"(~{lam_tot*60:.1f} cli/hora | ~{lam_tot*480:.0f}/día)\n"
            f"E[IA] = {model.expected_interarrival_time('Mixto'):.3f} min\n\n"
            f"• Retiros: 70%\n"
            f"  λ_R = {model.branch_arrival_rate('Retiro'):.4f}/min\n"
            f"  E[S_R] = {model.expected_service_moments('Retiro')[0]:.2f} min\n\n"
            f"• Pagos: 30%\n"
            f"  λ_P = {model.branch_arrival_rate('Pago'):.4f}/min\n"
            f"  E[S_P] = {model.expected_service_moments('Pago')[0]:.2f} min",
            ha="center", va="center", fontsize=8.4, color="#1E293B", linespacing=1.32,
        )

        # Tarjetas de escenarios calculadas dinámicamente desde el modelo analítico
        t_e1 = model.analyze_scenario_theoretically("E1_3_Mixtas")
        t_e2 = model.analyze_scenario_theoretically("E2_1R_2P")
        t_e3 = model.analyze_scenario_theoretically("E3_2R_1P")
        t_e4a = model.analyze_scenario_theoretically("E4a_4_Mixtas")
        t_e4b = model.analyze_scenario_theoretically("E4b_2R_2P")

        e2_r = next(m for _, m in t_e2["cashiers"] if m.role == "Retiro")
        e2_p = next(m for _, m in t_e2["cashiers"] if m.role == "Pago")
        e3_r = next(m for _, m in t_e3["cashiers"] if m.role == "Retiro")
        e3_p = next(m for _, m in t_e3["cashiers"] if m.role == "Pago")
        e4b_r = next(m for _, m in t_e4b["cashiers"] if m.role == "Retiro")
        e4b_p = next(m for _, m in t_e4b["cashiers"] if m.role == "Pago")

        cards = [
            (
                "E1: 3 Cajas Mixtas (Base)",
                f"3 × Mixto  |  ρ = {t_e1['mean_rho']*100:.1f}% c/u  |  Wq(M/M/1) = {t_e1['weighted_wq_mm1']:.2f} min",
                "#F0FDF4", "#16A34A", 5.55,
            ),
            (
                "E2: 1 Retiro + 2 Pagos",
                f"1R (ρ={e2_r.rho*100:.1f}%, Wq={e2_r.wq_queue:.2f}m)  +  2P (ρ={e2_p.rho*100:.1f}%, Wq={e2_p.wq_queue:.2f}m)",
                "#FFFBEB", "#D97706", 4.10,
            ),
            (
                "E3: 2 Retiros + 1 Pago",
                f"2R (ρ={e3_r.rho*100:.1f}%, Wq={e3_r.wq_queue:.2f}m)  +  1P (ρ={e3_p.rho*100:.1f}%, Wq={e3_p.wq_queue:.2f}m)",
                "#FEF2F2", "#DC2626", 2.65,
            ),
            (
                "E4: 4 Cajas (4 Mixtas / 2R+2P)",
                f"4M: ρ={t_e4a['mean_rho']*100:.1f}%, Wq={t_e4a['weighted_wq_mm1']:.2f}m  |  2R+2P: Wq_R={e4b_r.wq_queue:.2f}m, Wq_P={e4b_p.wq_queue:.2f}m",
                "#EEF2FF", "#4338CA", 1.20,
            ),
        ]

        for title, subtitle, bg, edge, y0 in cards:
            card = FancyBboxPatch(
                (4.1, y0), 8.9, 1.05,
                boxstyle="round,pad=0.08,rounding_size=0.18",
                facecolor=bg, edgecolor=edge, linewidth=1.6,
            )
            ax.add_patch(card)
            ax.text(4.35, y0 + 0.72, title, ha="left", va="center", fontsize=10, fontweight="bold", color="#0F172A")
            ax.text(4.35, y0 + 0.30, subtitle, ha="left", va="center", fontsize=8.8, color="#334155")

            arrow = FancyArrowPatch(
                (3.22, 4.2), (4.02, y0 + 0.52),
                arrowstyle="-|>,head_width=5,head_length=7",
                color=edge, linewidth=1.6, connectionstyle="arc3,rad=0.05",
            )
            ax.add_patch(arrow)

        ax.text(
            6.75, 0.45,
            "Nota: Cada cajero opera como cola M/M/1 independiente (Poisson thinning 1/k entre cajeros elegibles) con disciplina FCFS.",
            ha="center", va="center", fontsize=8.5, style="italic", color="#64748B",
        )

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_base_cashier_performance(
        self,
        df_cashiers: pd.DataFrame,
        df_cashier_summary: pd.DataFrame,
        filename: str = "fig2_tiempos_atencion_por_cajero.png",
    ) -> str:
        """
        Figura para el Punto 1: identifica el cajero con menor y mayor tiempo promedio
        de atención en el escenario base (3 Cajas Mixtas, 10 réplicas).
        """
        base_sum = df_cashier_summary[df_cashier_summary["escenario"] == "E1_3_Mixtas"].copy()
        base_rep = df_cashiers[df_cashiers["escenario"] == "E1_3_Mixtas"].copy()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=300)

        # Panel A: Desglose Servicio S, Espera Wq y Atención Total W por cajero
        x = np.arange(len(base_sum))
        w = 0.25
        cajeros = base_sum["cajero"].tolist()
        srv = base_sum["servicio_s_prom"].values
        wq = base_sum["espera_wq_prom"].values
        wtot = base_sum["atencion_w_prom"].values

        b1 = ax1.bar(x - w, srv, width=w, label="Servicio promedio (S)", color=self.palette["teal"], alpha=0.9)
        b2 = ax1.bar(x, wq, width=w, label="Espera en cola (Wq)", color=self.palette["amber"], alpha=0.9)
        b3 = ax1.bar(x + w, wtot, width=w, label="Atención total (W = Wq + S)", color=self.palette["navy"], alpha=0.9)

        for bars in (b1, b2, b3):
            for bar in bars:
                h = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2, h + 0.14,
                    f"{h:.2f}", ha="center", va="bottom", fontsize=8.0, color="#1E293B",
                )

        idx_min_srv = int(np.argmin(srv))
        idx_max_srv = int(np.argmax(srv))
        idx_min_w = int(np.argmin(wtot))
        idx_max_w = int(np.argmax(wtot))

        ax1.set_xticks(x)
        ax1.set_xticklabels(cajeros, fontsize=9.5, fontweight="bold")
        ax1.set_ylabel("Tiempo promedio (minutos)", fontsize=10)
        ax1.set_title("A. Tiempos Promedio por Cajero (Escenario Base: 3 Mixtas)", fontsize=10.8, fontweight="bold", color="#0F172A")
        ax1.set_ylim(0, max(wtot) * 1.46)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper left", fontsize=8.2, frameon=True)

        summary_note = (
            f"Servicio (S): Menor = {cajeros[idx_min_srv]} ({srv[idx_min_srv]:.2f} m) | "
            f"Mayor = {cajeros[idx_max_srv]} ({srv[idx_max_srv]:.2f} m)\n"
            f"Sistema (W): Menor = {cajeros[idx_min_w]} ({wtot[idx_min_w]:.2f} m) | "
            f"Mayor = {cajeros[idx_max_w]} ({wtot[idx_max_w]:.2f} m)"
        )
        ax1.text(
            0.98, 0.97, summary_note, transform=ax1.transAxes,
            ha="right", va="top", fontsize=7.6,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#F8FAFC", edgecolor="#CBD5E1"),
        )

        # Panel B: Evolución por réplica del tiempo de atención total W por cajero
        n_reps = int(base_rep["replica"].nunique())
        colors = [self.palette["blue"], self.palette["teal"], self.palette["red"]]
        markers = ["o", "s", "^"]
        for c_idx, cname in enumerate(cajeros):
            sub_c = base_rep[base_rep["cajero"] == cname].sort_values("replica")
            ax2.plot(
                sub_c["replica"], sub_c["atencion_total_w_min"],
                marker=markers[c_idx], linewidth=1.9, markersize=5.5,
                color=colors[c_idx], label=f"{cname} (prom={wtot[c_idx]:.2f} m)",
            )

        y_min_w = float(base_rep["atencion_total_w_min"].min())
        y_max_w = float(base_rep["atencion_total_w_min"].max())
        ax2.set_xticks(sorted(base_rep["replica"].unique()))
        ax2.set_ylim(max(0.0, y_min_w * 0.85), y_max_w * 1.24)
        ax2.set_xlabel("Número de réplica (corrida)", fontsize=10)
        ax2.set_ylabel("Tiempo promedio total en sistema W (min)", fontsize=10)
        ax2.set_title(
            f"B. Variabilidad de W por Cajero ({n_reps} Réplicas)",
            fontsize=10.8, fontweight="bold", color="#0F172A",
        )
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.legend(loc="upper right", fontsize=8.5, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_user_types_and_replicas(
        self,
        model: BankQueuingModel,
        df_replicas: pd.DataFrame,
        filename: str = "fig3_distribucion_usuarios_por_tipo_replicas.png",
    ) -> str:
        """
        Figura para los Puntos 2 y 3: promedio de usuarios por tipo en toda la sucursal
        y evolución del total de usuarios por tipo en cada una de las 10 réplicas.
        """
        base_rep = df_replicas[df_replicas["escenario"] == "E1_3_Mixtas"].sort_values("replica")
        col_map = {
            "Rápido": "rapido",
            "Normal": "normal",
            "Lento": "lento",
            "Muy lento": "muy_lento",
        }

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.4), dpi=300)

        # Panel A: Promedio de usuarios por tipo (Empírico vs Teórico esperado en 8h)
        n_reps = int(base_rep["replica"].nunique())
        emp_means = [float(base_rep[col_map[u]].mean()) for u in USER_TYPES]
        emp_stds = [float(base_rep[col_map[u]].std(ddof=1)) for u in USER_TYPES]
        exp_arr = model.branch_arrival_rate("Mixto") * model.horizon_minutes
        marg_p = model.marginal_user_type_probabilities()
        theo_means = [exp_arr * marg_p[u] for u in USER_TYPES]

        x = np.arange(len(USER_TYPES))
        w = 0.34
        b1 = ax1.bar(x - w / 2, emp_means, yerr=emp_stds, capsize=4, width=w,
                     color=[self.user_colors[u] for u in USER_TYPES], alpha=0.90,
                     label=f"Promedio simulado (± DE, {n_reps} réplicas)")
        b2 = ax1.bar(x + w / 2, theo_means, width=w, color="#94A3B8", edgecolor="#475569",
                     linewidth=0.8, hatch="//", label="Valor esperado teórico (8 h)")

        for idx, bar in enumerate(b1):
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + emp_stds[idx] + 1.6, f"{h:.1f}",
                     ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#0F172A")
        for bar in b2:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.6, f"{h:.1f}",
                     ha="center", va="bottom", fontsize=8.3, color="#475569")

        ax1.set_xticks(x)
        ax1.set_xticklabels(USER_TYPES, fontsize=9.5, fontweight="bold")
        ax1.set_ylabel("Usuarios promedio por jornada (8 h)", fontsize=10)
        ax1.set_title(
            f"A. Promedio de Usuarios por Tipo ({n_reps} Réplicas, Totalidad de Cajeros)",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        ax1.set_ylim(0, max(max(np.array(emp_means) + np.array(emp_stds)), max(theo_means)) * 1.25)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=8.3, frameon=True)

        # Panel B: Total de usuarios por tipo en cada réplica (1..N)
        replicas = base_rep["replica"].values
        all_vals = base_rep[list(col_map.values())].values
        min_y_b = max(0, int(all_vals.min()) - 4)
        max_y_b = int(all_vals.max())
        for u in USER_TYPES:
            vals = base_rep[col_map[u]].values
            ax2.plot(
                replicas, vals, marker="o", linewidth=2.0, markersize=5.5,
                color=self.user_colors[u], label=f"{u} (mín={vals.min()} en R{replicas[np.argmin(vals)]})",
            )
            min_idx = int(np.argmin(vals))
            ax2.scatter([replicas[min_idx]], [vals[min_idx]], s=90, facecolors="none",
                        edgecolors=self.user_colors[u], linewidths=2.0, zorder=5)

        ax2.set_xticks(replicas)
        ax2.set_ylim(min_y_b, max_y_b * 1.24)
        ax2.set_xlabel("Réplica", fontsize=10)
        ax2.set_ylabel("Total de usuarios atendidos en jornada", fontsize=10)
        ax2.set_title(
            f"B. Total de Usuarios por Tipo en las {n_reps} Réplicas (Mínimos Marcados)",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.legend(loc="upper center", fontsize=7.8, frameon=True, ncol=2)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_scenarios_wait_comparison(
        self,
        df_summary: pd.DataFrame,
        filename: str = "fig4_comparativa_espera_escenarios.png",
    ) -> str:
        """
        Figura para los Puntos 4 y 5: compara tiempo promedio global de espera Wq,
        peor cajero cuello de botella y descomposición W = Wq + S entre los 5 escenarios.
        """
        labels = df_summary["nombre_corto"].tolist()
        n_reps = int(df_summary["replicas"].iloc[0]) if "replicas" in df_summary.columns else 10
        x = np.arange(len(labels))
        wq = df_summary["espera_wq_media_min"].values
        wq_err = np.vstack([
            wq - df_summary["espera_wq_ic95_inf"].values,
            df_summary["espera_wq_ic95_sup"].values - wq,
        ])
        peor_wq = df_summary["peor_cajero_wq_media_min"].values
        srv = df_summary["servicio_s_media_min"].values
        rho_med = df_summary["utilizacion_rho_media"].values * 100.0
        rho_max = df_summary["utilizacion_max_media"].values * 100.0

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.6), dpi=300)

        # Panel A: Wq global vs Peor Cajero Wq
        w = 0.35
        b1 = ax1.bar(x - w / 2, wq, yerr=np.clip(wq_err, 0, None), capsize=4, width=w,
                     color=self.palette["blue"], alpha=0.90, label=f"Espera global Wq ({n_reps} rép., IC95%)")
        b2 = ax1.bar(x + w / 2, peor_wq, width=w,
                     color=self.palette["red"], alpha=0.82, label="Peor cajero / cuello de botella (Wq máx)")

        ax1.axhline(5.0, color="#0F766E", linestyle="--", linewidth=1.3, label="Umbral referencia servicio (5.0 min)")

        for idx, bar in enumerate(b1):
            h = bar.get_height()
            top_err = max(0.0, float(wq_err[1, idx]))
            ax1.text(bar.get_x() + bar.get_width() / 2, h + top_err + 0.20, f"{h:.2f}",
                     ha="center", va="bottom", fontsize=8.2, fontweight="bold", color="#1E3A8A")
        for bar in b2:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.25, f"{h:.2f}",
                     ha="center", va="bottom", fontsize=8.2, fontweight="bold", color="#991B1B")

        max_top_a = max(float(np.max(peor_wq)), float(np.max(wq + np.clip(wq_err[1], 0, None))))
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, fontsize=9.0, fontweight="bold")
        ax1.set_ylabel("Tiempo promedio de espera en cola Wq (min)", fontsize=10)
        ax1.set_title(
            f"A. Tiempos de Espera por Escenario ({n_reps} Réplicas)",
            fontsize=10.6, fontweight="bold", color="#0F172A",
        )
        ax1.set_ylim(0, max_top_a * 1.25)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=8.0, frameon=True)

        # Panel B: Descomposición W = Wq + S y utilización promedio / máxima
        b_srv = ax2.bar(x, srv, width=0.48, color=self.palette["teal"], alpha=0.88, label="Servicio S (min)")
        b_wq = ax2.bar(x, wq, bottom=srv, width=0.48, color=self.palette["amber"], alpha=0.88, label="Espera en cola Wq (min)")

        for i in range(len(x)):
            tot = srv[i] + wq[i]
            ax2.text(x[i], tot + 0.25, f"W={tot:.2f}m\n(ρmax={rho_max[i]:.0f}%)",
                     ha="center", va="bottom", fontsize=7.8, fontweight="bold", color="#0F172A")

        ax2_twin = ax2.twinx()
        ax2_twin.plot(x, rho_med, color="#7C3AED", marker="D", linewidth=2.0, markersize=6, label="Utilización media ρ (%)")
        ax2_twin.set_ylabel("Utilización media ρ (%)", fontsize=10, color="#7C3AED")
        ax2_twin.tick_params(axis="y", labelcolor="#7C3AED")
        ax2_twin.set_ylim(0, 100)

        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, fontsize=9.0, fontweight="bold")
        ax2.set_ylabel("Tiempo total en el sistema W (min)", fontsize=10)
        ax2.set_title(
            f"B. Tiempo en Sistema (W = S + Wq) vs. Utilización ({n_reps} Rép.)",
            fontsize=10.6, fontweight="bold", color="#0F172A",
        )
        ax2.set_ylim(0, float(np.max(srv + wq)) * 1.38)
        ax2.grid(axis="y", linestyle=":", alpha=0.6)

        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8.0, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_theory_and_montecarlo_validation(
        self,
        df_mc_summary: pd.DataFrame,
        df_jsq_summary: pd.DataFrame,
        df_mc_replicas: pd.DataFrame,
        filename: str = "fig5_validacion_montecarlo_y_teoria.png",
    ) -> str:
        """
        Valida convergencia Monte Carlo (100 réplicas) frente a las soluciones analíticas
        M/M/1 y Pollaczek-Khinchine M/G/1, y muestra la sensibilidad frente a cola más corta (JSQ).
        """
        labels = df_mc_summary["nombre_corto"].tolist()
        n_mc = int(df_mc_summary["replicas"].iloc[0]) if "replicas" in df_mc_summary.columns else 100
        x = np.arange(len(labels))
        w = 0.20

        wq_mm1 = df_mc_summary["wq_teorica_mm1_min"].values
        wq_mg1 = df_mc_summary["wq_teorica_mg1_min"].values
        wq_sim = df_mc_summary["espera_wq_media_min"].values
        wq_jsq = df_jsq_summary["espera_wq_media_min"].values

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.5), dpi=300)

        ax1.bar(x - 1.5 * w, wq_mm1, width=w, color="#64748B", label="Analítico M/M/1")
        ax1.bar(x - 0.5 * w, wq_mg1, width=w, color="#0F766E", label="Analítico M/G/1 (P-K)")
        ax1.bar(x + 0.5 * w, wq_sim, width=w, color="#2563EB", label=f"Simulado {n_mc} Rép. (Indep. M/M/1)")
        ax1.bar(x + 1.5 * w, wq_jsq, width=w, color="#F59E0B", label="Sensibilidad JSQ (Cola Observable)")

        for idx in range(len(x)):
            ax1.text(x[idx] + 0.5 * w, wq_sim[idx] + 0.12, f"{wq_sim[idx]:.2f}",
                     ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#1E3A8A")
            ax1.text(x[idx] + 1.5 * w, wq_jsq[idx] + 0.12, f"{wq_jsq[idx]:.2f}",
                     ha="center", va="bottom", fontsize=7.6, color="#B45309")

        max_bar = max(float(np.max(wq_mm1)), float(np.max(wq_mg1)), float(np.max(wq_sim)), float(np.max(wq_jsq)))
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, fontsize=9.0, fontweight="bold")
        ax1.set_ylabel("Tiempo medio de espera en cola Wq (min)", fontsize=10)
        ax1.set_title(
            f"A. Validación Teórica vs. {n_mc} Réplicas y JSQ Observable",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        ax1.set_ylim(0, max_bar * 1.26)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=8.0, frameon=True)

        # Panel B: Convergencia acumulada de Wq en N réplicas Monte Carlo
        colors = ["#16A34A", "#D97706", "#DC2626", "#2563EB", "#7C3AED"]
        min_cum = float("inf")
        max_cum = float("-inf")
        for idx, skey in enumerate(SCENARIO_DEFINITIONS.keys()):
            sub = df_mc_replicas[df_mc_replicas["escenario"] == skey].sort_values("replica")
            cum_mean = sub["espera_cola_wq_min"].expanding().mean().values
            min_cum = min(min_cum, float(np.min(cum_mean)))
            max_cum = max(max_cum, float(np.max(cum_mean)))
            reps = sub["replica"].values
            short_n = SCENARIO_DEFINITIONS[skey]["nombre_corto"]
            ax2.plot(reps, cum_mean, linewidth=2.0, color=colors[idx],
                     label=f"{short_n} (final={cum_mean[-1]:.2f} m)")

        pad_y = max(0.35, (max_cum - min_cum) * 0.12)
        ax2.axvline(10, color="#475569", linestyle="--", linewidth=1.2, label="Mínimo exigido (10 réplicas)")
        ax2.set_ylim(max(0.0, min_cum - pad_y), max_cum + pad_y * 2.2)
        ax2.set_xlabel("Número acumulado de réplicas Monte Carlo", fontsize=10)
        ax2.set_ylabel("Media acumulada de espera en cola Wq (min)", fontsize=10)
        ax2.set_title(
            f"B. Convergencia Estocástica de Wq (1 a {n_mc} Réplicas)",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.legend(loc="upper right", fontsize=8.0, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_per_cashier_load_and_wait_across_scenarios(
        self,
        df_cashier_summary: pd.DataFrame,
        filename: str = "fig6_balance_carga_cajeros_escenarios.png",
        num_replicas: Optional[int] = None,
    ) -> str:
        """
        Muestra el balance de carga (usuarios/día) y espera Wq por cada cajero individual
        en los 5 escenarios, evidenciando los cuellos de botella de la especialización.
        """
        scenarios = ["E1_3_Mixtas", "E2_1R_2P", "E3_2R_1P", "E4a_4_Mixtas", "E4b_2R_2P"]
        fig, axes = plt.subplots(1, 2, figsize=(14.2, 6.4), dpi=300)

        # Preparar etiquetas combinadas Escenario - Cajero
        rows = df_cashier_summary[df_cashier_summary["escenario"].isin(scenarios)].copy().reset_index(drop=True)
        rows["etiqueta"] = rows["nombre_corto"] + " · " + rows["cajero"].str.replace("Cajero ", "C")

        rep_tag = f" ({num_replicas} Réplicas)" if num_replicas else ""
        y_pos = np.arange(len(rows))
        role_colors = {
            "Mixto": "#2563EB",
            "Retiro": "#0F766E",
            "Pago": "#DC2626",
        }
        bar_colors = [role_colors[r] for r in rows["rol"]]

        # Panel A: Usuarios promedio atendidos por cajero
        bars_u = axes[0].barh(y_pos, rows["usuarios_prom"], color=bar_colors, alpha=0.88)
        for bar in bars_u:
            w = bar.get_width()
            axes[0].text(w + 1.8, bar.get_y() + bar.get_height() / 2, f"{w:.1f}",
                         va="center", ha="left", fontsize=7.9, color="#0F172A")
        axes[0].set_yticks(y_pos)
        axes[0].set_yticklabels(rows["etiqueta"], fontsize=8.0)
        axes[0].invert_yaxis()
        axes[0].set_xlabel("Usuarios atendidos promedio por jornada (8 h)", fontsize=9.8)
        axes[0].set_title(
            f"A. Carga de Usuarios por Cajero y Rol{rep_tag}",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        axes[0].set_xlim(0, rows["usuarios_prom"].max() * 1.18)
        axes[0].grid(axis="x", linestyle=":", alpha=0.6)

        # Panel B: Espera promedio Wq por cajero
        bars_w = axes[1].barh(y_pos, rows["espera_wq_prom"], color=bar_colors, alpha=0.88)
        axes[1].axvline(5.0, color="#475569", linestyle="--", linewidth=1.2, zorder=1)
        for bar in bars_w:
            w = bar.get_width()
            axes[1].text(
                w + 0.16, bar.get_y() + bar.get_height() / 2, f"{w:.2f} m",
                va="center", ha="left", fontsize=7.9, fontweight="bold", color="#0F172A",
                bbox=dict(boxstyle="square,pad=0.1", facecolor="white", edgecolor="none", alpha=0.85),
                zorder=4,
            )

        # Separadores horizontales entre escenarios
        for idx in range(1, len(rows)):
            if rows.loc[idx, "escenario"] != rows.loc[idx - 1, "escenario"]:
                axes[0].axhline(idx - 0.5, color="#CBD5E1", linewidth=1.0, linestyle="-")
                axes[1].axhline(idx - 0.5, color="#CBD5E1", linewidth=1.0, linestyle="-")
        axes[1].set_yticks(y_pos)
        axes[1].set_yticklabels([""] * len(rows))
        axes[1].invert_yaxis()
        axes[1].set_xlabel("Tiempo promedio de espera en cola Wq (min)", fontsize=9.8)
        axes[1].set_title(
            f"B. Espera Individual Wq y Cuellos de Botella{rep_tag}",
            fontsize=10.5, fontweight="bold", color="#0F172A",
        )
        axes[1].set_xlim(0, max(float(rows["espera_wq_prom"].max()), 5.0) * 1.26)
        axes[1].grid(axis="x", linestyle=":", alpha=0.6)

        # Leyenda compartida (incluye línea de umbral para evitar solapamientos sobre barras)
        legend_handles = [
            Patch(facecolor=role_colors["Mixto"], label="Cajero Mixto"),
            Patch(facecolor=role_colors["Retiro"], label="Exclusivo Retiros"),
            Patch(facecolor=role_colors["Pago"], label="Exclusivo Pagos"),
            Line2D([0], [0], color="#475569", linestyle="--", linewidth=1.2, label="Umbral servicio (5.0 min)"),
        ]
        axes[1].legend(handles=legend_handles, loc="lower right", fontsize=8.2, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path
