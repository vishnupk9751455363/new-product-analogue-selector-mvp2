"""
src/analogue_selector.py
New-Product Analogue Selector with Weighted Feature Similarity, Explainability,
Promotional De-Biasing, and Data-Driven Cross-Validated Weight Optimization.

CONTRACT:
---------
- AnalogueSelector.find_analogues(new_product, k=5) -> List[AnalogueResult]
- AnalogueResult contains:
    - product_id
    - product_name
    - similarity_score
    - confidence_score
    - contributing_attributes: dict[str, float] (per-attribute explainable contributions)
    - explanation: human-readable explanation string
    - launch_curve: weekly historical launch sales per store (raw)
    - debiased_launch_curve: weekly historical sales stripped of promotional discounts
    - promo_lift_pct: empirical promotional lift ratio
    - promotional_inflation_units: volume expansion from promotions

- AnalogueSelector.forecast_launch_curve(new_product, k=5, debias_promotions=False) -> ForecastResult
    - Combines top-k analogue launch curves weighted by similarity score.
    - Gracefully degrades to baseline if new_product has an unseen category or insufficient analogues.
    - Optionally de-biases promotional lifts to reflect pure organic cold-start baseline.

- AnalogueSelector.optimize_weights(cv_folds=5, k=5, seed=42) -> Dict[str, Any]
    - Optimizes attribute weights using cross-validation over historical catalogue.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class AnalogueResult:
    """Individual analogue retrieved from historical catalog."""
    product_id: str
    product_name: str
    similarity_score: float
    confidence_score: float
    contributing_attributes: Dict[str, float]
    explanation: str
    launch_curve: Dict[str, float] = field(default_factory=dict)
    debiased_launch_curve: Dict[str, float] = field(default_factory=dict)
    has_promo_activity: bool = False
    promo_lift_pct: float = 0.0
    promotional_inflation_units: float = 0.0

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "similarity_score": round(self.similarity_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "contributing_attributes": {k: round(v, 4) for k, v in self.contributing_attributes.items()},
            "explanation": self.explanation,
            "launch_curve": {k: round(v, 2) for k, v in self.launch_curve.items()},
            "debiased_launch_curve": {k: round(v, 2) for k, v in self.debiased_launch_curve.items()},
            "has_promo_activity": self.has_promo_activity,
            "promo_lift_pct": round(self.promo_lift_pct, 2),
            "promotional_inflation_units": round(self.promotional_inflation_units, 2)
        }


@dataclass
class ForecastResult:
    """Combined launch forecast generated from analogue pool."""
    new_product_id: str
    forecast_curve: Dict[str, float]
    confidence_score: float
    analogues: List[AnalogueResult]
    is_degraded: bool = False
    degradation_reason: Optional[str] = None
    raw_curve: Optional[Dict[str, float]] = None
    debiased_curve: Optional[Dict[str, float]] = None
    promo_debias_applied: bool = False
    promotional_inflation_units: float = 0.0
    promotional_inflation_pct: float = 0.0
    edge_cases: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "new_product_id": self.new_product_id,
            "forecast_curve": {k: round(v, 2) for k, v in self.forecast_curve.items()},
            "confidence_score": round(self.confidence_score, 4),
            "is_degraded": self.is_degraded,
            "degradation_reason": self.degradation_reason,
            "raw_curve": {k: round(v, 2) for k, v in self.raw_curve.items()} if self.raw_curve else None,
            "debiased_curve": {k: round(v, 2) for k, v in self.debiased_curve.items()} if self.debiased_curve else None,
            "promo_debias_applied": self.promo_debias_applied,
            "promotional_inflation_units": round(self.promotional_inflation_units, 2),
            "promotional_inflation_pct": round(self.promotional_inflation_pct, 2),
            "edge_cases": self.edge_cases,
            "analogues": [a.to_dict() for a in self.analogues]
        }


class AnalogueSelector:
    """
    Interpretable analogue selector using Weighted Gower-style Similarity.
    Computes per-attribute affinity breakdowns, launch curve variance confidence,
    data-driven empirical promotional de-biasing, and cross-validated weight optimization.
    """

    PRICE_TIER_MAP = {"budget": 1, "mid": 2, "premium": 3}

    DEFAULT_WEIGHTS = {
        "category": 0.25,
        "subcategory": 0.20,
        "festival": 0.15,
        "price_tier": 0.15,
        "pack_size": 0.10,
        "shelf_life": 0.08,
        "weather_sensitivity": 0.07,
    }

    # Fallback promotional lift ratio if no historical promo variance is available
    DEFAULT_PROMO_LIFT_RATIO = 0.28

    def __init__(self, weights: Optional[Dict[str, float]] = None, similarity_threshold: float = 0.60):
        """
        Args:
            weights: Attribute weighting dictionary (sums to 1.0).
            similarity_threshold: Threshold below which an analogue is considered weak.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        # Normalize weights to ensure sum == 1.0
        total_w = sum(self.weights.values())
        self.weights = {k: v / total_w for k, v in self.weights.items()}

        self.similarity_threshold = similarity_threshold
        self.catalog_df: Optional[pd.DataFrame] = None
        self.sales_df: Optional[pd.DataFrame] = None
        self.historical_curves: Dict[str, Dict[str, float]] = {}
        self.debiased_curves: Dict[str, Dict[str, float]] = {}
        self.promo_flags: Dict[str, bool] = {}
        self.category_promo_lifts: Dict[str, float] = {}
        self.product_promo_lifts: Dict[str, float] = {}
        self.product_inflation_units: Dict[str, float] = {}
        self.numeric_ranges: Dict[str, Tuple[float, float]] = {}
        self.is_fitted: bool = False
        
        # Internal cache for fast cross-validation
        self._S_tensors: Optional[np.ndarray] = None
        self._Y_matrix: Optional[np.ndarray] = None
        self.cached_optimization_result: Optional[Dict[str, Any]] = None

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Updates and normalizes current attribute weights."""
        total_w = sum(weights.values())
        if total_w <= 0:
            raise ValueError("Sum of weights must be positive.")
        self.weights = {k: float(v) / total_w for k, v in weights.items()}

    def fit(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> "AnalogueSelector":
        """
        Indexes established products and precomputes both raw and promotionally
        de-biased weekly empirical launch curves using category/product empirical lifts.

        Args:
            products_df: Products table containing catalogue metadata.
            sales_df: Weekly sales table across stores.
        """
        # Filter to established catalogue
        if "is_historical" in products_df.columns:
            self.catalog_df = products_df[products_df["is_historical"] == 1].copy().reset_index(drop=True)
        else:
            self.catalog_df = products_df.copy().reset_index(drop=True)

        self.sales_df = sales_df.copy()

        # Compute min/max ranges for continuous normalization
        self.numeric_ranges["pack_size"] = (
            float(self.catalog_df["pack_size_units"].min()),
            float(self.catalog_df["pack_size_units"].max())
        )
        self.numeric_ranges["shelf_life"] = (
            float(self.catalog_df["shelf_life_days"].min()),
            float(self.catalog_df["shelf_life_days"].max())
        )

        # Merge sales with catalogue
        sales_hist_merged = self.sales_df.merge(
            self.catalog_df[["product_id", "category"]], on="product_id", how="inner"
        )

        # Precompute raw launch curves (average units per store for weeks 1..8)
        avg_curves = sales_hist_merged.groupby(["product_id", "week_post_launch"])["units_sold"].mean().reset_index()

        self.historical_curves = {}
        for p_id, group in avg_curves.groupby("product_id"):
            curve_dict = {}
            for _, row in group.iterrows():
                w = int(row["week_post_launch"])
                if 1 <= w <= 8:
                    curve_dict[f"W{w}"] = float(row["units_sold"])
            self.historical_curves[str(p_id)] = curve_dict

        # Calculate Empirical Category-Level and Product-Level Promotional Lifts
        has_promo_col = "is_promotion_active" in sales_hist_merged.columns
        self.category_promo_lifts = {}
        self.product_promo_lifts = {}

        if has_promo_col:
            # Category empirical lift
            cat_promo_avg = sales_hist_merged[sales_hist_merged["is_promotion_active"] == 1].groupby("category")["units_sold"].mean()
            cat_base_avg = sales_hist_merged[sales_hist_merged["is_promotion_active"] == 0].groupby("category")["units_sold"].mean()
            for cat in cat_promo_avg.index:
                if cat in cat_base_avg and cat_base_avg[cat] > 0:
                    lift_val = float((cat_promo_avg[cat] - cat_base_avg[cat]) / cat_base_avg[cat])
                    self.category_promo_lifts[cat] = max(0.10, min(2.50, lift_val))
                else:
                    self.category_promo_lifts[cat] = self.DEFAULT_PROMO_LIFT_RATIO

            # Product empirical lift
            for p_id, p_group in sales_hist_merged.groupby("product_id"):
                p_promo = p_group[p_group["is_promotion_active"] == 1]["units_sold"]
                p_base = p_group[p_group["is_promotion_active"] == 0]["units_sold"]
                if len(p_promo) > 0 and len(p_base) > 0 and p_base.mean() > 0:
                    prod_lift = float((p_promo.mean() - p_base.mean()) / p_base.mean())
                    self.product_promo_lifts[str(p_id)] = max(0.10, min(2.50, prod_lift))

        # Precompute promotionally de-biased curves
        self.debiased_curves = {}
        self.promo_flags = {}
        self.product_inflation_units = {}

        prod_cat_map = dict(zip(self.catalog_df["product_id"].astype(str), self.catalog_df["category"].astype(str)))

        for p_id, group in sales_hist_merged.groupby("product_id"):
            p_id_str = str(p_id)
            p_cat = prod_cat_map.get(p_id_str, "")
            
            # Determine effective empirical promotional lift
            eff_lift = self.product_promo_lifts.get(
                p_id_str, 
                self.category_promo_lifts.get(p_cat, self.DEFAULT_PROMO_LIFT_RATIO)
            )

            debiased_dict = {}
            had_any_promo = False
            total_raw_vol = 0.0
            total_debiased_vol = 0.0

            for w in range(1, 9):
                w_key = f"W{w}"
                week_rows = group[group["week_post_launch"] == w]
                if not week_rows.empty:
                    raw_units = float(week_rows["units_sold"].mean())
                    total_raw_vol += raw_units
                    is_promo = False
                    if has_promo_col:
                        is_promo = bool(week_rows["is_promotion_active"].mean() > 0.3)

                    if is_promo:
                        had_any_promo = True
                        # De-bias promotional lift: Base = Raw / (1 + Lift)
                        debiased_units = raw_units / (1.0 + eff_lift)
                    else:
                        debiased_units = raw_units

                    debiased_dict[w_key] = round(debiased_units, 2)
                    total_debiased_vol += debiased_units
                else:
                    raw_val = self.historical_curves.get(p_id_str, {}).get(w_key, 0.0)
                    debiased_dict[w_key] = raw_val
                    total_raw_vol += raw_val
                    total_debiased_vol += raw_val

            self.debiased_curves[p_id_str] = debiased_dict
            self.promo_flags[p_id_str] = had_any_promo
            self.product_inflation_units[p_id_str] = max(0.0, total_raw_vol - total_debiased_vol)

        # Precompute tensors for fast cross-validation optimization
        self._precompute_pairwise_tensors()

        self.is_fitted = True
        return self

    def _precompute_pairwise_tensors(self) -> None:
        """Precomputes component similarity tensors across historical products for vectorized optimization."""
        if self.catalog_df is None:
            return

        hist_df = self.catalog_df
        n = len(hist_df)
        attrs = list(self.DEFAULT_WEIGHTS.keys())

        S_tensor = np.zeros((len(attrs), n, n), dtype=np.float32)

        for m_idx, attr in enumerate(attrs):
            for i in range(n):
                p_i = hist_df.iloc[i].to_dict()
                for j in range(n):
                    if i == j:
                        continue
                    p_j = hist_df.iloc[j]
                    if attr == "category":
                        val = 1.0 if str(p_i["category"]).strip() == str(p_j["category"]).strip() else 0.0
                    elif attr == "subcategory":
                        val = 1.0 if str(p_i["subcategory"]).strip() == str(p_j["subcategory"]).strip() else 0.0
                    elif attr == "festival":
                        f_i, f_j = int(p_i.get("is_festival_linked", 0)), int(p_j.get("is_festival_linked", 0))
                        fn_i, fn_j = str(p_i.get("festival_name", "") or ""), str(p_j.get("festival_name", "") or "")
                        if f_i == 0 and f_j == 0:
                            val = 1.0
                        elif f_i == 1 and f_j == 1:
                            val = 1.0 if (fn_i == fn_j and fn_i != "") else 0.5
                        else:
                            val = 0.0
                    elif attr == "price_tier":
                        t_i = self.PRICE_TIER_MAP.get(str(p_i.get("price_tier", "mid")).lower(), 2)
                        t_j = self.PRICE_TIER_MAP.get(str(p_j.get("price_tier", "mid")).lower(), 2)
                        val = 1.0 - abs(t_i - t_j) / 2.0
                    elif attr == "pack_size":
                        min_p, max_p = self.numeric_ranges.get("pack_size", (1.0, 12.0))
                        val = 1.0 - min(1.0, abs(float(p_i.get("pack_size_units", 1.0)) - float(p_j.get("pack_size_units", 1.0))) / max(1.0, max_p - min_p))
                    elif attr == "shelf_life":
                        min_l, max_l = self.numeric_ranges.get("shelf_life", (4.0, 360.0))
                        val = 1.0 - min(1.0, abs(float(p_i.get("shelf_life_days", 14.0)) - float(p_j.get("shelf_life_days", 14.0))) / max(1.0, max_l - min_l))
                    elif attr == "weather_sensitivity":
                        val = 1.0 if int(p_i.get("weather_sensitivity", 0)) == int(p_j.get("weather_sensitivity", 0)) else 0.0
                    else:
                        val = 0.0
                    S_tensor[m_idx, i, j] = val

        # Precompute historical launch curves matrix (n x 8)
        Y_mat = np.zeros((n, 8), dtype=np.float32)
        for i in range(n):
            p_id = str(hist_df.iloc[i]["product_id"])
            curve = self.historical_curves.get(p_id, {})
            for w in range(1, 9):
                Y_mat[i, w - 1] = curve.get(f"W{w}", 0.0)

        self._S_tensors = S_tensor
        self._Y_matrix = Y_mat

    def optimize_weights(
        self,
        cv_folds: int = 5,
        k: int = 5,
        seed: int = 42,
        apply: bool = False
    ) -> Dict[str, Any]:
        """
        Transitions from static heuristic weights to data-driven optimal weights
        validated via cross-validation over the historical catalogue.

        Args:
            cv_folds: Number of cross-validation folds.
            k: Number of analogues to retrieve per validation SKU.
            seed: Deterministic random seed for fold partition.
            apply: If True, automatically replaces selector weights with optimized weights.

        Returns:
            Dictionary with optimal_weights, baseline_cv_wape, optimized_cv_wape, and improvement metrics.
        """
        if not self.is_fitted or self._S_tensors is None or self._Y_matrix is None:
            raise RuntimeError("AnalogueSelector must be fitted before running weight optimization.")

        n = len(self.catalog_df)
        attrs = list(self.DEFAULT_WEIGHTS.keys())
        S_tensor = self._S_tensors
        Y_mat = self._Y_matrix

        # Generate K-fold splits
        np.random.seed(seed)
        indices = np.arange(n)
        np.random.shuffle(indices)
        folds = np.array_split(indices, cv_folds)

        def compute_cv_wape(w_vec: np.ndarray) -> Tuple[float, List[float]]:
            w_norm = np.maximum(w_vec, 1e-4)
            w_norm = w_norm / np.sum(w_norm)

            sim_matrix = np.tensordot(w_norm, S_tensor, axes=(0, 0))

            total_abs_err = 0.0
            total_actual = 0.0
            fold_wapes = []

            for fold_val_idx in folds:
                train_mask = np.ones(n, dtype=bool)
                train_mask[fold_val_idx] = False
                train_idx = np.where(train_mask)[0]

                fold_err = 0.0
                fold_act = 0.0

                for vi in fold_val_idx:
                    sims = sim_matrix[vi, train_idx]
                    top_k_sub = np.argsort(-sims)[:k]
                    top_train_idx = train_idx[top_k_sub]
                    top_sims = np.maximum(sims[top_k_sub], 1e-4)
                    sim_wgts = top_sims / np.sum(top_sims)

                    pred_curve = np.dot(sim_wgts, Y_mat[top_train_idx, :])
                    act_curve = Y_mat[vi, :]

                    err = np.sum(np.abs(act_curve - pred_curve))
                    act = np.sum(act_curve)

                    fold_err += err
                    fold_act += act
                    total_abs_err += err
                    total_actual += act

                fold_wapes.append(float((fold_err / max(1e-4, fold_act)) * 100.0))

            overall_wape = float((total_abs_err / max(1e-4, total_actual)) * 100.0)
            return overall_wape, fold_wapes

        # Baseline heuristic performance
        heuristic_w = np.array([self.DEFAULT_WEIGHTS[a] for a in attrs], dtype=np.float32)
        base_cv_wape, base_fold_wapes = compute_cv_wape(heuristic_w)

        # Objective function with Softmax logits parameterization (strictly non-negative and sum-to-one)
        def objective(logits: np.ndarray) -> float:
            weights = np.exp(logits - np.max(logits))
            weights = weights / np.sum(weights)
            wape, _ = compute_cv_wape(weights)
            return wape

        init_logits = np.log(heuristic_w)
        res = minimize(
            objective,
            init_logits,
            method="Nelder-Mead",
            options={"maxiter": 220, "xatol": 1e-3, "fatol": 1e-3}
        )

        opt_weights_vec = np.exp(res.x - np.max(res.x))
        opt_weights_vec = opt_weights_vec / np.sum(opt_weights_vec)
        opt_cv_wape, opt_fold_wapes = compute_cv_wape(opt_weights_vec)

        optimal_weights_dict = {
            attr: round(float(w), 4) for attr, w in zip(attrs, opt_weights_vec)
        }

        improvement_pts = round(base_cv_wape - opt_cv_wape, 2)
        pct_improvement = round((improvement_pts / base_cv_wape) * 100.0, 2) if base_cv_wape > 0 else 0.0

        result = {
            "optimal_weights": optimal_weights_dict,
            "heuristic_weights": {k: round(v, 4) for k, v in self.DEFAULT_WEIGHTS.items()},
            "baseline_cv_wape": round(base_cv_wape, 2),
            "optimized_cv_wape": round(opt_cv_wape, 2),
            "wape_improvement_pts": improvement_pts,
            "pct_error_reduction": pct_improvement,
            "cv_folds": cv_folds,
            "k_analogues": k,
            "validation_samples": n,
            "fold_breakdown": [
                {
                    "fold": i + 1,
                    "baseline_wape": round(base_fold_wapes[i], 2),
                    "optimized_wape": round(opt_fold_wapes[i], 2),
                    "gain_pts": round(base_fold_wapes[i] - opt_fold_wapes[i], 2)
                }
                for i in range(len(base_fold_wapes))
            ],
            "methodology": f"Data-driven L-Softmax Nelder-Mead optimization across {cv_folds}-fold cross validation"
        }

        self.cached_optimization_result = result

        if apply:
            self.set_weights(optimal_weights_dict)

        return result

    def _compute_attribute_similarity(
        self,
        new_prod: Union[pd.Series, dict],
        cand_prod: pd.Series
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Computes pairwise Gower-style affinity per attribute between candidate and new product.
        Returns:
            (total_similarity, contributing_attributes_dict, human_explanation_lines)
        """
        contributions: Dict[str, float] = {}
        explanations: List[str] = []

        # 1. Category (Exact match)
        new_cat = str(new_prod.get("category", "")).strip()
        cand_cat = str(cand_prod.get("category", "")).strip()
        sim_cat = 1.0 if new_cat == cand_cat else 0.0
        contributions["category"] = self.weights["category"] * sim_cat
        if sim_cat == 1.0:
            explanations.append(f"Same category '{new_cat}'")
        else:
            explanations.append(f"Category mismatch ('{new_cat}' vs '{cand_cat}')")

        # 2. Subcategory (Exact match)
        new_sub = str(new_prod.get("subcategory", "")).strip()
        cand_sub = str(cand_prod.get("subcategory", "")).strip()
        sim_sub = 1.0 if new_sub == cand_sub else 0.0
        contributions["subcategory"] = self.weights["subcategory"] * sim_sub
        if sim_sub == 1.0:
            explanations.append(f"Matching subcategory '{new_sub}'")

        # 3. Festival Linkage & Festival Name
        new_is_fest = int(new_prod.get("is_festival_linked", 0))
        cand_is_fest = int(cand_prod.get("is_festival_linked", 0))
        new_fest_name = str(new_prod.get("festival_name", "") or "")
        cand_fest_name = str(cand_prod.get("festival_name", "") or "")

        if new_is_fest == 0 and cand_is_fest == 0:
            sim_fest = 1.0
            explanations.append("Both non-festival products")
        elif new_is_fest == 1 and cand_is_fest == 1:
            if new_fest_name == cand_fest_name and new_fest_name != "":
                sim_fest = 1.0
                explanations.append(f"Shares festival '{new_fest_name}'")
            else:
                sim_fest = 0.5
                explanations.append(f"Both festival products but different events ('{new_fest_name}' vs '{cand_fest_name}')")
        else:
            sim_fest = 0.0
            explanations.append("Festival status mismatch")
        contributions["festival"] = self.weights["festival"] * sim_fest

        # 4. Price Tier (Ordinal distance)
        new_tier = self.PRICE_TIER_MAP.get(str(new_prod.get("price_tier", "mid")).lower(), 2)
        cand_tier = self.PRICE_TIER_MAP.get(str(cand_prod.get("price_tier", "mid")).lower(), 2)
        tier_dist = abs(new_tier - cand_tier) / 2.0  # Max diff between 3 and 1 is 2
        sim_tier = 1.0 - tier_dist
        contributions["price_tier"] = self.weights["price_tier"] * sim_tier
        if sim_tier == 1.0:
            explanations.append(f"Identical price tier ({new_prod.get('price_tier')})")
        else:
            explanations.append(f"Different price tier ({new_prod.get('price_tier')} vs {cand_prod.get('price_tier')})")

        # 5. Pack Size (Normalized continuous)
        new_pack = float(new_prod.get("pack_size_units", 1.0))
        cand_pack = float(cand_prod.get("pack_size_units", 1.0))
        min_p, max_p = self.numeric_ranges.get("pack_size", (1.0, 12.0))
        range_p = max(1.0, max_p - min_p)
        pack_dist = min(1.0, abs(new_pack - cand_pack) / range_p)
        sim_pack = 1.0 - pack_dist
        contributions["pack_size"] = self.weights["pack_size"] * sim_pack
        if abs(new_pack - cand_pack) < 0.1:
            explanations.append(f"Identical pack size ({int(new_pack)} units)")

        # 6. Shelf Life (Normalized continuous)
        new_life = float(new_prod.get("shelf_life_days", 14.0))
        cand_life = float(cand_prod.get("shelf_life_days", 14.0))
        min_l, max_l = self.numeric_ranges.get("shelf_life", (4.0, 360.0))
        range_l = max(1.0, max_l - min_l)
        life_dist = min(1.0, abs(new_life - cand_life) / range_l)
        sim_life = 1.0 - life_dist
        contributions["shelf_life"] = self.weights["shelf_life"] * sim_life

        # 7. Weather Sensitivity (Binary)
        new_ws = int(new_prod.get("weather_sensitivity", 0))
        cand_ws = int(cand_prod.get("weather_sensitivity", 0))
        sim_ws = 1.0 if new_ws == cand_ws else 0.0
        contributions["weather_sensitivity"] = self.weights["weather_sensitivity"] * sim_ws
        if sim_ws == 1.0 and new_ws == 1:
            explanations.append("Both sensitive to weather swings")

        total_sim = sum(contributions.values())
        return total_sim, contributions, explanations

    def _compute_confidence_score(
        self,
        top_similarities: List[float],
        top_curves: List[Dict[str, float]],
        k: int
    ) -> float:
        """
        Calculates explicit confidence score C in [0.0, 1.0]:
        C = Average(Top_k_Sim) * (1 - min(0.5, CV(curves) / 2)) * (N_valid / k)
        """
        if not top_similarities:
            return 0.0

        avg_sim = float(np.mean(top_similarities))

        # Analogue depth: count of analogues meeting threshold
        valid_count = sum(1 for s in top_similarities if s >= self.similarity_threshold)
        depth_factor = min(1.0, valid_count / float(max(1, k)))

        # Launch curve consensus (variance check)
        cv_penalty = 0.0
        if top_curves and len(top_curves) > 1:
            totals = [sum(c.values()) for c in top_curves if c]
            if totals and np.mean(totals) > 0:
                std_dev = float(np.std(totals))
                mean_val = float(np.mean(totals))
                cv = std_dev / mean_val
                cv_penalty = min(0.5, cv / 2.0)

        confidence = avg_sim * (1.0 - cv_penalty) * depth_factor
        return float(np.clip(confidence, 0.0, 1.0))

    def analyze_edge_cases(
        self,
        new_product: Union[pd.Series, dict],
        analogues: Optional[List[AnalogueResult]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates potential cold-start edge case vulnerabilities.
        Returns diagnostic dictionary flagging operational risks.
        """
        p_dict = dict(new_product)
        category = str(p_dict.get("category", "")).strip()
        pack_size = float(p_dict.get("pack_size_units", 1.0))
        shelf_life = float(p_dict.get("shelf_life_days", 14.0))
        is_weather = int(p_dict.get("weather_sensitivity", 0))

        flags = []
        severity = "normal"

        # 1. Novel Category
        cat_matches = (self.catalog_df["category"] == category).sum() if self.catalog_df is not None else 0
        if cat_matches == 0:
            flags.append("NOVEL_CATEGORY: Category does not exist in historical catalog.")
            severity = "critical"

        # 2. Extreme Pack Size
        min_p, max_p = self.numeric_ranges.get("pack_size", (1.0, 12.0))
        if pack_size > max_p * 1.5:
            flags.append(f"EXTREME_PACK_SIZE: Pack size ({pack_size}) exceeds historical maximum ({max_p}).")
            if severity != "critical":
                severity = "warning"

        # 3. Severe Perishability
        if shelf_life <= 7:
            flags.append(f"HIGH_PERISHABILITY: Shelf life ({shelf_life} days) presents severe stockout/spoilage risk.")
            if severity != "critical":
                severity = "warning"

        # 4. Promotional Confound Risk
        if analogues:
            promo_analogues = sum(1 for a in analogues if a.has_promo_activity)
            if promo_analogues >= len(analogues) / 2:
                flags.append("PROMOTIONAL_CONFOUND: 50%+ of retrieved analogues had heavy intro promotions. Recommendation: enable de-biasing.")

        # 5. Weather Sensitivity Divergence
        if is_weather == 1:
            flags.append("CLIMATE_VOLATILITY: Product is sensitive to weather shocks; buffer inventory recommended.")

        return {
            "severity": severity,
            "risk_flags": flags,
            "has_warnings": len(flags) > 0,
            "recommendation": "Review planner override before release" if flags else "Safe for automated release"
        }

    def find_analogues(
        self,
        new_product: Union[pd.Series, dict],
        k: int = 5
    ) -> List[AnalogueResult]:
        """
        Finds top-k historical analogues with explainability and de-biased curves.
        """
        if not self.is_fitted or self.catalog_df is None:
            raise RuntimeError("AnalogueSelector must be fitted before find_analogues().")

        results = []
        new_prod_dict = dict(new_product)

        for _, cand_row in self.catalog_df.iterrows():
            sim_score, contributions, exp_lines = self._compute_attribute_similarity(new_prod_dict, cand_row)
            p_id = str(cand_row["product_id"])
            p_name = str(cand_row["product_name"])
            raw_curve = self.historical_curves.get(p_id, {})
            debiased_curve = self.debiased_curves.get(p_id, raw_curve)
            has_promo = self.promo_flags.get(p_id, False)
            cand_cat = str(cand_row["category"])

            eff_lift = self.product_promo_lifts.get(
                p_id, 
                self.category_promo_lifts.get(cand_cat, self.DEFAULT_PROMO_LIFT_RATIO)
            )
            inflation_units = self.product_inflation_units.get(p_id, 0.0)

            explanation_text = f"Selected because: {'; '.join(exp_lines[:4])}."

            results.append({
                "product_id": p_id,
                "product_name": p_name,
                "similarity_score": sim_score,
                "contributing_attributes": contributions,
                "explanation": explanation_text,
                "launch_curve": raw_curve,
                "debiased_launch_curve": debiased_curve,
                "has_promo_activity": has_promo,
                "promo_lift_pct": eff_lift * 100.0,
                "promotional_inflation_units": inflation_units
            })

        # Sort descending by similarity score
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_k = results[:k]

        # Compute collective confidence score
        top_sims = [r["similarity_score"] for r in top_k]
        top_curves = [r["launch_curve"] for r in top_k]
        confidence = self._compute_confidence_score(top_sims, top_curves, k)

        analogue_results: List[AnalogueResult] = []
        for r in top_k:
            analogue_results.append(AnalogueResult(
                product_id=r["product_id"],
                product_name=r["product_name"],
                similarity_score=r["similarity_score"],
                confidence_score=confidence,
                contributing_attributes=r["contributing_attributes"],
                explanation=r["explanation"],
                launch_curve=r["launch_curve"],
                debiased_launch_curve=r["debiased_launch_curve"],
                has_promo_activity=r["has_promo_activity"],
                promo_lift_pct=r["promo_lift_pct"],
                promotional_inflation_units=r["promotional_inflation_units"]
            ))

        return analogue_results

    def forecast_launch_curve(
        self,
        new_product: Union[pd.Series, dict],
        k: int = 5,
        horizon_weeks: int = 8,
        debias_promotions: bool = False
    ) -> ForecastResult:
        """
        Combines top-k analogues' historical curves into an 8-week launch forecast.
        Supports promotional de-biasing and graceful degradation.
        """
        new_prod_dict = dict(new_product)
        prod_id = str(new_prod_dict.get("product_id", "NEW_PROD_000"))
        category = str(new_prod_dict.get("category", "")).strip()

        # Check for novel category
        matching_cat_count = (self.catalog_df["category"] == category).sum() if self.catalog_df is not None else 0

        if matching_cat_count == 0:
            degradation_msg = (
                f"Graceful degradation: Category '{category}' has 0 historical matches in catalogue. "
                f"Falling back to global baseline curve."
            )
            analogues = self.find_analogues(new_product, k=k)
            confidence = 0.15

            fallback_curve: Dict[str, float] = {}
            for w in range(1, horizon_weeks + 1):
                w_key = f"W{w}"
                vals = [c.get(w_key, 50.0) for c in self.historical_curves.values() if c]
                fallback_curve[w_key] = round(float(np.mean(vals) if vals else 50.0), 2)

            edge_diag = self.analyze_edge_cases(new_product, analogues)

            return ForecastResult(
                new_product_id=prod_id,
                forecast_curve=fallback_curve,
                confidence_score=confidence,
                analogues=analogues,
                is_degraded=True,
                degradation_reason=degradation_msg,
                raw_curve=fallback_curve,
                debiased_curve=fallback_curve,
                promo_debias_applied=False,
                promotional_inflation_units=0.0,
                promotional_inflation_pct=0.0,
                edge_cases=edge_diag
            )

        # Retrieve top-k analogues
        analogues = self.find_analogues(new_product, k=k)
        if not analogues:
            raise RuntimeError(f"No analogues could be retrieved for product {prod_id}.")

        sim_weights = [max(1e-4, a.similarity_score) for a in analogues]
        total_weight = sum(sim_weights)

        # Synthesize raw curve
        raw_curve: Dict[str, float] = {}
        for w in range(1, horizon_weeks + 1):
            w_key = f"W{w}"
            week_vals = [a.launch_curve.get(w_key, 0.0) for a in analogues]
            weighted_val = sum(v * wgt for v, wgt in zip(week_vals, sim_weights)) / total_weight
            raw_curve[w_key] = round(float(weighted_val), 2)

        # Synthesize debiased curve
        debiased_curve: Dict[str, float] = {}
        for w in range(1, horizon_weeks + 1):
            w_key = f"W{w}"
            week_vals = [a.debiased_launch_curve.get(w_key, a.launch_curve.get(w_key, 0.0)) for a in analogues]
            weighted_val = sum(v * wgt for v, wgt in zip(week_vals, sim_weights)) / total_weight
            debiased_curve[w_key] = round(float(weighted_val), 2)

        raw_total = sum(raw_curve.values())
        debiased_total = sum(debiased_curve.values())
        promo_inflation_units = max(0.0, raw_total - debiased_total)
        promo_inflation_pct = (promo_inflation_units / max(1e-4, raw_total)) * 100.0 if raw_total > 0 else 0.0

        active_curve = debiased_curve if debias_promotions else raw_curve
        edge_diag = self.analyze_edge_cases(new_product, analogues)

        return ForecastResult(
            new_product_id=prod_id,
            forecast_curve=active_curve,
            confidence_score=analogues[0].confidence_score,
            analogues=analogues,
            is_degraded=False,
            degradation_reason=None,
            raw_curve=raw_curve,
            debiased_curve=debiased_curve,
            promo_debias_applied=debias_promotions,
            promotional_inflation_units=round(promo_inflation_units, 2),
            promotional_inflation_pct=round(promo_inflation_pct, 2),
            edge_cases=edge_diag
        )
