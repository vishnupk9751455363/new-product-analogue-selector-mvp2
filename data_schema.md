# Data Schema & Entity-Relationship Architecture

This document specifies the relational data model for the **New-Product Analogue Selector** decision-support platform (Phase 1).

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    PRODUCTS ||--o{ SALES_HISTORY : "generates sales"
    PRODUCTS ||--o{ PROMOTIONS : "featured in"
    PRODUCTS ||--o{ PLAN_CHANGES : "audited under"
    STORES ||--o{ SALES_HISTORY : "recorded at"

    PRODUCTS {
        TEXT product_id PK "Unique SKU identifier"
        TEXT product_name "Descriptive product title"
        TEXT category "Broad category (e.g., Bakery, Beverages)"
        TEXT subcategory "Granular class (e.g., Artisan Bread)"
        TEXT price_tier "budget | mid | premium"
        REAL pack_size_units "Units per consumer pack"
        INTEGER shelf_life_days "Freshness lifecycle in days"
        INTEGER is_festival_linked "Flag 0 or 1"
        TEXT festival_name "Diwali | Lunar New Year | etc."
        INTEGER weather_sensitivity "Flag 0 or 1"
        TEXT launch_date "ISO date of introductory rollout"
        INTEGER is_historical "1 = Analogue Pool, 0 = Test Cold-Start"
    }

    STORES {
        TEXT store_id PK "Store identifier"
        TEXT store_name "Retail outlet title"
        TEXT region "Geographical territory"
        TEXT climate_zone "Temperate | Tropical | Mountain"
        TEXT nearby_festivals "JSON list of relevant local festivals"
    }

    SALES_HISTORY {
        INTEGER sale_id PK "Auto-increment primary key"
        TEXT product_id FK "References products(product_id)"
        TEXT store_id FK "References stores(store_id)"
        TEXT date "ISO date of transaction period"
        INTEGER week_post_launch "Week number relative to launch (1..52)"
        REAL units_sold "Aggregate units sold"
        INTEGER is_promotion_active "Flag 0 or 1"
    }

    PROMOTIONS {
        TEXT promo_id PK "Promotion identifier"
        TEXT product_id FK "References products(product_id)"
        TEXT start_date "ISO campaign start"
        TEXT end_date "ISO campaign end"
        REAL discount_pct "Fractional discount (e.g., 0.20)"
        TEXT promo_type "Introductory Discount | BOGO | etc."
    }

    PLAN_CHANGES {
        INTEGER change_id PK "Auto-increment audit entry"
        TEXT product_id FK "References products(product_id)"
        TEXT changed_by "User identity or system engine tag"
        TEXT changed_at "UTC timestamp of modification"
        TEXT field_changed "Specific target attribute or forecast vector"
        TEXT old_value "Serialized state prior to modification"
        TEXT new_value "Serialized state post modification"
        TEXT reason "Rationale or business justification"
        TEXT source "system | planner_override"
    }
```

---

## 2. Table Specifications & Data Dictionary

### `products`
The master registry of products across both historical reference items and upcoming cold-start candidates.
- `product_id` (TEXT, PK): Unique SKU code.
- `category` & `subcategory` (TEXT): Hierarchical categorization.
- `price_tier` (TEXT): Restricted to `budget`, `mid`, or `premium`.
- `pack_size_units` (REAL): Volume per pack (e.g., 1, 4, 6, 12).
- `shelf_life_days` (INTEGER): Expiry horizon. Directly informs retailer stockout aversion.
- `is_festival_linked` (INTEGER) & `festival_name` (TEXT): Flags if product launch coincides with cultural/regional events.
- `weather_sensitivity` (INTEGER): Binary flag (1 = demand swings with temperature/rain).
- `is_historical` (INTEGER): `1` for established products (analogue search pool), `0` for held-out cold-start test products.

### `stores`
Represents the retail distribution footprint across differing microclimates and festival geographies.
- `store_id` (TEXT, PK): Store branch identifier.
- `region` (TEXT): Operational regional cluster.
- `climate_zone` (TEXT): Regional climate characteristics.
- `nearby_festivals` (TEXT): Cultural events celebrated by the local store community.

### `sales_history`
Granular historical velocity logs. Used to construct empirical 8-week launch curves.
- `week_post_launch` (INTEGER): Relative launch milestone index ($W_1$ to $W_{52}$). In cold-start forecasting, initial weeks ($W_1 \dots W_8$) are the target horizon.
- `units_sold` (REAL): Weekly sales volume.
- `is_promotion_active` (INTEGER): Records if promotional discount influenced demand.

### `promotions`
Catalog of planned and historical promotional incentives.

### `plan_changes` (Immutable Audit Trail)
A non-repudiable audit ledger capturing every forecast proposal and manual override.
- **Append-Only Guarantee**: Enforced at the database engine level via SQLite triggers (`BEFORE UPDATE` and `BEFORE DELETE` aborting transactions).
- `source`: Distinguishes between automated generation (`system`) and human interventions (`planner_override`).
- `reason`: Mandatory text capture documenting why a change was accepted or adjusted.
