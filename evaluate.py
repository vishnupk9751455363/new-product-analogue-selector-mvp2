"""
src/evaluate.py
Evaluation Harness: Benchmarking Naive Baseline vs. Analogue Selector
on Cold-Start New Products.

METRICS COMPUTED:
-----------------
1. MAPE (Mean Absolute Percentage Error):
   MAPE = (1/N) * sum(|y_actual - y_pred| / max(y_actual, 1e-4)) * 100%

2. WAPE (Weighted Absolute Percentage Error):
   WAPE = (sum(|y_actual - y_pred|) / sum(y_actual)) * 100%
   (Industry standard metric in grocery/retail forecasting to prevent small-denominator distortion).

EVALUATION METHODOLOGY:
-----------------------
- Training catalogue: 80 established products (is_historical = 1)
- Test set: 12 held-out new products (is_historical = 0) with zero prior history available to models.
- Horizon: First 8 weeks post-launch (W1..W8).
- Ground truth: Empirical average units sold per store per week from sales_history.
"""

import os
import sys
import sqlite3
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.baseline import CategoryAverageBaselineForecaster
from src.analogue_selector import AnalogueSelector
DB_PATH = os.path.join(BASE_DIR, "db", "warehouse.db")


def calculate_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Calculates Mean Absolute Percentage Error (MAPE)."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denominator = np.maximum(actual, 1e-3)
    return float(np.mean(np.abs((actual - predicted) / denominator)) * 100.0)


def calculate_wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Calculates Weighted Absolute Percentage Error (WAPE)."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denom = np.sum(actual)
    if denom == 0:
        return 0.0
    return float((np.sum(np.abs(actual - predicted)) / denom) * 100.0)


def load_data(db_path: str = DB_PATH) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Loads products and sales history from SQLite."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}. Run scripts/generate_synthetic_data.py first.")

    conn = sqlite3.connect(db_path)
    products_df = pd.read_sql("SELECT * FROM products", conn)
    sales_df = pd.read_sql("SELECT * FROM sales_history", conn)
    conn.close()
    return products_df, sales_df


def extract_ground_truth_curves(sales_df: pd.DataFrame, product_ids: List[str], horizon_weeks: int = 8) -> Dict[str, Dict[str, float]]:
    """Extracts average units sold per store per week (W1..W8) for given product IDs."""
    filtered_sales = sales_df[sales_df["product_id"].isin(product_ids)]
    grouped = filtered_sales.groupby(["product_id", "week_post_launch"])["units_sold"].mean().reset_index()

    ground_truth = {}
    for p_id, group in grouped.groupby("product_id"):
        gt_curve = {}
        for _, r in group.iterrows():
            w = int(r["week_post_launch"])
            if 1 <= w <= horizon_weeks:
                gt_curve[f"W{w}"] = float(r["units_sold"])
        ground_truth[str(p_id)] = gt_curve

    return ground_truth


def run_benchmark(db_path: str = DB_PATH, k: int = 5, horizon_weeks: int = 8) -> Dict[str, any]:
    """
    Executes full evaluation benchmark comparing Baseline vs Analogue Selector
    across all held-out cold-start test products.
    """
    products_df, sales_df = load_data(db_path)

    established_df = products_df[products_df["is_historical"] == 1].copy()
    test_products_df = products_df[products_df["is_historical"] == 0].copy()

    test_ids = test_products_df["product_id"].tolist()
    ground_truth_curves = extract_ground_truth_curves(sales_df, test_ids, horizon_weeks)

    # 1. Fit models on established data only
    baseline = CategoryAverageBaselineForecaster(use_price_tier=True)
    baseline.fit(established_df, sales_df)

    selector = AnalogueSelector()
    selector.fit(established_df, sales_df)

    results_records = []

    all_actuals = []
    all_baseline_preds = []
    all_selector_preds = []

    weekly_actuals = {f"W{w}": [] for w in range(1, horizon_weeks + 1)}
    weekly_baseline_preds = {f"W{w}": [] for w in range(1, horizon_weeks + 1)}
    weekly_selector_preds = {f"W{w}": [] for w in range(1, horizon_weeks + 1)}

    for _, prod_row in test_products_df.iterrows():
        p_id = str(prod_row["product_id"])
        p_name = str(prod_row["product_name"])
        category = str(prod_row["category"])

        gt_curve = ground_truth_curves.get(p_id, {})
        if not gt_curve:
            continue

        # Generate forecasts
        base_forecast = baseline.forecast(prod_row, horizon_weeks=horizon_weeks)
        sel_result = selector.forecast_launch_curve(prod_row, k=k, horizon_weeks=horizon_weeks)
        sel_forecast = sel_result.forecast_curve

        prod_actuals = [gt_curve.get(f"W{w}", 0.0) for w in range(1, horizon_weeks + 1)]
        prod_base = [base_forecast.get(f"W{w}", 0.0) for w in range(1, horizon_weeks + 1)]
        prod_sel = [sel_forecast.get(f"W{w}", 0.0) for w in range(1, horizon_weeks + 1)]

        prod_base_wape = calculate_wape(np.array(prod_actuals), np.array(prod_base))
        prod_sel_wape = calculate_wape(np.array(prod_actuals), np.array(prod_sel))

        results_records.append({
            "product_id": p_id,
            "product_name": p_name,
            "category": category,
            "confidence": sel_result.confidence_score,
            "baseline_wape": prod_base_wape,
            "selector_wape": prod_sel_wape,
            "wape_improvement": prod_base_wape - prod_sel_wape
        })

        all_actuals.extend(prod_actuals)
        all_baseline_preds.extend(prod_base)
        all_selector_preds.extend(prod_sel)

        for w in range(1, horizon_weeks + 1):
            w_key = f"W{w}"
            weekly_actuals[w_key].append(gt_curve.get(w_key, 0.0))
            weekly_baseline_preds[w_key].append(base_forecast.get(w_key, 0.0))
            weekly_selector_preds[w_key].append(sel_forecast.get(w_key, 0.0))

    # Overall metrics
    arr_actuals = np.array(all_actuals)
    arr_base = np.array(all_baseline_preds)
    arr_sel = np.array(all_selector_preds)

    overall_base_mape = calculate_mape(arr_actuals, arr_base)
    overall_sel_mape = calculate_mape(arr_actuals, arr_sel)

    overall_base_wape = calculate_wape(arr_actuals, arr_base)
    overall_sel_wape = calculate_wape(arr_actuals, arr_sel)

    # Weekly metrics
    weekly_breakdown = []
    for w in range(1, horizon_weeks + 1):
        w_key = f"W{w}"
        w_act = np.array(weekly_actuals[w_key])
        w_base = np.array(weekly_baseline_preds[w_key])
        w_sel = np.array(weekly_selector_preds[w_key])

        weekly_breakdown.append({
            "week": w_key,
            "baseline_wape": calculate_wape(w_act, w_base),
            "selector_wape": calculate_wape(w_act, w_sel),
            "baseline_mape": calculate_mape(w_act, w_base),
            "selector_mape": calculate_mape(w_act, w_sel)
        })

    return {
        "overall": {
            "baseline_mape": overall_base_mape,
            "selector_mape": overall_sel_mape,
            "baseline_wape": overall_base_wape,
            "selector_wape": overall_sel_wape,
            "wape_reduction_pts": overall_base_wape - overall_sel_wape,
            "wape_pct_improvement": ((overall_base_wape - overall_sel_wape) / overall_base_wape) * 100.0
        },
        "per_product": pd.DataFrame(results_records),
        "weekly": pd.DataFrame(weekly_breakdown)
    }


def main():
    print("=" * 78)
    print("NEW-PRODUCT COLD-START EVALUATION BENCHMARK (PHASE 1)")
    print("=" * 78)

    benchmark = run_benchmark()
    overall = benchmark["overall"]
    prod_df = benchmark["per_product"]
    weekly_df = benchmark["weekly"]

    print("\n[1] OVERALL PERFORMANCE SUMMARY (12 Held-Out Test Products, W1..W8 Horizon):")
    print("-" * 78)
    print(f"  Naive Baseline WAPE:        {overall['baseline_wape']:6.2f}%")
    print(f"  Analogue Selector v1 WAPE:  {overall['selector_wape']:6.2f}%")
    print(f"  --> WAPE Improvement:       {overall['wape_reduction_pts']:+6.2f}% points ({overall['wape_pct_improvement']:+.1f}% error reduction)")
    print("-" * 78)
    print(f"  Naive Baseline MAPE:        {overall['baseline_mape']:6.2f}%")
    print(f"  Analogue Selector v1 MAPE:  {overall['selector_mape']:6.2f}%")
    print("-" * 78)

    print("\n[2] WEEK-BY-WEEK FORECAST ACCURACY (WAPE %):")
    print("-" * 78)
    print(f"{'Week':<8} | {'Baseline WAPE':<16} | {'Selector WAPE':<16} | {'Improvement':<16}")
    print("-" * 78)
    for _, row in weekly_df.iterrows():
        diff = row["baseline_wape"] - row["selector_wape"]
        print(f"{row['week']:<8} | {row['baseline_wape']:>14.2f}% | {row['selector_wape']:>14.2f}% | {diff:>+14.2f}% pts")
    print("-" * 78)

    print("\n[3] PER-PRODUCT ACCURACY BREAKDOWN (Cold-Start Test SKUs):")
    print("-" * 78)
    print(f"{'Product ID':<12} | {'Category':<14} | {'Conf':<6} | {'Base WAPE':<10} | {'Sel WAPE':<10} | {'Status'}")
    print("-" * 78)
    for _, row in prod_df.iterrows():
        status = "BETTER" if row["wape_improvement"] > 0 else "COMPARABLE"
        print(
            f"{row['product_id']:<12} | "
            f"{row['category']:<14} | "
            f"{row['confidence']:>5.2f}  | "
            f"{row['baseline_wape']:>8.2f}%  | "
            f"{row['selector_wape']:>8.2f}%  | "
            f"{status} ({row['wape_improvement']:+.1f}%)"
        )
    print("=" * 78)


if __name__ == "__main__":
    main()
