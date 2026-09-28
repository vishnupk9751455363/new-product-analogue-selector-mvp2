# Stakeholder Assumptions & Operational Context

## 1. Primary User Personas

### Persona A: Regional Demand Planner (Primary Operational User)
- **Role**: Responsible for setting 4- to 12-week replenishment orders and introductory stock allocations across 15+ regional grocery retail stores.
- **Workflow Today**:
  - Receives notice from commercial merchandising that a new SKU is launching in 4 weeks.
  - Planners currently guess analogues manually based on intuition (e.g., *"this seasonal gingerbread biscuit is kind of like the festive sugar cookie from two years ago"*).
  - Copies an ad-hoc spreadsheet curve, adjusts volumes by an arbitrary percentage in Excel, and sends warehouse purchase orders.
- **Pain Points**:
  - High variance in cold-start accuracy; frequent stockouts in Week 1-2 on breakout hits, followed by severe perishable spoilage/waste on over-forecasted items.
  - Zero institutional memory: when a planner departs or changes categories, the rationale for past launch decisions disappears.
- **What "Good Enough" Looks Like**:
  - An interpretable forecast reducing cold-start launch WAPE from ~35% down into the 20-25% range.
  - High explainability: Planners will reject black-box predictions; they must see *which* 3-5 historical SKUs were selected and *why* (attribute similarity match).
  - Simple override interface with automatic logging of justification.

### Persona B: Merchandising Category Manager (Strategic Stakeholder)
- **Role**: Manages supplier vendor agreements, introductory promotional calendars, and gross margins across broad categories (Bakery, Beverages, Fresh Produce, Confectionery).
- **Workflow Today**:
  - Negotiates trade promotions and introductory slotting fees with food brands.
  - Frustrated by distributors either failing to stock enough inventory for promoted festival launches or over-ordering short-shelf-life goods.
- **Needs**:
  - Visibility into confidence ratings: high confidence allows aggressive marketing; low confidence triggers staged rollouts and tighter initial replenishment cycles.

---

## 2. Key Operational Assumptions

1. **Cold-Start Boundary Definition**:
   - A "cold-start" product has zero prior sales history in the distributor's system at launch planning time ($T_0 - 4\text{ weeks}$).
   - However, fixed product specifications (category, subcategory, price tier, unit pack size, shelf-life days, target festival linkage, and weather sensitivity flag) are known at product onboarding time.

2. **Forecast Horizon**:
   - The critical business risk window is the first **8 weeks post-launch** ($W_1 \dots W_8$).
   - Weeks 1-2 capture initial pipeline fill and promotional trial; Weeks 3-5 capture post-trial retention/dip; Weeks 6-8 capture recurring baseline velocity.

3. **Festival & Cultural Calendars**:
   - Regional festivals (e.g., Diwali, Lunar New Year, Harvest Fair, Spring Holiday) dramatically concentrate demand for specific food items within a 2-3 week window.
   - Analogue selection must treat festival linkages as distinct from generic year-round velocity.

4. **Auditability as a Hard Regulatory / Business Constraint**:
   - Every modification to a baseline plan (whether algorithmically generated or manually adjusted) must be permanently logged with UTC timestamp, user ID, previous values, new values, and business rationale.
   - Planners must never be able to retroactively edit past logs.

5. **Human-in-the-Loop Decision Support**:
   - The system is an assistive **decision-support tool**, not an autonomous replenishment agent.
   - The system proposes; the planner approves or overrides.
