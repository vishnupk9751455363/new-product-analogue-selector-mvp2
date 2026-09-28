#!/usr/bin/env python3
"""
scripts/generate_synthetic_data.py
Generates a realistic, synthetic dataset for a regional grocery distributor decision-support system.

Entities generated:
- Stores (regional footprint, climate zones, festival associations)
- Products (established catalogue of 80 products + 12 cold-start test products)
- Sales History (weekly sales per product per store, with launch curve dynamics:
    - introductory stocking surge in W1-W2
    - trial dip/stabilization in W3-W5
    - steady-state or festival spikes in W6-W8
    - promotional lifts
- Promotions (introductory campaigns, seasonal features)
- Plan Changes (seed audit entries with system baseline suggestions and planner overrides)

Saves data into SQLite DB (db/warehouse.db) and CSV exports in data/.
Fixed random seed ensures full reproducibility.
"""

import os
import json
import sqlite3
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

# Set fixed seed for reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "warehouse.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
DATA_DIR = os.path.join(BASE_DIR, "data")

CATEGORIES = {
    "Bakery": {
        "subcategories": ["Artisan Bread", "Pastries & Croissants", "Flatbreads & Wraps", "Cakes & Muffins"],
        "base_volume_range": (80, 220),
        "shelf_life_range": (5, 12),
        "pack_sizes": [1, 2, 4, 6],
        "weather_sensitivity_prob": 0.20
    },
    "Beverages": {
        "subcategories": ["Cold Brew & Iced Coffee", "Craft Soda", "Herbal Teas", "Kombucha & Tonics"],
        "base_volume_range": (60, 200),
        "shelf_life_range": (30, 180),
        "pack_sizes": [1, 4, 6, 12],
        "weather_sensitivity_prob": 0.80
    },
    "Fresh Produce": {
        "subcategories": ["Organic Berries", "Specialty Greens", "Heirloom Citrus", "Root Vegetables"],
        "base_volume_range": (70, 250),
        "shelf_life_range": (4, 14),
        "pack_sizes": [1, 2, 3],
        "weather_sensitivity_prob": 0.65
    },
    "Confectionery": {
        "subcategories": ["Artisan Chocolate", "Gourmet Candies", "Festive Sweet Treats", "Nut & Fruit Bites"],
        "base_volume_range": (40, 150),
        "shelf_life_range": (60, 360),
        "pack_sizes": [1, 2, 4, 8],
        "weather_sensitivity_prob": 0.35
    }
}

PRICE_TIERS = ["budget", "mid", "premium"]
PRICE_TIER_WEIGHTS = [0.35, 0.45, 0.20]
TIER_VOLUME_MULTIPLIER = {"budget": 1.35, "mid": 1.0, "premium": 0.70}

FESTIVALS = ["Diwali", "Lunar New Year", "Harvest Fair", "Spring Holiday"]

REGIONS = [
    {"region": "North Metro", "climate_zone": "Temperate", "festivals": ["Harvest Fair", "Spring Holiday"]},
    {"region": "South Coastal", "climate_zone": "Tropical", "festivals": ["Diwali", "Spring Holiday"]},
    {"region": "Central Valley", "climate_zone": "Temperate", "festivals": ["Harvest Fair", "Lunar New Year"]},
    {"region": "Highland East", "climate_zone": "Mountain", "festivals": ["Lunar New Year", "Diwali"]}
]


def create_schema(conn):
    """Executes db/schema.sql against the SQLite database."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    cursor = conn.cursor()
    cursor.executescript(schema_sql)
    conn.commit()


def generate_stores(num_stores=15):
    """Generates store network across regions and climate zones."""
    stores = []
    for i in range(1, num_stores + 1):
        reg = random.choice(REGIONS)
        store_id = f"STR_{i:03d}"
        store_name = f"{reg['region']} Market #{i}"
        stores.append({
            "store_id": store_id,
            "store_name": store_name,
            "region": reg["region"],
            "climate_zone": reg["climate_zone"],
            "nearby_festivals": json.dumps(reg["festivals"])
        })
    return pd.DataFrame(stores)


def generate_products(num_established=80, num_cold_start=12):
    """
    Generates product catalogue:
    - 80 established products (is_historical = 1)
    - 12 held-out new products (is_historical = 0)
    """
    products = []
    prod_counter = 1

    total_prods = [("established", num_established, 1), ("cold_start", num_cold_start, 0)]

    for group_name, count, is_hist in total_prods:
        for _ in range(count):
            category = random.choice(list(CATEGORIES.keys()))
            cat_cfg = CATEGORIES[category]
            subcategory = random.choice(cat_cfg["subcategories"])
            price_tier = np.random.choice(PRICE_TIERS, p=PRICE_TIER_WEIGHTS)
            pack_size = random.choice(cat_cfg["pack_sizes"])
            shelf_life = random.randint(cat_cfg["shelf_life_range"][0], cat_cfg["shelf_life_range"][1])

            # Festival association
            is_festival = 1 if random.random() < 0.35 else 0
            festival_name = random.choice(FESTIVALS) if is_festival else None

            # Weather sensitivity
            weather_sens = 1 if random.random() < cat_cfg["weather_sensitivity_prob"] else 0

            # Launch date
            if is_hist == 1:
                # Launched 1-2 years ago
                days_ago = random.randint(180, 720)
            else:
                # Launching recently / imminent
                days_ago = random.randint(10, 60)
            launch_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            prefix = "EST" if is_hist == 1 else "NEW"
            prod_id = f"PRD_{prefix}_{prod_counter:03d}"
            prod_name = f"{subcategory} ({price_tier.capitalize()} {pack_size}pk)"
            if festival_name:
                prod_name += f" - {festival_name} Edition"

            products.append({
                "product_id": prod_id,
                "product_name": prod_name,
                "category": category,
                "subcategory": subcategory,
                "price_tier": price_tier,
                "pack_size_units": float(pack_size),
                "shelf_life_days": int(shelf_life),
                "is_festival_linked": is_festival,
                "festival_name": festival_name,
                "weather_sensitivity": weather_sens,
                "launch_date": launch_date,
                "is_historical": is_hist
            })
            prod_counter += 1

    return pd.DataFrame(products)


def generate_launch_curve_profile(category, price_tier, is_festival, weather_sensitivity):
    """
    Synthesizes an 8-week launch trajectory shape:
    - W1: Initial pipeline fill & introductory trial surge (1.3x - 1.6x baseline)
    - W2: Sustained initial interest / early repeat (1.1x - 1.4x)
    - W3-W5: Dip / novelty decay to baseline customer adoption (0.8x - 1.0x)
    - W6-W8: Steady-state trajectory, modulated by festival spikes or weather
    """
    cat_cfg = CATEGORIES[category]
    base_min, base_max = cat_cfg["base_volume_range"]
    base_velocity = random.uniform(base_min, base_max) * TIER_VOLUME_MULTIPLIER[price_tier]

    # Weekly curve multipliers (Week 1 through 8)
    multipliers = [
        random.uniform(1.35, 1.65),  # W1: initial rollout stocking surge
        random.uniform(1.15, 1.40),  # W2: early repeat / promotion
        random.uniform(0.85, 1.05),  # W3: post-launch dip
        random.uniform(0.80, 1.00),  # W4: settling
        random.uniform(0.85, 1.05),  # W5: plateau
        random.uniform(0.90, 1.10),  # W6: steady state
        random.uniform(0.90, 1.15),  # W7: steady state
        random.uniform(0.92, 1.20)   # W8: steady state
    ]

    # If festival-linked, inject a demand spike in Week 3 or 4 (peak holiday week)
    if is_festival:
        spike_week = random.choice([2, 3, 4])  # 0-indexed: W3, W4, or W5
        multipliers[spike_week] *= random.uniform(1.6, 2.2)

    weekly_volumes = [max(5.0, round(base_velocity * m, 1)) for m in multipliers]
    return weekly_volumes


def generate_sales_and_promotions(products_df, stores_df):
    """
    Generates weekly sales for each product across stores for weeks 1 to 8 post-launch.
    Also generates promotions table.
    """
    sales_records = []
    promotions_records = []
    promo_id_counter = 1

    stores_list = stores_df.to_dict("records")

    for _, prod in products_df.iterrows():
        p_id = prod["product_id"]
        cat = prod["category"]
        tier = prod["price_tier"]
        is_fest = prod["is_festival_linked"]
        w_sens = prod["weather_sensitivity"]

        # 8-week launch curve volume profile
        launch_curve = generate_launch_curve_profile(cat, tier, is_fest, w_sens)
        launch_dt = datetime.strptime(prod["launch_date"], "%Y-%m-%d")

        # Create promotion if applicable (e.g. 50% chance of introductory promo in W1-W2)
        has_promo = random.random() < 0.50
        promo_start_week = 1
        promo_end_week = 2
        promo_discount = 0.15 if random.random() < 0.7 else 0.25

        if has_promo:
            promo_p_id = f"PRM_{promo_id_counter:04d}"
            promotions_records.append({
                "promo_id": promo_p_id,
                "product_id": p_id,
                "start_date": (launch_dt + timedelta(weeks=promo_start_week - 1)).strftime("%Y-%m-%d"),
                "end_date": (launch_dt + timedelta(weeks=promo_end_week)).strftime("%Y-%m-%d"),
                "discount_pct": promo_discount,
                "promo_type": "Introductory Launch Discount"
            })
            promo_id_counter += 1

        # Distribute across stores
        for week_idx, base_vol in enumerate(launch_curve, start=1):
            week_date = (launch_dt + timedelta(weeks=week_idx - 1)).strftime("%Y-%m-%d")
            is_promo_active = 1 if (has_promo and promo_start_week <= week_idx <= promo_end_week) else 0

            for store in stores_list:
                s_id = store["store_id"]
                # Store volume scaling factor (e.g. 0.8x to 1.2x based on store size)
                store_factor = 0.8 + (hash(s_id) % 40) / 100.0

                # Climate/weather effect if weather sensitive
                weather_factor = 1.0
                if w_sens and store["climate_zone"] == "Tropical":
                    weather_factor = 1.25 if cat == "Beverages" else 0.90

                # Festival synergy if store matches festival
                fest_factor = 1.0
                if is_fest and prod["festival_name"] and prod["festival_name"] in store["nearby_festivals"]:
                    if week_idx in [3, 4]:
                        fest_factor = 1.35

                promo_boost = (1.0 + promo_discount * 1.5) if is_promo_active else 1.0

                noise = random.uniform(0.92, 1.08)
                store_units = max(1.0, round(base_vol * store_factor * weather_factor * fest_factor * promo_boost * noise, 1))

                sales_records.append({
                    "product_id": p_id,
                    "store_id": s_id,
                    "date": week_date,
                    "week_post_launch": week_idx,
                    "units_sold": store_units,
                    "is_promotion_active": is_promo_active
                })

    return pd.DataFrame(sales_records), pd.DataFrame(promotions_records)


def generate_seed_plan_changes(products_df):
    """
    Generates realistic initial audit log entries in plan_changes:
    Demonstrating automated system recommendations and subsequent human planner overrides.
    """
    plan_changes = []
    # Take a couple of established products and one cold-start product
    sample_prods = products_df.head(4).to_dict("records")

    for p in sample_prods:
        p_id = p["product_id"]
        # 1. System initial launch curve suggestion
        plan_changes.append({
            "product_id": p_id,
            "changed_by": "system_analogue_engine_v1",
            "changed_at": (datetime.now(timezone.utc) - timedelta(days=5, hours=3)).strftime("%Y-%m-%d %H:%M:%S.%fZ"),
            "field_changed": "launch_curve_w1_w8",
            "old_value": "null",
            "new_value": json.dumps({"W1": 180, "W2": 150, "W3": 120, "W4": 115, "W5": 110, "W6": 110, "W7": 110, "W8": 115}),
            "reason": "Automated analogue retrieval based on subcategory, price_tier, and festival affinity.",
            "source": "system"
        })

        # 2. Planner manual override for first week buffer
        plan_changes.append({
            "product_id": p_id,
            "changed_by": "planner_jdoe",
            "changed_at": (datetime.now(timezone.utc) - timedelta(days=4, hours=1)).strftime("%Y-%m-%d %H:%M:%S.%fZ"),
            "field_changed": "launch_curve_w1",
            "old_value": "180",
            "new_value": "210",
            "reason": "Increased Week 1 allocation by 30 units to prevent stockouts during regional marketing push.",
            "source": "planner_override"
        })

    return pd.DataFrame(plan_changes)


def main():
    print("=" * 70)
    print("Generating Synthetic Dataset for New-Product Analogue Selector...")
    print("=" * 70)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Initialize SQLite Database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed previous database file at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    print(f"Schema initialized successfully from {SCHEMA_PATH}")

    # 2. Generate Entities
    stores_df = generate_stores(num_stores=15)
    print(f"Generated {len(stores_df)} stores.")

    products_df = generate_products(num_established=80, num_cold_start=12)
    hist_count = (products_df["is_historical"] == 1).sum()
    cold_count = (products_df["is_historical"] == 0).sum()
    print(f"Generated {len(products_df)} products ({hist_count} established catalogue, {cold_count} cold-start test items).")

    sales_df, promos_df = generate_sales_and_promotions(products_df, stores_df)
    print(f"Generated {len(sales_df)} weekly sales records across stores.")
    print(f"Generated {len(promos_df)} promotion campaigns.")

    plan_changes_df = generate_seed_plan_changes(products_df)
    print(f"Generated {len(plan_changes_df)} seed audit log entries.")

    # 3. Write into SQLite DB
    stores_df.to_sql("stores", conn, if_exists="append", index=False)
    products_df.to_sql("products", conn, if_exists="append", index=False)
    sales_df.to_sql("sales_history", conn, if_exists="append", index=False)
    promos_df.to_sql("promotions", conn, if_exists="append", index=False)
    plan_changes_df.to_sql("plan_changes", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    print(f"All records committed into SQLite database at {DB_PATH}")

    # 4. Export CSVs for inspection
    stores_df.to_csv(os.path.join(DATA_DIR, "stores.csv"), index=False)
    products_df.to_csv(os.path.join(DATA_DIR, "products.csv"), index=False)
    sales_df.to_csv(os.path.join(DATA_DIR, "sales_history.csv"), index=False)
    promos_df.to_csv(os.path.join(DATA_DIR, "promotions.csv"), index=False)
    plan_changes_df.to_csv(os.path.join(DATA_DIR, "plan_changes.csv"), index=False)
    print(f"CSV files exported to {DATA_DIR}/")

    print("\nDataset generation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
