"""
Simulador de Eventos Discretos (DES) para Cajeros Independientes M/M/1.
Banco de Colombia — Actividad Didáctica 2-M3.

Implementa:
- Simulación fiel de una jornada bancaria de 8 horas (480 min) por réplica.
- Asignación equiprobable (Poisson thinning) para preservar la independencia M/M/1
  de cada cajero, más modo comparativo Join-the-Shortest-Queue (JSQ observable, no
  clarividente) y Least-Work-Left (LWL) para análisis de sensibilidad.
- Evaluación completa de los 5 escenarios (3 Mixtas, 1R+2P, 2R+1P, 4 Mixtas, 2R+2P).
- Corridas oficiales (10 réplicas piloto detalladas), cálculo de tamaño muestral n*
  y validación Monte Carlo (100 réplicas) con intervalos de confianza t de Student al 95 %.
"""

from collections import deque
import math
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .model import (
    ACTION_PROBS,
    BANK_MINUTES,
    SCENARIO_DEFINITIONS,
    USER_TYPES,
    ArrivalCustomer,
    BankQueuingModel,
    classify_utilization_regime,
)


def _betacf(a: float, b: float, x: float) -> float:
    """Fracción continua de Lentz para la función beta incompleta regularizada."""
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Función beta incompleta regularizada I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_crit_two_sided(df: int, confidence: float = 0.95) -> float:
    """
    Valor crítico bilateral t_{alpha/2, df} de la distribución t de Student
    calculado sin dependencias externas mediante inversión por bisección de I_x.
    """
    if df < 1:
        raise ValueError(f"Los grados de libertad (df) deben ser >= 1, recibido: {df}")
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"El nivel de confianza debe estar en (0, 1), recibido: {confidence}")

    target = 1.0 - confidence
    lo, hi = 0.0, 20.0
    while _betainc(0.5 * df, 0.5, df / (df + hi * hi)) > target:
        hi *= 2.0

    for _ in range(90):
        mid = 0.5 * (lo + hi)
        p_two_tail = _betainc(0.5 * df, 0.5, df / (df + mid * mid))
        if p_two_tail > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class BankSimulationEngine:
    """Motor de simulación discreta multi-escenario para el sistema de colas del banco."""

    def __init__(self, model: Optional[BankQueuingModel] = None):
        self.model = model or BankQueuingModel()

    @staticmethod
    def _aggregate_records(
        records: List[Tuple[str, str, float, float, float]],
        key_fn: Callable[[Tuple[str, str, float, float, float]], object],
        keys: List[object],
    ) -> Dict[object, Dict[str, float]]:
        """Agrupa registros individuales (accion, tipo, wq, s, w) sin duplicar lógica."""
        grouped: Dict[object, List[Tuple[float, float, float]]] = {k: [] for k in keys}
        for rec in records:
            k = key_fn(rec)
            if k in grouped:
                grouped[k].append((rec[2], rec[3], rec[4]))

        summary: Dict[object, Dict[str, float]] = {}
        for k in keys:
            vals = grouped[k]
            if not vals:
                summary[k] = {
                    "count": 0,
                    "mean_wait_wq": float("nan"),
                    "mean_service_s": float("nan"),
                    "mean_system_w": float("nan"),
                }
            else:
                arr = np.asarray(vals, dtype=float)
                summary[k] = {
                    "count": len(vals),
                    "mean_wait_wq": float(np.mean(arr[:, 0])),
                    "mean_service_s": float(np.mean(arr[:, 1])),
                    "mean_system_w": float(np.mean(arr[:, 2])),
                }
        return summary

    @staticmethod
    def _simulate_cashier_fcfs(
        assigned_customers: List[ArrivalCustomer],
        horizon_minutes: float = BANK_MINUTES,
        include_records: bool = False,
    ) -> Dict[str, object]:
        """
        Simula un cajero individual bajo disciplina FCFS (M/M/1 independiente)
        y calcula métricas exactas respetando la Ley de Little sobre la trayectoria.
        """
        n = len(assigned_customers)
        if n == 0:
            res = {
                "total_customers": 0,
                "completed_in_shift": 0,
                "overtime_customers": 0,
                "mean_wait_wq": 0.0,
                "std_wait_wq": 0.0,
                "p95_wait_wq": 0.0,
                "max_wait_wq": 0.0,
                "prob_wq_gt_5min": 0.0,
                "mean_service_s": 0.0,
                "std_service_s": 0.0,
                "mean_system_w": 0.0,
                "std_system_w": 0.0,
                "utilization_rho": 0.0,
                "idle_pct": 100.0,
                "lq_empirical": 0.0,
                "l_empirical": 0.0,
                "horizon_effective": horizon_minutes,
                "counts_by_type": {u: 0 for u in USER_TYPES},
                "counts_by_action": {a: 0 for a in ACTION_PROBS},
                "counts_in_shift_by_type": {u: 0 for u in USER_TYPES},
            }
            if include_records:
                res["_records"] = []
            return res

        wait_times = np.empty(n, dtype=float)
        service_times = np.empty(n, dtype=float)
        system_times = np.empty(n, dtype=float)
        counts_by_type = {u: 0 for u in USER_TYPES}
        counts_by_action = {a: 0 for a in ACTION_PROBS}
        counts_in_shift_by_type = {u: 0 for u in USER_TYPES}
        records: List[Tuple[str, str, float, float, float]] = []

        free_time = 0.0
        completed_in_shift = 0

        for idx, cust in enumerate(assigned_customers):
            start_time = cust.arrival_time if cust.arrival_time >= free_time else free_time
            wait = start_time - cust.arrival_time
            end_time = start_time + cust.service_time
            free_time = end_time

            sys_time = wait + cust.service_time
            wait_times[idx] = wait
            service_times[idx] = cust.service_time
            system_times[idx] = sys_time

            if include_records:
                records.append((cust.action, cust.user_type, wait, cust.service_time, sys_time))

            counts_by_type[cust.user_type] += 1
            counts_by_action[cust.action] += 1
            if end_time <= horizon_minutes:
                completed_in_shift += 1
                counts_in_shift_by_type[cust.user_type] += 1

        horizon_eff = max(horizon_minutes, free_time)
        total_busy = float(np.sum(service_times))
        total_wait = float(np.sum(wait_times))
        total_sys = float(np.sum(system_times))

        res = {
            "total_customers": n,
            "completed_in_shift": completed_in_shift,
            "overtime_customers": n - completed_in_shift,
            "mean_wait_wq": float(np.mean(wait_times)),
            "std_wait_wq": float(np.std(wait_times, ddof=1)) if n > 1 else 0.0,
            "p95_wait_wq": float(np.percentile(wait_times, 95)),
            "max_wait_wq": float(np.max(wait_times)),
            "prob_wq_gt_5min": float(np.mean(wait_times > 5.0) * 100.0),
            "mean_service_s": float(np.mean(service_times)),
            "std_service_s": float(np.std(service_times, ddof=1)) if n > 1 else 0.0,
            "mean_system_w": float(np.mean(system_times)),
            "std_system_w": float(np.std(system_times, ddof=1)) if n > 1 else 0.0,
            "utilization_rho": total_busy / horizon_eff,
            "idle_pct": max(0.0, (1.0 - total_busy / horizon_eff) * 100.0),
            "lq_empirical": total_wait / horizon_eff,
            "l_empirical": total_sys / horizon_eff,
            "horizon_effective": horizon_eff,
            "counts_by_type": counts_by_type,
            "counts_by_action": counts_by_action,
            "counts_in_shift_by_type": counts_in_shift_by_type,
        }
        if include_records:
            res["_records"] = records
        return res

    def simulate_single_replica(
        self,
        scenario_key: str,
        arrivals: List[ArrivalCustomer],
        routing_seed: int,
        routing_mode: str = "random_mm1",
    ) -> Dict[str, object]:
        """
        Simula una réplica diaria de un escenario dado sobre la secuencia de llegadas.

        routing_mode:
          - 'random_mm1': Descomposición de Poisson (1/k entre cajeros elegibles)
            para mantener cajeros estrictamente independientes M/M/1.
          - 'shortest_queue': Join-the-Shortest-Queue (JSQ) no clarividente; el
            cliente observa únicamente cuántos usuarios están presentes (en cola o
            en servicio) en cada cajero elegible y desempata uniformemente al azar.
          - 'least_work': Cota inferior clarividente por menor tiempo de liberación.
        """
        cfg = SCENARIO_DEFINITIONS[scenario_key]
        cajeros_cfg: List[Tuple[str, str]] = cfg["cajeros"]
        num_cajeros = len(cajeros_cfg)

        queues_by_cashier: List[List[ArrivalCustomer]] = [[] for _ in range(num_cajeros)]
        departure_queues: List[deque[float]] = [deque() for _ in range(num_cajeros)]
        free_times = [0.0 for _ in range(num_cajeros)]
        eligible_indices_by_action: Dict[str, List[int]] = {
            act: [
                i for i, (_, role) in enumerate(cajeros_cfg)
                if role == "Mixto" or role == act
            ]
            for act in ACTION_PROBS
        }

        rng = np.random.default_rng(routing_seed)
        waits_by_arrival_order: List[Tuple[float, float, float]] = []

        for cust in arrivals:
            eligible = eligible_indices_by_action[cust.action]
            if len(eligible) == 1:
                chosen = eligible[0]
            elif routing_mode == "random_mm1":
                chosen = eligible[int(rng.integers(0, len(eligible)))]
            elif routing_mode == "shortest_queue":
                # Purgar salidas completadas antes de la llegada actual: complejidad O(1) amortizada
                for idx in eligible:
                    dq = departure_queues[idx]
                    while dq and dq[0] <= cust.arrival_time:
                        dq.popleft()
                min_q = min(len(departure_queues[idx]) for idx in eligible)
                tied = [idx for idx in eligible if len(departure_queues[idx]) == min_q]
                chosen = tied[0] if len(tied) == 1 else tied[int(rng.integers(0, len(tied)))]
            elif routing_mode == "least_work":
                chosen = min(eligible, key=lambda idx: (free_times[idx], idx))
            else:
                raise ValueError(f"Modo de enrutamiento desconocido: {routing_mode}")

            queues_by_cashier[chosen].append(cust)
            start_t = max(cust.arrival_time, free_times[chosen])
            wait_t = start_t - cust.arrival_time
            end_t = start_t + cust.service_time
            free_times[chosen] = end_t
            departure_queues[chosen].append(end_t)
            waits_by_arrival_order.append((cust.arrival_time, wait_t, wait_t + cust.service_time))

        cashier_results = {}
        all_records: List[Tuple[str, str, float, float, float]] = []

        for idx, (cname, role) in enumerate(cajeros_cfg):
            assigned = queues_by_cashier[idx]
            res = self._simulate_cashier_fcfs(
                assigned,
                self.model.horizon_minutes,
                include_records=True,
            )
            recs = res.pop("_records")
            all_records.extend(recs)
            res["cashier_name"] = cname
            res["role"] = role
            cashier_results[cname] = res

        all_waits = [r[2] for r in all_records]
        all_services = [r[3] for r in all_records]
        all_systems = [r[4] for r in all_records]

        actions = list(ACTION_PROBS.keys())
        profiles = [(a, u) for a in actions for u in USER_TYPES]
        metrics_by_action = self._aggregate_records(all_records, lambda r: r[0], actions)
        metrics_by_type = self._aggregate_records(all_records, lambda r: r[1], USER_TYPES)
        metrics_by_profile = self._aggregate_records(
            all_records, lambda r: (r[0], r[1]), profiles
        )

        total_customers = len(arrivals)
        completed_in_shift = sum(r["completed_in_shift"] for r in cashier_results.values())
        counts_by_type = {
            u: sum(r["counts_by_type"][u] for r in cashier_results.values())
            for u in USER_TYPES
        }
        counts_in_shift_by_type = {
            u: sum(r["counts_in_shift_by_type"][u] for r in cashier_results.values())
            for u in USER_TYPES
        }
        counts_by_action = {
            a: sum(r["counts_by_action"][a] for r in cashier_results.values())
            for a in ACTION_PROBS
        }

        min_srv_cashier = min(cashier_results.values(), key=lambda r: r["mean_service_s"])
        max_srv_cashier = max(cashier_results.values(), key=lambda r: r["mean_service_s"])
        min_sys_cashier = min(cashier_results.values(), key=lambda r: r["mean_system_w"])
        max_sys_cashier = max(cashier_results.values(), key=lambda r: r["mean_system_w"])
        max_wait_cashier = max(cashier_results.values(), key=lambda r: r["mean_wait_wq"])

        return {
            "scenario_key": scenario_key,
            "total_customers": total_customers,
            "completed_in_shift": completed_in_shift,
            "overtime_customers": total_customers - completed_in_shift,
            "counts_by_type": counts_by_type,
            "counts_in_shift_by_type": counts_in_shift_by_type,
            "counts_by_action": counts_by_action,
            "mean_wait_wq": float(np.mean(all_waits)) if all_waits else 0.0,
            "p95_wait_wq": float(np.percentile(all_waits, 95)) if all_waits else 0.0,
            "max_wait_wq": float(np.max(all_waits)) if all_waits else 0.0,
            "prob_wq_gt_5min": float(np.mean(np.asarray(all_waits) > 5.0) * 100.0) if all_waits else 0.0,
            "waits_by_arrival_order": waits_by_arrival_order,
            "mean_service_s": float(np.mean(all_services)) if all_services else 0.0,
            "mean_system_w": float(np.mean(all_systems)) if all_systems else 0.0,
            "mean_rho": float(np.mean([r["utilization_rho"] for r in cashier_results.values()])),
            "max_rho": float(np.max([r["utilization_rho"] for r in cashier_results.values()])),
            "total_lq": float(sum(r["lq_empirical"] for r in cashier_results.values())),
            "total_l": float(sum(r["l_empirical"] for r in cashier_results.values())),
            "max_cashier_wq": float(max_wait_cashier["mean_wait_wq"]),
            "bottleneck_cashier": str(max_wait_cashier["cashier_name"]),
            "min_service_cashier": str(min_srv_cashier["cashier_name"]),
            "max_service_cashier": str(max_srv_cashier["cashier_name"]),
            "min_system_cashier": str(min_sys_cashier["cashier_name"]),
            "max_system_cashier": str(max_sys_cashier["cashier_name"]),
            "metrics_by_action": metrics_by_action,
            "metrics_by_type": metrics_by_type,
            "metrics_by_profile": metrics_by_profile,
            "cashiers": cashier_results,
        }

    @staticmethod
    def _ci95(values: List[float], confidence: float = 0.95) -> Tuple[float, float, float, float]:
        """Retorna (media, desv_est, ic_inf, ic_sup) usando t de Student exacta."""
        clean = [float(v) for v in values if v is not None and not np.isnan(v)]
        arr = np.asarray(clean, dtype=float)
        n = len(arr)
        if n == 0:
            return 0.0, 0.0, 0.0, 0.0
        mean = float(np.mean(arr))
        if n == 1:
            return mean, 0.0, mean, mean
        std = float(np.std(arr, ddof=1))
        t_val = t_crit_two_sided(n - 1, confidence=confidence)
        half = t_val * std / np.sqrt(n)
        return mean, std, mean - half, mean + half

    @staticmethod
    def _required_n_for_precision(
        std: float,
        tol: float,
        pilot_n: int,
        confidence: float = 0.95,
    ) -> Tuple[int, int]:
        """
        Calcula (n_piloto, n_iterativo) usando:
          n = ceil((t_{alpha/2, df} * s / tol)^2)
        con refinamiento iterativo de los grados de libertad hasta convergencia.
        """
        if std <= 0.0 or tol <= 0.0:
            return 1, 1
        t0 = t_crit_two_sided(max(1, pilot_n - 1), confidence=confidence)
        n_pilot_est = max(2, math.ceil((t0 * std / tol) ** 2))
        n = n_pilot_est
        for _ in range(50):
            t_cur = t_crit_two_sided(max(1, n - 1), confidence=confidence)
            n_next = max(2, math.ceil((t_cur * std / tol) ** 2))
            if n_next == n:
                break
            n = n_next
        return n_pilot_est, n

    def compute_required_replicas(
        self,
        df_replicas: pd.DataFrame,
        confidence: float = 0.95,
        wq_abs_tol_min: float = 0.50,
        w_rel_tol: float = 0.05,
        users_abs_tol: float = 5.0,
    ) -> pd.DataFrame:
        """
        Determina y detalla el número mínimo de réplicas necesarias (n*) por escenario
        para alcanzar precisión estadística controlada con confianza (1 - alpha).
        """
        if df_replicas.empty:
            return pd.DataFrame()

        rows: List[Dict[str, object]] = []
        for skey, cfg in SCENARIO_DEFINITIONS.items():
            sub = df_replicas[df_replicas["escenario"] == skey]
            if sub.empty:
                continue
            n0 = len(sub)
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["espera_cola_wq_min"].tolist(), confidence)
            w_m, w_sd, w_l, w_u = self._ci95(sub["atencion_total_w_min"].tolist(), confidence)
            u_m, u_sd, u_l, u_u = self._ci95(sub["total_usuarios"].tolist(), confidence)

            w_tol_min = max(1e-6, w_rel_tol * w_m)
            n_wq_0, n_wq_it = self._required_n_for_precision(wq_sd, wq_abs_tol_min, n0, confidence)
            n_w_0, n_w_it = self._required_n_for_precision(w_sd, w_tol_min, n0, confidence)
            n_u_0, n_u_it = self._required_n_for_precision(u_sd, users_abs_tol, n0, confidence)

            wq_se = wq_sd / math.sqrt(n0)
            wq_me = 0.5 * (wq_u - wq_l)
            wq_er_pct = (wq_me / wq_m * 100.0) if wq_m > 0.0 else 0.0
            n_wq_er10_prof = max(2, math.ceil(n0 * ((wq_er_pct / 10.0) ** 2))) if wq_er_pct > 0 else 2

            w_se = w_sd / math.sqrt(n0)
            w_me = 0.5 * (w_u - w_l)
            w_er_pct = (w_me / w_m * 100.0) if w_m > 0.0 else 0.0
            n_w_er5_prof = max(2, math.ceil(n0 * ((w_er_pct / 5.0) ** 2))) if w_er_pct > 0 else 2

            u_me = 0.5 * (u_u - u_l)
            u_er_pct = (u_me / u_m * 100.0) if u_m > 0.0 else 0.0

            rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "replicas_piloto_n0": n0,
                "t_crit_piloto_95": t_crit_two_sided(max(1, n0 - 1), confidence=confidence),
                "wq_media_min": wq_m,
                "wq_sd_min": wq_sd,
                "wq_se_min": wq_se,
                "wq_semiamp_ic95_min": wq_me,
                "wq_ancho_ic95_min": 2.0 * wq_me,
                "wq_er_piloto_pct": wq_er_pct,
                "n_req_wq_er10_prof": n_wq_er10_prof,
                "tol_wq_min": wq_abs_tol_min,
                "n_req_wq_piloto": n_wq_0,
                "n_req_wq_iterativo": n_wq_it,
                "w_media_min": w_m,
                "w_sd_min": w_sd,
                "w_se_min": w_se,
                "w_semiamp_ic95_min": w_me,
                "w_er_piloto_pct": w_er_pct,
                "n_req_w_er5_prof": n_w_er5_prof,
                "tol_w_rel_5pct_min": w_tol_min,
                "n_req_w_piloto": n_w_0,
                "n_req_w_iterativo": n_w_it,
                "usuarios_media_dia": u_m,
                "usuarios_sd_dia": u_sd,
                "usuarios_semiamp_ic95": u_me,
                "usuarios_er_piloto_pct": u_er_pct,
                "tol_usuarios": users_abs_tol,
                "n_req_usuarios_iterativo": n_u_it,
                "n_req_global_max": max(n_wq_it, n_w_it, n_u_it),
            })
        return pd.DataFrame(rows)

    def _summarize_wait_dimension(
        self,
        raw_df: pd.DataFrame,
        group_cols: List[str],
    ) -> pd.DataFrame:
        """Resume tiempos Wq, S y W con desviación e IC95% t de Student por subgrupo."""
        if raw_df.empty:
            return pd.DataFrame()
        rows: List[Dict[str, object]] = []
        for keys, sub in raw_df.groupby(group_cols, sort=False):
            key_tuple = keys if isinstance(keys, tuple) else (keys,)
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["wq_min"].tolist())
            s_m, s_sd, _, _ = self._ci95(sub["s_min"].tolist())
            w_m, w_sd, w_l, w_u = self._ci95(sub["w_min"].tolist())
            u_m, u_sd, _, _ = self._ci95(sub["usuarios"].tolist())
            row: Dict[str, object] = dict(zip(group_cols, key_tuple))
            row.update({
                "usuarios_dia_prom": u_m,
                "usuarios_dia_sd": u_sd,
                "wq_media_min": wq_m,
                "wq_sd_min": wq_sd,
                "wq_ic95_inf": wq_l,
                "wq_ic95_sup": wq_u,
                "s_media_min": s_m,
                "s_sd_min": s_sd,
                "w_media_min": w_m,
                "w_sd_min": w_sd,
                "w_ic95_inf": w_l,
                "w_ic95_sup": w_u,
            })
            rows.append(row)
        return pd.DataFrame(rows)

    def run_multi_replica_experiment(
        self,
        num_replicas: int = 10,
        base_seed: int = 42,
        routing_mode: str = "random_mm1",
        independent_arrivals_per_scenario: bool = False,
    ) -> Dict[str, object]:
        """
        Ejecuta `num_replicas` corridas completas para todos los escenarios definidos.

        Si `independent_arrivals_per_scenario=False` (por defecto), usa Números Aleatorios
        Comunes (CRN) por réplica para que la comparación entre configuraciones de cajas
        no tenga sesgo muestral de llegadas.
        """
        scenario_keys = list(SCENARIO_DEFINITIONS.keys())
        replica_rows: List[Dict[str, object]] = []
        cashier_rows: List[Dict[str, object]] = []
        subtype_rows: List[Dict[str, object]] = []
        wait_action_rows: List[Dict[str, object]] = []
        wait_type_rows: List[Dict[str, object]] = []
        wait_profile_rows: List[Dict[str, object]] = []

        # Almacenar flujos base de llegadas por réplica
        shared_arrivals: Dict[int, List[ArrivalCustomer]] = {}
        if not independent_arrivals_per_scenario:
            for r in range(1, num_replicas + 1):
                shared_arrivals[r] = self.model.generate_day_arrivals(seed=base_seed + r)

        for s_idx, skey in enumerate(scenario_keys):
            cfg = SCENARIO_DEFINITIONS[skey]
            for r in range(1, num_replicas + 1):
                if independent_arrivals_per_scenario:
                    arrivals = self.model.generate_day_arrivals(seed=base_seed + s_idx * 1000 + r)
                else:
                    arrivals = shared_arrivals[r]

                r_seed = base_seed * 100 + s_idx * 1000 + r
                sim_res = self.simulate_single_replica(
                    scenario_key=skey,
                    arrivals=arrivals,
                    routing_seed=r_seed,
                    routing_mode=routing_mode,
                )

                act_m = sim_res["metrics_by_action"]
                row = {
                    "escenario": skey,
                    "nombre_escenario": cfg["nombre"],
                    "nombre_corto": cfg["nombre_corto"],
                    "num_cajeros": cfg["num_cajeros"],
                    "replica": r,
                    "total_usuarios": sim_res["total_customers"],
                    "atendidos_en_turno_480m": sim_res["completed_in_shift"],
                    "usuarios_fuera_turno": sim_res["overtime_customers"],
                    "retiros": sim_res["counts_by_action"]["Retiro"],
                    "pagos": sim_res["counts_by_action"]["Pago"],
                    "rapido": sim_res["counts_by_type"]["Rápido"],
                    "normal": sim_res["counts_by_type"]["Normal"],
                    "lento": sim_res["counts_by_type"]["Lento"],
                    "muy_lento": sim_res["counts_by_type"]["Muy lento"],
                    "rapido_en_turno": sim_res["counts_in_shift_by_type"]["Rápido"],
                    "normal_en_turno": sim_res["counts_in_shift_by_type"]["Normal"],
                    "lento_en_turno": sim_res["counts_in_shift_by_type"]["Lento"],
                    "muy_lento_en_turno": sim_res["counts_in_shift_by_type"]["Muy lento"],
                    "espera_cola_wq_min": sim_res["mean_wait_wq"],
                    "wq_retiro_min": act_m["Retiro"]["mean_wait_wq"],
                    "wq_pago_min": act_m["Pago"]["mean_wait_wq"],
                    "espera_p95_min": sim_res["p95_wait_wq"],
                    "espera_max_min": sim_res["max_wait_wq"],
                    "prob_espera_mayor_5m_pct": sim_res["prob_wq_gt_5min"],
                    "servicio_medio_s_min": sim_res["mean_service_s"],
                    "atencion_total_w_min": sim_res["mean_system_w"],
                    "w_retiro_min": act_m["Retiro"]["mean_system_w"],
                    "w_pago_min": act_m["Pago"]["mean_system_w"],
                    "utilizacion_media_rho": sim_res["mean_rho"],
                    "utilizacion_max_rho": sim_res["max_rho"],
                    "cola_media_lq": sim_res["total_lq"],
                    "sistema_medio_l": sim_res["total_l"],
                    "peor_wq_cajero_min": sim_res["max_cashier_wq"],
                    "cajero_cuello_botella": sim_res["bottleneck_cashier"],
                    "cajero_menor_servicio": sim_res["min_service_cashier"],
                    "cajero_mayor_servicio": sim_res["max_service_cashier"],
                    "cajero_menor_atencion_total": sim_res["min_system_cashier"],
                    "cajero_mayor_atencion_total": sim_res["max_system_cashier"],
                }
                replica_rows.append(row)

                for act, mvals in act_m.items():
                    wait_action_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "accion": act,
                        "usuarios": mvals["count"],
                        "wq_min": mvals["mean_wait_wq"],
                        "s_min": mvals["mean_service_s"],
                        "w_min": mvals["mean_system_w"],
                    })

                for utype, mvals in sim_res["metrics_by_type"].items():
                    wait_type_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "tipo_usuario": utype,
                        "usuarios": mvals["count"],
                        "wq_min": mvals["mean_wait_wq"],
                        "s_min": mvals["mean_service_s"],
                        "w_min": mvals["mean_system_w"],
                    })

                for (act, utype), mvals in sim_res["metrics_by_profile"].items():
                    wait_profile_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "accion": act,
                        "tipo_usuario": utype,
                        "usuarios": mvals["count"],
                        "wq_min": mvals["mean_wait_wq"],
                        "s_min": mvals["mean_service_s"],
                        "w_min": mvals["mean_system_w"],
                    })

                for cname, cres in sim_res["cashiers"].items():
                    cashier_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "cajero": cname,
                        "rol": cres["role"],
                        "usuarios_atendidos": cres["total_customers"],
                        "atendidos_en_turno": cres["completed_in_shift"],
                        "retiros": cres["counts_by_action"]["Retiro"],
                        "pagos": cres["counts_by_action"]["Pago"],
                        "rapido": cres["counts_by_type"]["Rápido"],
                        "normal": cres["counts_by_type"]["Normal"],
                        "lento": cres["counts_by_type"]["Lento"],
                        "muy_lento": cres["counts_by_type"]["Muy lento"],
                        "servicio_medio_s_min": cres["mean_service_s"],
                        "espera_cola_wq_min": cres["mean_wait_wq"],
                        "atencion_total_w_min": cres["mean_system_w"],
                        "espera_max_min": cres["max_wait_wq"],
                        "prob_espera_mayor_5m_pct": cres["prob_wq_gt_5min"],
                        "utilizacion_rho": cres["utilization_rho"],
                        "ocio_pct": cres["idle_pct"],
                        "cola_media_lq": cres["lq_empirical"],
                    })

                if skey == "E1_3_Mixtas":
                    # Desglose de los 8 perfiles (acción x tipo) en el flujo real
                    counts_8 = {
                        (act, u): 0 for act in ACTION_PROBS for u in USER_TYPES
                    }
                    for cust in arrivals:
                        counts_8[(cust.action, cust.user_type)] += 1
                    for (act, u), cnt in counts_8.items():
                        subtype_rows.append({
                            "replica": r,
                            "accion": act,
                            "tipo_usuario": u,
                            "cantidad": cnt,
                            "proporcion_empirica": cnt / len(arrivals) if arrivals else 0.0,
                        })

        df_replicas = pd.DataFrame(replica_rows)
        df_cashiers = pd.DataFrame(cashier_rows)
        df_subtypes = pd.DataFrame(subtype_rows)

        df_wait_by_action = self._summarize_wait_dimension(
            pd.DataFrame(wait_action_rows), ["escenario", "nombre_corto", "accion"]
        )
        df_wait_by_type = self._summarize_wait_dimension(
            pd.DataFrame(wait_type_rows), ["escenario", "nombre_corto", "tipo_usuario"]
        )
        df_wait_profiles = self._summarize_wait_dimension(
            pd.DataFrame(wait_profile_rows),
            ["escenario", "nombre_corto", "accion", "tipo_usuario"],
        )
        df_sample_size = self.compute_required_replicas(df_replicas)

        # Resumen consolidado por escenario (empírico + IC95% + teórico M/M/1 y M/G/1)
        summary_rows: List[Dict[str, object]] = []
        for skey in scenario_keys:
            sub = df_replicas[df_replicas["escenario"] == skey]
            theo = self.model.analyze_scenario_theoretically(skey)
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["espera_cola_wq_min"].tolist())
            wqr_m, _, _, _ = self._ci95(sub["wq_retiro_min"].tolist())
            wqp_m, _, _, _ = self._ci95(sub["wq_pago_min"].tolist())
            w_m, w_sd, w_l, w_u = self._ci95(sub["atencion_total_w_min"].tolist())
            s_m, s_sd, _, _ = self._ci95(sub["servicio_medio_s_min"].tolist())
            rho_m, rho_sd, _, _ = self._ci95(sub["utilizacion_media_rho"].tolist())
            pwq_m, pwq_sd, _, _ = self._ci95(sub["peor_wq_cajero_min"].tolist())
            usr_m, usr_sd, _, _ = self._ci95(sub["total_usuarios"].tolist())
            turn_m, turn_sd, _, _ = self._ci95(sub["atendidos_en_turno_480m"].tolist())

            summary_rows.append({
                "escenario": skey,
                "nombre_escenario": theo["nombre"],
                "nombre_corto": theo["nombre_corto"],
                "num_cajeros": theo["num_cajeros"],
                "replicas": num_replicas,
                "usuarios_promedio_dia": usr_m,
                "usuarios_sd": usr_sd,
                "atendidos_en_turno_prom": turn_m,
                "atendidos_en_turno_sd": turn_sd,
                "espera_wq_media_min": wq_m,
                "espera_wq_sd_min": wq_sd,
                "espera_wq_se_min": wq_sd / np.sqrt(num_replicas) if num_replicas > 0 else 0.0,
                "espera_wq_ic95_inf": wq_l,
                "espera_wq_ic95_sup": wq_u,
                "espera_wq_er_pct": ((0.5 * (wq_u - wq_l)) / wq_m * 100.0) if wq_m > 0.0 else 0.0,
                "wq_retiro_media_min": wqr_m,
                "wq_pago_media_min": wqp_m,
                "peor_cajero_wq_media_min": pwq_m,
                "peor_cajero_wq_sd_min": pwq_sd,
                "prob_wq_mayor_5m_pct": float(sub["prob_espera_mayor_5m_pct"].mean()),
                "prob_wq_mayor_5m_teorica_pct": theo["weighted_prob_wq_gt_5min"] * 100.0,
                "servicio_s_media_min": s_m,
                "servicio_s_sd_min": s_sd,
                "sistema_w_media_min": w_m,
                "sistema_w_sd_min": w_sd,
                "sistema_w_se_min": w_sd / np.sqrt(num_replicas) if num_replicas > 0 else 0.0,
                "sistema_w_ic95_inf": w_l,
                "sistema_w_ic95_sup": w_u,
                "sistema_w_er_pct": ((0.5 * (w_u - w_l)) / w_m * 100.0) if w_m > 0.0 else 0.0,
                "utilizacion_rho_media": rho_m,
                "utilizacion_rho_sd": rho_sd,
                "utilizacion_max_media": float(sub["utilizacion_max_rho"].mean()),
                "regimen_estabilidad": classify_utilization_regime(float(sub["utilizacion_max_rho"].mean())),
                "regimen_estabilidad_teorico": theo["regime_max_rho"],
                "lq_total_simulada": float(sub["cola_media_lq"].mean()),
                "l_total_simulada": float(sub["sistema_medio_l"].mean()),
                "wq_teorica_mm1_min": theo["weighted_wq_mm1"],
                "wq_teorica_mg1_min": theo["weighted_wq_mg1"],
                "w_teorica_mm1_min": theo["weighted_w_mm1"],
                "rho_teorica_media": theo["mean_rho"],
                "rho_teorica_max": theo["max_rho"],
                "peor_wq_teorica_mm1_min": theo["max_wq_mm1"],
            })

        df_summary = pd.DataFrame(summary_rows)

        # Resumen por cajero en cada escenario
        df_cashier_summary = (
            df_cashiers.groupby(["escenario", "nombre_corto", "cajero", "rol"], sort=False)
            .agg(
                usuarios_prom=("usuarios_atendidos", "mean"),
                usuarios_sd=("usuarios_atendidos", "std"),
                usuarios_min=("usuarios_atendidos", "min"),
                usuarios_max=("usuarios_atendidos", "max"),
                retiros_prom=("retiros", "mean"),
                pagos_prom=("pagos", "mean"),
                rapido_prom=("rapido", "mean"),
                normal_prom=("normal", "mean"),
                lento_prom=("lento", "mean"),
                muy_lento_prom=("muy_lento", "mean"),
                servicio_s_prom=("servicio_medio_s_min", "mean"),
                servicio_s_sd=("servicio_medio_s_min", "std"),
                espera_wq_prom=("espera_cola_wq_min", "mean"),
                espera_wq_sd=("espera_cola_wq_min", "std"),
                atencion_w_prom=("atencion_total_w_min", "mean"),
                atencion_w_sd=("atencion_total_w_min", "std"),
                prob_wq_mayor_5m_prom=("prob_espera_mayor_5m_pct", "mean"),
                utilizacion_rho_prom=("utilizacion_rho", "mean"),
                ocio_pct_prom=("ocio_pct", "mean"),
                lq_prom=("cola_media_lq", "mean"),
            )
            .reset_index()
        )

        return {
            "num_replicas": num_replicas,
            "routing_mode": routing_mode,
            "df_replicas": df_replicas,
            "df_cashiers": df_cashiers,
            "df_subtypes": df_subtypes,
            "df_wait_by_action": df_wait_by_action,
            "df_wait_by_type": df_wait_by_type,
            "df_wait_profiles": df_wait_profiles,
            "df_sample_size": df_sample_size,
            "df_summary": df_summary,
            "df_cashier_summary": df_cashier_summary,
        }

    def analyze_warmup_and_steady_state(
        self,
        num_replicas: int = 100,
        base_seed: int = 42,
        window: int = 15,
        k_horizon: int = 160,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Identifica el período transitorio (warm-up desde arranque en vacío L(0)=0)
        mediante promedios móviles transversales y mínima varianza móvil por ventana,
        comparando estadísticas con transitorio vs. estado estable (Semana 7).
        """
        shared_arrivals = {
            r: self.model.generate_day_arrivals(seed=base_seed + r)
            for r in range(1, num_replicas + 1)
        }
        summary_rows: List[Dict[str, object]] = []
        curve_e1_rows: List[Dict[str, object]] = []

        for s_idx, (skey, cfg) in enumerate(SCENARIO_DEFINITIONS.items()):
            theo = self.model.analyze_scenario_theoretically(skey)
            mat_arr = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            mat_wq = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            mat_w = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            rep_seqs: List[List[Tuple[float, float, float]]] = []

            for r in range(1, num_replicas + 1):
                arrivals = shared_arrivals[r]
                r_seed = base_seed * 100 + s_idx * 1000 + r
                sim_res = self.simulate_single_replica(
                    scenario_key=skey,
                    arrivals=arrivals,
                    routing_seed=r_seed,
                    routing_mode="random_mm1",
                )
                seq = sim_res["waits_by_arrival_order"]
                rep_seqs.append(seq)
                lim = min(k_horizon, len(seq))
                for idx in range(lim):
                    mat_arr[r - 1, idx] = seq[idx][0]
                    mat_wq[r - 1, idx] = seq[idx][1]
                    mat_w[r - 1, idx] = seq[idx][2]

            wq_cross = np.nanmean(mat_wq, axis=0)
            arr_cross = np.nanmean(mat_arr, axis=0)

            mov_avgs = [
                float(np.mean(wq_cross[i:i + window]))
                for i in range(len(wq_cross) - window + 1)
            ]
            # Ventana candidata en el primer tercio de la jornada para detectar el fin del arranque vacío
            cand_indices = []
            cand_vars = []
            for i in range(max(0, 20 - window), min(len(mov_avgs) - window + 1, 66 - window + 1)):
                k_cand = i + window
                if 20 <= k_cand <= 65:
                    cand_indices.append(k_cand)
                    cand_vars.append(float(np.var(mov_avgs[i:i + window])))

            if cand_vars:
                k_cut = cand_indices[int(np.argmin(cand_vars))]
            else:
                k_cut = 30

            t_cut_min = float(arr_cross[k_cut - 1])
            wq_all_reps = [float(np.mean([x[1] for x in seq])) for seq in rep_seqs if seq]
            w_all_reps = [float(np.mean([x[2] for x in seq])) for seq in rep_seqs if seq]
            wq_ss_reps = [
                float(np.mean([x[1] for x in seq[k_cut - 1:]]))
                for seq in rep_seqs
                if len(seq) >= k_cut
            ]
            w_ss_reps = [
                float(np.mean([x[2] for x in seq[k_cut - 1:]]))
                for seq in rep_seqs
                if len(seq) >= k_cut
            ]

            wq_all_m = float(np.mean(wq_all_reps))
            wq_ss_m = float(np.mean(wq_ss_reps))
            n_ss_reps = len(wq_ss_reps)
            wq_ss_sd = float(np.std(wq_ss_reps, ddof=1)) if n_ss_reps > 1 else 0.0
            wq_ss_se = wq_ss_sd / float(np.sqrt(n_ss_reps)) if n_ss_reps > 0 else 0.0
            w_all_m = float(np.mean(w_all_reps))
            w_ss_m = float(np.mean(w_ss_reps))
            sesgo_pct = ((wq_ss_m - wq_all_m) / wq_ss_m * 100.0) if wq_ss_m > 0 else 0.0

            summary_rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "k_corte_clientes": k_cut,
                "tiempo_corte_aprox_min": t_cut_min,
                "wq_con_transitorio_min": wq_all_m,
                "wq_estado_estable_min": wq_ss_m,
                "wq_estado_estable_sd_min": wq_ss_sd,
                "wq_estado_estable_se_min": wq_ss_se,
                "n_replicas_estado_estable": n_ss_reps,
                "wq_teorica_mg1_min": theo["weighted_wq_mg1"],
                "w_con_transitorio_min": w_all_m,
                "w_estado_estable_min": w_ss_m,
                "sesgo_transitorio_wq_pct": sesgo_pct,
            })

            if skey == "E1_3_Mixtas":
                for idx in range(k_horizon):
                    ma_val = (
                        float(np.mean(wq_cross[max(0, idx - window + 1):idx + 1]))
                        if idx >= window - 1
                        else float(np.mean(wq_cross[:idx + 1]))
                    )
                    curve_e1_rows.append({
                        "cliente_idx": idx + 1,
                        "tiempo_medio_llegada_min": float(arr_cross[idx]),
                        "wq_media_transversal_min": float(wq_cross[idx]),
                        "wq_promedio_movil_min": ma_val,
                        "en_estado_estable": (idx + 1) >= k_cut,
                    })

        return pd.DataFrame(summary_rows), pd.DataFrame(curve_e1_rows)

    def compute_vv_and_critical_matrix(
        self,
        res_10: Dict[str, object],
        res_mc: Dict[str, object],
        df_warmup: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Consolida la matriz de Verificación, Calibración y Validación (V&V)
        y clasifica cada escenario frente a los valores aceptables y críticos del curso.
        """
        df_mc_sum = res_mc["df_summary"].set_index("escenario")
        df_mc_caj = res_mc["df_cashier_summary"]
        df_warm_idx = df_warmup.set_index("escenario")

        # 1. Verificación exacta de Ley de Little sobre trayectoria completa en cada escenario
        arrivals_ref = self.model.generate_day_arrivals(seed=42)
        little_ok_map: Dict[str, bool] = {}
        for s_idx, skey in enumerate(SCENARIO_DEFINITIONS):
            sim_ref = self.simulate_single_replica(skey, arrivals_ref, routing_seed=4200 + s_idx * 1000 + 1)
            max_err = max(
                abs(c["lq_empirical"] - (c["total_customers"] / c["horizon_effective"]) * c["mean_wait_wq"])
                for c in sim_ref["cashiers"].values()
                if c["total_customers"] > 0
            )
            little_ok_map[skey] = max_err < 1e-10

        # 2. Calibración: error absoluto medio en puntos porcentuales sobre los 8 perfiles
        joint_p = self.model.joint_profile_probabilities()
        df_sub100 = res_mc["df_subtypes"]
        calib_sub = df_sub100.groupby(["accion", "tipo_usuario"], sort=False)["proporcion_empirica"].mean()
        calib_err_pct = float(
            np.mean([
                abs(float(calib_sub.loc[(act, u)]) - joint_p[(act, u)]) * 100.0
                for act, u in joint_p
            ])
        )

        # 3. Evaluación V&V y criterios críticos por escenario
        rows: List[Dict[str, object]] = []
        for skey, cfg in SCENARIO_DEFINITIONS.items():
            r_sum = df_mc_sum.loc[skey]
            w_row = df_warm_idx.loc[skey]
            c_sub = df_mc_caj[df_mc_caj["escenario"] == skey]

            n_mc = int(r_sum["replicas"])
            wq_sim = float(r_sum["espera_wq_media_min"])
            wq_ss = float(w_row["wq_estado_estable_min"])
            wq_mg1 = float(r_sum["wq_teorica_mg1_min"])
            wq_ss_se = float(w_row["wq_estado_estable_se_min"])
            n_ss = int(w_row.get("n_replicas_estado_estable", n_mc))
            w_sim = float(r_sum["sistema_w_media_min"])
            peor_wq = float(r_sum["peor_cajero_wq_media_min"])
            rho_med = float(r_sum["utilizacion_rho_media"]) * 100.0
            rho_max = float(r_sum["utilizacion_max_media"]) * 100.0
            prob_gt5_global = float(r_sum["prob_wq_mayor_5m_pct"])
            prob_gt5_peor = float(c_sub["prob_wq_mayor_5m_prom"].max())

            # Prueba t de Student frente a referencia teórica Pollaczek-Khinchine M/G/1
            # usando el error estándar del estimador estacionario (post-warmup)
            t_stat = (wq_ss - wq_mg1) / wq_ss_se if wq_ss_se > 0 else 0.0
            df_t = max(1, n_ss - 1)
            p_val = _betainc(0.5 * df_t, 0.5, df_t / (df_t + t_stat * t_stat))

            if peor_wq > 5.5 or wq_sim > 5.0:
                crit_wq = "Crítico (>5m)"
            elif wq_sim <= 3.0 and peor_wq <= 5.0:
                crit_wq = "Óptimo (<3m)"
            else:
                crit_wq = "Aceptable (<=5m)"

            crit_w = "Aceptable (<=8m)" if w_sim <= 8.0 else "Crítico (>8m)"
            crit_rho = classify_utilization_regime(rho_max / 100.0)
            crit_prob5 = "Aceptable (<=20%)" if prob_gt5_peor <= 20.0 else "Crítico (>20%)"

            if "Crítico" in crit_wq or "Crítico" in crit_w:
                dictamen = "NO RECOMENDADO: viola umbrales críticos de espera en servidor cuello de botella"
            elif "Subutilizado" in crit_rho:
                dictamen = "REDUNDANTE: cumple esperas con subutilización elevada y sobrecosto de posición"
            elif "Crítico" in crit_prob5:
                dictamen = (
                    "RECOMENDADO CON MITIGACIÓN JSQ: cumple Wq<=5m y W<=8m sin saturación, "
                    "pero P(Wq>5m) supera levemente el 20% bajo cola aleatoria"
                )
            else:
                dictamen = "ÓPTIMO: cumple todas las metas de espera, riesgo P(Wq>5m) y utilización"

            rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "verificacion_little_ok": little_ok_map[skey],
                "calibracion_mae_prop_pct": calib_err_pct,
                "wq_sim_100_min": wq_sim,
                "wq_estable_min": wq_ss,
                "wq_teorica_mg1_min": wq_mg1,
                "t_stat_vs_mg1": t_stat,
                "p_valor_vs_mg1": p_val,
                "wq_er_100_pct": float(r_sum["espera_wq_er_pct"]),
                "w_sim_100_min": w_sim,
                "w_er_100_pct": float(r_sum["sistema_w_er_pct"]),
                "peor_cajero_wq_min": peor_wq,
                "rho_media_pct": rho_med,
                "rho_max_pct": rho_max,
                "prob_wq_mayor_5m_global_pct": prob_gt5_global,
                "prob_wq_mayor_5m_peor_cajero_pct": prob_gt5_peor,
                "criterio_wq": crit_wq,
                "criterio_w": crit_w,
                "criterio_rho": crit_rho,
                "criterio_prob_wq_5m": crit_prob5,
                "dictamen_global": dictamen,
            })

        return pd.DataFrame(rows)
