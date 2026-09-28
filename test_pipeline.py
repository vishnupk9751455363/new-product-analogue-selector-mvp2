"""
tests/test_pipeline.py
Unit and Integration Test Suite for New-Product Analogue Selector (Phase 1).

Covers:
1. SQLite schema initialization and table creation.
2. Immutability trigger enforcement on plan_changes table (rejecting UPDATE/DELETE).
3. Synthetic dataset generator output integrity (expected counts, schema validity).
4. AnalogueSelector contract compliance (AnalogueResult fields, explainability breakdown).
5. Robustness against zero-match / unseen category edge cases (graceful degradation).
6. CategoryAverageBaselineForecaster functionality.
7. End-to-end evaluation harness execution.
"""

import os
import sys
import sqlite3
import unittest
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.analogue_selector import AnalogueSelector, AnalogueResult, ForecastResult
from src.baseline import CategoryAverageBaselineForecaster
from src.audit_log import PlanAuditLogger
from src.evaluate import run_benchmark, calculate_mape, calculate_wape
from scripts.generate_synthetic_data import (
    create_schema,
    generate_stores,
    generate_products,
    generate_sales_and_promotions,
    generate_seed_plan_changes
)


class TestDatabaseAndSchema(unittest.TestCase):
    """Verifies schema creation, constraints, and audit log immutability triggers."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_tables_created(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        expected_tables = {"stores", "products", "sales_history", "promotions", "plan_changes"}
        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

    def test_audit_log_immutability_triggers(self):
        """Validates that BEFORE UPDATE and BEFORE DELETE triggers block tampering."""
        cursor = self.conn.cursor()
        # Insert test product
        cursor.execute(
            """
            INSERT INTO products VALUES (
                'TEST_P1', 'Test Bread', 'Bakery', 'Artisan Bread',
                'mid', 1.0, 7, 0, NULL, 0, '2026-01-01', 1
            )
            """
        )
        # Insert audit log entry
        cursor.execute(
            """
            INSERT INTO plan_changes (
                product_id, changed_by, changed_at, field_changed, old_value, new_value, reason, source
            ) VALUES ('TEST_P1', 'system_v1', '2026-01-01 12:00:00', 'w1', '100', '120', 'auto', 'system')
            """
        )
        change_id = cursor.lastrowid
        self.conn.commit()

        # Test UPDATE rejection
        with self.assertRaises(sqlite3.DatabaseError) as update_ctx:
            cursor.execute("UPDATE plan_changes SET reason = 'Tampered' WHERE change_id = ?", (change_id,))
        self.assertIn("IMMUTABILITY VIOLATION", str(update_ctx.exception))

        # Test DELETE rejection
        with self.assertRaises(sqlite3.DatabaseError) as delete_ctx:
            cursor.execute("DELETE FROM plan_changes WHERE change_id = ?", (change_id,))
        self.assertIn("IMMUTABILITY VIOLATION", str(delete_ctx.exception))


class TestSyntheticDataGenerator(unittest.TestCase):
    """Validates the synthetic data generation logic and row structures."""

    def test_data_shapes_and_seed_stability(self):
        stores_df = generate_stores(num_stores=10)
        self.assertEqual(len(stores_df), 10)
        self.assertIn("climate_zone", stores_df.columns)

        products_df = generate_products(num_established=50, num_cold_start=10)
        self.assertEqual(len(products_df), 60)
        self.assertEqual((products_df["is_historical"] == 1).sum(), 50)
        self.assertEqual((products_df["is_historical"] == 0).sum(), 10)

        sales_df, promos_df = generate_sales_and_promotions(products_df, stores_df)
        # 60 products * 10 stores * 8 weeks = 4800 rows
        self.assertEqual(len(sales_df), 4800)
        self.assertTrue((sales_df["units_sold"] > 0).all())

        plan_changes_df = generate_seed_plan_changes(products_df)
        self.assertGreater(len(plan_changes_df), 0)
        self.assertTrue(set(plan_changes_df["source"]).issubset({"system", "planner_override"}))


class TestAnalogueSelector(unittest.TestCase):
    """Tests AnalogueSelector contract, explainability, confidence scoring, and edge cases."""

    @classmethod
    def setUpClass(cls):
        cls.stores_df = generate_stores(num_stores=5)
        cls.products_df = generate_products(num_established=30, num_cold_start=5)
        cls.sales_df, _ = generate_sales_and_promotions(cls.products_df, cls.stores_df)
        cls.selector = AnalogueSelector()
        cls.selector.fit(cls.products_df, cls.sales_df)

    def test_find_analogues_contract(self):
        target = self.products_df[self.products_df["is_historical"] == 0].iloc[0]
        analogues = self.selector.find_analogues(target, k=4)

        self.assertEqual(len(analogues), 4)
        for a in analogues:
            self.assertIsInstance(a, AnalogueResult)
            self.assertIsInstance(a.product_id, str)
            self.assertIsInstance(a.similarity_score, float)
            self.assertIsInstance(a.confidence_score, float)
            self.assertIsInstance(a.contributing_attributes, dict)
            self.assertIsInstance(a.explanation, str)
            self.assertGreater(len(a.explanation), 0)

            # Check per-attribute explainability sums to similarity_score
            attr_sum = sum(a.contributing_attributes.values())
            self.assertAlmostEqual(attr_sum, a.similarity_score, places=4)

    def test_forecast_launch_curve(self):
        target = self.products_df[self.products_df["is_historical"] == 0].iloc[0]
        fc_res = self.selector.forecast_launch_curve(target, k=5, horizon_weeks=8)

        self.assertIsInstance(fc_res, ForecastResult)
        self.assertEqual(len(fc_res.forecast_curve), 8)
        for w in range(1, 9):
            self.assertIn(f"W{w}", fc_res.forecast_curve)
            self.assertGreater(fc_res.forecast_curve[f"W{w}"], 0.0)

    def test_edge_case_unseen_category_graceful_degradation(self):
        """Verifies system degrades gracefully when product has an unseen category."""
        novel_product = {
            "product_id": "PRD_NOVEL_001",
            "product_name": "Lab-Grown Caviar (Premium 1pk)",
            "category": "ExtremelyRareExoticFoods",  # Unseen
            "subcategory": "Cellular Agriculture",
            "price_tier": "premium",
            "pack_size_units": 1.0,
            "shelf_life_days": 180,
            "is_festival_linked": 0,
            "festival_name": None,
            "weather_sensitivity": 0
        }
        fc_res = self.selector.forecast_launch_curve(novel_product, k=5)
        self.assertTrue(fc_res.is_degraded)
        self.assertIsNotNone(fc_res.degradation_reason)
        self.assertIn("Graceful degradation", fc_res.degradation_reason)
        self.assertLessEqual(fc_res.confidence_score, 0.30)
        self.assertEqual(len(fc_res.forecast_curve), 8)


class TestBaselineAndEvaluation(unittest.TestCase):
    """Tests the baseline forecaster and the evaluation metrics harness."""

    def test_metric_calculations(self):
        actual = np.array([100.0, 150.0, 200.0])
        pred = np.array([110.0, 135.0, 210.0])

        mape = calculate_mape(actual, pred)
        wape = calculate_wape(actual, pred)

        # Errors: 10, 15, 10 -> Sum=35. Denom=450 -> WAPE = 35/450 * 100 = 7.777%
        self.assertAlmostEqual(wape, 7.7777, places=3)
        self.assertGreater(mape, 0.0)

    def test_evaluation_harness_runs(self):
        """Ensures run_benchmark runs end-to-end on synthetic db."""
        db_path = os.path.join(BASE_DIR, "db", "warehouse.db")
        if not os.path.exists(db_path):
            self.skipTest("warehouse.db not found; run generate_synthetic_data first.")

        benchmark = run_benchmark(db_path=db_path, k=5, horizon_weeks=8)
        self.assertIn("overall", benchmark)
        self.assertIn("baseline_wape", benchmark["overall"])
        self.assertIn("selector_wape", benchmark["overall"])
        self.assertIn("per_product", benchmark)
        self.assertIn("weekly", benchmark)
        self.assertFalse(benchmark["per_product"].empty)
        self.assertEqual(len(benchmark["weekly"]), 8)


if __name__ == "__main__":
    unittest.main()
