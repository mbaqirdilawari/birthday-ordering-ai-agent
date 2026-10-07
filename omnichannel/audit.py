"""Listing quality checker for chain stores on a quick commerce platform.

The business problem: chain store accounts sell the brand's ice cream on a quick
commerce (online delivery) platform, but their online listings were in poor shape:
missing or placeholder photos, wrong prices, discontinued products still showing,
active products missing or hidden. Customers cannot buy what they cannot see.

What this tool does, step by step:
  1. Compares every listing with the master catalog (the single source of truth).
  2. Flags each problem with a plain language fix.
  3. Scores each account's "listing health".
  4. Ranks accounts by sales, so the accounts that matter most are fixed first.
  5. Ranks accounts that are not yet on the platform, to plan who to onboard next.
  6. Shows listing health before and after fixing the priority accounts.

All data is SIMULATED (data/simulated/).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "simulated"
TABLES = ROOT / "outputs" / "tables"

PRICE_TOLERANCE = 0.02      # a price more than 2 percent away from the master price is wrong
PRIORITY_SALES_SHARE = 0.80  # fix first the accounts that make up 80 percent of platform sales

ISSUE_FIX = {
    "Discontinued product still listed": "Remove the listing",
    "Price does not match master price": "Update the price to the master price",
    "Missing product photo": "Upload the official product photo",
    "Placeholder product photo": "Replace with the official product photo",
    "Product hidden from customers": "Make the listing visible",
    "Product name does not match": "Use the official product name",
    "Active product not listed": "Add the product to the store",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def load():
    catalog = pd.read_csv(DATA / "master_catalog.csv")
    accounts = pd.read_csv(DATA / "chain_accounts.csv")
    listings = pd.read_csv(DATA / "platform_listings.csv", keep_default_na=False)
    listings["visible"] = listings["visible"].astype(str).str.lower().eq("true")
    listings["listed_price_pkr"] = pd.to_numeric(listings["listed_price_pkr"])
    return catalog, accounts, listings


def audit(catalog: pd.DataFrame, accounts: pd.DataFrame, listings: pd.DataFrame) -> pd.DataFrame:
    """Return one row per problem found, with the fix to apply."""
    merged = listings.merge(catalog, on="sku_id", how="left")
    issues = []

    def add(mask, issue, detail):
        part = merged.loc[mask, ["account_id", "sku_id", "product_name"]].copy()
        part["issue"] = issue
        part["detail"] = detail(merged.loc[mask]) if callable(detail) else detail
        issues.append(part)

    disc = merged["status"] == "Discontinued"
    active = ~disc
    add(disc, "Discontinued product still listed", "No longer sold")
    price_gap = (merged["listed_price_pkr"] - merged["list_price_pkr"]) / merged["list_price_pkr"]
    add(active & (price_gap.abs() > PRICE_TOLERANCE), "Price does not match master price",
        lambda d: "Listed PKR " + d["listed_price_pkr"].astype(int).astype(str) + ", should be PKR " + d["list_price_pkr"].astype(int).astype(str))
    add(active & (merged["image"].str.strip() == ""), "Missing product photo", "No photo")
    add(active & (merged["image"] == "placeholder.png"), "Placeholder product photo", "Generic image shown")
    add(active & ~merged["visible"], "Product hidden from customers", "Listing is switched off")
    add(active & (merged["listed_name"] != merged["product_name"]), "Product name does not match",
        lambda d: "Listed as '" + d["listed_name"] + "'")

    # Active products the account does not list at all
    live = accounts.loc[accounts["on_platform"], "account_id"]
    active_skus = catalog.loc[catalog["status"] == "Active", ["sku_id", "product_name"]]
    expected = pd.MultiIndex.from_product([live, active_skus["sku_id"]], names=["account_id", "sku_id"]).to_frame(index=False)
    have = listings[["account_id", "sku_id"]].drop_duplicates()
    missing = expected.merge(have, how="left", indicator=True).query("_merge == 'left_only'").drop(columns="_merge")
    missing = missing.merge(active_skus, on="sku_id")
    missing["issue"] = "Active product not listed"
    missing["detail"] = "Not available to customers"
    issues.append(missing)

    out = pd.concat(issues, ignore_index=True)
    out["fix"] = out["issue"].map(ISSUE_FIX)
    return out.sort_values(["account_id", "issue", "sku_id"]).reset_index(drop=True)


def scorecard(catalog: pd.DataFrame, accounts: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    """Listing health per live account: share of active products that are listed correctly."""
    n_active = int((catalog["status"] == "Active").sum())
    live = accounts[accounts["on_platform"]].copy()
    active_issue_types = [k for k in ISSUE_FIX if k != "Discontinued product still listed"]
    bad_active = (issues[issues["issue"].isin(active_issue_types)]
                  .groupby("account_id")["sku_id"].nunique())
    by_type = issues.pivot_table(index="account_id", columns="issue", values="sku_id", aggfunc="count", fill_value=0)
    live["active_products_correct"] = n_active - live["account_id"].map(bad_active).fillna(0).astype(int)
    live["listing_health"] = live["active_products_correct"] / n_active
    live["total_issues"] = live["account_id"].map(issues.groupby("account_id").size()).fillna(0).astype(int)
    live = live.merge(by_type, left_on="account_id", right_index=True, how="left").fillna(0)

    live = live.sort_values("half_year_sales_pkr", ascending=False)
    live["cumulative_sales_share"] = live["half_year_sales_pkr"].cumsum() / live["half_year_sales_pkr"].sum()
    live["priority"] = np.where(live["cumulative_sales_share"].shift(fill_value=0) < PRIORITY_SALES_SHARE,
                                "Fix first", "Fix later")
    return live.reset_index(drop=True)


def onboarding_pipeline(accounts: pd.DataFrame) -> pd.DataFrame:
    """Accounts not yet on the platform, biggest first."""
    off = accounts[~accounts["on_platform"]].sort_values("half_year_sales_pkr", ascending=False).copy()
    off["onboarding_rank"] = np.arange(1, len(off) + 1)
    return off.reset_index(drop=True)


def after_fixes(card: pd.DataFrame) -> pd.DataFrame:
    """Listing health once every issue in the priority accounts is fixed."""
    out = card.copy()
    out["listing_health_after"] = np.where(out["priority"] == "Fix first", 1.0, out["listing_health"])
    return out


def sales_weighted_health(card: pd.DataFrame, column: str) -> float:
    return float((card[column] * card["half_year_sales_pkr"]).sum() / card["half_year_sales_pkr"].sum())


def run(save: bool = True) -> dict:
    catalog, accounts, listings = load()
    issues = audit(catalog, accounts, listings)
    card = after_fixes(scorecard(catalog, accounts, issues))
    pipeline = onboarding_pipeline(accounts)
    summary = {
        "accounts_on_platform": int(accounts["on_platform"].sum()),
        "accounts_not_on_platform": int((~accounts["on_platform"]).sum()),
        "listings_checked": int(len(listings)),
        "issues_found": int(len(issues)),
        "priority_accounts": int((card["priority"] == "Fix first").sum()),
        "priority_share_of_sales": float(card.loc[card["priority"] == "Fix first", "half_year_sales_pkr"].sum()
                                         / card["half_year_sales_pkr"].sum()),
        "health_before_sales_weighted": sales_weighted_health(card, "listing_health"),
        "health_after_sales_weighted": sales_weighted_health(card, "listing_health_after"),
    }
    if save:
        TABLES.mkdir(parents=True, exist_ok=True)
        issues.to_csv(TABLES / "listing_issue_log.csv", index=False)
        card.to_csv(TABLES / "account_scorecard.csv", index=False)
        pipeline.to_csv(TABLES / "onboarding_priority.csv", index=False)
        pd.Series(summary).to_csv(TABLES / "listing_audit_summary.csv", header=["value"])
    return {"issues": issues, "scorecard": card, "pipeline": pipeline, "summary": summary, "catalog": catalog}


if __name__ == "__main__":
    s = run()["summary"]
    for k, v in s.items():
        print(f"{k:35s} {v:,.2f}" if isinstance(v, float) else f"{k:35s} {v:,}")
