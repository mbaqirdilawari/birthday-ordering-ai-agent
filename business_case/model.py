"""Business case for the birthday trike service: when do the launch costs pay back?

Two ways to measure payback, step by step:
  1. Revenue basis (the quick method used in the original pitch):
       orders needed = launch costs / average order value
     It answers "how many orders bring in as much money as we spent?".
  2. Margin basis (stricter, used here as the main answer):
       each order only contributes its gross margin, and running costs
       (event supervision) continue every month.
     Payback month = the first month where cumulative margin covers
     launch costs plus all running costs so far.

Also: how much more a trike seller earns on a day with a birthday event.

All numbers are SIMULATED assumptions. Change them in ASSUMPTIONS.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"

ASSUMPTIONS = {
    # One time launch costs (PKR)
    "cost_social_media_and_influencers": 900_000,
    "cost_posters_and_flyers": 150_000,
    "cost_trial_events": 10_000,
    # Running cost (PKR per month)
    "monthly_event_supervision": 40_000,
    # Orders and value
    "avg_order_value": 2_600,
    "gross_margin": 0.45,
    "orders_month_1": 15,
    "orders_month_2": 35,
    "orders_per_month_after": 80,
    # Trike seller earnings (PKR per day)
    "seller_earnings_normal_day": 900,
    "seller_earnings_event_day": 1_700,
    # Months to model
    "months": 36,
}


def launch_cost(a: dict = ASSUMPTIONS) -> int:
    return a["cost_social_media_and_influencers"] + a["cost_posters_and_flyers"] + a["cost_trial_events"]


def monthly_table(a: dict = ASSUMPTIONS) -> pd.DataFrame:
    m = np.arange(1, a["months"] + 1)
    orders = np.where(m == 1, a["orders_month_1"], np.where(m == 2, a["orders_month_2"], a["orders_per_month_after"]))
    df = pd.DataFrame({"month": m, "orders": orders})
    df["revenue"] = df["orders"] * a["avg_order_value"]
    df["gross_margin"] = df["revenue"] * a["gross_margin"]
    df["cumulative_revenue"] = df["revenue"].cumsum()
    df["cumulative_margin"] = df["gross_margin"].cumsum()
    df["cumulative_cost"] = launch_cost(a) + a["monthly_event_supervision"] * df["month"]
    df["net_position"] = df["cumulative_margin"] - df["cumulative_cost"]
    return df


def payback_month(a: dict = ASSUMPTIONS) -> int | None:
    """First month where cumulative margin covers all costs so far (month by month)."""
    df = monthly_table({**a, "months": 5000})
    hit = df[df["net_position"] >= 0]
    return int(hit["month"].iloc[0]) if len(hit) else None


def payback_month_formula(a: dict = ASSUMPTIONS) -> int | None:
    """Same answer as payback_month, solved with a formula (this is what the Excel model uses)."""
    m1 = a["orders_month_1"] * a["avg_order_value"] * a["gross_margin"]
    m2 = a["orders_month_2"] * a["avg_order_value"] * a["gross_margin"]
    s = a["orders_per_month_after"] * a["avg_order_value"] * a["gross_margin"]
    c, f = launch_cost(a), a["monthly_event_supervision"]
    if m1 >= c + f:
        return 1
    if m1 + m2 >= c + 2 * f:
        return 2
    if s <= f:
        return None
    # From month 3: m1 + m2 + (m - 2) * s >= c + f * m
    return max(3, math.ceil((c - m1 - m2 + 2 * s) / (s - f) - 1e-9))


def revenue_basis_orders(a: dict = ASSUMPTIONS) -> int:
    """Orders needed for revenue to equal launch costs (the quick pitch method)."""
    return math.ceil(launch_cost(a) / a["avg_order_value"])


def sensitivity(a: dict = ASSUMPTIONS, orders=(50, 60, 70, 80, 90, 100, 120), values=(2_000, 2_300, 2_600, 2_900, 3_200)) -> pd.DataFrame:
    """Payback month for different steady order levels and average order values."""
    grid = {v: [payback_month_formula({**a, "orders_per_month_after": o, "avg_order_value": v}) for o in orders] for v in values}
    out = pd.DataFrame(grid, index=list(orders))
    out.index.name = "orders_per_month"
    out.columns.name = "avg_order_value_pkr"
    return out


def seller_uplift(a: dict = ASSUMPTIONS) -> dict:
    normal, event = a["seller_earnings_normal_day"], a["seller_earnings_event_day"]
    return {"normal_day": normal, "event_day": event, "increase_pkr": event - normal, "increase_pct": event / normal - 1}


def run(save: bool = True) -> dict:
    table = monthly_table()
    result = {
        "launch_cost": launch_cost(),
        "revenue_basis_orders": revenue_basis_orders(),
        "payback_month_margin_basis": payback_month(),
        "sensitivity": sensitivity(),
        "table": table,
        "seller": seller_uplift(),
    }
    if save:
        TABLES.mkdir(parents=True, exist_ok=True)
        table.to_csv(TABLES / "business_case_monthly.csv", index=False)
        result["sensitivity"].to_csv(TABLES / "business_case_sensitivity.csv")
    return result


if __name__ == "__main__":
    r = run()
    print(f"Launch cost: PKR {r['launch_cost']:,}")
    print(f"Orders to recover launch cost (revenue basis): {r['revenue_basis_orders']}")
    print(f"Payback month (margin basis, incl. running costs): {r['payback_month_margin_basis']}")
    s = r["seller"]
    print(f"Seller earnings: PKR {s['normal_day']:,} normal day, PKR {s['event_day']:,} event day (+{s['increase_pct']:.0%})")
    print(r["sensitivity"])
