"""
tests/test_disruptions.py
Comprehensive Unit and Integration Test Suite for Disruption Simulation Engine,
Promotional De-Biasing, and REST APIs (Phase 2).
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app
from src.disruption_scenarios import (
    simulate_supplier_delay,
    simulate_capacity_loss,
    simulate_unplanned_spike,
    run_disruption_scenario,
    DisruptionResult
)
from src.analogue_selector import AnalogueSelector
from scripts.generate_synthetic_data import (
    generate_stores,
    generate_products,
    generate_sales_and_promotions
)


class TestDisruptionScenarios(unittest.TestCase):
    """Verifies all mathematical models of supply chain and demand disruptions."""

    def setUp(self):
        self.base_forecast = {
            "W1": 150.0,
            "W2": 160.0,
            "W3": 130.0,
            "W4": 120.0,
            "W5": 115.0,
            "W6": 110.0,
            "W7": 105.0,
            "W8": 100.0,
        }

    def test_supplier_delay_shifts_and_zeros_early_weeks(self):
        """Verifies launch is shifted forward and initial delayed weeks are zeroed."""
        delay = 2
        res = simulate_supplier_delay(
            launch_forecast=self.base_forecast,
            delay_weeks=delay,
            spoilage_rate_pct=0.05,
            shelf_life_days=60
        )

        self.assertIsInstance(res, DisruptionResult)
        self.assertEqual(res.scenario_type, "supplier_delay")
        self.assertEqual(res.disrupted_forecast["W1"], 0.0)
        self.assertEqual(res.disrupted_forecast["W2"], 0.0)
        # Week 3 should now receive the shifted launch wave
        self.assertGreater(res.disrupted_forecast["W3"], 0.0)
        self.assertGreater(res.lost_sales_units, 0.0)
        self.assertEqual(res.stockout_risk_pct, 100.0)

    def test_supplier_delay_perishability_penalty(self):
        """Verifies short shelf-life items suffer higher spoilage inventory loss."""
        perishable_res = simulate_supplier_delay(
            launch_forecast=self.base_forecast,
            delay_weeks=2,
            shelf_life_days=7  # Perishable
        )
        ambient_res = simulate_supplier_delay(
            launch_forecast=self.base_forecast,
            delay_weeks=2,
            shelf_life_days=180  # Ambient
        )

        self.assertGreater(perishable_res.spoilage_units, ambient_res.spoilage_units)

    def test_capacity_loss_caps_throughput_and_tracks_spillover(self):
        """Verifies logistics bottleneck clips peak deliveries and records backlog."""
        ceiling = 120.0
        res = simulate_capacity_loss(
            launch_forecast=self.base_forecast,
            max_weekly_store_capacity=ceiling,
            spillover_rate=0.35,
            shelf_life_days=30
        )

        self.assertIsInstance(res, DisruptionResult)
        self.assertEqual(res.scenario_type, "capacity_loss")
        for w, val in res.disrupted_forecast.items():
            self.assertLessEqual(val, ceiling + 1e-5, f"Week {w} exceeded capacity ceiling!")

        self.assertGreater(res.lost_sales_units, 0.0)
        self.assertGreater(res.metrics["bottlenecked_weeks_count"], 0)

    def test_unplanned_spike_magnifies_demand_and_sizes_buffer(self):
        """Verifies demand surge at specified week and emergency buffer calculation."""
        res = simulate_unplanned_spike(
            launch_forecast=self.base_forecast,
            spike_week=3,
            spike_multiplier=2.5,
            safety_buffer_pct=0.20
        )

        self.assertIsInstance(res, DisruptionResult)
        self.assertEqual(res.scenario_type, "unplanned_spike")
        expected_surge = self.base_forecast["W3"] * 2.5
        self.assertAlmostEqual(res.disrupted_forecast["W3"], expected_surge, places=2)
        # Unaffected weeks should match baseline
        self.assertAlmostEqual(res.disrupted_forecast["W1"], self.base_forecast["W1"], places=2)
        # Recommended replenishment buffer should be positive
        self.assertGreater(res.recommended_buffer_units, 0.0)
        self.assertGreater(res.stockout_risk_pct, 0.0)

    def test_master_dispatcher_run_disruption_scenario(self):
        """Verifies master dispatcher handles all scenario strings and errors appropriately."""
        res1 = run_disruption_scenario("supplier_delay", self.base_forecast, delay_weeks=1)
        self.assertEqual(res1.scenario_type, "supplier_delay")

        res2 = run_disruption_scenario("capacity_loss", self.base_forecast, max_weekly_store_capacity=100.0)
        self.assertEqual(res2.scenario_type, "capacity_loss")

        res3 = run_disruption_scenario("unplanned_spike", self.base_forecast, spike_week=2, spike_multiplier=2.0)
        self.assertEqual(res3.scenario_type, "unplanned_spike")

        res4 = run_disruption_scenario("weather_anomaly", self.base_forecast, weather_type="heatwave", intensity_pct=0.65)
        self.assertEqual(res4.scenario_type, "weather_anomaly")
        self.assertGreater(res4.disrupted_forecast["W2"], self.base_forecast["W2"])

        res5 = run_disruption_scenario("festival_shift", self.base_forecast, shift_direction="earlier", shift_weeks=2, original_peak_week=4, peak_multiplier=1.9, is_festival_linked=1)
        self.assertEqual(res5.scenario_type, "festival_shift")
        self.assertGreater(res5.disrupted_forecast["W2"], self.base_forecast["W2"])

        with self.assertRaises(ValueError):
            run_disruption_scenario("invalid_scenario_type", self.base_forecast)


class TestPromotionalDebiasingAndEdgeCases(unittest.TestCase):
    """Tests promotional de-biasing on historical analogue curves and edge case diagnostics."""

    @classmethod
    def setUpClass(cls):
        stores_df = generate_stores(num_stores=5)
        cls.products_df = generate_products(num_established=30, num_cold_start=5)
        cls.sales_df, _ = generate_sales_and_promotions(cls.products_df, stores_df)
        cls.selector = AnalogueSelector()
        cls.selector.fit(cls.products_df, cls.sales_df)

    def test_promotional_debiasing_reduces_or_maintains_forecast_volume(self):
        """Verifies de-biased curve strips promotional artificial lifts."""
        test_prod = self.products_df[self.products_df["is_historical"] == 0].iloc[0]

        fc_raw = self.selector.forecast_launch_curve(test_prod, k=5, debias_promotions=False)
        fc_debiased = self.selector.forecast_launch_curve(test_prod, k=5, debias_promotions=True)

        raw_total = sum(fc_raw.forecast_curve.values())
        debiased_total = sum(fc_debiased.forecast_curve.values())

        self.assertLessEqual(debiased_total, raw_total)
        self.assertTrue(fc_debiased.promo_debias_applied)

    def test_edge_case_diagnostic_flags(self):
        """Verifies multi-scenario edge case diagnostic analysis."""
        novel_item = {
            "product_id": "TEST_NOVEL",
            "category": "ExtraterrestrialProduce",
            "pack_size_units": 48.0,  # Extreme pack size
            "shelf_life_days": 3,     # Extreme perishability
            "weather_sensitivity": 1
        }
        edge_diag = self.selector.analyze_edge_cases(novel_item)
        self.assertIn("severity", edge_diag)
        self.assertIn("risk_flags", edge_diag)
        self.assertTrue(edge_diag["has_warnings"])
        flag_text = " ".join(edge_diag["risk_flags"])
        self.assertIn("NOVEL_CATEGORY", flag_text)
        self.assertIn("EXTREME_PACK_SIZE", flag_text)
        self.assertIn("HIGH_PERISHABILITY", flag_text)


class TestAPIEndpoints(unittest.TestCase):
    """Integration tests for FastAPI disruption and analogue endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app.app)
        app.init_models()

    def test_disruption_presets_api(self):
        resp = self.client.get("/api/disruptions/presets")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("presets", data)
        self.assertGreaterEqual(len(data["presets"]), 3)

    def test_disruption_simulation_api(self):
        payload = {
            "product_id": "PRD_NEW_083",
            "scenario_type": "supplier_delay",
            "delay_weeks": 2,
            "spoilage_rate_pct": 0.05
        }
        resp = self.client.post("/api/disruptions/simulate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("result", data)
        self.assertEqual(data["result"]["scenario_type"], "supplier_delay")
        self.assertEqual(data["result"]["disrupted_forecast"]["W1"], 0.0)

    def test_analogues_api_with_promo_debiasing(self):
        payload = {
            "product_id": "PRD_NEW_083",
            "k": 5,
            "debias_promotions": True
        }
        resp = self.client.post("/api/analogues", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["debias_promotions_applied"])
        self.assertIn("edge_cases", data)

    def test_weight_optimization_api(self):
        resp = self.client.get("/api/weights/optimized")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("optimization_result", data)
        self.assertIn("optimal_weights", data["optimization_result"])
        self.assertIn("baseline_cv_wape", data["optimization_result"])


if __name__ == "__main__":
    unittest.main()
