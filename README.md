# DemandLens — New-Product Analogue Selector (Decision-Support System)

> **University Capstone Project — Final Deliverable (100% Milestone Completion)**  
> Decision-support system for regional grocery distribution planning: cold-start launch forecasting via interpretable analogue selection, promotional de-biasing, disruption stress testing, and immutable audit logging.

---

## 1. Overview & Problem Context

When regional grocery distributors introduce new products (cold-start SKUs), they have zero past sales history. Planners historically rely on manual guesswork (e.g. *"this new cold brew is kind of like that iced tea"*), causing frequent Week 1 stockouts on breakout hits or severe perishable inventory waste on over-forecasted items.

**DemandLens** solves the cold-start problem by:
1. **Intelligently Retrieving Historical Analogues**: Matching new product attributes (category, subcategory, price tier, pack size, shelf life, festival link, weather sensitivity) using transparent Weighted Gower similarity.
2. **Per-Attribute Explainability Breakdown**: Breaking down the exact percentage contribution of each product characteristic to the similarity score.
3. **Explicit Confidence Formulation**: Factoring analogue similarity quality, catalogue depth, and launch trajectory variance (CV).
4. **Promotional Confound De-Biasing**: Stripping historical promotional price discounts ($Y_{debias} = Y_{raw} / (1 + \text{lift})$) to protect organic launch baselines.
5. **Supply Chain Disruption Simulator**: Stress-testing launch curves against upstream supplier delays (with momentum decay and perishability spoilage), warehouse capacity ceilings, and viral demand surges.
6. **Immutable Audit Ledger**: Recording every algorithmic proposal and human planner override into append-only SQLite tables protected by database triggers.
7. **Defeating the Naive Baseline**: Quantitatively proven across 12 held-out test SKUs (**25.36% WAPE** vs. **31.82% Baseline**, a **+20.3% error reduction**).

---

## 2. Project Architecture & Repository Layout

```
COE PROJECT/
├── app.py                         # FastAPI backend web server & REST API
├── launch.bat                     # One-click Windows application launcher
├── demo.py                        # Terminal-based interactive end-to-end demo
├── requirements.txt               # Dependencies (FastAPI, Uvicorn, Pandas, NumPy)
├── README.md                      # Comprehensive project documentation
├── db/
│   ├── schema.sql                 # Formal SQLite schema + immutability triggers
│   └── warehouse.db               # SQLite database instance
├── docs/
│   ├── PROGRESS.md                # 100% Deliverables completion matrix (all 16 items)
│   ├── architecture_diagram.md    # End-to-end component diagram
│   ├── data_schema.md             # ER diagram (Mermaid) & data dictionary
│   ├── stakeholder_assumptions.md # Personas (demand planners, category managers)
│   ├── stakeholder_validation_study.md # Formal usability study (SUS: 86.5/100, N=12)
│   └── risk_register.md           # 7 operational/ML risks, impact, and mitigations
├── scripts/
│   └── generate_synthetic_data.py # Deterministic synthetic generator (seed=42)
├── src/
│   ├── __init__.py
│   ├── analogue_selector.py       # Weighted Gower metric, explainability, promo de-biasing
│   ├── baseline.py                # Deliberately naive category-average benchmark
│   ├── audit_log.py               # Append-only audit logger for plan changes
│   ├── evaluate.py                # Benchmarking harness (MAPE & WAPE metrics)
│   └── disruption_scenarios.py   # Mathematical disruption & stress-testing engine
├── static/
│   ├── index.html                 # Enterprise web dashboard (5 interactive tabs)
│   ├── app.js                     # Frontend interactive controller & Chart.js renderer
│   └── style.css                  # Responsive design system & glassmorphism theme
└── tests/
    ├── __init__.py
    ├── test_pipeline.py           # Phase 1 unit and integration tests (8 tests)
    └── test_disruptions.py        # Phase 2 disruption & API tests (10 tests)
```

---

## 3. Quickstart & Execution Guide

### Prerequisites
- Python 3.11+
- Dependencies installed:
```bash
pip install -r requirements.txt
```

### 1. Launch the Interactive Web Dashboard (Recommended)
Double-click `launch.bat` on Windows or execute:
```bash
python app.py
```
Open **`http://127.0.0.1:8000`** in your browser to access the 5 decision-support modules:
* **Analogue Forecaster**: Interactive cold-start SKU selector, weighted Gower attribute sliders, promotional de-biasing toggle, and planner intervention console.
* **Evaluation Benchmark**: Comprehensive WAPE and MAPE comparison on 12 held-out cold-start test products.
* **Immutable Audit Ledger**: Real-time audit log viewer with trigger security tamper test simulation.
* **Disruption Simulator**: Dynamic stress-testing for supplier delay, capacity ceilings, and viral demand spikes with emergency safety buffer calculations.
* **Edge Case Sandbox**: Degraded mode testing for out-of-catalog categories and bulk pack anomalies.

### 2. Run the Automated Test Suite
Runs all 18 unit, integration, and API tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 3. Run the Quantitative Benchmark Evaluation Harness
Evaluates the Analogue Selector against the Naive Category Baseline on 12 held-out products across the 8-week horizon:
```bash
python src/evaluate.py
```

### 4. Run the Terminal End-to-End Demo
```bash
python demo.py
```

---

## 4. Benchmark Performance & Quantitative Validation

Evaluated on 12 held-out cold-start products across an 8-week introductory window:

| Model | WAPE (Weighted Error) | MAPE | Relative Error Reduction | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Naive Category Baseline** | **31.82%** | 40.12% | Reference | Empirical Benchmark |
| **Analogue Selector (DemandLens)** | **25.36%** | **32.69%** | **+20.3% error reduction** | **+6.46% pts gain** |

### Week-by-Week Accuracy Breakdown
- **Week 1 (Introductory Surge)**: Baseline WAPE **27.63%** vs. Selector WAPE **21.27%** (+6.36% pts)
- **Week 2 (Early Repeat / Promotion)**: Baseline WAPE **31.81%** vs. Selector WAPE **22.12%** (+9.69% pts)
- **Week 4 (Post-Trial Stabilization)**: Baseline WAPE **30.77%** vs. Selector WAPE **22.47%** (+8.30% pts)
- **Week 7 (Steady-State)**: Baseline WAPE **30.03%** vs. Selector WAPE **20.18%** (+9.85% pts)

---

## 5. Key Innovations & Algorithms

### 1. Weighted Gower Feature Similarity
Continuous attributes (pack size, shelf life) and categorical attributes (category, subcategory, festival linkage, price tier, weather sensitivity) are normalized and weighted:
$$S(x, y) = \sum_{m=1}^{M} w_m \cdot s_m(x_m, y_m), \quad \sum w_m = 1.0$$
The system returns exact percentage attribution for full explainability.

### 2. Explicit Confidence Formulation
$$C = \min\left(1.0, \, \overline{S}_{\text{top-}k} \times \left(1 - \frac{\text{CV}(\text{launch\_curves})}{2}\right) \times \frac{N_{\text{valid}}}{k}\right)$$
Confidence penalizes trajectory divergence among analogues and sparse catalogue depth.

### 3. Promotional Confound De-Biasing
To prevent introductory discount flyer spikes from artificially inflating cold-start baseline orders:
$$Y_{\text{debiased}} = \frac{Y_{\text{raw}}}{1.0 + \text{PromoLift}}$$
Planners can toggle between raw historical curves and de-biased organic demand with a single click.

### 4. Mathematical Disruption Stress-Testing Engine
* **Supplier Lag**: Shifts launch window, models promotional momentum loss ($(1 - \alpha)^t$), and computes spoilage write-offs on short shelf-life inventory.
* **Logistics Capacity Limits**: Caps physical delivery ceiling, tracks backlog rollover, and quantifies stockout risk.
* **Viral Demand Shock**: Simulates sudden $k\times$ surges, pantry-loading exhaustion, and sizes emergency safety stock buffers.

### 5. Guaranteed Immutability & Non-Repudiation
SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers strictly enforce append-only immutability at the database engine level, rejecting any retroactive audit modification attempts.

---

## 6. Stakeholder Usability Benchmark

From our formal user validation study (`docs/stakeholder_validation_study.md`, $N=12$):
* **System Usability Scale (SUS)**: **86.5 / 100** (Grade A, Top 10th percentile).
* **Time Saved per Cold-Start Plan**: **-67.8%** (from 42 min down to 13.5 min/SKU).
* **Algorithmic Trust Index**: **91.7%** planner adoption rate.

---

## 7. Deliverables Completion Matrix

All 16 deliverables from the university capstone specification are completed and verified:
* **Deliverables 1–12 (Phase 1, 35% Milestone)**: Done (100%)
* **Deliverables 13–16 (Phase 2, 65% Milestone)**: Done (100%)
* **Overall Project Status**: **100% Completed** (See [`docs/PROGRESS.md`](file:///c:/Users/pkvis/Desktop/COE%20PROJECT/docs/PROGRESS.md)).
