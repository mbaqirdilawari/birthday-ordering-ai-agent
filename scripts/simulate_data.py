"""Generate ALL the simulated data used in this repository.

Everything created here is fake. It is not real company data, and it exists only to
show how the system works. Product names are generic, distributors are invented,
and all prices, stock levels, sales and accounts are made up.

Usage:
    python scripts/simulate_data.py
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "simulated"
SEED = 2022

# ---------------------------------------------------------------------------
# Part 1: birthday ordering agent
# ---------------------------------------------------------------------------
PRODUCTS = [
    # product_id, name, category, price per piece (PKR, simulated)
    ("P01", "Chocolate Cone", "Cone", 120),
    ("P02", "Strawberry Cone", "Cone", 120),
    ("P03", "Vanilla Cup", "Cup", 70),
    ("P04", "Mango Ice Lolly", "Stick", 50),
    ("P05", "Orange Ice Lolly", "Stick", 50),
    ("P06", "Chocolate Bar", "Stick", 90),
    ("P07", "Kulfi Stick", "Stick", 80),
    ("P08", "Cookies and Cream Cup", "Cup", 110),
    ("P09", "Family Tub Vanilla 1 Liter", "Tub", 650),
    ("P10", "Family Tub Chocolate 1 Liter", "Tub", 650),
]

# bundle_id, name, serves children (up to), contents {product_id: quantity}, bundle price (PKR)
BUNDLES = [
    ("B1", "Mini Party Pack", 10, {"P04": 5, "P05": 5, "P03": 10}, 1_350),
    ("B2", "Classic Party Pack", 20, {"P01": 10, "P06": 10, "P03": 20}, 3_600),
    ("B3", "Mega Party Pack", 35, {"P01": 15, "P02": 10, "P06": 15, "P08": 20, "P09": 2}, 7_800),
    ("B4", "Family Celebration Pack", 15, {"P07": 10, "P08": 10, "P10": 1}, 2_700),
]

# Public neighbourhoods of Karachi with approximate centre coordinates
AREAS = {
    "Clifton": (24.8138, 67.0300),
    "DHA": (24.8000, 67.0650),
    "Saddar": (24.8556, 67.0300),
    "PECHS": (24.8700, 67.0640),
    "Gulshan-e-Iqbal": (24.9200, 67.0950),
    "Gulistan-e-Jauhar": (24.9100, 67.1350),
    "North Nazimabad": (24.9420, 67.0400),
    "Nazimabad": (24.9150, 67.0300),
    "Federal B Area": (24.9300, 67.0750),
    "Malir": (24.8930, 67.2050),
    "Korangi": (24.8350, 67.1300),
    "Bahadurabad": (24.8800, 67.0700),
    "Tariq Road": (24.8720, 67.0570),
    "Garden": (24.8770, 67.0150),
    "Shah Faisal Colony": (24.8780, 67.1550),
    "Scheme 33": (24.9550, 67.1300),
}

# Invented distributors (each runs a small fleet of event-ready trikes)
DISTRIBUTORS = [
    ("D01", "South Distributor", 24.8300, 67.0400, 3),
    ("D02", "Central Distributor", 24.8800, 67.0600, 3),
    ("D03", "East Distributor", 24.9050, 67.1300, 2),
    ("D04", "North Distributor", 24.9400, 67.0550, 2),
    ("D05", "Malir Distributor", 24.8900, 67.1950, 2),
]


def build_agent_data(rng: np.random.Generator) -> None:
    pd.DataFrame(PRODUCTS, columns=["product_id", "name", "category", "unit_price_pkr"]).to_csv(OUT / "products.csv", index=False)

    rows = []
    for bid, name, serves, contents, price in BUNDLES:
        items = "; ".join(f"{q} x {dict((p[0], p[1]) for p in PRODUCTS)[pid]}" for pid, q in contents.items())
        rows.append({"bundle_id": bid, "name": name, "serves_children": serves, "contents": items,
                     "contents_ids": ";".join(f"{pid}:{q}" for pid, q in contents.items()), "price_pkr": price})
    pd.DataFrame(rows).to_csv(OUT / "bundles.csv", index=False)

    pd.DataFrame([{"area": a, "latitude": la, "longitude": lo} for a, (la, lo) in AREAS.items()]).to_csv(OUT / "areas.csv", index=False)

    dist, trikes, stock = [], [], []
    for did, name, lat, lon, n_trikes in DISTRIBUTORS:
        dist.append({"distributor_id": did, "name": name, "latitude": lat, "longitude": lon})
        for k in range(1, n_trikes + 1):
            trikes.append({"trike_id": f"{did}-T{k}", "distributor_id": did})
        for pid, *_ in PRODUCTS:
            stock.append({"distributor_id": did, "product_id": pid, "units_available": int(rng.integers(20, 160))})
    pd.DataFrame(dist).to_csv(OUT / "distributors.csv", index=False)
    pd.DataFrame(trikes).to_csv(OUT / "trikes.csv", index=False)
    pd.DataFrame(stock).to_csv(OUT / "stock.csv", index=False)


# ---------------------------------------------------------------------------
# Part 2: listing quality checker (quick commerce platform)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "Cone": ["Chocolate", "Strawberry", "Vanilla", "Caramel", "Pistachio", "Mint"],
    "Cup": ["Vanilla", "Chocolate", "Mango", "Cookies and Cream", "Butterscotch"],
    "Stick": ["Mango Lolly", "Orange Lolly", "Chocolate Bar", "Kulfi", "Almond Bar", "Berry Lolly"],
    "Tub": ["Vanilla 1 Liter", "Chocolate 1 Liter", "Mango 1 Liter", "Neapolitan 1.5 Liter", "Praline 1 Liter"],
    "Sandwich": ["Vanilla Sandwich", "Chocolate Sandwich"],
}
CITIES = ["Karachi", "Lahore", "Islamabad", "Multan"]


def build_listing_data(rng: np.random.Generator) -> None:
    # Master catalog: the single source of truth for products and prices
    cat = []
    i = 0
    for category, flavours in CATEGORIES.items():
        for f in flavours:
            i += 1
            base = {"Cone": 120, "Cup": 90, "Stick": 60, "Tub": 650, "Sandwich": 100}[category]
            cat.append({
                "sku_id": f"SKU{i:03d}",
                "product_name": f"{f} {category}" if category not in ("Stick", "Tub", "Sandwich") else f,
                "category": category,
                "list_price_pkr": int(base * rng.uniform(0.85, 1.35) // 5 * 5),
                "status": "Discontinued" if rng.random() < 0.15 else "Active",
                "official_image": f"images/sku{i:03d}.png",
            })
    catalog = pd.DataFrame(cat)
    catalog.to_csv(OUT / "master_catalog.csv", index=False)

    # Chain store accounts: a few large chains drive most sales (simulated)
    n_accounts = 240
    sales = np.sort(rng.pareto(1.2, n_accounts) + 1)[::-1] * 400_000
    accounts = pd.DataFrame({
        "account_id": [f"ACC{k:03d}" for k in range(1, n_accounts + 1)],
        "account_name": [f"Chain Store {k:03d}" for k in range(1, n_accounts + 1)],
        "city": rng.choice(CITIES, n_accounts, p=[0.35, 0.35, 0.18, 0.12]),
        "branches": np.clip((sales / 400_000 * rng.uniform(0.5, 1.5, n_accounts)).astype(int), 1, 60),
        "half_year_sales_pkr": sales.round(-3).astype(int),
        "on_platform": rng.random(n_accounts) < 0.5,
    })
    accounts.to_csv(OUT / "chain_accounts.csv", index=False)

    # Platform listings for accounts that are live on the quick commerce platform
    rows = []
    active = catalog[catalog["status"] == "Active"]
    discontinued = catalog[catalog["status"] == "Discontinued"]
    for acc in accounts[accounts["on_platform"]].itertuples():
        care = rng.uniform(0.3, 1.0)  # how carefully this account maintains its listings
        listed = active.sample(frac=rng.uniform(0.55, 1.0), random_state=int(rng.integers(1e9)))
        stale = discontinued.sample(frac=rng.uniform(0, 1 - care), random_state=int(rng.integers(1e9)))
        for r in pd.concat([listed, stale]).itertuples():
            price = r.list_price_pkr
            if rng.random() > care:
                price = int(price * rng.choice([0.8, 0.9, 1.1, 1.25]))
            image = r.official_image
            roll = rng.random()
            if roll > care + 0.15:
                image = "" if rng.random() < 0.5 else "placeholder.png"
            name = r.product_name
            if rng.random() > care + 0.2:
                name = name.upper() if rng.random() < 0.5 else name.replace(" ", "")
            rows.append({
                "account_id": acc.account_id,
                "sku_id": r.sku_id,
                "listed_name": name,
                "listed_price_pkr": price,
                "image": image,
                "visible": bool(rng.random() < 0.6 + 0.4 * care),
            })
    pd.DataFrame(rows).to_csv(OUT / "platform_listings.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)
    rng = np.random.default_rng(SEED)
    build_agent_data(rng)
    build_listing_data(rng)
    print(f"Simulated data written to {OUT}")


if __name__ == "__main__":
    main()
