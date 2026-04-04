"""
=============================================================================
MICROSOFT SMB INTELLIGENCE ENGINE - Synthetic Data Generator
=============================================================================
Author : Aditi Portfolio Project
Purpose : Generate a realistic Bronze-layer SMB telemetry dataset for the Microsoft SMB Intelligence Engine project
OUTPUT : smb_accounts_bronze.csv
GRAIN : One row per account per month
SCALE : 5,000 accounts × 12 months = 60,000 rows

=============================================================================
"""

import os
import random
import numpy as np
import pandas as pd
from faker import Faker

# =============================================================================
# REPRODUCIBILITY
# =============================================================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
rng = np.random.default_rng(SEED)
fake = Faker()
Faker.seed(SEED)

# =============================================================================
# CONFIG
# =============================================================================
NUM_ACCOUNTS = 5000
MONTHS = list(range(1, 13))
OUTFILE = r"C:\Users\Aditi Patil\OneDrive\Documents\Master's Projects\SMB_Intelligence_Engine\smb_accounts_bronze.csv"

INDUSTRIES = ["Retail", "Finance", "Healthcare", "Manufacturing", "Tech"]
REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
REVENUE_TIERS = ["Low", "Mid", "High"]

INDUSTRY_WEIGHTS = {
    "Retail": 0.22,
    "Finance": 0.18,
    "Healthcare": 0.20,
    "Manufacturing": 0.18,
    "Tech": 0.22,
}

REGION_WEIGHTS = {
    "Northeast": 0.18,
    "Southeast": 0.22,
    "Midwest": 0.20,
    "West": 0.24,
    "Southwest": 0.16,
}

REVENUE_TIER_WEIGHTS = {
    "Low": 0.50,
    "Mid": 0.32,
    "High": 0.18,
}

REVENUE_TIER_TO_CLV = {
    "Low": 12000,
    "Mid": 40000,
    "High": 90000,
}

INDUSTRY_CHURN_ADJ = {
    "Retail": 0.06,
    "Finance": -0.04,
    "Healthcare": 0.01,
    "Manufacturing": 0.02,
    "Tech": -0.01,
}

# =============================================================================
# HELPERS
# =============================================================================
def weighted_choice(mapping: dict):
    keys = list(mapping.keys())
    probs = list(mapping.values())
    return rng.choice(keys, p=probs)

def clamp_int(x, low, high):
    return int(np.clip(round(x), low, high))

def clamp_float(x, low, high, decimals=2):
    return round(float(np.clip(x, low, high)), decimals)

def pct_chance(p):
    return rng.random() < p

def revenue_multiplier(revenue_tier: str) -> float:
    return {"Low": 0.8, "Mid": 1.0, "High": 1.25}[revenue_tier]

def industry_multiplier(industry: str) -> float:
    return {
        "Retail": 0.95,
        "Finance": 1.02,
        "Healthcare": 0.98,
        "Manufacturing": 0.97,
        "Tech": 1.08,
    }[industry]

# =============================================================================
# ACCOUNT-LEVEL BASE GENERATION
# =============================================================================
def generate_account_master(account_id: int) -> dict:
    industry = weighted_choice(INDUSTRY_WEIGHTS)
    region = weighted_choice(REGION_WEIGHTS)
    revenue_tier = weighted_choice(REVENUE_TIER_WEIGHTS)

    employee_count = int(rng.integers(10, 501))
    signup_month = int(rng.integers(1, 10))

    company_name = fake.company()

    seat_ratio = rng.uniform(0.55, 0.95)
    base_licensed_seats = clamp_int(employee_count * seat_ratio, 5, employee_count + 50)

    if employee_count < 50:
        util_base = rng.uniform(0.72, 0.92)
    elif employee_count < 200:
        util_base = rng.uniform(0.62, 0.85)
    else:
        util_base = rng.uniform(0.50, 0.78)

    azure_adopted = int(pct_chance(0.40 if revenue_tier != "Low" else 0.28))
    dynamics_adopted = int(pct_chance(0.30 if revenue_tier == "High" else 0.20))
    security_adopted = int(pct_chance(0.52))

    churn_score = 0.14
    churn_score += INDUSTRY_CHURN_ADJ[industry]

    if azure_adopted:
        churn_score -= 0.07
    if dynamics_adopted:
        churn_score -= 0.03
    if security_adopted:
        churn_score -= 0.02

    if revenue_tier == "High":
        churn_score -= 0.03
    elif revenue_tier == "Low":
        churn_score += 0.02

    if signup_month >= 7:
        churn_score += 0.02

    churn_score = float(np.clip(churn_score, 0.05, 0.35))
    will_churn = int(pct_chance(churn_score))

    decline_start_month = int(rng.integers(9, 11)) if will_churn else None

    return {
        "account_id": account_id,
        "company_name": company_name,
        "signup_month": signup_month,
        "industry": industry,
        "employee_count": employee_count,
        "revenue_tier": revenue_tier,
        "region": region,
        "base_licensed_seats": base_licensed_seats,
        "util_base": util_base,
        "azure_adopted": azure_adopted,
        "dynamics_adopted": dynamics_adopted,
        "security_product": security_adopted,
        "will_churn": will_churn,
        "decline_start_month": decline_start_month,
    }

# =============================================================================
# MONTHLY TELEMETRY GENERATION
# =============================================================================
def generate_monthly_row(master: dict, month: int) -> dict:
    signup_month = master["signup_month"]
    pre_signup = month < signup_month

    employee_count = master["employee_count"]
    revenue_tier = master["revenue_tier"]
    industry = master["industry"]

    base_seats = master["base_licensed_seats"]
    if pre_signup:
        licensed_seats = 0
    else:
        growth_noise = rng.normal(0, 2.5)
        if master["will_churn"]:
            licensed_seats = base_seats + clamp_int((month - signup_month) * 0.3 + growth_noise, -5, 10)
        else:
            licensed_seats = base_seats + clamp_int((month - signup_month) * rng.uniform(0.8, 1.8) + growth_noise, -3, 30)
        licensed_seats = max(licensed_seats, 0)

    if pre_signup or licensed_seats == 0:
        active_users = 0
    else:
        util = master["util_base"]
        if master["will_churn"] and month >= master["decline_start_month"]:
            decline_steps = month - master["decline_start_month"] + 1
            util -= 0.10 * decline_steps
        else:
            util += rng.normal(0.01, 0.02)
        util = float(np.clip(util, 0.05, 0.97))
        active_users = clamp_int(licensed_seats * util + rng.normal(0, 4), 0, licensed_seats)

    if active_users == 0:
        teams_daily_active = 0
    else:
        teams_ratio = rng.uniform(0.50, 0.88)
        if master["will_churn"] and month >= (master["decline_start_month"] or 12):
            teams_ratio -= 0.10
        teams_ratio = float(np.clip(teams_ratio, 0.20, 0.95))
        teams_daily_active = clamp_int(active_users * teams_ratio + rng.normal(0, 2), 0, active_users)

    if pre_signup:
        azure_compute_hours = 0.0
    else:
        if master["azure_adopted"]:
            az_base = rng.uniform(40, 220) * revenue_multiplier(revenue_tier) * industry_multiplier(industry)
            if master["will_churn"] and month >= (master["decline_start_month"] or 12):
                az_base *= 0.82
            azure_compute_hours = clamp_float(az_base + rng.normal(0, 12), 0, 400)
        else:
            azure_compute_hours = clamp_float(rng.uniform(0, 12), 0, 20)

    if pre_signup or not master["dynamics_adopted"] or active_users == 0:
        dynamics_users = 0
    else:
        dyn_ratio = rng.uniform(0.18, 0.55)
        if revenue_tier == "High":
            dyn_ratio += 0.06
        dynamics_users = clamp_int(active_users * dyn_ratio + rng.normal(0, 2), 0, active_users)

    if pre_signup:
        support_tickets = 0
    else:
        if master["will_churn"] and month >= max((master["decline_start_month"] or 12) - 1, signup_month):
            support_tickets = int(rng.integers(3, 7))
        else:
            base_low = 0 if industry == "Finance" else 1
            support_tickets = int(rng.integers(base_low, 3))

    churned = int(master["will_churn"] == 1 and month == 12)

    base_clv = REVENUE_TIER_TO_CLV[revenue_tier]
    breadth_count = (
        int(active_users > 0)
        + int(azure_compute_hours > 20)
        + int(dynamics_users > 0)
        + int(master["security_product"] == 1)
    )
    health_factor = 0.75
    if licensed_seats > 0:
        aur = active_users / max(licensed_seats, 1)
        health_factor += min(aur, 1.0) * 0.35
    health_factor += 0.04 * breadth_count
    estimated_clv_12mo = clamp_float(base_clv * health_factor, 5000, 180000, 0)

    return {
        "account_id": master["account_id"],
        "company_name": master["company_name"],
        "signup_month": master["signup_month"],
        "month": month,
        "industry": master["industry"],
        "employee_count": master["employee_count"],
        "revenue_tier": master["revenue_tier"],
        "region": master["region"],
        "m365_active_users": active_users,
        "m365_licensed_seats": licensed_seats,
        "teams_daily_active": teams_daily_active,
        "azure_compute_hours": azure_compute_hours,
        "dynamics_users": dynamics_users,
        "security_product": master["security_product"],
        "support_tickets": support_tickets,
        "estimated_clv_12mo": estimated_clv_12mo,
        "churned": churned,
    }

# =============================================================================
# CLEAN DATASET BUILD
# =============================================================================
print("=" * 80)
print("GENERATING CLEAN SMB DATASET...")
print("=" * 80)

account_masters = [generate_account_master(i) for i in range(1, NUM_ACCOUNTS + 1)]

rows = []
for master in account_masters:
    for month in MONTHS:
        rows.append(generate_monthly_row(master, month))

df = pd.DataFrame(rows)

print(f"Clean dataset generated: {df.shape[0]:,} rows × {df.shape[1]} columns")
print("Columns:")
for col in df.columns:
    print(f"  - {col}")

# =============================================================================
# CLEAN CONSTRAINT CHECKS
# =============================================================================
print("\n" + "=" * 80)
print("RUNNING CLEAN CONSTRAINT CHECKS...")
print("=" * 80)

checks = {
    "m365_active_users <= m365_licensed_seats":
        (df["m365_active_users"] <= df["m365_licensed_seats"]).all(),
    "teams_daily_active <= m365_active_users":
        (df["teams_daily_active"] <= df["m365_active_users"]).all(),
    "dynamics_users <= m365_active_users":
        (df["dynamics_users"] <= df["m365_active_users"]).all(),
    "employee_count between 10 and 500":
        df["employee_count"].between(10, 500).all(),
    "month between 1 and 12":
        df["month"].between(1, 12).all(),
    "support_tickets >= 0":
        (df["support_tickets"] >= 0).all(),
    "azure_compute_hours >= 0":
        (df["azure_compute_hours"] >= 0).all(),
    "security_product in {0,1}":
        df["security_product"].isin([0, 1]).all(),
    "churned in {0,1}":
        df["churned"].isin([0, 1]).all(),
}

all_passed = True
for name, passed in checks.items():
    print(f"  {'✓' if passed else '✗'} {name}")
    if not passed:
        all_passed = False

print(f"\n  All clean checks passed: {'YES ✓' if all_passed else 'NO - fix before dirty injection'}")

# =============================================================================
# DIRTY DATA INJECTION - BRONZE REALISM
# =============================================================================
print("\n" + "=" * 80)
print("INJECTING DIRTY DATA (BRONZE REALISM)...")
print("=" * 80)

bronze_df = df.copy()
n = len(bronze_df)

def dirty_idx(pct, excluded=None):
    if excluded is None:
        excluded = np.array([], dtype=int)
    available = np.setdiff1d(np.arange(n), excluded)
    k = max(1, int(round(n * pct)))
    return rng.choice(available, size=min(k, len(available)), replace=False)

used = np.array([], dtype=int)

idx = dirty_idx(0.025, used)
bronze_df.loc[idx, "account_id"] = np.nan
used = np.union1d(used, idx)
print(f"  1. account_id nulls                         : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.06, used)
dirty_industry_vals = ["retail", "Finance ", "HEALTHCARE", "manufacturing", " Tech", "TECH "]
bronze_df.loc[idx, "industry"] = rng.choice(dirty_industry_vals, size=len(idx))
used = np.union1d(used, idx)
print(f"  2. industry inconsistent casing/spaces     : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.04, used)
dirty_revenue_vals = ["low", "MID", "High ", " mid", "LOW "]
bronze_df.loc[idx, "revenue_tier"] = rng.choice(dirty_revenue_vals, size=len(idx))
used = np.union1d(used, idx)
print(f"  3. revenue_tier inconsistent variants      : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.03, used)
bronze_df["month"] = bronze_df["month"].astype(object)  # allow mixed types
month_dirty = []
for m in bronze_df.loc[idx, "month"].tolist():
    m_int = int(m)
    month_dirty.append(rng.choice([str(m_int), f"{m_int:02d}", f"{m_int} "]))
bronze_df.loc[idx, "month"] = month_dirty
used = np.union1d(used, idx)
print(f"  4. month stored as messy strings           : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.035, used)
half = len(idx) // 2
bronze_df.loc[idx[:half], "m365_licensed_seats"] = -1
bronze_df.loc[idx[half:], "m365_licensed_seats"] = 9999
used = np.union1d(used, idx)
print(f"  5. m365_licensed_seats invalid values      : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.04, used)
bronze_df.loc[idx, "m365_active_users"] = np.nan
used = np.union1d(used, idx)
print(f"  6. m365_active_users nulls                 : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.04, used)
base_vals = bronze_df.loc[idx, "m365_active_users"].fillna(0).astype(float)
bronze_df.loc[idx, "teams_daily_active"] = (base_vals + rng.integers(5, 25, size=len(idx))).astype(int)
used = np.union1d(used, idx)
print(f"  7. teams_daily_active exceeds active users : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.02, used)
bronze_df.loc[idx, "azure_compute_hours"] = -5.0
used = np.union1d(used, idx)
print(f"  8. azure_compute_hours negative sentinel   : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.02, used)
bronze_df.loc[idx, "azure_compute_hours"] = np.nan
used = np.union1d(used, idx)
print(f"  9. azure_compute_hours nulls               : {len(idx):>5} rows ({len(idx)/n:.1%})")

idx = dirty_idx(0.04, used)
bronze_df.loc[idx, "support_tickets"] = 99
used = np.union1d(used, idx)
print(f" 10. support_tickets sentinel 99             : {len(idx):>5} rows ({len(idx)/n:.1%})")

# =============================================================================
# SAVE
# =============================================================================
bronze_df.to_csv(OUTFILE, index=False)

print("\n" + "=" * 80)
print("DATASET SAVED")
print("=" * 80)
print(f"File: {OUTFILE}")
print(f"Size: {os.path.getsize(OUTFILE)/1024/1024:.1f} MB")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 80)
print("NULL SUMMARY (AFTER DIRTY INJECTION)")
print("=" * 80)
for col, cnt in bronze_df.isnull().sum().items():
    flag = " ← dirty injected" if cnt > 0 else ""
    print(f"  {col:<28} {cnt:>6}{flag}")

# =============================================================================
# SANITY CHECKS - BUSINESS SIGNALS
# =============================================================================
print("\n" + "=" * 80)
print("ANALYTICAL SANITY CHECKS (CLEAN DATA - PRE DIRTY INJECTION)")
print("=" * 80)

churn_accounts = df.groupby("account_id", as_index=False)["churned"].max()
overall_churn_rate = churn_accounts["churned"].mean()
print(f"\n1. Overall account churn rate: {overall_churn_rate:.1%}  (believable SMB range: 10–25%)")

account_meta = df.groupby("account_id", as_index=False).agg(
    industry=("industry", "first"),
    revenue_tier=("revenue_tier", "first"),
    signup_month=("signup_month", "first"),
    churned=("churned", "max")
)
retail_churn  = account_meta.loc[account_meta["industry"] == "Retail",  "churned"].mean()
finance_churn = account_meta.loc[account_meta["industry"] == "Finance", "churned"].mean()
print(f"\n2. Churn by industry:")
print(f"   Retail  = {retail_churn:.1%}")
print(f"   Finance = {finance_churn:.1%}")
print(f"   Retail > Finance ? {'YES ✓' if retail_churn > finance_churn else 'NO ✗'}")

account_azure = df.groupby("account_id", as_index=False).agg(
    azure_mean=("azure_compute_hours", "mean"),
    churned=("churned", "max")
)
account_azure["azure_flag"] = (account_azure["azure_mean"] > 20).astype(int)
churn_az  = account_azure.loc[account_azure["azure_flag"] == 1, "churned"].mean()
churn_naz = account_azure.loc[account_azure["azure_flag"] == 0, "churned"].mean()
print(f"\n3. Azure protective effect:")
print(f"   Azure-active churn = {churn_az:.1%}")
print(f"   No-Azure churn     = {churn_naz:.1%}")
print(f"   Azure lowers churn ? {'YES ✓' if churn_az < churn_naz else 'NO ✗'}")

month12      = df[df["month"] == 12][["account_id","churned"]]
pre_support  = df[df["month"].isin([10,11])].groupby("account_id", as_index=False)["support_tickets"].mean()
sup_check    = month12.merge(pre_support, on="account_id", how="left")
avg_sup_c    = sup_check.loc[sup_check["churned"] == 1, "support_tickets"].mean()
avg_sup_r    = sup_check.loc[sup_check["churned"] == 0, "support_tickets"].mean()
print(f"\n4. Support tickets months 10–11:")
print(f"   Churned accounts avg  = {avg_sup_c:.2f}")
print(f"   Retained accounts avg = {avg_sup_r:.2f}")
print(f"   Churned > Retained ? {'YES ✓' if avg_sup_c > avg_sup_r else 'NO ✗'}")

temp = df.copy()
temp["aur"] = np.where(temp["m365_licensed_seats"] > 0,
                        temp["m365_active_users"] / temp["m365_licensed_seats"], 0)
aur_trend   = temp[temp["month"].isin([9,10,11,12])].groupby(
    ["account_id","month"], as_index=False)["aur"].mean()
churn_flags = df.groupby("account_id", as_index=False)["churned"].max()
aur_merged  = aur_trend.merge(churn_flags, on="account_id", how="left")
aur9  = aur_merged[(aur_merged["churned"]==1) & (aur_merged["month"]==9)]["aur"].mean()
aur12 = aur_merged[(aur_merged["churned"]==1) & (aur_merged["month"]==12)]["aur"].mean()
print(f"\n5. Active user rate decline (churned accounts):")
print(f"   AUR month 9  = {aur9:.3f}")
print(f"   AUR month 12 = {aur12:.3f}")
print(f"   Decline confirmed ? {'YES ✓' if aur12 < aur9 else 'NO ✗'}")

cohort_counts = account_meta["signup_month"].value_counts().sort_index()
print(f"\n6. Cohort coverage by signup_month:")
for m, cnt in cohort_counts.items():
    print(f"   Month {m:>2}: {cnt:>4} accounts")

print("\n" + "=" * 80)
print("SMB SYNTHETIC DATA GENERATION COMPLETE")
print("=" * 80)
