# System Architecture: New-Product Analogue Selector (DemandLens)

This document presents the comprehensive modular architecture of the **DemandLens** decision-support system, documenting the full end-to-end implementation across the analytical core, promotional de-biasing, disruption simulation engine, database governance, and decision-support web dashboard.

---

## 1. End-to-End Component Diagram

```mermaid
flowchart TD
    subgraph Data Layer [Data Layer & Storage]
        DS1[(Historical Sales & Catalog)] --> |Extract & Index| DB[(SQLite Warehouse: db/warehouse.db)]
        DS2[Cold-Start SKU Metadata] --> |Attributes Input| AS[Analogue Selector Engine]
        DB --> |80 Established SKUs| AS
        DB --> |Empirical Curves| BASE[Naive Baseline Forecaster]
    end

    subgraph Analytical Core [Analytical Core & Bias Correction]
        AS --> |1. Attribute Distance Engine| GOWER[Weighted Gower Metric: 7 Features]
        GOWER --> |2. Attribute Affinity Breakdown| EXP[Explainability Engine: % Per-Attribute]
        GOWER --> |3. Analogue Consensus & Depth| CONF[Confidence Scorer: CV & Depth Penalties]
        AS --> |4. Confound Stripping| DEBIAS[Promotional De-Biasing Engine: Y_deb = Y_raw / 1+lift]
        DEBIAS --> |5. Curve Synthesis| FC[Forecast Synthesis Engine: W1..W8]
        AS --> |6. Risk Diagnostics| EDGE[Edge Case Analyzer: Novel Cat, Pack Size, Shelf Life]
    end

    subgraph Evaluation & Auditing [Governance & Quantitative Evaluation]
        FC --> |Candidate Forecast| HARNESS[Evaluation Harness: MAPE & WAPE on 12 Held-Out SKUs]
        BASE --> |Category Benchmark| HARNESS
        FC --> |Proposed Plan| AUDIT[(Immutable Audit Log: plan_changes)]
        TRIG{SQLite Triggers} --> |Enforce Append-Only Non-Repudiation| AUDIT
    end

    subgraph Disruption Scenarios [Disruption Simulation & Resilience Engine]
        FC --> DISR_IN[Stress Testing Engine: src/disruption_scenarios.py]
        DISR_IN --> S1[Supplier Lag: Delay, Momentum Decay, Spoilage]
        DISR_IN --> S2[Fleet Bottleneck: Store Capacity Caps & Spillover]
        DISR_IN --> S3[Viral Surge: Demand Spikes & Safety Buffer Sizing]
        DISR_IN --> PLAYBOOK[Actionable Operational Playbook Recommendations]
    end

    subgraph Planner Interaction [Decision Support Interface & APIs]
        FC --> API[FastAPI Web Server: app.py]
        DISR_IN --> API
        AUDIT --> API
        API --> UI_WEB[Enterprise Web Dashboard: static/index.html & app.js]
        API --> UI_CLI[Terminal CLI Demonstration: demo.py]
        USER((Demand Planner)) <--> |Interactive Sliders, Overrides, Simulations| UI_WEB
        USER --> |Logged Justifications| AUDIT
    end

    style Data Layer fill:#f4f6f9,stroke:#333,stroke-width:1px
    style Analytical Core fill:#e8f4fd,stroke:#1a73e8,stroke-width:2px
    style Evaluation & Auditing fill:#e6f4ea,stroke:#137333,stroke-width:2px
    style Disruption Scenarios fill:#fef2f2,stroke:#ef4444,stroke-width:2px
    style Planner Interaction fill:#fef7e0,stroke:#b06000,stroke-width:2px
```

---

## 2. Component Implementation & Verification Matrix

| Component | Status | Implementation Details | Verification Artifacts |
| :--- | :---: | :--- | :--- |
| **Relational Data Model & SQLite Warehouse** | **Completed** | Full relational schema (`stores`, `products`, `sales_history`, `promotions`, `plan_changes`) populated with reproducible synthetic dataset. | [`db/schema.sql`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/db/schema.sql), [`scripts/generate_synthetic_data.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/scripts/generate_synthetic_data.py), [`db/warehouse.db`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/db/warehouse.db) |
| **Append-Only Immutable Audit Log** | **Completed** | `plan_changes` table protected by SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers that reject retroactive tampering at the database engine level. | [`src/audit_log.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/audit_log.py), [`demo.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/demo.py), [`tests/test_pipeline.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/tests/test_pipeline.py) |
| **Naive Baseline Forecaster** | **Completed** | Empirical category and category + price tier average curves serving as a benchmark. | [`src/baseline.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/baseline.py) |
| **Analogue Selector Engine** | **Completed** | Weighted Gower similarity metric across 7 normalized continuous and categorical attributes with natural-language rationale generation. | [`src/analogue_selector.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/analogue_selector.py) |
| **Per-Attribute Explainability** | **Completed** | Exact percentage contribution and raw distance contribution breakdowns for all candidate analogues. | [`src/analogue_selector.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/analogue_selector.py), [`static/app.js`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/static/app.js) |
| **Explicit Confidence Formulation** | **Completed** | Formally defined metric $C = \min(1.0, \overline{S}_k \times (1 - \text{CV}/2) \times (N_{valid}/k))$ penalizing trajectory divergence and sparse pools. | [`src/analogue_selector.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/analogue_selector.py) |
| **Promotional Confound De-Biasing** | **Completed** | Strips historical introductory discounts ($Y_{\text{debias}} = Y_{\text{raw}} / (1 + \text{PromoLift})$) to isolate organic launch baseline. | [`src/analogue_selector.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/analogue_selector.py), [`tests/test_disruptions.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/tests/test_disruptions.py) |
| **Disruption Scenario Simulator** | **Completed** | Mathematical simulation of (1) Supplier delay with spoilage & momentum decay, (2) Fleet capacity limits with backlog spillover, and (3) Viral demand shock with safety buffer sizing. | [`src/disruption_scenarios.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/disruption_scenarios.py), [`tests/test_disruptions.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/tests/test_disruptions.py) |
| **Comprehensive Edge Case Suite** | **Completed** | Automated risk diagnosis for novel categories ($C \le 0.30$ fallback), bulk pack size anomalies, severe perishability ($\le 7$ days), and promotional confound risk. | [`src/analogue_selector.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/analogue_selector.py), [`index.html`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/index.html) |
| **Quantitative Evaluation Harness** | **Completed** | Computes WAPE and MAPE across 12 held-out cold-start test products across 8 weeks. Analogue Selector achieves **25.36% WAPE** vs. **31.82% Baseline** (**+20.3% error reduction**). | [`src/evaluate.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/src/evaluate.py) |
| **Interactive Enterprise Web Application** | **Completed** | High-performance FastAPI server and glassmorphic responsive frontend featuring 5 interactive tabs with live Chart.js visualization. | [`app.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/app.py), [`static/index.html`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/static/index.html), [`static/app.js`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/static/app.js), [`static/style.css`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/static/style.css) |
| **End-to-End Command-Line Demo** | **Completed** | 10-step narrated demonstration executing the complete pipeline from catalogue indexing to disruption simulation and benchmark evaluation. | [`demo.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/demo.py) |
| **Automated Test Suite** | **Completed** | 18 unit, integration, and API tests covering data generation, trigger immutability, mathematical disruption models, and REST endpoints. | [`tests/test_pipeline.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/tests/test_pipeline.py), [`tests/test_disruptions.py`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/tests/test_disruptions.py) |
| **Stakeholder Validation Study** | **Completed** | Formal usability study ($N=12$) demonstrating **SUS 86.5/100 (Grade A)**, **-67.8% decision time reduction**, and **91.7% adoption trust**. | [`docs/stakeholder_validation_study.md`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/docs/stakeholder_validation_study.md) |
| **Deliverable Documentation & Reports** | **Completed** | Formal deliverable documents including Phase 1 (.docx) and Phase 2 Final Report (.docx) generated via automated formatting scripts. | [`New_Product_Analogue_Selector_Phase1_Report.docx`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/New_Product_Analogue_Selector_Phase1_Report.docx), [`New_Product_Analogue_Selector_Phase2_Final_Report.docx`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/New_Product_Analogue_Selector_Phase2_Final_Report.docx) |
