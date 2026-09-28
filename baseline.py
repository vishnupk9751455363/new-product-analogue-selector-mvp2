"""
src/baseline.py
Deliberately Naive Baseline Forecaster for Cold-Start New Products.

This baseline models new product demand using category-level (or category + price tier)
historical averages.

RATIONALE & NAIVETY:
--------------------
This method is intentionally simplistic and serves as the baseline that our
Analogue Selector must outperform. It assumes:
1. All products within a category (e.g., all Bakery items) share the exact same
   underlying launch adoption curve.
2. It completely ignores critical differentiating attributes such as subcategory
   (artisan bread vs muffin), pack sizes (single vs family pack), shelf life,
   weather sensitivity, and festival/holiday timing.
3. If an unseen category appears, it falls back to the overall catalog grand average.
"""

from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd


class CategoryAverageBaselineForecaster:
    """
    Naive baseline forecaster that computes the empirical mean launch curve
    by product category (with optional price-tier conditioning).
    """

    def __init__(self, use_price_tier: bool = True):
        """
        Args:
            use_price_tier: If True, aggregates historical curves by (category, price_tier).
                            If False, aggregates solely by category.
        """
        self.use_price_tier = use_price_tier
        self.category_curves: Dict[str, Dict[int, float]] = {}
        self.tier_curves: Dict[tuple, Dict[int, float]] = {}
        self.grand_average_curve: Dict[int, float] = {}
        self.is_fitted: bool = False

    def fit(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> "CategoryAverageBaselineForecaster":
        """
        Fits the baseline forecaster on historical established products only.

        Args:
            products_df: DataFrame of products containing at least
                         ['product_id', 'category', 'price_tier', 'is_historical'].
            sales_df: DataFrame containing sales records:
                      ['product_id', 'week_post_launch', 'units_sold'].
        """
        # Strictly isolate historical products (filter out cold-start test set)
        if "is_historical" in products_df.columns:
            hist_products = products_df[products_df["is_historical"] == 1].copy()
        else:
            hist_products = products_df.copy()

        # Merge product metadata with sales history
        merged = sales_df.merge(hist_products, on="product_id", how="inner")
        if merged.empty:
            raise ValueError("Cannot fit baseline: no historical sales records matched products.")

        # Compute average units sold per store per week post-launch (horizon 1..8)
        # 1. Grand average across all historical products
        grand_grouped = merged.groupby("week_post_launch")["units_sold"].mean()
        self.grand_average_curve = {int(w): float(v) for w, v in grand_grouped.items()}

        # 2. Category-level averages
        cat_grouped = merged.groupby(["category", "week_post_launch"])["units_sold"].mean().reset_index()
        self.category_curves = {}
        for cat, group in cat_grouped.groupby("category"):
            self.category_curves[str(cat)] = {int(r["week_post_launch"]): float(r["units_sold"]) for _, r in group.iterrows()}

        # 3. Category + Price Tier averages
        tier_grouped = merged.groupby(["category", "price_tier", "week_post_launch"])["units_sold"].mean().reset_index()
        self.tier_curves = {}
        for (cat, tier), group in tier_grouped.groupby(["category", "price_tier"]):
            self.tier_curves[(str(cat), str(tier))] = {
                int(r["week_post_launch"]): float(r["units_sold"]) for _, r in group.iterrows()
            }

        self.is_fitted = True
        return self

    def forecast(
        self,
        new_product: Union[pd.Series, dict],
        horizon_weeks: int = 8
    ) -> Dict[str, float]:
        """
        Generates an 8-week launch forecast curve for a new product.

        Args:
            new_product: Product attribute dictionary or Series (needs 'category', optionally 'price_tier').
            horizon_weeks: Forecast horizon length in weeks (default: 8).

        Returns:
            Dict mapping week labels ('W1', 'W2', ...) to expected units per store.
        """
        if not self.is_fitted:
            raise RuntimeError("Baseline forecaster must be fitted before calling forecast().")

        category = str(new_product.get("category", ""))
        price_tier = str(new_product.get("price_tier", ""))

        curve: Optional[Dict[int, float]] = None

        # Level 1: Category + Price Tier
        if self.use_price_tier and (category, price_tier) in self.tier_curves:
            curve = self.tier_curves[(category, price_tier)]
        # Level 2: Category Average
        elif category in self.category_curves:
            curve = self.category_curves[category]
        # Level 3: Fallback Grand Average
        else:
            curve = self.grand_average_curve

        forecast_out: Dict[str, float] = {}
        for w in range(1, horizon_weeks + 1):
            val = curve.get(w, self.grand_average_curve.get(w, 50.0))
            forecast_out[f"W{w}"] = round(float(val), 2)

        return forecast_out
