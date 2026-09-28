"""
app.py
FastAPI Web Application Backend for the New-Product Analogue Selector.
Exposes REST APIs for:
- Cold-start catalogue browsing
- Interactive analogue retrieval with per-attribute explainability & promotional de-biasing
- Data-driven cross-validated weight optimization
- Launch curve forecasting vs. naive baseline
- Disruption scenario simulation & stress testing (supplier delay, capacity loss, viral spikes, weather anomalies, festival shifts)
- Immutable audit trail queries and planner overrides
- Benchmark evaluation results
"""

import os
import sys
import json
import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.analogue_selector import AnalogueSelector
from src.baseline import CategoryAverageBaselineForecaster
from src.audit_log import PlanAuditLogger
from src.evaluate import run_benchmark
from src.disruption_scenarios import run_disruption_scenario, DisruptionResult

DB_PATH = os.path.join(BASE_DIR, "db", "warehouse.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="New-Product Analogue Selector API",
    description="Decision-support system for grocery cold-start launch forecasting & disruption stress testing",
    version="2.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global models initialized at startup
selector_engine: Optional[AnalogueSelector] = None
baseline_engine: Optional[CategoryAverageBaselineForecaster] = None
audit_logger = PlanAuditLogger(DB_PATH)


def get_db():
    if not os.path.exists(DB_PATH):
        raise RuntimeError("Database not found. Please run scripts/generate_synthetic_data.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_models():
    global selector_engine, baseline_engine
    if not os.path.exists(DB_PATH):
        from scripts.generate_synthetic_data import main as gen_data
        gen_data()

    conn = get_db()
    products_df = pd.read_sql("SELECT * FROM products", conn)
    sales_df = pd.read_sql("SELECT * FROM sales_history", conn)
    conn.close()

    selector_engine = AnalogueSelector()
    selector_engine.fit(products_df, sales_df)

    baseline_engine = CategoryAverageBaselineForecaster(use_price_tier=True)
    baseline_engine.fit(products_df, sales_df)


@app.on_event("startup")
def on_startup():
    init_models()


# Models for API requests
class AnalogueRequest(BaseModel):
    product_id: Optional[str] = None
    custom_product: Optional[Dict[str, Any]] = None
    k: int = 5
    custom_weights: Optional[Dict[str, float]] = None
    debias_promotions: bool = False
    use_optimized_weights: bool = False


class OverrideRequest(BaseModel):
    product_id: str
    changed_by: str
    field_changed: str
    old_value: Any
    new_value: Any
    reason: str


class WeightOptimizeRequest(BaseModel):
    cv_folds: int = 5
    k: int = 5
    seed: int = 42
    apply_to_engine: bool = True


class DisruptionRequest(BaseModel):
    product_id: Optional[str] = None
    custom_forecast: Optional[Dict[str, float]] = None
    scenario_type: str = "supplier_delay"
    delay_weeks: int = 2
    spoilage_rate_pct: float = 0.05
    shelf_life_days: Optional[int] = None
    max_weekly_store_capacity: float = 120.0
    spillover_rate: float = 0.35
    spike_week: int = 3
    spike_multiplier: float = 2.2
    safety_buffer_pct: float = 0.20
    # Meteorological and calendar drift parameters
    weather_type: str = "heatwave"
    intensity_pct: float = 0.65
    affected_weeks: Optional[List[int]] = None
    weather_sensitivity: Optional[int] = None
    category: Optional[str] = None
    shift_direction: str = "earlier"
    shift_weeks: int = 2
    original_peak_week: int = 4
    peak_multiplier: float = 1.9
    is_festival_linked: Optional[int] = None


@app.get("/api/health")
def health_check():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    total_prods = cur.fetchone()[0]
    conn.close()
    return {
        "status": "online",
        "database": "connected",
        "total_products": total_prods,
        "models_loaded": selector_engine is not None and baseline_engine is not None,
        "phase": "Phase 2 Complete (Enterprise Grade)"
    }


@app.get("/api/products")
def list_products(is_historical: Optional[int] = Query(None)):
    conn = get_db()
    cur = conn.cursor()
    if is_historical is not None:
        cur.execute("SELECT * FROM products WHERE is_historical = ? ORDER BY product_id", (is_historical,))
    else:
        cur.execute("SELECT * FROM products ORDER BY is_historical ASC, product_id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"products": rows}


@app.post("/api/weights/optimize")
def optimize_weights_api(req: Optional[WeightOptimizeRequest] = None):
    """
    Executes data-driven weight optimization via K-fold cross validation on historical catalogue.
    """
    global selector_engine
    if selector_engine is None:
        init_models()

    cv_folds = req.cv_folds if req else 5
    k = req.k if req else 5
    seed = req.seed if req else 42
    apply_flag = req.apply_to_engine if req else True

    try:
        report = selector_engine.optimize_weights(cv_folds=cv_folds, k=k, seed=seed, apply=apply_flag)
        return {
            "status": "success",
            "optimization_result": report,
            "weights_applied": apply_flag
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weight optimization failed: {str(e)}")


@app.get("/api/weights/optimized")
def get_optimized_weights_api():
    """
    Returns cached or computed data-driven optimal weights.
    """
    global selector_engine
    if selector_engine is None:
        init_models()

    if selector_engine.cached_optimization_result:
        return {"status": "success", "optimization_result": selector_engine.cached_optimization_result}

    try:
        report = selector_engine.optimize_weights(cv_folds=5, apply=False)
        return {"status": "success", "optimization_result": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analogues")
def get_analogues(req: AnalogueRequest):
    global selector_engine, baseline_engine
    if selector_engine is None or baseline_engine is None:
        init_models()

    target_prod = None

    if req.product_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE product_id = ?", (req.product_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"Product {req.product_id} not found.")
        target_prod = dict(row)
    elif req.custom_product:
        target_prod = req.custom_product
        if "product_id" not in target_prod:
            target_prod["product_id"] = "PRD_CUSTOM_EXP"
    else:
        raise HTTPException(status_code=400, detail="Must provide either product_id or custom_product.")

    # Configure custom weights if provided or optimized
    local_selector = selector_engine
    if req.use_optimized_weights and selector_engine.cached_optimization_result:
        opt_w = selector_engine.cached_optimization_result["optimal_weights"]
        local_selector = AnalogueSelector(weights=opt_w)
        conn = get_db()
        products_df = pd.read_sql("SELECT * FROM products", conn)
        sales_df = pd.read_sql("SELECT * FROM sales_history", conn)
        conn.close()
        local_selector.fit(products_df, sales_df)
    elif req.custom_weights:
        local_selector = AnalogueSelector(weights=req.custom_weights)
        conn = get_db()
        products_df = pd.read_sql("SELECT * FROM products", conn)
        sales_df = pd.read_sql("SELECT * FROM sales_history", conn)
        conn.close()
        local_selector.fit(products_df, sales_df)

    # 1. Retrieve analogues
    analogues = local_selector.find_analogues(target_prod, k=req.k)

    # 2. Compute launch forecast (with empirical promo de-biasing)
    fc_result = local_selector.forecast_launch_curve(
        target_prod,
        k=req.k,
        debias_promotions=req.debias_promotions
    )

    # 3. Compute baseline forecast
    base_forecast = baseline_engine.forecast(target_prod)

    # 4. Diagnostic edge cases
    edge_cases = local_selector.analyze_edge_cases(target_prod, analogues)

    return {
        "target_product": target_prod,
        "analogues": [a.to_dict() for a in analogues],
        "forecast": fc_result.to_dict(),
        "baseline_forecast": base_forecast,
        "weights_used": local_selector.weights,
        "debias_promotions_applied": req.debias_promotions,
        "raw_curve": fc_result.raw_curve,
        "debiased_curve": fc_result.debiased_curve,
        "promotional_inflation_units": fc_result.promotional_inflation_units,
        "promotional_inflation_pct": fc_result.promotional_inflation_pct,
        "edge_cases": edge_cases
    }


@app.post("/api/disruptions/simulate")
def simulate_disruption(req: DisruptionRequest):
    """
    Stress-tests launch forecast against supply chain delays, capacity caps, viral spikes,
    weather anomalies, or localized festival shifts.
    """
    global selector_engine
    if selector_engine is None:
        init_models()

    launch_fc = req.custom_forecast
    shelf_life = req.shelf_life_days
    weather_sens = req.weather_sensitivity
    cat_val = req.category
    fest_flag = req.is_festival_linked

    if not launch_fc or shelf_life is None or weather_sens is None or cat_val is None or fest_flag is None:
        # Extract product specs from DB if available
        target_id = req.product_id or "PRD_NEW_083"
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE product_id = ?", (target_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            prod_dict = dict(row)
            if shelf_life is None:
                shelf_life = prod_dict.get("shelf_life_days", 14)
            if weather_sens is None:
                weather_sens = prod_dict.get("weather_sensitivity", 0)
            if cat_val is None:
                cat_val = prod_dict.get("category", "Beverages")
            if fest_flag is None:
                fest_flag = prod_dict.get("is_festival_linked", 0)
            if not launch_fc:
                fc_res = selector_engine.forecast_launch_curve(prod_dict, k=5)
                launch_fc = fc_res.forecast_curve
        else:
            if not launch_fc:
                raise HTTPException(status_code=404, detail=f"Product {target_id} not found.")

    try:
        res = run_disruption_scenario(
            scenario_type=req.scenario_type,
            launch_forecast=launch_fc,
            delay_weeks=req.delay_weeks,
            spoilage_rate_pct=req.spoilage_rate_pct,
            shelf_life_days=shelf_life,
            max_weekly_store_capacity=req.max_weekly_store_capacity,
            spillover_rate=req.spillover_rate,
            spike_week=req.spike_week,
            spike_multiplier=req.spike_multiplier,
            safety_buffer_pct=req.safety_buffer_pct,
            weather_type=req.weather_type,
            intensity_pct=req.intensity_pct,
            affected_weeks=req.affected_weeks or [2, 3],
            weather_sensitivity=weather_sens if weather_sens is not None else 1,
            category=cat_val or "Beverages",
            shift_direction=req.shift_direction,
            shift_weeks=req.shift_weeks,
            original_peak_week=req.original_peak_week,
            peak_multiplier=req.peak_multiplier,
            is_festival_linked=fest_flag if fest_flag is not None else 1
        )
        return {"status": "success", "result": res.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/disruptions/presets")
def get_disruption_presets():
    """Returns curated stress-testing scenario presets."""
    return {
        "presets": [
            {
                "id": "supplier_delay_2w",
                "name": "Upstream Port Congestion (2-Week Delay)",
                "scenario_type": "supplier_delay",
                "delay_weeks": 2,
                "spoilage_rate_pct": 0.05,
                "description": "Container port bottleneck shifts commercial arrival by 14 days. Marketing buzz dampens by ~15%."
            },
            {
                "id": "supplier_delay_4w_perishable",
                "name": "Severe Packaging Shortage (4-Week Delay)",
                "scenario_type": "supplier_delay",
                "delay_weeks": 4,
                "spoilage_rate_pct": 0.08,
                "description": "Critical supplier raw ingredient delay. Severe spoilage penalty on short shelf-life categories."
            },
            {
                "id": "capacity_loss_reefer",
                "name": "Cold-Chain Reefer Fleet Bottleneck (110 Units/Store Cap)",
                "scenario_type": "capacity_loss",
                "max_weekly_store_capacity": 110.0,
                "spillover_rate": 0.35,
                "description": "Refrigerated transport fleet capacity shortage caps weekly delivery volume across retail doors."
            },
            {
                "id": "viral_social_spike",
                "name": "Viral Social Media Surge (2.5x in Week 3)",
                "scenario_type": "unplanned_spike",
                "spike_week": 3,
                "spike_multiplier": 2.5,
                "safety_buffer_pct": 0.20,
                "description": "Organic influencer promotion triggers sudden 250% demand spike above forecast."
            },
            {
                "id": "heatwave_surge",
                "name": "Unseasonal Heatwave Surge (+65% in W2-W3)",
                "scenario_type": "weather_anomaly",
                "weather_type": "heatwave",
                "intensity_pct": 0.65,
                "affected_weeks": [2, 3],
                "description": "Prolonged high temperatures drive massive cold-beverage demand spike and elevate refrigeration spoilage risk."
            },
            {
                "id": "monsoon_flooding",
                "name": "Torrential Monsoon Storm (-30% Store Footfall)",
                "scenario_type": "weather_anomaly",
                "weather_type": "torrential_rain",
                "intensity_pct": 0.60,
                "affected_weeks": [2, 3],
                "description": "Flooding causes store footfall drop, transport road closures, and staged inventory write-offs."
            },
            {
                "id": "festival_shift_early",
                "name": "Diwali Date Drift (-2 Weeks Earlier)",
                "scenario_type": "festival_shift",
                "shift_direction": "earlier",
                "shift_weeks": 2,
                "original_peak_week": 4,
                "peak_multiplier": 1.9,
                "description": "Lunar calendar drift brings holiday rush 14 days earlier, creating initial stockouts and post-holiday dead stock."
            },
            {
                "id": "festival_shift_late",
                "name": "Regional Holiday Delay (+2 Weeks Later)",
                "scenario_type": "festival_shift",
                "shift_direction": "later",
                "shift_weeks": 2,
                "original_peak_week": 3,
                "peak_multiplier": 1.8,
                "description": "Festival shift leaves early shipments sitting on shelves, risking short shelf-life expiration before demand hits."
            }
        ]
    }


@app.post("/api/audit/override")
def record_planner_override(req: OverrideRequest):
    try:
        change_id = audit_logger.record_change(
            product_id=req.product_id,
            changed_by=req.changed_by,
            field_changed=req.field_changed,
            old_value=req.old_value,
            new_value=req.new_value,
            reason=req.reason,
            source="planner_override"
        )
        return {"status": "success", "change_id": change_id, "message": "Override recorded into immutable audit log."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/audit/trail")
def get_audit_trail(product_id: Optional[str] = Query(None)):
    trail = audit_logger.get_audit_trail(product_id=product_id)
    return {"audit_trail": trail, "total_records": len(trail)}


@app.post("/api/audit/test-tamper")
def test_tamper(change_id: int = Query(1)):
    """Attempts to update an existing audit log entry to verify database-level trigger prevention."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE plan_changes SET reason = 'Unauthorized Modification' WHERE change_id = ?", (change_id,))
        conn.commit()
        conn.close()
        return {"tamper_successful": True, "message": "CRITICAL: Immutability trigger failed!"}
    except sqlite3.DatabaseError as e:
        conn.close()
        return {
            "tamper_successful": False,
            "trigger_blocked": True,
            "error_message": str(e),
            "description": "Database triggers actively rejected unauthorized UPDATE operation."
        }


@app.get("/api/benchmark")
def get_benchmark_results():
    try:
        res = run_benchmark(db_path=DB_PATH, k=5, horizon_weeks=8)
        return {
            "overall": res["overall"],
            "weekly": res["weekly"].to_dict(orient="records"),
            "per_product": res["per_product"].to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static assets
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend static file is generating..."}


@app.get("/style.css")
def serve_css():
    return FileResponse(os.path.join(STATIC_DIR, "style.css"))


@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
