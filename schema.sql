-- =============================================================================
-- Capstone Project: New-Product Analogue Selector
-- Phase 1 SQLite Database Schema
-- =============================================================================

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- 1. Stores Table
CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    region TEXT NOT NULL,                  -- e.g. North, South, Central
    climate_zone TEXT NOT NULL,            -- e.g. Temperate, Tropical, Mountain
    nearby_festivals TEXT                  -- JSON array or comma-separated list of local festivals
);

-- 2. Products Table
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,                -- e.g. Bakery, Beverages, Fresh Produce, Confectionery
    subcategory TEXT NOT NULL,             -- e.g. Artisan Bread, Cold Brew, Citrus, Chocolates
    price_tier TEXT NOT NULL CHECK (price_tier IN ('budget', 'mid', 'premium')),
    pack_size_units REAL NOT NULL,         -- e.g. 1, 4, 6, 12 units
    shelf_life_days INTEGER NOT NULL,      -- e.g. 7, 14, 60, 180 days
    is_festival_linked INTEGER NOT NULL CHECK (is_festival_linked IN (0, 1)),
    festival_name TEXT,                    -- e.g. Diwali, Lunar New Year, Harvest Fair, NULL
    weather_sensitivity INTEGER NOT NULL CHECK (weather_sensitivity IN (0, 1)),
    launch_date TEXT NOT NULL,             -- YYYY-MM-DD
    is_historical INTEGER NOT NULL CHECK (is_historical IN (0, 1)) -- 1 = Established Catalogue, 0 = Cold-Start Test
);

-- 3. Sales History Table (Established products analogue pool + ground truth test launches)
CREATE TABLE IF NOT EXISTS sales_history (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    date TEXT NOT NULL,                    -- YYYY-MM-DD
    week_post_launch INTEGER NOT NULL,     -- 1, 2, 3...
    units_sold REAL NOT NULL,
    is_promotion_active INTEGER NOT NULL CHECK (is_promotion_active IN (0, 1)),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_prod_week ON sales_history(product_id, week_post_launch);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_history(date);

-- 4. Promotions Table
CREATE TABLE IF NOT EXISTS promotions (
    promo_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    start_date TEXT NOT NULL,              -- YYYY-MM-DD
    end_date TEXT NOT NULL,                -- YYYY-MM-DD
    discount_pct REAL NOT NULL,            -- e.g. 0.15 for 15% off
    promo_type TEXT NOT NULL,              -- e.g. 'Introductory Discount', 'BOGO', 'Seasonal Feature'
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 5. Plan Changes Audit Log Table (Immutable / Append-Only)
CREATE TABLE IF NOT EXISTS plan_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    changed_by TEXT NOT NULL,              -- e.g. 'system_v1' or 'planner_jdoe'
    changed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%fZ', 'now')), -- UTC timestamp
    field_changed TEXT NOT NULL,           -- e.g. 'launch_curve_w1', 'suggested_analogues', 'order_qty'
    old_value TEXT,
    new_value TEXT NOT NULL,
    reason TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('system', 'planner_override')),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_changes_product ON plan_changes(product_id);
CREATE INDEX IF NOT EXISTS idx_plan_changes_time ON plan_changes(changed_at);

-- =============================================================================
-- Triggers to Enforce Immutability (Append-Only) on plan_changes
-- =============================================================================

CREATE TRIGGER IF NOT EXISTS trg_prevent_plan_changes_update
BEFORE UPDATE ON plan_changes
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: Updates are prohibited on the plan_changes audit log.');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_plan_changes_delete
BEFORE DELETE ON plan_changes
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: Deletions are prohibited on the plan_changes audit log.');
END;
