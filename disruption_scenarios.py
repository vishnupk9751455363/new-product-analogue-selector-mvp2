"""
src/disruption_scenarios.py
Disruption Scenario Simulation & Stress-Testing Engine for Cold-Start Grocery Launches.

Simulates supply chain and demand shocks:
1. Supplier Inbound Delay: Upstream delivery lag, launch curve shifting, promotional momentum decay, and perishability spoilage.
2. Logistics Capacity Loss: Warehouse logistics bottlenecks and cold-chain capacity caps with spillover dynamics.
3. Unplanned Demand Shock: Viral social trends or extreme surges with inventory exhaustion and safety buffer deficits.
4. Weather Anomalies: Unseasonal heatwaves, cold snaps, or torrential monsoon flooding altering category-specific demand trajectories and spoilage.
5. Localized Festival Calendar Drift: Cultural festival date shifts (e.g., Diwali, Lunar New Year, Eid) creating demand peak mismatches, retail stockouts, and post-holiday perishable write-offs.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class DisruptionResult:
    """Standardized output container for disruption scenario simulations."""
    scenario_name: str
    scenario_type: str
    original_forecast: Dict[str, float]
    disrupted_forecast: Dict[str, float]
    lost_sales_units: float
    spoilage_units: float
    stockout_risk_pct: float
    recommended_buffer_units: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    operational_guidance: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "original_forecast": {k: round(v, 2) for k, v in self.original_forecast.items()},
            "disrupted_forecast": {k: round(v, 2) for k, v in self.disrupted_forecast.items()},
            "lost_sales_units": round(self.lost_sales_units, 2),
            "spoilage_units": round(self.spoilage_units, 2),
            "stockout_risk_pct": round(self.stockout_risk_pct, 2),
            "recommended_buffer_units": round(self.recommended_buffer_units, 2),
            "metrics": self.metrics,
            "operational_guidance": self.operational_guidance
        }


def simulate_supplier_delay(
    launch_forecast: Dict[str, float],
    delay_weeks: int = 2,
    spoilage_rate_pct: float = 0.05,
    shelf_life_days: Optional[int] = None,
    momentum_decay_per_week: float = 0.08
) -> DisruptionResult:
    """
    Simulates upstream supplier or packaging delay on introductory launch trajectory.

    Args:
        launch_forecast: Weekly baseline forecast dictionary {'W1': units, ...}.
        delay_weeks: Number of weeks launch is delayed (zeros out initial weeks).
        spoilage_rate_pct: Base perishability loss rate per week of storage delay.
        shelf_life_days: Product shelf life; if short (<14 days), spoilage accelerates.
        momentum_decay_per_week: Rate at which initial launch marketing momentum decays.

    Returns:
        DisruptionResult with shifted curve, spoilage losses, and operational guidance.
    """
    if delay_weeks < 0:
        raise ValueError("delay_weeks must be non-negative.")

    weeks = list(launch_forecast.keys())
    orig_vals = [launch_forecast[w] for w in weeks]

    # Effective spoilage multiplier: highly perishable items suffer accelerated decay
    eff_spoilage_rate = spoilage_rate_pct
    if shelf_life_days is not None and shelf_life_days > 0:
        if shelf_life_days <= 7:
            eff_spoilage_rate = min(1.0, spoilage_rate_pct * 4.5)  # E.g. Artisan bakery / fresh dairy
        elif shelf_life_days <= 21:
            eff_spoilage_rate = min(1.0, spoilage_rate_pct * 2.0)

    # Calculate spoilage on pre-ordered pipeline inventory
    pipeline_initial_stock = orig_vals[0] if orig_vals else 0.0
    spoilage_units = min(pipeline_initial_stock, pipeline_initial_stock * eff_spoilage_rate * delay_weeks)

    # Momentum factor: promotional buzz decays while on backorder
    momentum_retention = max(0.5, (1.0 - momentum_decay_per_week) ** delay_weeks)

    disrupted_curve: Dict[str, float] = {}
    lost_demand_total = 0.0

    for i, w in enumerate(weeks):
        if i < delay_weeks:
            # During delay weeks, product is out-of-stock at retail
            disrupted_curve[w] = 0.0
            lost_demand_total += orig_vals[i]
        else:
            # Shifted launch: launch wave begins at (i - delay_weeks)
            source_idx = i - delay_weeks
            base_demand = orig_vals[source_idx]
            
            # Apply momentum damping to initial surge weeks (first 2 active weeks)
            if source_idx < 2:
                adjusted_demand = base_demand * momentum_retention
            else:
                adjusted_demand = base_demand
                
            disrupted_curve[w] = round(adjusted_demand, 2)

    # Stockout risk is 100% during the delay window
    stockout_risk = 100.0 if delay_weeks > 0 else 0.0

    guidance = (
        f"Supplier delay of {delay_weeks} week(s) zeroes initial retail fulfillment, risking "
        f"{round(lost_demand_total, 1)} units in unfulfilled intro demand. "
        f"Estimated inventory write-off: {round(spoilage_units, 1)} units due to shelf-life degradation. "
        f"Launch marketing momentum reduced to {round(momentum_retention * 100, 1)}%. "
        f"Action: Reschedule retail flyer promotions to Week {delay_weeks + 1} and notify distributor fleet."
    )

    return DisruptionResult(
        scenario_name=f"Supplier Inbound Delay ({delay_weeks} Weeks)",
        scenario_type="supplier_delay",
        original_forecast=launch_forecast,
        disrupted_forecast=disrupted_curve,
        lost_sales_units=lost_demand_total,
        spoilage_units=spoilage_units,
        stockout_risk_pct=stockout_risk,
        recommended_buffer_units=round(spoilage_units * 1.2, 2),
        metrics={
            "delay_weeks": delay_weeks,
            "effective_spoilage_rate": round(eff_spoilage_rate, 4),
            "momentum_retention_pct": round(momentum_retention * 100, 1),
            "lost_introductory_demand": round(lost_demand_total, 2)
        },
        operational_guidance=guidance
    )


def simulate_capacity_loss(
    launch_forecast: Dict[str, float],
    max_weekly_store_capacity: float,
    spillover_rate: float = 0.35,
    shelf_life_days: Optional[int] = None
) -> DisruptionResult:
    """
    Simulates regional warehouse throughput limits, refrigerated trucking shortages,
    or shelf allocation caps.

    Args:
        launch_forecast: Weekly baseline forecast dictionary {'W1': units, ...}.
        max_weekly_store_capacity: Upper physical limit on store delivery per week.
        spillover_rate: Fraction of unfulfilled demand that rolls into subsequent week.
        shelf_life_days: If shelf life is short (<= 7 days), spillover drops to 0 (perishable substitution).

    Returns:
        DisruptionResult with capped curve, lost sales, and bottleneck analysis.
    """
    if max_weekly_store_capacity <= 0:
        raise ValueError("max_weekly_store_capacity must be positive.")

    weeks = list(launch_forecast.keys())
    orig_vals = [launch_forecast[w] for w in weeks]

    eff_spillover = spillover_rate
    if shelf_life_days is not None and shelf_life_days <= 7:
        eff_spillover = 0.05  # Perishable shoppers switch brands immediately rather than wait

    disrupted_curve: Dict[str, float] = {}
    total_lost_sales = 0.0
    carryover_demand = 0.0
    bottleneck_count = 0
    max_deficit = 0.0

    for w in weeks:
        unconstrained_demand = launch_forecast[w] + carryover_demand
        if unconstrained_demand > max_weekly_store_capacity:
            shipped = max_weekly_store_capacity
            unfulfilled = unconstrained_demand - shipped
            deficit = unfulfilled
            if deficit > max_deficit:
                max_deficit = deficit
            bottleneck_count += 1
            lost_sales = unfulfilled * (1.0 - eff_spillover)
            carryover_demand = unfulfilled * eff_spillover
            total_lost_sales += lost_sales
        else:
            shipped = unconstrained_demand
            carryover_demand = 0.0

        disrupted_curve[w] = round(shipped, 2)

    # Any remaining carryover at the end of horizon is permanently lost
    total_lost_sales += carryover_demand

    peak_demand = max(orig_vals) if orig_vals else 0.0
    stockout_risk = min(100.0, max(0.0, (peak_demand - max_weekly_store_capacity) / (peak_demand or 1.0) * 100.0))

    guidance = (
        f"Throughput cap of {round(max_weekly_store_capacity, 1)} units/store restricts distribution in "
        f"{bottleneck_count} out of {len(weeks)} launch weeks. "
        f"Peak delivery deficit reached {round(max_deficit, 1)} units/store. "
        f"Estimated permanent lost sales: {round(total_lost_sales, 1)} units. "
        f"Action: Authorize secondary cross-dock distributor or stagger regional rollouts by sub-zones."
    )

    return DisruptionResult(
        scenario_name=f"Logistics Capacity Ceiling ({round(max_weekly_store_capacity, 0)} Units/Store)",
        scenario_type="capacity_loss",
        original_forecast=launch_forecast,
        disrupted_forecast=disrupted_curve,
        lost_sales_units=total_lost_sales,
        spoilage_units=0.0,
        stockout_risk_pct=stockout_risk,
        recommended_buffer_units=round(max_deficit, 2),
        metrics={
            "capacity_ceiling": max_weekly_store_capacity,
            "bottlenecked_weeks_count": bottleneck_count,
            "max_weekly_deficit": round(max_deficit, 2),
            "spillover_retention_pct": round(eff_spillover * 100, 1)
        },
        operational_guidance=guidance
    )


def simulate_unplanned_spike(
    launch_forecast: Dict[str, float],
    spike_week: int = 3,
    spike_multiplier: float = 2.2,
    post_spike_exhaustion_rate: float = 0.15,
    safety_buffer_pct: float = 0.20
) -> DisruptionResult:
    """
    Simulates unexpected demand shock from viral social media traction, heatwaves,
    or sudden competitor stockouts.

    Args:
        launch_forecast: Weekly baseline forecast dictionary {'W1': units, ...}.
        spike_week: Week index (1..8) where the shock hits.
        spike_multiplier: Multiplier factor for surge demand (e.g. 2.2x).
        post_spike_exhaustion_rate: Demand dip in subsequent week due to pantry-loading.
        safety_buffer_pct: Existing baseline safety inventory buffer.

    Returns:
        DisruptionResult with shocked demand curve and emergency replenishment sizing.
    """
    weeks = list(launch_forecast.keys())
    n_weeks = len(weeks)

    if spike_week < 1 or spike_week > n_weeks:
        raise ValueError(f"spike_week must be between 1 and {n_weeks}.")

    target_week_key = f"W{spike_week}"
    next_week_key = f"W{spike_week + 1}" if spike_week < n_weeks else None

    disrupted_curve: Dict[str, float] = {}
    base_surge_demand = launch_forecast.get(target_week_key, 0.0)
    surge_volume = base_surge_demand * spike_multiplier
    
    # Existing safety inventory can only absorb buffer_pct above baseline
    absorbed_capacity = base_surge_demand * (1.0 + safety_buffer_pct)
    unmitigated_deficit = max(0.0, surge_volume - absorbed_capacity)
    stockout_risk = min(100.0, (surge_volume - base_surge_demand) / (surge_volume or 1.0) * 100.0)

    for i, w in enumerate(weeks, start=1):
        if i == spike_week:
            disrupted_curve[w] = round(surge_volume, 2)
        elif next_week_key and w == next_week_key:
            # Slight post-surge exhaustion dip
            dip_demand = launch_forecast[w] * (1.0 - post_spike_exhaustion_rate)
            disrupted_curve[w] = round(dip_demand, 2)
        else:
            disrupted_curve[w] = round(launch_forecast[w], 2)

    guidance = (
        f"Unplanned demand spike in Week {spike_week} at {spike_multiplier}x baseline elevates demand to "
        f"{round(surge_volume, 1)} units/store (baseline: {round(base_surge_demand, 1)} units). "
        f"Current safety stock ({round(safety_buffer_pct * 100, 0)}%) leaves a critical buffer deficit of "
        f"{round(unmitigated_deficit, 1)} units/store with {round(stockout_risk, 1)}% stockout probability. "
        f"Action: Trigger emergency supplier expedite order of {round(unmitigated_deficit * 1.15, 1)} units."
    )

    return DisruptionResult(
        scenario_name=f"Demand Surge Shock ({spike_multiplier}x at Week {spike_week})",
        scenario_type="unplanned_spike",
        original_forecast=launch_forecast,
        disrupted_forecast=disrupted_curve,
        lost_sales_units=unmitigated_deficit,
        spoilage_units=0.0,
        stockout_risk_pct=stockout_risk,
        recommended_buffer_units=round(unmitigated_deficit * 1.15, 2),
        metrics={
            "spike_week": spike_week,
            "multiplier": spike_multiplier,
            "surge_volume": round(surge_volume, 2),
            "unmitigated_buffer_deficit": round(unmitigated_deficit, 2)
        },
        operational_guidance=guidance
    )


def simulate_weather_anomaly(
    launch_forecast: Dict[str, float],
    weather_type: str = "heatwave",
    intensity_pct: float = 0.65,
    affected_weeks: Optional[List[int]] = None,
    weather_sensitivity: int = 1,
    category: str = "Beverages",
    shelf_life_days: Optional[int] = None,
    safety_buffer_pct: float = 0.20
) -> DisruptionResult:
    """
    Simulates meteorological disruption scenarios:
    - Heatwave Surge: Intense heat causes +50% to +85% demand surge for weather-sensitive beverages/dairy,
      with elevated refrigerated storage degradation risk.
    - Torrential Monsoon / Storms: Severe flooding and friction dampens footfall by -25% to -40%,
      with elevated in-transit perishability write-offs.
    - Cold Snap / Frost: Chilled categories drop (-35%), while warm comfort bakery goods surge (+30%).

    Args:
        launch_forecast: Baseline 8-week launch forecast dictionary.
        weather_type: 'heatwave', 'torrential_rain', or 'cold_snap'.
        intensity_pct: Shock magnitude (e.g. 0.65 = +65% surge or -35% drop).
        affected_weeks: List of affected 1-indexed weeks (default: [2, 3]).
        weather_sensitivity: 1 if target SKU is sensitive to temperature/weather swings.
        category: Product category name.
        shelf_life_days: Product shelf life in days.
        safety_buffer_pct: Existing baseline safety inventory buffer.

    Returns:
        DisruptionResult with adjusted demand, stockout deficit, spoilage, and playbook guidance.
    """
    weeks = list(launch_forecast.keys())
    n_weeks = len(weeks)
    active_weeks = affected_weeks if affected_weeks else [2, 3]

    disrupted_curve: Dict[str, float] = {}
    total_unmitigated_deficit = 0.0
    spoilage_units = 0.0
    max_stockout_risk = 0.0

    wt = weather_type.lower().strip()
    is_chilled_category = category in ["Beverages", "Dairy & Refrigerated", "Dairy", "Fresh Produce"]

    for i, w in enumerate(weeks, start=1):
        base_val = launch_forecast[w]
        
        if i in active_weeks:
            if wt == "heatwave":
                if weather_sensitivity == 1 or is_chilled_category:
                    # Surge for cold drinks/dairy
                    surge_vol = base_val * (1.0 + intensity_pct)
                    disrupted_curve[w] = round(surge_vol, 2)
                    absorbed = base_val * (1.0 + safety_buffer_pct)
                    deficit = max(0.0, surge_vol - absorbed)
                    total_unmitigated_deficit += deficit
                    risk = min(100.0, (surge_vol - base_val) / (surge_vol or 1.0) * 100.0)
                    if risk > max_stockout_risk:
                        max_stockout_risk = risk
                    # Heatwave storage spoilage on perishable items
                    if shelf_life_days and shelf_life_days <= 14:
                        spoilage_units += base_val * 0.04
                else:
                    # Ambient categories experience slight footfall diversion
                    disrupted_curve[w] = round(base_val * 0.90, 2)

            elif wt == "torrential_rain":
                # Severe monsoon/storm: footfall drops across all categories
                drop_rate = min(0.60, max(0.15, intensity_pct * 0.5))
                suppressed_vol = base_val * (1.0 - drop_rate)
                disrupted_curve[w] = round(suppressed_vol, 2)
                # In-transit humidity/water damage write-offs
                if shelf_life_days and shelf_life_days <= 21:
                    spoilage_units += base_val * 0.06
                
            elif wt == "cold_snap":
                if is_chilled_category:
                    drop_val = base_val * max(0.5, (1.0 - intensity_pct * 0.6))
                    disrupted_curve[w] = round(drop_val, 2)
                else:
                    # Comfort bakery/warm items surge
                    boost_val = base_val * (1.0 + intensity_pct * 0.5)
                    disrupted_curve[w] = round(boost_val, 2)
                    absorbed = base_val * (1.0 + safety_buffer_pct)
                    deficit = max(0.0, boost_val - absorbed)
                    total_unmitigated_deficit += deficit
            else:
                disrupted_curve[w] = base_val

        elif i == max(active_weeks) + 1 and i <= n_weeks:
            # Post-shock normalization bounce
            if wt == "torrential_rain":
                # Deferred shopping bounce-back
                disrupted_curve[w] = round(base_val * 1.15, 2)
            elif wt == "heatwave" and (weather_sensitivity == 1 or is_chilled_category):
                # Mild normalization dip
                disrupted_curve[w] = round(base_val * 0.92, 2)
            else:
                disrupted_curve[w] = round(base_val, 2)
        else:
            disrupted_curve[w] = round(base_val, 2)

    scenario_label = {
        "heatwave": f"Heatwave Surge (+{round(intensity_pct * 100, 0)}% in W{active_weeks[0]}-W{active_weeks[-1]})",
        "torrential_rain": f"Unseasonal Monsoon Flooding (-{round(intensity_pct * 50, 0)}% Footfall)",
        "cold_snap": f"Unseasonal Cold Snap & Freeze Shock"
    }.get(wt, f"Weather Shock ({wt.capitalize()})")

    guidance = (
        f"Weather anomaly ({wt.capitalize()}) over weeks {active_weeks} alters launch trajectory. "
        f"Unmitigated buffer deficit: {round(total_unmitigated_deficit, 1)} units/store with "
        f"{round(max_stockout_risk, 1)}% peak stockout risk. "
        f"Perishability and cold-chain write-off risk: {round(spoilage_units, 1)} units. "
        f"Action: Dispatch emergency regional safety buffer of {round(total_unmitigated_deficit * 1.2 + spoilage_units, 1)} units "
        f"to priority refrigerated retail doors."
    )

    return DisruptionResult(
        scenario_name=scenario_label,
        scenario_type="weather_anomaly",
        original_forecast=launch_forecast,
        disrupted_forecast=disrupted_curve,
        lost_sales_units=total_unmitigated_deficit,
        spoilage_units=spoilage_units,
        stockout_risk_pct=max_stockout_risk,
        recommended_buffer_units=round(total_unmitigated_deficit * 1.2 + spoilage_units, 2),
        metrics={
            "weather_type": wt,
            "intensity_pct": round(intensity_pct * 100, 1),
            "affected_weeks": active_weeks,
            "weather_sensitivity_flag": weather_sensitivity,
            "unmitigated_buffer_deficit": round(total_unmitigated_deficit, 2),
            "weather_induced_spoilage": round(spoilage_units, 2)
        },
        operational_guidance=guidance
    )


def simulate_festival_shift(
    launch_forecast: Dict[str, float],
    shift_direction: str = "earlier",
    shift_weeks: int = 2,
    original_peak_week: int = 4,
    peak_multiplier: float = 1.9,
    is_festival_linked: int = 1,
    shelf_life_days: Optional[int] = None
) -> DisruptionResult:
    """
    Simulates localized cultural festival calendar drift (e.g. Diwali, Lunar New Year,
    Eid, Easter, regional harvest fairs):
    - When festival date shifts EARLIER: holiday surge hits when retail inventory is only
      at routine introductory replenishment levels, causing severe stockouts. When pre-ordered
      holiday stock finally arrives in the original week, the festival is over, causing excess
      dead stock and perishable spoilage write-offs.
    - When festival date shifts LATER: introductory holiday circulars run prematurely; stock
      stagnates and expires before peak customer shopping begins.

    Args:
        launch_forecast: Baseline 8-week launch forecast dictionary.
        shift_direction: 'earlier' (date advanced) or 'later' (date delayed).
        shift_weeks: Number of weeks festival date drifts (1, 2, or 3).
        original_peak_week: Planned peak holiday demand week (default: 4).
        peak_multiplier: Ratio of holiday peak demand vs standard baseline (default: 1.9x).
        is_festival_linked: 1 if product is tied to festive consumption.
        shelf_life_days: Shelf life in days.

    Returns:
        DisruptionResult detailing calendar misalignment, stockouts, and dead stock.
    """
    weeks = list(launch_forecast.keys())
    n_weeks = len(weeks)

    sd = shift_direction.lower().strip()
    shift_amt = max(1, min(3, shift_weeks))

    if sd == "earlier":
        new_peak_week = max(1, original_peak_week - shift_amt)
    else:
        new_peak_week = min(n_weeks, original_peak_week + shift_amt)

    disrupted_curve: Dict[str, float] = {}
    lost_demand_total = 0.0
    spoilage_units = 0.0
    max_stockout_risk = 0.0

    orig_peak_key = f"W{original_peak_week}"
    new_peak_key = f"W{new_peak_week}"

    orig_peak_vol = launch_forecast.get(orig_peak_key, 100.0)
    baseline_vol = orig_peak_vol / peak_multiplier if is_festival_linked else orig_peak_vol

    for i, w in enumerate(weeks, start=1):
        curr_planned = launch_forecast[w]

        if not is_festival_linked:
            # Minor secondary footfall variation
            disrupted_curve[w] = curr_planned
            continue

        if i == new_peak_week:
            # Holiday demand surge arrives in shifted week
            actual_festive_demand = curr_planned * peak_multiplier
            disrupted_curve[w] = round(actual_festive_demand, 2)
            
            # Retail doors only held ordinary planned stock
            deficit = max(0.0, actual_festive_demand - curr_planned)
            lost_demand_total += deficit
            risk = min(100.0, (actual_festive_demand - curr_planned) / (actual_festive_demand or 1.0) * 100.0)
            if risk > max_stockout_risk:
                max_stockout_risk = risk

        elif i == original_peak_week and new_peak_week != original_peak_week:
            # Originally planned peak week: festival has passed or hasn't started!
            post_festive_demand = baseline_vol * (0.60 if sd == "earlier" else 0.85)
            disrupted_curve[w] = round(post_festive_demand, 2)
            
            # Massive over-supply arriving when shoppers have departed
            excess_shipped = max(0.0, curr_planned - post_festive_demand)
            # Perishability write-off on dead festive stock
            if shelf_life_days and shelf_life_days <= 21:
                spoilage_units += excess_shipped * 0.75  # Severe write-off on short shelf-life festive items
            else:
                spoilage_units += excess_shipped * 0.20  # Discounted liquidation salvage loss
        else:
            disrupted_curve[w] = curr_planned

    scenario_label = f"Festival Calendar Shift ({shift_amt} Wks {sd.capitalize()}: Peak W{new_peak_week})"

    guidance = (
        f"Cultural festival date drift shifts peak customer demand by {shift_amt} week(s) {sd} "
        f"(from Week {original_peak_week} to Week {new_peak_week}). "
        f"Severe calendar misalignment results in {round(lost_demand_total, 1)} units in unfulfilled peak demand "
        f"with {round(max_stockout_risk, 1)}% stockout risk in Week {new_peak_week}. "
        f"Post-holiday dead inventory causes {round(spoilage_units, 1)} units in write-offs. "
        f"Action: Immediately re-index replenishment order triggers from Gregorian calendar dates to relative "
        f"event week (T_festival - {shift_amt}w) and redirect inbound shipments to regional cross-dock."
    )

    return DisruptionResult(
        scenario_name=scenario_label,
        scenario_type="festival_shift",
        original_forecast=launch_forecast,
        disrupted_forecast=disrupted_curve,
        lost_sales_units=lost_demand_total,
        spoilage_units=spoilage_units,
        stockout_risk_pct=max_stockout_risk,
        recommended_buffer_units=round(lost_demand_total * 1.15, 2),
        metrics={
            "shift_direction": sd,
            "shift_weeks": shift_amt,
            "original_peak_week": original_peak_week,
            "shifted_peak_week": new_peak_week,
            "is_festival_linked": is_festival_linked,
            "peak_stockout_deficit": round(lost_demand_total, 2),
            "dead_stock_spoilage": round(spoilage_units, 2)
        },
        operational_guidance=guidance
    )


def run_disruption_scenario(
    scenario_type: str,
    launch_forecast: Dict[str, float],
    **kwargs
) -> DisruptionResult:
    """
    Master dispatcher for disruption stress testing.

    Args:
        scenario_type: 'supplier_delay', 'capacity_loss', 'unplanned_spike',
                       'weather_anomaly', or 'festival_shift'.
        launch_forecast: Baseline 8-week forecast dictionary.
        **kwargs: Specific parameters for the selected scenario.

    Returns:
        DisruptionResult instance.
    """
    st = scenario_type.lower().strip()
    if st == "supplier_delay":
        return simulate_supplier_delay(
            launch_forecast=launch_forecast,
            delay_weeks=int(kwargs.get("delay_weeks", 2)),
            spoilage_rate_pct=float(kwargs.get("spoilage_rate_pct", 0.05)),
            shelf_life_days=kwargs.get("shelf_life_days"),
            momentum_decay_per_week=float(kwargs.get("momentum_decay_per_week", 0.08))
        )
    elif st == "capacity_loss":
        return simulate_capacity_loss(
            launch_forecast=launch_forecast,
            max_weekly_store_capacity=float(kwargs.get("max_weekly_store_capacity", 120.0)),
            spillover_rate=float(kwargs.get("spillover_rate", 0.35)),
            shelf_life_days=kwargs.get("shelf_life_days")
        )
    elif st == "unplanned_spike":
        return simulate_unplanned_spike(
            launch_forecast=launch_forecast,
            spike_week=int(kwargs.get("spike_week", 3)),
            spike_multiplier=float(kwargs.get("spike_multiplier", 2.2)),
            post_spike_exhaustion_rate=float(kwargs.get("post_spike_exhaustion_rate", 0.15)),
            safety_buffer_pct=float(kwargs.get("safety_buffer_pct", 0.20))
        )
    elif st == "weather_anomaly":
        return simulate_weather_anomaly(
            launch_forecast=launch_forecast,
            weather_type=str(kwargs.get("weather_type", "heatwave")),
            intensity_pct=float(kwargs.get("intensity_pct", 0.65)),
            affected_weeks=kwargs.get("affected_weeks", [2, 3]),
            weather_sensitivity=int(kwargs.get("weather_sensitivity", 1)),
            category=str(kwargs.get("category", "Beverages")),
            shelf_life_days=kwargs.get("shelf_life_days"),
            safety_buffer_pct=float(kwargs.get("safety_buffer_pct", 0.20))
        )
    elif st == "festival_shift":
        return simulate_festival_shift(
            launch_forecast=launch_forecast,
            shift_direction=str(kwargs.get("shift_direction", "earlier")),
            shift_weeks=int(kwargs.get("shift_weeks", 2)),
            original_peak_week=int(kwargs.get("original_peak_week", 4)),
            peak_multiplier=float(kwargs.get("peak_multiplier", 1.9)),
            is_festival_linked=int(kwargs.get("is_festival_linked", 1)),
            shelf_life_days=kwargs.get("shelf_life_days")
        )
    else:
        raise ValueError(
            f"Unknown disruption scenario type '{scenario_type}'. "
            "Supported: 'supplier_delay', 'capacity_loss', 'unplanned_spike', 'weather_anomaly', 'festival_shift'."
        )
