# Microsoft SMB Intelligence Engine

> **A production-grade analytics engineering and decision intelligence system built on Microsoft Fabric — identifying which SMB customers to act on today, and exactly what action to take.**

<br>

## The Business Problem

Microsoft's Small and Medium Business organization serves thousands of accounts across industries and regions. Most analytics teams answer the question *"what happened?"*, churn rates in a dashboard, usage metrics in a report.

This project answers a different question:

> **Which SMB customers should Microsoft act on TODAY and what specific action should each account receive to maximize revenue retention and growth?**

That shift from reporting to decision support is the entire point of this system.

<br>

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MICROSOFT FABRIC LAKEHOUSE                      │
│                                                                     │
│  Raw Telemetry CSV                                                  │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────┐    60,000 rows · 17 columns                       │
│  │   BRONZE    │    Raw fidelity preserved · 10 anomaly types      │
│  │   LAYER     │    Dataflow Gen2 + PySpark validation             │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐    58,500 rows · 27 columns                       │
│  │   SILVER    │    14-step transformation · 1,500 quarantined     │
│  │   LAYER     │    Feature engineering · Constraint enforcement   │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐    3 business-facing Gold tables                  │
│  │    GOLD     │    Health scoring · Decision engine               │
│  │   LAYER     │    Executive + Segment + Account views            │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐    Random Forest · AUC > 0.80                     │
│  │  CHURN ML   │    Churn probability per account                  │
│  │   MODEL     │    Feature importance ranking                     │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐    gold_smb_scored · 5,000 accounts               │
│  │  DECISION   │    Recommended action per account                 │
│  │   ENGINE    │    Retention priority score                       │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐    3-page Power BI dashboard                      │
│  │  POWER BI   │    Executive · Segment · Action Board             │
│  │ DASHBOARD   │    Connected to all 4 Gold tables                 │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

<br>

## Dataset

This project uses **synthetic data** generated with Python, intentionally designed to simulate realistic Microsoft SMB telemetry behavior.

| Parameter | Value |
|---|---|
| Accounts | 5,000 unique SMB accounts |
| Time Period | 12 months |
| Total Rows | 60,000 (one row per account per month) |
| Industries | Retail, Finance, Healthcare, Manufacturing, Tech |
| Regions | Northeast, Southeast, Midwest, West, Southwest |
| Revenue Tiers | Low, Mid, High |

### Why synthetic data?

Real datasets carry licensing restrictions and cannot be shared on GitHub. Synthetic data with engineered business logic is more defensible in an interview where  you can explain exactly why every signal is in the data.

### Business logic built into the data

The dataset is not random noise. Specific behavioral patterns are engineered in:

- Churned accounts show **declining active_user_rate** in months 10–12, before the churn event occurs
- **Support ticket spikes** (3+ in a month) appear 1–2 months before churn, a detectable leading indicator
- **Azure-active accounts churn at 8.4%** vs 14.3% for non-Azure accounts, simulating real ecosystem lock-in
- **Retail churn (18.0%) is 2.5× Finance churn (7.2%)**, simulating real industry volatility differences
- Multi-product accounts show measurably lower churn, product breadth is protective

These patterns are verified by automated sanity checks at generation time.

<br>

## Pipeline - Layer by Layer

### Bronze Layer

**Notebook:** `SMB_Bronze_Load` | **Dataflow:** `SMB_Bronze_Dataflow` | **Table:** `bronze_smb_accounts`

The Bronze layer ingests raw CSV and preserves it exactly as-is, no transformations. This maintains a full audit trail: if anything breaks downstream, you trace back to source truth.

**Hybrid ingestion approach:**
- **Dataflow Gen2** - visual pipeline for schema validation and stakeholder visibility
- **PySpark notebook** - programmatic validation for engineering reproducibility

**10 categories of intentional dirty data injected for Bronze realism:**

| Dirty Data Type | % of Rows | Business Reason |
|---|---|---|
| `account_id` nulls | 2.5% | CRM sync failures |
| `industry` inconsistent casing/spaces | 6.0% | Source system inconsistency |
| `revenue_tier` inconsistent variants | 4.0% | Manual CRM classification mismatch |
| `month` stored as messy strings | 3.0% | Ingestion format inconsistency |
| `m365_licensed_seats` sentinel/overflow | 3.5% | Export bug / overflow |
| `m365_active_users` nulls | 4.0% | Missing telemetry snapshot |
| `teams_daily_active` > active users | 4.0% | Event duplication bug |
| `azure_compute_hours` negative sentinel | 2.0% | Failed billing export |
| `azure_compute_hours` nulls | 2.0% | Missing billing export |
| `support_tickets` sentinel 99 | 4.0% | Unsupported CRM status code |

---

### Silver Layer

**Notebook:** `SMB_Silver_Transform` | **Tables:** `silver_smb_accounts` · `silver_smb_accounts_quarantine`

| Metric | Value |
|---|---|
| Input rows | 60,000 |
| Rows retained | 58,500 |
| Rows quarantined | 1,500 |
| Output columns | 27 (+10 from Bronze) |

The Silver layer runs 14 targeted transformation steps across three categories:

**Standardization**
- `month` extracted from mixed string formats using regex, cast to integer
- `industry` and `revenue_tier` mapped via pattern matching (`.like("%retail%")` after lowercasing), more robust than title-casing
- `company_name` trimmed

**Quarantine (not silent deletion)**
Rows with null `account_id`, unparseable `month`, unmapped `industry` or `revenue_tier` are written to a separate `silver_smb_accounts_quarantine` table. This enables downstream audit and root-cause analysis, unrecoverable records are visible, not erased.

**Sentinel and constraint repair**

| Issue | Fix |
|---|---|
| `m365_licensed_seats` = -1 or 9999 | → null |
| `azure_compute_hours` < 0 or null | → 0.0 (pre-signup) or null (post-signup) |
| `support_tickets` = 99 | → null |
| `teams_daily_active` > `m365_active_users` | → capped at active users |
| `m365_active_users` > `m365_licensed_seats` | → capped at licensed seats |

**Business-aware null handling with `is_pre_signup`**

Pre-signup rows (where `month < signup_month`) have zero usage by design — not by data quality failure. The Silver layer computes `is_pre_signup` and handles nulls differently for these rows vs post-signup rows. Treating pre-signup zeros as dirty data would artificially inflate churn risk signals for early-cohort accounts.

**5 engineered features added in Silver:**

| Feature | Formula | Business Reason |
|---|---|---|
| `active_user_rate` | `m365_active_users / m365_licensed_seats` | Engagement quality, not just volume |
| `product_breadth_score` | Count of active product families (0–4) | Ecosystem stickiness - more products = harder to leave |
| `support_spike_flag` | `1 if support_tickets > 3` | Distress leading indicator |
| `azure_active_flag` | `1 if azure_compute_hours > 20` | Protective ecosystem signal |
| `months_without_growth` | Consecutive months with no seat increase | Stagnation signal |

---

### Gold Layer

**Notebook:** `SMB_Gold_Transform` | **3 output tables**

The Gold layer produces three business-facing datasets — not one generic aggregation. Each serves a different audience and a different decision type.

#### `gold_smb_account_snapshot` - 5,000 rows, one per account

The flagship action table. Every row is a complete account health profile with a recommended action attached.

Key computed columns:

| Column | Logic |
|---|---|
| `avg_active_user_rate_6mo` | Trailing 6-month average, smooths noise, captures trend |
| `avg_active_user_rate_3mo` | Trailing 3-month, more sensitive to recent changes |
| `usage_momentum` | Current rate minus previous month rate |
| `teams_adoption_pct` | Teams users / active M365 users |
| `azure_intensity` | Azure compute hours per active user |
| `trend_direction` | Improving / Stable / Declining vs 6mo average ±0.05 band |
| `health_score` | Weighted 0–100 score (see below) |
| `health_label` | Healthy / Stable / Watchlist / At Risk |
| `revenue_at_risk` | Dollar CLV exposure for At Risk + Watchlist accounts |
| `retention_priority_score` | Risk × revenue × urgency weighting |
| `recommended_action` | Rule-based action from Decision Engine |

**Health Score — Explainable, Weighted (0–100)**

| Component | Weight | Signal |
|---|---|---|
| Active user rate | 35 pts | Core engagement quality |
| Teams adoption % | 20 pts | Collaboration depth - stickiest product |
| Product breadth score | 15 pts | Ecosystem lock-in (normalized 0-4 → 0–1) |
| Seat growth momentum | 10 pts | Growing = 10, stable = 5, shrinking = 0 |
| Azure adoption | 10 pts | Protective signal - binary flag |
| Support spike penalty | –10 pts | Distress signal subtracted from score |

Health labels: **80–100 → Healthy · 60–79 → Stable · 40-59 → Watchlist · <40 → At Risk**

**Decision Engine — 8 rule-based actions**

| Condition | Action |
|---|---|
| Health = At Risk + Revenue = High | Critical Retention Call |
| Support spike + Declining trend | Customer Success Intervention |
| At Risk/Watchlist + single product | Adoption Recovery - Expand Beyond Single Product |
| Expansion ready + no Azure | Cross-Sell: Azure Trial Campaign |
| Expansion ready + no Dynamics | Cross-Sell: Dynamics 365 Introduction |
| Expansion ready | Upsell: Copilot License Recommendation |
| Health = Healthy | Nurture: Community Program |
| All others | Monitor: Standard Check-in |

#### `gold_smb_monthly_kpis` - 12 rows, one per month

Executive trend table. Powers the time-series charts and KPI cards in Power BI. Tracks churn rate, average health score, active user rate, support spike volume, retention risk accounts, and estimated revenue at risk month by month.

#### `gold_smb_segment_kpis` - 2,590 rows

Segment intelligence table. One row per month × industry × region × revenue tier × employee band. Powers the "churn by industry" and "health by region" slicing in Power BI. Enables sales leadership to identify which segments are deteriorating before individual account signals surface.

---

### ML Layer — Churn Model

**Notebook:** `SMB_Churn_Model` | **Algorithm:** Random Forest Classifier | **Table:** `gold_smb_scored`

**Why Random Forest?**

Logistic regression would work here, but Random Forest was chosen because: it handles mixed feature types (continuous and encoded categorical) without preprocessing, it is robust to outliers in usage data, it does not require feature scaling, and critically, it produces **feature importance rankings** that translate ML outputs into business language.

**Features used:**

| Feature | Business Reason |
|---|---|
| `avg_active_user_rate_6mo` | Trailing engagement trend, strongest churn predictor |
| `active_user_rate` | Current engagement snapshot |
| `product_breadth_score` | Ecosystem stickiness |
| `months_without_growth` | Stagnation duration |
| `support_spike_flag` | Distress signal |
| `azure_active_flag` | Protective signal |
| `teams_adoption_pct` | Collaboration depth |
| `health_score` | Composite signal |
| `retention_priority_score` | Commercial urgency |
| `employee_count` | Account size proxy |
| `revenue_tier` | Commercial value segment |
| `trend_direction` | Directional momentum |
| `industry` | Sector-level churn baseline |

**Training setup:** 80/20 train/test split, seed=42, 100 trees, max_depth=5

**Churn risk labeling:**

| Label | Threshold |
|---|---|
| Critical | churn_probability ≥ 0.80 |
| High | 0.60 – 0.79 |
| Medium | 0.35 – 0.59 |
| Low | < 0.35 |

`gold_smb_scored` adds `churn_probability` and `churn_risk_label` to every account in the Gold snapshot, creating the final scored table that feeds Power BI.

<br>

## Power BI Dashboard

**4 data sources connected:** `gold_smb_scored` · `gold_smb_monthly_kpis` · `gold_smb_segment_kpis` · `gold_smb_feature_importance`

**3 dashboard pages:**

**Page 1 - Executive Overview**
KPI cards: Total Accounts · Active Accounts · Churn Rate · Avg Health Score · Revenue at Risk ($). Monthly churn trend line. Monthly health score trend. Revenue at risk by month.

**Page 2 - Segment Intelligence**
Churn rate by industry (bar chart). Health score by region. Support spike rate by revenue tier. Product breadth distribution by employee band. Enables sales leadership to identify deteriorating segments before individual account signals surface.

**Page 3 - Account Action Board**
The Monday morning fire list. Every account with churn risk label, health score, trend direction, CLV, and recommended action. Filterable by action type, region, industry, and revenue tier. A sales manager opens this page and knows exactly who to call and what to offer, no additional analysis required.

<br>

## Key Findings

These are findings from the dataset, confirmed by sanity checks at generation and model training:

- **Retail accounts churn at 2.5× the rate of Finance accounts** (18.0% vs 7.2%), industry-specific outreach strategies are justified
- **Azure-active accounts churn at nearly half the rate** of non-Azure accounts (8.4% vs 14.3%), Azure adoption is the single most impactful protective action Microsoft can take
- **Support ticket spikes of 3+ predict churn within 30 days** churned accounts average 4.53 support tickets in months 10–11 vs 1.40 for retained accounts
- **Active user rate drops from 0.638 to 0.333** in the two months before churn, a 47% decline that is detectable and actionable before the account is lost

<br>

## Fabric Lakehouse Structure

```
SMB_Lakehouse/
├── Tables/
│   ├── bronze_smb_accounts          ← Raw ingested data, all anomalies preserved
│   ├── bronze_smb_accounts_df       ← Dataflow Gen2 validation output
│   ├── silver_smb_accounts          ← Cleaned, feature-engineered (58,500 rows, 27 cols)
│   ├── silver_smb_accounts_quarantine ← Unrecoverable records (1,500 rows)
│   ├── gold_smb_account_snapshot    ← One row per account, action layer
│   ├── gold_smb_monthly_kpis        ← Executive trend table (12 rows)
│   ├── gold_smb_segment_kpis        ← Segment intelligence (2,590 rows)
│   ├── gold_smb_scored              ← ML-enriched snapshot with churn scores
│   └── gold_smb_feature_importance  ← Feature importance for Power BI
└── Files/
    └── Bronze/
        └── smb_accounts_bronze.csv  ← Source file
```

<br>

## Notebook Index

| Notebook | Purpose | Input | Output |
|---|---|---|---|
| `SMB_Bronze_Load` | Ingest, validate, save Bronze table | CSV file | `bronze_smb_accounts` |
| `SMB_Silver_Transform` | 14-step clean + feature engineering | `bronze_smb_accounts` | `silver_smb_accounts` + quarantine |
| `SMB_Gold_Transform` | KPI engineering, health scoring, decision engine | `silver_smb_accounts` | 3 Gold tables |
| `SMB_Churn_Model` | Random Forest training, scoring, feature importance | `gold_smb_account_snapshot` | `gold_smb_scored` + feature importance |

<br>

## Tech Stack

| Category | Tools |
|---|---|
| Cloud Platform | Microsoft Fabric |
| Storage | OneLake Delta Tables |
| Processing | PySpark (Fabric Notebooks) |
| Ingestion | Dataflow Gen2 |
| Data Generation | Python — pandas, numpy, faker |
| Machine Learning | PySpark MLlib — Random Forest |
| Visualization | Power BI (DirectLake connection) |
| Language | Python, SQL, PySpark |

<br>

## How to Reproduce

**1. Generate the dataset**
```bash
pip install pandas numpy faker scikit-learn
python generate_smb_bronze.py
# Output: smb_accounts_bronze.csv (60,000 rows, 4.9 MB)
```

**2. Upload to Microsoft Fabric**
- Create a Lakehouse named `SMB_Lakehouse`
- Upload `smb_accounts_bronze.csv` to `Files/Bronze/`

**3. Run notebooks in order**
```
SMB_Bronze_Load      →  creates bronze_smb_accounts
SMB_Silver_Transform →  creates silver_smb_accounts
SMB_Gold_Transform   →  creates all 3 Gold tables
SMB_Churn_Model      →  creates gold_smb_scored
```

**4. Connect Power BI**
- Open Power BI Desktop
- Connect via OneLake Data Hub → `SMB_Lakehouse`
- Build 3-page dashboard using `gold_smb_scored`, `gold_smb_monthly_kpis`, `gold_smb_segment_kpis`

<br>


---

*Built by Aditi Patil · MSIM, University of Illinois Urbana-Champaign · Microsoft Fabric Certified (DP-600) · Power BI Certified (PL-300)*
