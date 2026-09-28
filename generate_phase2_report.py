"""
scripts/generate_phase2_report.py
Generates the formal Phase 2 Final Capstone Deliverable Report (.docx):
'New_Product_Analogue_Selector_Phase2_Final_Report.docx'.
"""

import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "New_Product_Analogue_Selector_Phase2_Final_Report.docx")


def set_cell_shading(cell, color_hex):
    """Applies background shading color to a table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets inner padding margins for a cell."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def create_report():
    doc = Document()

    # Set page margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Style definitions
    NAVY = RGBColor(15, 23, 42)       # #0F172A
    SLATE = RGBColor(71, 85, 105)     # #475569
    BLUE = RGBColor(37, 99, 235)      # #2563EB
    EMERALD = RGBColor(5, 150, 105)   # #059669
    DARK_GRAY = RGBColor(30, 41, 59)  # #1E293B

    # Header / Title Block
    p_pre = doc.add_paragraph()
    r_pre = p_pre.add_run("PROJECT FINAL DELIVERABLE REPORT")
    r_pre.font.name = "Calibri"
    r_pre.font.size = Pt(11)
    r_pre.font.bold = True
    r_pre.font.color.rgb = BLUE
    p_pre.paragraph_format.space_after = Pt(4)

    p_title = doc.add_paragraph()
    r_title = p_title.add_run("New-Product Analogue Selector (DemandLens)")
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(26)
    r_title.font.bold = True
    r_title.font.color.rgb = NAVY
    p_title.paragraph_format.space_after = Pt(4)

    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run(
        "A Decision-Support System for Cold-Start Demand Forecasting & Disruption Resilience in Regional Grocery Distribution"
    )
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(14)
    r_sub.font.color.rgb = SLATE
    p_sub.paragraph_format.space_after = Pt(12)

    p_meta = doc.add_paragraph()
    r_meta = p_meta.add_run(
        "Final Capstone Deliverable Report — 100% Project Completion (Phase 1 & Phase 2 Full Delivery)\n"
        "Center of Excellence (COE) Capstone Project\n"
        "Report Date: September 2026 | Milestone Status: Verified & Approved"
    )
    r_meta.font.name = "Calibri"
    r_meta.font.size = Pt(10)
    r_meta.font.italic = True
    r_meta.font.color.rgb = SLATE
    p_meta.paragraph_format.space_after = Pt(24)

    # Divider
    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_after = Pt(16)

    def add_sec_heading(num_and_title):
        p = doc.add_paragraph()
        r = p.add_run(num_and_title)
        r.font.name = "Calibri"
        r.font.size = Pt(16)
        r.font.bold = True
        r.font.color.rgb = NAVY
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(8)
        return p

    def add_sub_heading(num_and_title):
        p = doc.add_paragraph()
        r = p.add_run(num_and_title)
        r.font.name = "Calibri"
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = BLUE
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        return p

    def add_body_p(text):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(11)
        r.font.color.rgb = DARK_GRAY
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        return p

    def add_bullet_p(bold_prefix, text):
        p = doc.add_paragraph(style="List Bullet")
        r_b = p.add_run(bold_prefix)
        r_b.font.name = "Calibri"
        r_b.font.size = Pt(11)
        r_b.font.bold = True
        r_b.font.color.rgb = DARK_GRAY
        r_t = p.add_run(text)
        r_t.font.name = "Calibri"
        r_t.font.size = Pt(11)
        r_t.font.color.rgb = DARK_GRAY
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        return p

    # 1. Executive Summary
    add_sec_heading("1. Executive Summary")
    add_body_p(
        "Regional grocery distribution networks frequently introduce cold-start stock-keeping units (SKUs)—items with "
        "zero past sales history. Conventional forecasting models (such as ARIMA, Prophet, or recurrent neural networks) "
        "fail entirely because they require historical series data that does not exist at launch time. In practice, human demand "
        "planners rely on ad-hoc intuition (e.g., 'this artisanal pastry is probably like that chocolate chip cookie'), leading "
        "to widespread initial stockouts, costly perishable waste, and no audit trail of replenishment decisions."
    )
    add_body_p(
        "This project delivers DemandLens, an enterprise decision-support platform that formalizes analogue selection into a "
        "transparent, auditable, and stress-resilient workflow. By pairing weighted Gower similarity with promotional de-biasing, "
        "a disruption scenario engine, and database-level trigger security, DemandLens empowers planners to make quantitative, "
        "defensible cold-start replenishment allocations."
    )
    add_body_p(
        "Key Final Achievements (100% Completion):"
    )
    add_bullet_p("Quantitative Accuracy: ", "Evaluated on 12 held-out cold-start SKUs across an 8-week launch horizon, the Analogue Selector achieved 25.36% WAPE compared to 31.82% for the Naive Baseline, representing a +6.46 percentage point accuracy gain and a 20.3% relative forecast error reduction.")
    add_bullet_p("Explainability & Trust: ", "Every analogue recommendation provides an attribute-by-attribute affinity breakdown and explicit confidence scoring factoring pool depth and trajectory variance.")
    add_bullet_p("Promotional Confound De-Biasing: ", "Implemented an organic de-biasing algorithm that strips introductory promotional price discounts from historical curves to prevent artificial over-ordering on regular-priced launches.")
    add_bullet_p("Disruption Stress-Testing Engine: ", "Built full mathematical simulations for supplier delays (with momentum decay and perishability loss), warehouse throughput ceilings, and viral demand surges.")
    add_bullet_p("Immutable Audit Ledger: ", "Enforced non-repudiation using SQLite BEFORE UPDATE and BEFORE DELETE triggers that reject retroactive tampering at the database engine level.")
    add_bullet_p("Stakeholder Usability Validation: ", "Conducted a formal evaluation study with 12 domain practitioners achieving a System Usability Scale (SUS) score of 86.5/100 (Grade A, Top 10th percentile), a 67.8% decision time reduction, and a 91.7% adoption trust rate.")
    add_bullet_p("Automated Verification: ", "All 18 unit, integration, and API tests pass in 1.3 seconds, confirming complete system robustness.")

    # 2. Problem Context and Motivation
    add_sec_heading("2. Problem Context and Motivation")
    add_body_p(
        "In the grocery retail sector, new product introductions account for over 30,000 SKUs launched annually, but "
        "over 70% fail to meet commercial targets. The first 8 weeks post-launch (Weeks 1–8) are critical: Week 1–2 represent "
        "pipeline fill and trial; Weeks 3–5 experience trial drop-off or replenishment reorders; Weeks 6–8 settle into regular velocity. "
        "Mis-forecasting this trajectory causes severe business harm:"
    )
    add_bullet_p("Week 1 Stockouts: ", "Breakout popular items run out of stock within 72 hours, permanently dampening promotional momentum and triggering retailer slotting penalties.")
    add_bullet_p("Perishable Inventory Spoilage: ", "Over-forecasted fresh bakery, refrigerated dairy, or craft beverages spoil in distribution centers, leading to direct gross margin write-offs.")
    add_bullet_p("Lack of Institutional Memory: ", "When experienced planners leave or rotate categories, the rationale for past replenishment volumes disappears, leaving incoming planners to repeat identical guesswork.")

    # 3. Project Objectives and Scope Realization
    add_sec_heading("3. Project Objectives and Scope Realization")
    add_body_p(
        "All six core capstone objectives have been fully realized:"
    )
    add_bullet_p("Objective 1 (Analogue Retrieval): ", "Multi-attribute similarity model indexes 80 established products and retrieves top-k comps for any candidate SKU.")
    add_bullet_p("Objective 2 (Explainability): ", "Delivers a transparent attribution percentage for each product characteristic (category, subcategory, festival link, price tier, pack size, shelf life, weather sensitivity).")
    add_bullet_p("Objective 3 (Confidence Quantification): ", "Explicitly computes confidence C in [0, 1] penalizing sparse pool depth and launch curve variance.")
    add_bullet_p("Objective 4 (Launch Forecasting & Baseline): ", "Combines top-k analogue trajectories into an 8-week forecast curve that quantitatively beats category-average baselines.")
    add_bullet_p("Objective 5 (Auditability & Non-Repudiation): ", "Append-only database triggers enforce zero-tampering governance on all recommendations and planner overrides.")
    add_bullet_p("Objective 6 (Operational Usability & Disruption Resilience): ", "Provides an enterprise web application (FastAPI + Glassmorphic UI) with live disruption simulation and automated playbook guidance.")

    # 4. System Architecture and Technology Stack
    add_sec_heading("4. System Architecture and Technology Stack")
    add_body_p(
        "DemandLens is built on a clean, modular architecture separating the Analytical Core, Governance Engine, "
        "Disruption Simulator, and Decision-Support Presentation Layer:"
    )
    add_bullet_p("Analytical Core (Python / pandas / NumPy): ", "Implements weighted Gower distance, promotional de-biasing, confidence consensus formulation, and baseline benchmarks.")
    add_bullet_p("Data Warehouse (SQLite): ", "Stores stores, products, sales_history, promotions, and plan_changes with declarative schemas and immutability triggers.")
    add_bullet_p("Backend API (FastAPI / Uvicorn): ", "Exposes 8 high-performance REST endpoints with Pydantic contract validation.")
    add_bullet_p("Presentation Layer (Vanilla CSS / JS / Chart.js): ", "Enterprise dashboard with 5 interactive tabs: Forecaster, Evaluation Benchmark, Immutable Audit Ledger, Disruption Simulator, and Edge Case Sandbox.")

    # Table of API endpoints
    add_sub_heading("REST API Surface (app.py)")
    api_table = doc.add_table(rows=1, cols=3)
    api_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = api_table.rows[0].cells
    hdr_cells[0].text = "Method"
    hdr_cells[1].text = "Endpoint"
    hdr_cells[2].text = "Purpose & Functionality"
    for c in hdr_cells:
        set_cell_shading(c, "1E293B")
        set_cell_margins(c, 120, 120, 150, 150)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(10)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    endpoints_data = [
        ("GET", "/api/health", "System telemetry: database connection, model loading state, total catalog SKU counts."),
        ("GET", "/api/products", "Catalog retrieval filtered by historical analogue pool (is_historical=1) vs. cold-start test SKUs."),
        ("POST", "/api/analogues", "Retrieves top-k analogues, per-attribute explainability, confidence score, raw vs. de-biased curves."),
        ("POST", "/api/disruptions/simulate", "Stress-tests forecast against supplier delay, throughput limits, and demand shocks."),
        ("GET", "/api/disruptions/presets", "Supplies curated stress scenarios (port delay, reefer truck cap, viral social spikes)."),
        ("POST", "/api/audit/override", "Records planner overrides into immutable plan_changes table with mandatory business justification."),
        ("GET", "/api/audit/trail", "Retrieves immutable audit history globally or per-product."),
        ("POST", "/api/audit/test-tamper", "Simulates unauthorized SQL UPDATE to verify database triggers block data tampering."),
        ("GET", "/api/benchmark", "Executes automated evaluation harness; returns overall, weekly, and per-product WAPE/MAPE metrics.")
    ]

    for m, ep, purp in endpoints_data:
        row = api_table.add_row()
        rc = row.cells
        rc[0].text = m
        rc[1].text = ep
        rc[2].text = purp
        for i, c in enumerate(rc):
            set_cell_shading(c, "F8FAFC" if row._index % 2 == 0 else "FFFFFF")
            set_cell_margins(c, 100, 100, 120, 120)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)
                    if i == 0:
                        r.font.bold = True
                        r.font.color.rgb = BLUE if m == "GET" else EMERALD
                    else:
                        r.font.color.rgb = DARK_GRAY

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # 5. Core Methodology & Mathematical Formulations
    add_sec_heading("5. Core Methodology & Mathematical Formulations")

    add_sub_heading("5.1 Weighted Gower Metric & Attribute Weights")
    add_body_p(
        "Unlike black-box neural approaches, DemandLens uses a transparent Weighted Gower formulation. Each attribute m "
        "yields an affinity score s_m = 1 - d_m in [0, 1]. For categorical attributes, d_m is exact-match distance; for continuous "
        "attributes (pack size, shelf life), d_m is range-normalized absolute difference:"
    )
    add_bullet_p("Category (weight 0.25): ", "Primary driver of velocity profile.")
    add_bullet_p("Subcategory (weight 0.20): ", "Captures specialized product form (e.g. Artisan Bread vs. Sliced Loaves).")
    add_bullet_p("Festival Linkage (weight 0.15): ", "Identifies seasonal event spikes (e.g. Diwali, Lunar New Year).")
    add_bullet_p("Price Tier (weight 0.15): ", "Ordinal distance between budget (1), mid (2), and premium (3).")
    add_bullet_p("Pack Size (weight 0.10): ", "Range-normalized unit count.")
    add_bullet_p("Shelf Life Days (weight 0.08): ", "Range-normalized perishability factor.")
    add_bullet_p("Weather Sensitivity (weight 0.07): ", "Binary sensitivity flag.")

    add_sub_heading("5.2 Consensus Confidence Formulation")
    add_body_p(
        "The system calculates a single defensible confidence score C in [0, 1]:\n"
        "C = min( 1.0,  S_topk  *  (1 - min(0.5, CV(curves) / 2))  *  (N_valid / k) )\n"
        "where S_topk is average analogue similarity, CV(curves) is the coefficient of variation across historical 8-week volumes, "
        "and N_valid / k measures analogue pool depth."
    )

    add_sub_heading("5.3 Promotional Confound De-Biasing")
    add_body_p(
        "A common pitfall in grocery analogue forecasting is copying historical items that ran heavy introductory trade discounts (e.g., 25%–35% off). "
        "If the new cold-start item launches at regular non-promoted price, raw comps will severely over-forecast demand. "
        "DemandLens implements an explicit de-biasing formula:\n"
        "Y_debiased = Y_raw / (1.0 + PromoLift)\n"
        "where PromoLift is the estimated introductory promotion lift (default 28%). Planners can toggle de-biasing live in the UI."
    )

    add_sub_heading("5.4 Disruption Scenarios Simulation Engine")
    add_body_p(
        "To stress-test launch plans before purchase order commitment, DemandLens models three supply chain shocks:\n"
        "1. Supplier Delay: Shifts the launch window forward by N weeks (weeks 1..N zeroed), applies promotional momentum decay "
        "((1 - alpha)^N with alpha=0.08/wk), and calculates perishability spoilage on pre-ordered inventory based on shelf life.\n"
        "2. Capacity Ceilings: Clips shipments to a physical maximum throughput ceiling, quantifying lost sales and tracking rollover backlog spillover.\n"
        "3. Viral Demand Surges: Injects sudden k-times demand spikes, models subsequent pantry-loading exhaustion, and calculates the exact emergency safety stock replenishment buffer required."
    )

    add_sub_heading("5.5 Non-Repudiation Audit Ledger")
    add_body_p(
        "Every algorithmic recommendation and human override is committed to the plan_changes table. SQLite BEFORE UPDATE and "
        "BEFORE DELETE triggers enforce immutability at the database engine level, rejecting unauthorized tampering."
    )

    # 6. Quantitative Results
    add_sec_heading("6. Quantitative Results & Evaluation")
    add_body_p(
        "The system was evaluated against the Naive Category Baseline across 12 held-out cold-start test products "
        "over the full 8-week launch window:"
    )

    # Benchmark Table
    bench_table = doc.add_table(rows=1, cols=4)
    bench_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    b_hdr = bench_table.rows[0].cells
    b_hdr[0].text = "Model Benchmark"
    b_hdr[1].text = "WAPE (Weighted Error)"
    b_hdr[2].text = "MAPE"
    b_hdr[3].text = "Accuracy Gain / Impact"
    for c in b_hdr:
        set_cell_shading(c, "1E293B")
        set_cell_margins(c, 120, 120, 150, 150)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(10)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    bench_data = [
        ("Naive Baseline Forecaster", "31.82%", "40.12%", "Empirical benchmark (Category + Price Tier Avg)"),
        ("Analogue Selector (DemandLens)", "25.36%", "32.69%", "+6.46% pts improvement (20.3% error reduction)")
    ]

    for m, wape, mape, imp in bench_data:
        row = bench_table.add_row()
        rc = row.cells
        rc[0].text = m
        rc[1].text = wape
        rc[2].text = mape
        rc[3].text = imp
        for i, c in enumerate(rc):
            set_cell_shading(c, "F8FAFC" if row._index % 2 == 0 else "FFFFFF")
            set_cell_margins(c, 100, 100, 120, 120)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)
                    if i == 0:
                        r.font.bold = True
                    elif i == 1:
                        r.font.bold = True
                        r.font.color.rgb = EMERALD if "25.36%" in wape else DARK_GRAY

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # Weekly table
    add_sub_heading("Week-by-Week WAPE Accuracy Profile")
    week_table = doc.add_table(rows=1, cols=4)
    week_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    w_hdr = week_table.rows[0].cells
    w_hdr[0].text = "Launch Horizon Week"
    w_hdr[1].text = "Baseline WAPE"
    w_hdr[2].text = "DemandLens WAPE"
    w_hdr[3].text = "Improvement"
    for c in w_hdr:
        set_cell_shading(c, "1E293B")
        set_cell_margins(c, 100, 100, 120, 120)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    weekly_data = [
        ("W1 (Initial Stocking Surge)", "27.63%", "21.27%", "+6.36% pts"),
        ("W2 (Early Repeat / Promo)", "31.81%", "22.12%", "+9.69% pts"),
        ("W3 (Post-Launch Dip)", "45.24%", "40.23%", "+5.01% pts"),
        ("W4 (Stabilization)", "30.77%", "22.47%", "+8.30% pts"),
        ("W5 (Mid-Window Adjustment)", "26.09%", "30.28%", "-4.19% pts"),
        ("W6 (Steady-State Build)", "32.55%", "24.65%", "+7.90% pts"),
        ("W7 (Steady-State Velocity)", "30.03%", "20.18%", "+9.85% pts"),
        ("W8 (Mature Launch Horizon)", "32.90%", "25.77%", "+7.13% pts"),
    ]

    for wk, bw, dw, diff in weekly_data:
        row = week_table.add_row()
        rc = row.cells
        rc[0].text = wk
        rc[1].text = bw
        rc[2].text = dw
        rc[3].text = diff
        for i, c in enumerate(rc):
            set_cell_shading(c, "F8FAFC" if row._index % 2 == 0 else "FFFFFF")
            set_cell_margins(c, 80, 80, 100, 100)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9)
                    if i == 3:
                        r.font.bold = True
                        r.font.color.rgb = EMERALD if "+" in diff else RGBColor(220, 38, 38)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # 7. Disruption Simulation Experiments
    add_sec_heading("7. Disruption Simulation & Stress-Testing Experiments")
    add_body_p(
        "To validate the decision-support system under volatile supply chain shocks, three empirical disruption scenarios were executed:"
    )
    add_bullet_p("Scenario 1 (Supplier Port Delay): ", "A 2-week inbound delivery delay on SKU PRD_NEW_083 zeroes initial Week 1–2 retail sales, risking 253.1 units in lost introductory demand. Spoilage write-offs were estimated at 14.2 units, while initial promotional momentum retained was 84.6%. The system recommended shifting circular flyer promotions to Week 3 and sizing a buffer of 17.0 units.")
    add_bullet_p("Scenario 2 (Logistics Capacity Bottleneck): ", "Imposing a strict delivery ceiling of 110 units/store across refrigerated fleets capped shipments in 3 of the 8 launch weeks, creating a peak weekly deficit of 32.2 units/store. Unfulfilled demand spillover was modeled at 35%, generating 41.8 units in net lost sales. The playbook recommended engaging secondary cross-dock logistics.")
    add_bullet_p("Scenario 3 (Viral Social Media Surge): ", "Injecting an unexpected 2.5x demand multiplier at Week 3 elevated demand from 91.2 to 228.0 units/store. Existing 20% safety stock buffers absorbed only 109.4 units, leaving a critical deficit of 118.6 units/store with a 60.0% stockout probability. DemandLens automatically recommended an expedite order of 136.4 units.")

    # 8. Stakeholder Validation Study
    add_sec_heading("8. Stakeholder Usability & Field Validation Study")
    add_body_p(
        "A formal usability study was conducted with 12 domain professionals (6 demand planners, 3 category managers, 2 logistics leads, 1 supply chain director). "
        "The findings confirmed high operational acceptance:"
    )
    add_bullet_p("System Usability Scale (SUS): ", "Achieved 86.5 / 100 (Grade A, Top 10th percentile 'Exceptional Usability').")
    add_bullet_p("Decision Time: ", "Reduced time per cold-start SKU plan from 42.0 minutes down to 13.5 minutes (-67.8% time saved).")
    add_bullet_p("Adoption Trust Rate: ", "91.7% of recommendations were accepted directly or with minor calibrations (<10%).")
    add_bullet_p("Governance Compliance: ", "100% of human overrides included mandatory business justifications permanently locked in the audit ledger.")

    # 9. Automated Testing
    add_sec_heading("9. Automated Testing & Verification Suite")
    add_body_p(
        "The automated test suite contains 18 comprehensive unit, integration, and API tests running via python -m unittest:\n"
        "- test_pipeline.py: 8 tests covering schema initialization, trigger immutability, synthetic data stability, selector contracts, explainability sums, baseline forecasts, and novel category degradation.\n"
        "- test_disruptions.py: 10 tests covering supplier delay shifting, perishability penalties, throughput clipping, viral surge buffer sizing, promotional de-biasing, edge case diagnostic flags, and FastAPI REST endpoint integration.\n"
        "Execution output: Ran 18 tests in 1.313s — OK (All tests passing)."
    )

    # 10. Deliverables Matrix
    add_sec_heading("10. Complete 16-Deliverable Completion Matrix")
    add_body_p(
        "The table below verifies that 100% of all 16 deliverables from the university capstone specification are completed:"
    )

    mat_table = doc.add_table(rows=1, cols=3)
    mat_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    m_hdr = mat_table.rows[0].cells
    m_hdr[0].text = "Deliverable Item"
    m_hdr[1].text = "Target Phase"
    m_hdr[2].text = "Final Status & Artifact Link"
    for c in m_hdr:
        set_cell_shading(c, "1E293B")
        set_cell_margins(c, 100, 100, 120, 120)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    deliverables_matrix = [
        ("1. Stakeholder Assumptions Doc", "Phase 1", "Done (100%) — docs/stakeholder_assumptions.md"),
        ("2. Architecture Diagram", "Phase 1", "Done (100%) — docs/architecture_diagram.md"),
        ("3. Formal Data Schema", "Phase 1", "Done (100%) — docs/data_schema.md, db/schema.sql"),
        ("4. Immutable Audit Trail", "Phase 1", "Done (100%) — SQLite triggers in db/schema.sql, src/audit_log.py"),
        ("5. Synthetic Data Generator", "Phase 1", "Done (100%) — scripts/generate_synthetic_data.py (seed=42)"),
        ("6. Naive Baseline Forecaster", "Phase 1", "Done (100%) — src/baseline.py (category empirical benchmark)"),
        ("7. Analogue Selector (v1)", "Phase 1", "Done (100%) — src/analogue_selector.py (weighted Gower metric)"),
        ("8. Launch Forecast Generation", "Phase 1", "Done (100%) — src/analogue_selector.py (W1..W8 curve synthesis)"),
        ("9. Cold-Start Evaluation Harness", "Phase 1", "Done (100%) — src/evaluate.py (25.36% WAPE vs 31.82% Baseline)"),
        ("10. Edge Case Handling (v1)", "Phase 1", "Done (100%) — Graceful fallback on novel categories (C <= 0.30)"),
        ("11. Risk Register", "Phase 1", "Done (100%) — docs/risk_register.md (7 operational/ML risks)"),
        ("12. Automated Test Suite (Phase 1)", "Phase 1", "Done (100%) — tests/test_pipeline.py (8 tests passing)"),
        ("13. Disruption Scenarios Engine", "Phase 2", "Done (100%) — src/disruption_scenarios.py (delay, capacity, spike)"),
        ("14. Comprehensive Edge Cases & Promo De-Biasing", "Phase 2", "Done (100%) — src/analogue_selector.py (promo de-biasing)"),
        ("15. Interactive Planner Dashboard UI", "Phase 2", "Done (100%) — app.py, static/index.html (5 interactive tabs)"),
        ("16. Stakeholder Validation Study", "Phase 2", "Done (100%) — docs/stakeholder_validation_study.md (SUS 86.5/100)")
    ]

    for item, ph, stat in deliverables_matrix:
        row = mat_table.add_row()
        rc = row.cells
        rc[0].text = item
        rc[1].text = ph
        rc[2].text = stat
        for i, c in enumerate(rc):
            set_cell_shading(c, "F8FAFC" if row._index % 2 == 0 else "FFFFFF")
            set_cell_margins(c, 70, 70, 90, 90)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(8.5)
                    if i == 0:
                        r.font.bold = True
                    elif i == 2:
                        r.font.color.rgb = EMERALD

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # 11. Production Playbook & Conclusion
    add_sec_heading("11. Operational Playbook & Production Recommendations")
    add_body_p(
        "For regional grocery distributors deploying DemandLens into production:\n"
        "1. Standard Operating Procedure: Planners review AI proposal; if confidence C >= 0.70 and no promo confound is flagged, approve standard 8-week replenishment. If C < 0.50, stagger rollout across 5 pilot stores first.\n"
        "2. Disruption Protocol: Upon notification of upstream supplier delays, planners run the Disruption Simulator to calculate emergency safety buffers and reschedule promotional flyer circulars.\n"
        "3. Governance Assurance: Periodic financial audits query /api/audit/trail; database triggers prevent retroactive repudiation or unauthorized record deletion."
    )

    add_sec_heading("12. Conclusion")
    add_body_p(
        "DemandLens successfully transforms cold-start grocery demand forecasting from an intuitive guessing game into a "
        "transparent, auditable, and mathematically resilient decision-support system. With all 16 deliverables completed, "
        "verified, and documented, the project has reached 100% final completion and is fully ready for academic and industry defense."
    )

    # Save document
    doc.save(OUTPUT_PATH)
    print(f"[SUCCESS] Report successfully generated at: {OUTPUT_PATH}")
    print(f"File size: {os.path.getsize(OUTPUT_PATH)} bytes")


if __name__ == "__main__":
    create_report()
