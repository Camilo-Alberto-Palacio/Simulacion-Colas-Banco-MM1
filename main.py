"""
Script Principal de Ejecución: Simulación de Colas Bancarias M/M/1 — Banco de Colombia.
Actividad Didáctica 2-M3 | Módulo 2 | IU Digital de Antioquia — Grupo 25.

Ejecución:
    python main.py
"""

import os
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bank_queue import (
    ACTION_LABELS,
    BANK_MINUTES,
    SCENARIO_DEFINITIONS,
    USER_TYPES,
    BankQueuingModel,
    BankSimulationEngine,
    BankVisualizer,
)


def print_banner() -> None:
    print("=" * 84)
    print("  SIMULACIÓN DISCRETA DE COLAS M/M/1 — CASO BANCO DE COLOMBIA (8 HORAS / DÍA)  ")
    print("  Actividad Didáctica 2-M3 | IU Digital de Antioquia - Grupo 25")
    print("=" * 84)


def main() -> None:
    print_banner()
    os.makedirs("results", exist_ok=True)

    model = BankQueuingModel()
    engine = BankSimulationEngine(model=model)
    viz = BankVisualizer(output_dir="results")

    # 1. Análisis Teórico Analítico M/M/1 y M/G/1
    print("\n[1/5] Calculando Propiedades Analíticas M/M/1 (Ley de Little)...")
    theo_rows = []
    for skey in SCENARIO_DEFINITIONS:
        theo = model.analyze_scenario_theoretically(skey)
        for cname, cm in theo["cashiers"]:
            theo_rows.append({
                "escenario": skey,
                "nombre_corto": theo["nombre_corto"],
                "cajero": cname,
                "rol": cm.role,
                "lambda_cli_min": cm.lam,
                "mu_cli_min": cm.mu,
                "rho": cm.rho,
                "p0_ocio": cm.p0,
                "es_min": cm.mean_service,
                "es2_min2": cm.mean_s2,
                "l_sistema": cm.l_system,
                "lq_cola": cm.lq_queue,
                "w_sistema_min": cm.w_system,
                "wq_cola_mm1_min": cm.wq_queue,
                "wq_cola_mg1_min": cm.wq_mg1,
                "estable": cm.stable,
            })

    df_theo = pd.DataFrame(theo_rows)
    df_theo.to_csv("results/parametros_teoricos_mm1.csv", index=False, encoding="utf-8-sig")

    print(
        f"  • Flujo total sucursal: λ = {model.branch_arrival_rate('Mixto'):.4f} cli/min "
        f"(~{model.branch_arrival_rate('Mixto') * BANK_MINUTES:.1f} usuarios/8h)"
    )
    print(
        f"  • Retiros (70%): λ_R = {model.branch_arrival_rate('Retiro'):.4f} cli/min | "
        f"E[S_R] = {model.expected_service_moments('Retiro')[0]:.2f} min"
    )
    print(
        f"  • Pagos   (30%): λ_P = {model.branch_arrival_rate('Pago'):.4f} cli/min | "
        f"E[S_P] = {model.expected_service_moments('Pago')[0]:.2f} min"
    )

    # 2. Corridas Oficiales: 10 Réplicas Completas
    print("\n[2/5] Ejecutando 10 Réplicas Oficiales por Escenario (Jornadas de 480 min)...")
    res_10 = engine.run_multi_replica_experiment(
        num_replicas=10,
        base_seed=42,
        routing_mode="random_mm1",
        independent_arrivals_per_scenario=False,
    )

    df_sum10 = res_10["df_summary"]
    df_rep10 = res_10["df_replicas"]
    df_caj10 = res_10["df_cashier_summary"]
    df_sub10 = res_10["df_subtypes"]
    df_sample_n = res_10["df_sample_size"]

    df_sum10.to_csv("results/resumen_10_replicas_escenarios.csv", index=False, encoding="utf-8-sig")
    df_rep10.to_csv("results/detalle_10_replicas_por_tipo.csv", index=False, encoding="utf-8-sig")
    df_caj10.to_csv("results/cajeros_10_replicas_resumen.csv", index=False, encoding="utf-8-sig")
    df_sample_n.to_csv("results/tamano_muestra_replicas.csv", index=False, encoding="utf-8-sig")

    # Tabla consolidada de los 8 perfiles (acción x tipo)
    joint_p = model.joint_profile_probabilities()
    sub_agg = (
        df_sub10.groupby(["accion", "tipo_usuario"], sort=False)
        .agg(
            total_10_replicas=("cantidad", "sum"),
            promedio_por_replica=("cantidad", "mean"),
            desv_est=("cantidad", "std"),
            min_replica=("cantidad", "min"),
            max_replica=("cantidad", "max"),
            prop_empirica_media=("proporcion_empirica", "mean"),
        )
        .reset_index()
    )
    sub_agg["accion_etiqueta"] = sub_agg["accion"].map(ACTION_LABELS)
    sub_agg["prop_teorica"] = [
        joint_p[(r["accion"], r["tipo_usuario"])] for _, r in sub_agg.iterrows()
    ]
    sub_agg.to_csv("results/perfiles_8_usuarios_10_replicas.csv", index=False, encoding="utf-8-sig")

    # Reporte Punto 1: Cajero con menor y mayor tiempo promedio de atención (Escenario Base)
    base_caj = df_caj10[df_caj10["escenario"] == "E1_3_Mixtas"].copy()
    c_min_srv = base_caj.loc[base_caj["servicio_s_prom"].idxmin()]
    c_max_srv = base_caj.loc[base_caj["servicio_s_prom"].idxmax()]
    c_min_w = base_caj.loc[base_caj["atencion_w_prom"].idxmin()]
    c_max_w = base_caj.loc[base_caj["atencion_w_prom"].idxmax()]

    print("\n  [Punto 1] Desempeño por cajero en Escenario Base (3 Cajas Mixtas, 10 réplicas):")
    for _, r in base_caj.iterrows():
        print(
            f"      - {r['cajero']:10s} | Usuarios/día={r['usuarios_prom']:5.1f} | "
            f"S={r['servicio_s_prom']:.3f} m | Wq={r['espera_wq_prom']:.3f} m | "
            f"W={r['atencion_w_prom']:.3f} m | ρ={r['utilizacion_rho_prom']*100:5.1f}%"
        )
    print(f"      -> Menor servicio medio (S): {c_min_srv['cajero']} ({c_min_srv['servicio_s_prom']:.3f} min)")
    print(f"      -> Mayor servicio medio (S): {c_max_srv['cajero']} ({c_max_srv['servicio_s_prom']:.3f} min)")
    print(f"      -> Menor atención total (W): {c_min_w['cajero']} ({c_min_w['atencion_w_prom']:.3f} min)")
    print(f"      -> Mayor atención total (W): {c_max_w['cajero']} ({c_max_w['atencion_w_prom']:.3f} min)")

    # Reporte Puntos 2 y 3: Promedio y total por réplica de usuarios de cada tipo
    base_rep = df_rep10[df_rep10["escenario"] == "E1_3_Mixtas"].sort_values("replica")
    print("\n  [Punto 2] Promedio diario de usuarios por tipo en toda la sucursal (10 réplicas):")
    for u, col in zip(USER_TYPES, ["rapido", "normal", "lento", "muy_lento"]):
        print(f"      - {u:10s}: {base_rep[col].mean():6.2f} usuarios/día (±{base_rep[col].std(ddof=1):.2f})")

    print("\n  [Punto 3] Mínimo por tipo entre réplicas (R1..R10):")
    for u, col in zip(USER_TYPES, ["rapido", "normal", "lento", "muy_lento"]):
        idx_m = base_rep[col].idxmin()
        row_m = base_rep.loc[idx_m]
        print(f"      - {u:10s}: mínimo = {int(row_m[col])} usuarios en Réplica {int(row_m['replica'])}")

    print("\n  [Tamaño de Muestra] Réplicas necesarias (n* con t de Student 95%, desde piloto n0=10):")
    for _, r in df_sample_n.iterrows():
        print(
            f"      - {r['nombre_corto']:10s} | ±0.50m Wq -> n*={int(r['n_req_wq_iterativo']):3d} | "
            f"±5% W -> n*={int(r['n_req_w_iterativo']):3d} | "
            f"±5 usr/día -> n*={int(r['n_req_usuarios_iterativo']):3d} | "
            f"Global máx={int(r['n_req_global_max']):3d}"
        )

    # 3. Validación Monte Carlo (100 Réplicas) y Sensibilidad Cola Más Corta (JSQ)
    print("\n[3/5] Ejecutando Validación Monte Carlo (100 Réplicas) y Sensibilidad JSQ...")
    res_mc = engine.run_multi_replica_experiment(
        num_replicas=100,
        base_seed=42,
        routing_mode="random_mm1",
        independent_arrivals_per_scenario=False,
    )
    res_jsq = engine.run_multi_replica_experiment(
        num_replicas=100,
        base_seed=42,
        routing_mode="shortest_queue",
        independent_arrivals_per_scenario=False,
    )

    df_mc_sum = res_mc["df_summary"]
    df_mc_rep = res_mc["df_replicas"]
    df_mc_caj = res_mc["df_cashier_summary"]
    df_mc_wait_act = res_mc["df_wait_by_action"]
    df_mc_wait_typ = res_mc["df_wait_by_type"]
    df_mc_wait_prof = res_mc["df_wait_profiles"]
    df_jsq_sum = res_jsq["df_summary"]

    df_mc_sum.to_csv("results/resumen_montecarlo_100_replicas.csv", index=False, encoding="utf-8-sig")
    df_mc_rep.to_csv("results/montecarlo_100_replicas_detalle.csv", index=False, encoding="utf-8-sig")
    df_mc_caj.to_csv("results/cajeros_montecarlo_100_resumen.csv", index=False, encoding="utf-8-sig")
    df_mc_wait_act.to_csv("results/esperas_por_accion_100_replicas.csv", index=False, encoding="utf-8-sig")
    df_mc_wait_typ.to_csv("results/esperas_por_tipo_100_replicas.csv", index=False, encoding="utf-8-sig")
    df_mc_wait_prof.to_csv("results/esperas_por_perfil_100_replicas.csv", index=False, encoding="utf-8-sig")
    df_jsq_sum.to_csv("results/sensibilidad_jsq_100_replicas.csv", index=False, encoding="utf-8-sig")

    print("\n  [Puntos 4 y 5] Resumen Comparativo de Escenarios (100 Réplicas M/M/1 Independientes):")
    for _, r in df_mc_sum.iterrows():
        print(
            f"      - {r['nombre_corto']:10s} | Wq={r['espera_wq_media_min']:5.2f} m "
            f"[IC95: {r['espera_wq_ic95_inf']:4.2f}–{r['espera_wq_ic95_sup']:4.2f}] | "
            f"Wq(R/P)={r['wq_retiro_media_min']:4.2f}/{r['wq_pago_media_min']:4.2f} | "
            f"Peor Cajero Wq={r['peor_cajero_wq_media_min']:5.2f} m | "
            f"W={r['sistema_w_media_min']:5.2f} m | ρ_med={r['utilizacion_rho_media']*100:4.1f}% | "
            f"ρ_max={r['utilizacion_max_media']*100:4.1f}%"
        )

    # 4. Generación de 6 Figuras Científicas a 300 DPI
    print("\n[4/5] Generando 6 Figuras Científicas en Alta Resolución (300 DPI)...")
    figs = [
        viz.plot_queue_architecture(model),
        viz.plot_base_cashier_performance(res_10["df_cashiers"], df_caj10),
        viz.plot_user_types_and_replicas(model, df_rep10),
        viz.plot_scenarios_wait_comparison(df_mc_sum),
        viz.plot_theory_and_montecarlo_validation(df_mc_sum, df_jsq_sum, df_mc_rep),
        viz.plot_per_cashier_load_and_wait_across_scenarios(df_mc_caj, num_replicas=100),
    ]
    for f in figs:
        print(f"      [+] Figura guardada: {f}")

    # 5. Confirmación Final
    print("\n[5/5] Pipeline experimental completado exitosamente.")
    print("  • Todos los CSVs y gráficas quedaron en 'results/'.")
    print("=" * 84)


if __name__ == "__main__":
    main()
