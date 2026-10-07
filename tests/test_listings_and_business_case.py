"""Tests for the listing quality checker and the business case model."""
import itertools
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from business_case import model as bc  # noqa: E402
from omnichannel import audit  # noqa: E402

CATALOG = pd.DataFrame({
    "sku_id": ["S1", "S2", "S3"],
    "product_name": ["Chocolate Cone", "Vanilla Cup", "Old Lolly"],
    "category": ["Cone", "Cup", "Stick"],
    "list_price_pkr": [100, 80, 50],
    "status": ["Active", "Active", "Discontinued"],
    "official_image": ["a.png", "b.png", "c.png"],
})
ACCOUNTS = pd.DataFrame({"account_id": ["A1", "A2"], "account_name": ["One", "Two"], "city": ["Karachi", "Lahore"],
                         "branches": [5, 2], "half_year_sales_pkr": [900, 100], "on_platform": [True, True]})


def listing(**kw):
    row = {"account_id": "A1", "sku_id": "S1", "listed_name": "Chocolate Cone", "listed_price_pkr": 100,
           "image": "a.png", "visible": True}
    row.update(kw)
    return row


def test_every_rule_is_detected():
    listings = pd.DataFrame([
        listing(listed_price_pkr=120, image="", listed_name="CHOCOLATE CONE", visible=False),
        listing(sku_id="S3", listed_name="Old Lolly", listed_price_pkr=50, image="c.png"),
        listing(account_id="A2", sku_id="S1"),
        listing(account_id="A2", sku_id="S2", listed_name="Vanilla Cup", listed_price_pkr=80, image="placeholder.png"),
    ])
    issues = audit.audit(CATALOG, ACCOUNTS, listings)
    a1 = set(issues.loc[issues["account_id"] == "A1", "issue"])
    assert a1 == {"Price does not match master price", "Missing product photo", "Product name does not match",
                  "Product hidden from customers", "Discontinued product still listed", "Active product not listed"}
    a2 = set(issues.loc[issues["account_id"] == "A2", "issue"])
    assert a2 == {"Placeholder product photo"}
    assert issues["fix"].notna().all()


def test_small_price_differences_are_tolerated():
    issues = audit.audit(CATALOG, ACCOUNTS.iloc[:1], pd.DataFrame([listing(listed_price_pkr=101), listing(sku_id="S2", listed_name="Vanilla Cup", listed_price_pkr=80, image="b.png")]))
    assert issues.empty


def test_priority_accounts_cover_80_percent_of_sales():
    card = audit.run(save=False)["scorecard"]
    first = card[card["priority"] == "Fix first"]
    share = first["half_year_sales_pkr"].sum() / card["half_year_sales_pkr"].sum()
    assert share >= audit.PRIORITY_SALES_SHARE
    # Dropping the smallest priority account would fall below 80 percent
    assert (share - first["half_year_sales_pkr"].iloc[-1] / card["half_year_sales_pkr"].sum()) < audit.PRIORITY_SALES_SHARE
    assert card["listing_health"].between(0, 1).all()


def test_payback_formula_equals_month_by_month():
    for o, v, g, f in itertools.product([5, 20, 50, 80, 120], [1500, 2600, 4000], [0.2, 0.45, 0.6], [0, 40000, 100000]):
        a = {**bc.ASSUMPTIONS, "orders_per_month_after": o, "avg_order_value": v, "gross_margin": g,
             "monthly_event_supervision": f}
        assert bc.payback_month(a) == bc.payback_month_formula(a), (o, v, g, f)


def test_revenue_basis_and_seller_uplift():
    a = bc.ASSUMPTIONS
    assert bc.revenue_basis_orders() * a["avg_order_value"] >= bc.launch_cost()
    assert (bc.revenue_basis_orders() - 1) * a["avg_order_value"] < bc.launch_cost()
    assert bc.seller_uplift()["increase_pkr"] == a["seller_earnings_event_day"] - a["seller_earnings_normal_day"]


def test_excel_business_case_matches_python():
    book = Path(__file__).resolve().parents[1] / "excel" / "Birthday_Trike_Business_Case.xlsx"
    summary = pd.read_excel(book, sheet_name="Summary", header=None)
    if summary.iloc[3:, 1].isna().all():
        pytest.skip("Workbook has no calculated values yet. Open and save it in Excel or LibreOffice first.")
    values = dict(zip(summary[0], summary[1]))
    assert values["PAYBACK MONTH (margin basis, including running costs)"] == bc.payback_month()
    grid = pd.read_excel(book, sheet_name="Sensitivity", header=3, index_col=0)
    assert (grid.values == bc.sensitivity().values).all()
