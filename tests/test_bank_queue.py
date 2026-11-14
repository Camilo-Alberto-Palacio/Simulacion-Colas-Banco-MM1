"""
Suite de Pruebas Unitarias y Verificación Matemática del Simulador Bancario M/M/1.
Valida restricciones probabilísticas de Kolmogorov, estabilidad de colas,
Ley de Little, consistencia teórica M/M/1 vs M/G/1 y reproducibilidad determinista.
"""

import unittest
import numpy as np

from bank_queue import (
    ACTION_PROBS,
    BANK_MINUTES,
    SCENARIO_DEFINITIONS,
    USER_TYPES,
    ArrivalCustomer,
    BankQueuingModel,
    BankSimulationEngine,
    t_crit_two_sided,
)


class TestBankQueuingModel(unittest.TestCase):
    """Pruebas rigurosas de parametrización, analítica M/M/1 y DES."""

    def setUp(self) -> None:
        self.model = BankQueuingModel()
        self.engine = BankSimulationEngine(self.model)

    def test_probability_constraints(self) -> None:
        """Verifica que todas las distribuciones sumen 1.0 y sean no negativas."""
        self.assertAlmostEqual(sum(self.model.action_probs.values()), 1.0, places=10)
        for act in self.model.action_probs:
            self.assertAlmostEqual(sum(self.model.user_type_probs[act].values()), 1.0, places=10)

        joint = self.model.joint_profile_probabilities()
        self.assertEqual(len(joint), 8)
        self.assertAlmostEqual(sum(joint.values()), 1.0, places=10)

        marg = self.model.marginal_user_type_probabilities()
        self.assertEqual(set(marg.keys()), set(USER_TYPES))
        self.assertAlmostEqual(sum(marg.values()), 1.0, places=10)

    def test_invalid_probabilities_raise_error(self) -> None:
        """Verifica que distribuciones mal normalizadas lancen ValueError."""
        with self.assertRaises(ValueError):
            BankQueuingModel(action_probs={"Retiro": 0.60, "Pago": 0.30})

    def test_exact_analytical_moments(self) -> None:
        """Comprueba los momentos teóricos exactos de Tablas 1 y 2."""
        e_ia = self.model.expected_interarrival_time("Mixto")
        # 0.70*(0.23*1 + 0.40*2 + 0.17*3 + 0.20*3) + 0.30*(0.10*1 + 0.20*2 + 0.30*3 + 0.40*4)
        self.assertAlmostEqual(e_ia, 2.398, places=10)

        e_s_ret, _ = self.model.expected_service_moments("Retiro")
        e_s_pag, _ = self.model.expected_service_moments("Pago")
        e_s_mix, _ = self.model.expected_service_moments("Mixto")
        self.assertAlmostEqual(e_s_ret, 2.34, places=10)
        self.assertAlmostEqual(e_s_pag, 5.20, places=10)
        self.assertAlmostEqual(e_s_mix, 3.198, places=10)

    def test_all_scenarios_stable_and_littles_law(self) -> None:
        """Verifica rho < 1 y cumplimiento exacto de L = lambda * W en teoría."""
        for skey in SCENARIO_DEFINITIONS:
            theo = self.model.analyze_scenario_theoretically(skey)
            for _, cm in theo["cashiers"]:
                self.assertTrue(cm.stable)
                self.assertGreater(cm.rho, 0.0)
                self.assertLess(cm.rho, 1.0)
                self.assertAlmostEqual(cm.l_system, cm.lam * cm.w_system, places=8)
                self.assertAlmostEqual(cm.lq_queue, cm.lam * cm.wq_queue, places=8)
                self.assertAlmostEqual(cm.w_system, cm.wq_queue + cm.mean_service, places=8)

    def test_empirical_littles_law_on_sample_path(self) -> None:
        """Verifica que la trayectoria simulada satisfaga L_q = lambda_eff * W_q."""
        arrivals = self.model.generate_day_arrivals(seed=42)
        res = self.engine.simulate_single_replica("E1_3_Mixtas", arrivals, routing_seed=100)
        for cname, cres in res["cashiers"].items():
            if cres["total_customers"] > 0:
                lam_eff = cres["total_customers"] / cres["horizon_effective"]
                self.assertAlmostEqual(
                    cres["lq_empirical"],
                    lam_eff * cres["mean_wait_wq"],
                    places=8,
                    msg=f"Violación de Ley de Little en {cname}",
                )
                self.assertAlmostEqual(
                    cres["l_empirical"],
                    lam_eff * cres["mean_system_w"],
                    places=8,
                )

    def test_deterministic_reproducibility(self) -> None:
        """Verifica reproducibilidad idéntica con semilla fija."""
        r1 = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        r2 = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        np.testing.assert_allclose(
            r1["df_summary"]["espera_wq_media_min"].values,
            r2["df_summary"]["espera_wq_media_min"].values,
            atol=1e-12,
        )

    def test_minimum_10_replicas_and_pooling_effect(self) -> None:
        """Verifica 10+ réplicas y que 4 Mixtas reduzca espera frente a 3 Mixtas."""
        mc = self.engine.run_multi_replica_experiment(num_replicas=50, base_seed=42)
        df = mc["df_summary"].set_index("escenario")
        self.assertGreaterEqual(int(df.loc["E1_3_Mixtas", "replicas"]), 10)
        # 4 Mixtas debe reducir Wq frente a 3 Mixtas
        self.assertLess(
            float(df.loc["E4a_4_Mixtas", "espera_wq_media_min"]),
            float(df.loc["E1_3_Mixtas", "espera_wq_media_min"]),
        )
        # 3 Mixtas debe tener menor espera global que 1R+2P y 2R+1P (efecto pooling)
        self.assertLess(
            float(df.loc["E1_3_Mixtas", "espera_wq_media_min"]),
            float(df.loc["E2_1R_2P", "espera_wq_media_min"]),
        )
        self.assertLess(
            float(df.loc["E1_3_Mixtas", "espera_wq_media_min"]),
            float(df.loc["E3_2R_1P", "espera_wq_media_min"]),
        )

    def test_horizon_respects_480_minutes(self) -> None:
        """Todas las llegadas generadas deben ocurrir dentro del horario [0, 480]."""
        arrivals = self.model.generate_day_arrivals(seed=99)
        self.assertGreater(len(arrivals), 100)
        self.assertTrue(all(0.0 < c.arrival_time <= BANK_MINUTES for c in arrivals))

    def test_student_t_critical_values_and_ci95(self) -> None:
        """Valida cuantiles exactos de t de Student y amplitud IC95 en muestras pequeñas."""
        self.assertAlmostEqual(t_crit_two_sided(1, 0.95), 12.70620474, places=5)
        self.assertAlmostEqual(t_crit_two_sided(9, 0.95), 2.26215716, places=5)
        self.assertAlmostEqual(t_crit_two_sided(99, 0.95), 1.98421695, places=5)

        with self.assertRaises(ValueError):
            t_crit_two_sided(0, 0.95)
        with self.assertRaises(ValueError):
            t_crit_two_sided(9, 1.2)

        sample = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0, 4.0, 6.0]
        mean, sd, low, high = self.engine._ci95(sample)
        expected_half = t_crit_two_sided(len(sample) - 1, 0.95) * sd / np.sqrt(len(sample))
        self.assertAlmostEqual(high - mean, expected_half, places=8)
        self.assertAlmostEqual(mean - low, expected_half, places=8)

    def test_non_clairvoyant_jsq_uses_queue_length_not_future_service(self) -> None:
        """
        Comprueba que shortest_queue (JSQ observable) enrute por longitud visible de cola
        (sin leer duraciones futuras de servicio) a diferencia de least_work (clarividente).
        """
        customers = [
            ArrivalCustomer(customer_id=1, arrival_time=0.0, interarrival_time=0.0, action="Retiro", user_type="Rápido", service_time=0.5),
            ArrivalCustomer(customer_id=2, arrival_time=0.01, interarrival_time=0.01, action="Retiro", user_type="Rápido", service_time=5.0),
            ArrivalCustomer(customer_id=3, arrival_time=0.02, interarrival_time=0.01, action="Retiro", user_type="Rápido", service_time=0.5),
            ArrivalCustomer(customer_id=4, arrival_time=0.05, interarrival_time=0.03, action="Retiro", user_type="Rápido", service_time=1.0),
        ]
        # Comparamos enrutamiento independiente M/M/1, JSQ no clarividente y LWL clarividente
        mc_rand = self.engine.run_multi_replica_experiment(num_replicas=30, base_seed=42, routing_mode="random_mm1")
        mc_jsq = self.engine.run_multi_replica_experiment(num_replicas=30, base_seed=42, routing_mode="shortest_queue")
        mc_lwl = self.engine.run_multi_replica_experiment(num_replicas=30, base_seed=42, routing_mode="least_work")

        wq_rand = float(mc_rand["df_summary"].set_index("escenario").loc["E1_3_Mixtas", "espera_wq_media_min"])
        wq_jsq = float(mc_jsq["df_summary"].set_index("escenario").loc["E1_3_Mixtas", "espera_wq_media_min"])
        wq_lwl = float(mc_lwl["df_summary"].set_index("escenario").loc["E1_3_Mixtas", "espera_wq_media_min"])
        self.assertLess(wq_jsq, wq_rand)
        self.assertLessEqual(wq_lwl, wq_jsq)
        self.assertGreater(abs(wq_jsq - wq_lwl), 0.1)

        with self.assertRaises(ValueError):
            self.engine.simulate_single_replica("E1_3_Mixtas", customers, routing_seed=1, routing_mode="invalid_mode")

    def test_required_replicas_and_disaggregated_wait_outputs(self) -> None:
        """Verifica cálculo de tamaño muestral n* y desglose por acción, tipo y 8 perfiles."""
        exp = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        df_req = exp["df_sample_size"]
        self.assertEqual(len(df_req), len(SCENARIO_DEFINITIONS))
        self.assertTrue((df_req["n_req_global_max"] >= 2).all())

        # Tolerancia más estricta exige >= número de réplicas
        df_strict = self.engine.compute_required_replicas(exp["df_replicas"], wq_abs_tol_min=0.25)
        self.assertTrue((df_strict["n_req_wq_iterativo"] >= df_req["n_req_wq_iterativo"]).all())

        df_act = exp["df_wait_by_action"]
        df_typ = exp["df_wait_by_type"]
        df_prof = exp["df_wait_profiles"]
        self.assertEqual(len(df_act), len(SCENARIO_DEFINITIONS) * len(ACTION_PROBS))
        self.assertEqual(len(df_typ), len(SCENARIO_DEFINITIONS) * len(USER_TYPES))
        self.assertEqual(len(df_prof), len(SCENARIO_DEFINITIONS) * 8)


if __name__ == "__main__":
    unittest.main()
