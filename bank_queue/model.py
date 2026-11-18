"""
Modelo Teórico M/M/1, Parametrización Axiomática y Generador de Llegadas
para el Sistema de Cajeros del Banco de Colombia.

Cumple exactamente con las Tablas 1 y 2 de la Actividad Didáctica 2-M3:
- Jornada operativa: 8 horas diarias (480 minutos).
- Proporción de acciones: 70 % Retiros, 30 % Consignaciones o pagos.
- Cajeros independientes modelados como sistemas de colas M/M/1.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


BANK_HOURS: float = 8.0
BANK_MINUTES: float = BANK_HOURS * 60.0  # 480.0 minutos

ACTION_PROBS: Dict[str, float] = {
    "Retiro": 0.70,
    "Pago": 0.30,
}

ACTION_LABELS: Dict[str, str] = {
    "Retiro": "Retiro",
    "Pago": "Consignación o pago",
}

USER_TYPES: List[str] = ["Rápido", "Normal", "Lento", "Muy lento"]

# Tabla 1: Exponencial de uso del servicio (media en minutos)
SERVICE_MEANS: Dict[str, Dict[str, float]] = {
    "Retiro": {
        "Rápido": 1.0,
        "Normal": 2.0,
        "Lento": 3.0,
        "Muy lento": 4.0,
    },
    "Pago": {
        "Rápido": 3.0,
        "Normal": 3.0,
        "Lento": 5.0,
        "Muy lento": 7.0,
    },
}

# Tabla 1: Exponencial de media de llegada (media en minutos)
ARRIVAL_MEANS: Dict[str, Dict[str, float]] = {
    "Retiro": {
        "Rápido": 1.0,
        "Normal": 2.0,
        "Lento": 3.0,
        "Muy lento": 3.0,
    },
    "Pago": {
        "Rápido": 1.0,
        "Normal": 2.0,
        "Lento": 3.0,
        "Muy lento": 4.0,
    },
}

# Tabla 2: Probabilidades condicionales de los tipos de usuario según acción
USER_TYPE_PROBS: Dict[str, Dict[str, float]] = {
    "Retiro": {
        "Rápido": 0.23,
        "Normal": 0.40,
        "Lento": 0.17,
        "Muy lento": 0.20,
    },
    "Pago": {
        "Rápido": 0.10,
        "Normal": 0.20,
        "Lento": 0.30,
        "Muy lento": 0.40,
    },
}

# Escenarios evaluados conforme al enunciado y la sesión de clase (Semana 6)
SCENARIO_DEFINITIONS: Dict[str, Dict[str, object]] = {
    "E1_3_Mixtas": {
        "nombre": "Escenario 1: 3 Cajas Mixtas (Baseline)",
        "nombre_corto": "3 Mixtas",
        "num_cajeros": 3,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
        ],
        "descripcion": "Configuración base actual: 3 cajeros multifunción para retiros y pagos.",
    },
    "E2_1R_2P": {
        "nombre": "Escenario 2: 1 Caja Retiros + 2 Cajas Pagos",
        "nombre_corto": "1R + 2P",
        "num_cajeros": 3,
        "cajeros": [
            ("Cajero 1 (Retiro)", "Retiro"),
            ("Cajero 2 (Pago)", "Pago"),
            ("Cajero 3 (Pago)", "Pago"),
        ],
        "descripcion": "Especialización con 1 cajero exclusivo de retiros y 2 exclusivos de pagos.",
    },
    "E3_2R_1P": {
        "nombre": "Escenario 3: 2 Cajas Retiros + 1 Caja Pagos",
        "nombre_corto": "2R + 1P",
        "num_cajeros": 3,
        "cajeros": [
            ("Cajero 1 (Retiro)", "Retiro"),
            ("Cajero 2 (Retiro)", "Retiro"),
            ("Cajero 3 (Pago)", "Pago"),
        ],
        "descripcion": "Especialización con 2 cajeros exclusivos de retiros y 1 exclusivo de pagos.",
    },
    "E4a_4_Mixtas": {
        "nombre": "Escenario 4A: 4 Cajas Mixtas (Nuevo Cajero)",
        "nombre_corto": "4 Mixtas",
        "num_cajeros": 4,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
            ("Cajero 4", "Mixto"),
        ],
        "descripcion": "Ampliación a 4 cajeros multifunción para evaluar reducción de espera.",
    },
    "E4b_2R_2P": {
        "nombre": "Escenario 4B: 2 Cajas Retiros + 2 Cajas Pagos (Nuevo Cajero)",
        "nombre_corto": "2R + 2P",
        "num_cajeros": 4,
        "cajeros": [
            ("Cajero 1 (Retiro)", "Retiro"),
            ("Cajero 2 (Retiro)", "Retiro"),
            ("Cajero 3 (Pago)", "Pago"),
            ("Cajero 4 (Pago)", "Pago"),
        ],
        "descripcion": "Ampliación a 4 cajeros con balance especializado (2 retiros, 2 pagos).",
    },
}


@dataclass(frozen=True)
class ArrivalCustomer:
    """Representa un cliente individual que arriba a la sucursal bancaria."""

    customer_id: int
    arrival_time: float
    interarrival_time: float
    action: str
    user_type: str
    service_time: float


@dataclass(frozen=True)
class MM1AnalyticalMetrics:
    """Métricas analíticas exactas de estado estable para un servidor M/M/1 (y referencia M/G/1)."""

    role: str
    lam: float                     # Tasa de llegadas (clientes/min)
    mu: float                      # Tasa de servicio (clientes/min)
    rho: float                     # Factor de utilización (lambda / mu)
    p0: float                      # Probabilidad de sistema vacío (1 - rho)
    mean_service: float            # E[S] = 1/mu (min)
    mean_s2: float                 # Segundo momento E[S^2] (min^2)
    l_system: float                # Número promedio en el sistema (L)
    lq_queue: float                # Número promedio en la cola (Lq)
    w_system: float                # Tiempo promedio en el sistema (W)
    wq_queue: float                # Tiempo promedio de espera en cola M/M/1 (Wq)
    wq_mg1: float                  # Tiempo promedio de espera Pollaczek-Khinchine M/G/1 (min)
    stable: bool                   # True si rho < 1
    prob_wq_gt_5min: float = 0.0   # P(Wq > 5 min) en M/M/1 = rho * exp(-(mu - lam) * 5)


def classify_utilization_regime(rho: float) -> str:
    """Clasifica el factor de utilización rho según los umbrales operativos del curso."""
    if rho < 0.50:
        return "Subutilizado (<50%)"
    if rho < 0.70:
        return "Moderado-Óptimo (50%-70%)"
    if rho < 0.85:
        return "Alta Utilización (70%-85%)"
    if rho < 1.00:
        return "Crítico / Saturación (85%-100%)"
    return "Inestable (>=100%)"


class BankQueuingModel:
    """
    Motor analítico y generador estocástico para el problema bancario del Banco de Colombia.
    Valida restricciones probabilísticas de Kolmogorov y calcula propiedades teóricas M/M/1.
    """

    def __init__(
        self,
        action_probs: Dict[str, float] = None,
        service_means: Dict[str, Dict[str, float]] = None,
        arrival_means: Dict[str, Dict[str, float]] = None,
        user_type_probs: Dict[str, Dict[str, float]] = None,
        horizon_minutes: float = BANK_MINUTES,
    ):
        self.action_probs = dict(action_probs or ACTION_PROBS)
        self.service_means = {k: dict(v) for k, v in (service_means or SERVICE_MEANS).items()}
        self.arrival_means = {k: dict(v) for k, v in (arrival_means or ARRIVAL_MEANS).items()}
        self.user_type_probs = {k: dict(v) for k, v in (user_type_probs or USER_TYPE_PROBS).items()}
        self.horizon_minutes = float(horizon_minutes)
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Verifica no-negatividad y suma unitaria en distribuciones de probabilidad."""
        if self.horizon_minutes <= 0:
            raise ValueError("El horizonte operativo debe ser positivo.")

        total_action_prob = sum(self.action_probs.values())
        if not np.isclose(total_action_prob, 1.0, atol=1e-9):
            raise ValueError(f"Las probabilidades de acción deben sumar 1.0 (actual: {total_action_prob}).")

        for action, p in self.action_probs.items():
            if p < 0:
                raise ValueError(f"Probabilidad negativa para acción {action}.")
            probs = self.user_type_probs[action]
            if any(v < 0 for v in probs.values()):
                raise ValueError(f"Probabilidad negativa en tabla de {action}.")
            if not np.isclose(sum(probs.values()), 1.0, atol=1e-9):
                raise ValueError(f"Las probabilidades de {action} deben sumar 1.0.")
            for utype in USER_TYPES:
                if self.service_means[action][utype] <= 0 or self.arrival_means[action][utype] <= 0:
                    raise ValueError(f"Medias exponenciales inválidas para {action}-{utype}.")

    def joint_profile_probabilities(self) -> Dict[Tuple[str, str], float]:
        """Probabilidad conjunta P(acción, tipo_usuario) de los 8 perfiles."""
        joint: Dict[Tuple[str, str], float] = {}
        for action, p_act in self.action_probs.items():
            for utype in USER_TYPES:
                joint[(action, utype)] = p_act * self.user_type_probs[action][utype]
        return joint

    def marginal_user_type_probabilities(self) -> Dict[str, float]:
        """Probabilidad marginal P(tipo_usuario) agregada sobre retiros y pagos."""
        joint = self.joint_profile_probabilities()
        return {
            utype: sum(joint[(action, utype)] for action in self.action_probs)
            for utype in USER_TYPES
        }

    def expected_interarrival_time(self, action: str = "Mixto") -> float:
        """Calcula el tiempo medio teórico entre llegadas E[IA] (min)."""
        if action == "Mixto":
            return sum(
                p_act * self.expected_interarrival_time(act)
                for act, p_act in self.action_probs.items()
            )
        return sum(
            self.user_type_probs[action][u] * self.arrival_means[action][u]
            for u in USER_TYPES
        )

    def expected_service_moments(self, action: str = "Mixto") -> Tuple[float, float]:
        """Calcula E[S] y E[S^2] para la mezcla exponencial de un flujo de servicio."""
        if action == "Mixto":
            e1 = sum(
                p_act * self.expected_service_moments(act)[0]
                for act, p_act in self.action_probs.items()
            )
            e2 = sum(
                p_act * self.expected_service_moments(act)[1]
                for act, p_act in self.action_probs.items()
            )
            return e1, e2

        e1 = sum(
            self.user_type_probs[action][u] * self.service_means[action][u]
            for u in USER_TYPES
        )
        # Para X ~ Exp(media = m), E[X^2] = 2 * m^2
        e2 = sum(
            self.user_type_probs[action][u] * 2.0 * (self.service_means[action][u] ** 2)
            for u in USER_TYPES
        )
        return e1, e2

    def branch_arrival_rate(self, role: str = "Mixto") -> float:
        """Tasa agregada de llegadas a la sucursal (clientes/min) para todo el banco o por acción."""
        lam_total = 1.0 / self.expected_interarrival_time("Mixto")
        if role == "Mixto":
            return lam_total
        return lam_total * self.action_probs[role]

    def compute_single_cashier_mm1(self, role: str, num_cashiers_with_role: int) -> MM1AnalyticalMetrics:
        """
        Calcula las métricas analíticas M/M/1 (y Wq M/G/1 de referencia) para un cajero
        independiente que recibe la fracción 1/k de su flujo asignado.
        """
        if num_cashiers_with_role <= 0:
            raise ValueError("El número de cajeros con el rol debe ser mayor que cero.")

        lam = self.branch_arrival_rate(role) / num_cashiers_with_role
        mean_s, mean_s2 = self.expected_service_moments(role)
        mu = 1.0 / mean_s
        rho = lam / mu
        stable = rho < 1.0

        if stable:
            p0 = 1.0 - rho
            l_sys = rho / (1.0 - rho)
            lq = (rho ** 2) / (1.0 - rho)
            w_sys = 1.0 / (mu - lam)
            wq = rho / (mu * (1.0 - rho))
            wq_mg1 = (lam * mean_s2) / (2.0 * (1.0 - rho))
            prob_wq_gt_5min = float(rho * np.exp(-(mu - lam) * 5.0))
        else:
            p0 = 0.0
            l_sys = float("inf")
            lq = float("inf")
            w_sys = float("inf")
            wq = float("inf")
            wq_mg1 = float("inf")
            prob_wq_gt_5min = 1.0

        return MM1AnalyticalMetrics(
            role=role,
            lam=lam,
            mu=mu,
            rho=rho,
            p0=p0,
            mean_service=mean_s,
            mean_s2=mean_s2,
            l_system=l_sys,
            lq_queue=lq,
            w_system=w_sys,
            wq_queue=wq,
            wq_mg1=wq_mg1,
            stable=stable,
            prob_wq_gt_5min=prob_wq_gt_5min,
        )

    def analyze_scenario_theoretically(self, scenario_key: str) -> Dict[str, object]:
        """Calcula las métricas analíticas ponderadas de un escenario completo."""
        cfg = SCENARIO_DEFINITIONS[scenario_key]
        cajeros = cfg["cajeros"]

        counts_by_role: Dict[str, int] = {}
        for _, role in cajeros:
            counts_by_role[role] = counts_by_role.get(role, 0) + 1

        cashier_metrics = []
        for name, role in cajeros:
            m = self.compute_single_cashier_mm1(role, counts_by_role[role])
            cashier_metrics.append((name, m))

        total_lam = sum(m.lam for _, m in cashier_metrics)
        weighted_wq_mm1 = sum((m.lam / total_lam) * m.wq_queue for _, m in cashier_metrics)
        weighted_wq_mg1 = sum((m.lam / total_lam) * m.wq_mg1 for _, m in cashier_metrics)
        weighted_w_mm1 = sum((m.lam / total_lam) * m.w_system for _, m in cashier_metrics)
        weighted_s = sum((m.lam / total_lam) * m.mean_service for _, m in cashier_metrics)
        weighted_prob_gt_5 = sum((m.lam / total_lam) * m.prob_wq_gt_5min for _, m in cashier_metrics)
        total_lq = sum(m.lq_queue for _, m in cashier_metrics)
        total_l = sum(m.l_system for _, m in cashier_metrics)
        mean_rho = float(np.mean([m.rho for _, m in cashier_metrics]))
        max_rho = float(np.max([m.rho for _, m in cashier_metrics]))
        max_wq_mm1 = float(np.max([m.wq_queue for _, m in cashier_metrics]))

        return {
            "scenario_key": scenario_key,
            "nombre": cfg["nombre"],
            "nombre_corto": cfg["nombre_corto"],
            "num_cajeros": cfg["num_cajeros"],
            "total_lambda": total_lam,
            "expected_arrivals_8h": total_lam * self.horizon_minutes,
            "weighted_s": weighted_s,
            "weighted_wq_mm1": weighted_wq_mm1,
            "weighted_wq_mg1": weighted_wq_mg1,
            "weighted_w_mm1": weighted_w_mm1,
            "weighted_prob_wq_gt_5min": weighted_prob_gt_5,
            "total_lq_mm1": total_lq,
            "total_l_mm1": total_l,
            "mean_rho": mean_rho,
            "max_rho": max_rho,
            "regime_max_rho": classify_utilization_regime(max_rho),
            "max_wq_mm1": max_wq_mm1,
            "cashiers": cashier_metrics,
        }

    def generate_day_arrivals(self, seed: int) -> List[ArrivalCustomer]:
        """
        Genera la secuencia estocástica de llegadas para una jornada de 8 horas (480 min)
        usando numpy.random.default_rng (PCG64) para reproducibilidad exacta.
        """
        rng = np.random.default_rng(seed)
        actions = list(self.action_probs.keys())
        action_p = [self.action_probs[a] for a in actions]

        utype_p_by_action = {
            act: [self.user_type_probs[act][u] for u in USER_TYPES]
            for act in actions
        }

        customers: List[ArrivalCustomer] = []
        current_time = 0.0
        cid = 1

        while True:
            action = str(rng.choice(actions, p=action_p))
            user_type = str(rng.choice(USER_TYPES, p=utype_p_by_action[action]))

            ia_mean = self.arrival_means[action][user_type]
            srv_mean = self.service_means[action][user_type]

            ia_time = float(rng.exponential(scale=ia_mean))
            current_time += ia_time
            if current_time > self.horizon_minutes:
                break

            srv_time = float(rng.exponential(scale=srv_mean))
            customers.append(
                ArrivalCustomer(
                    customer_id=cid,
                    arrival_time=current_time,
                    interarrival_time=ia_time,
                    action=action,
                    user_type=user_type,
                    service_time=srv_time,
                )
            )
            cid += 1

        return customers
