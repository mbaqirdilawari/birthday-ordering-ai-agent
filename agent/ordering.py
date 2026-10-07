"""The ordering system behind the agent: menu, availability, quotes, bookings.

The AI agent never changes data directly. It can only call the functions in this
file (its "tools"), and every business rule is enforced here, in plain Python:

  * Service area: the event address must be in a known area, within reach of a distributor.
  * Lead time: bookings must be made at least one day before the event.
  * Trikes: one trike per event per time slot. No double booking.
  * Stock: the distributor must have enough of every product. Stock is reserved on booking
    (in the original pilot, stock mismatches were a real problem, so stock is checked live).
  * Upper floor events: flagged so the team brings an insulated carry box
    (a lesson from the pilot: trikes cannot climb stairs).
  * Payment: cash on delivery.

When a booking is made, the order is passed to everyone who needs it, exactly like the
original process: the distributor, the cold chain team, the territory manager, the event
staffing supervisor and the head office project team.

All data is SIMULATED (see data/simulated/).
"""
from __future__ import annotations

import difflib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "simulated"

SLOTS = ["12:00-15:00", "15:00-18:00", "18:00-21:00"]  # every event is up to 3 hours
MAX_DISTANCE_KM = 15.0
MIN_LEAD_DAYS = 1
DELIVERY_FEE_PKR = 0  # trike visit is free: the brand's marketing at the event
STAKEHOLDERS = [
    "Distributor",
    "Cold chain team",
    "Territory manager",
    "Event staffing supervisor",
    "Head office project team",
]


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in kilometers."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


@dataclass
class OrderingSystem:
    """Holds the catalog, fleet, stock and bookings. One instance per running app."""

    today: date = field(default_factory=date.today)
    data_dir: Path = DATA

    def __post_init__(self) -> None:
        d = self.data_dir
        self.products = pd.read_csv(d / "products.csv").set_index("product_id")
        self.bundles = pd.read_csv(d / "bundles.csv").set_index("bundle_id")
        self.areas = pd.read_csv(d / "areas.csv").set_index("area")
        self.distributors = pd.read_csv(d / "distributors.csv").set_index("distributor_id")
        self.trikes = pd.read_csv(d / "trikes.csv")
        stock = pd.read_csv(d / "stock.csv")
        self.stock = {(r.distributor_id, r.product_id): int(r.units_available) for r in stock.itertuples()}
        self.bookings: dict[str, dict] = {}
        self.trike_schedule: dict[tuple[str, str, str], str] = {}  # (trike, date, slot) -> booking
        self.outbox: list[dict] = []
        self._next_id = 1

    # ------------------------------------------------------------------ helpers
    def _bundle_contents(self, bundle_id: str, quantity: int) -> dict[str, int]:
        out: dict[str, int] = {}
        for part in self.bundles.loc[bundle_id, "contents_ids"].split(";"):
            pid, q = part.split(":")
            out[pid] = out.get(pid, 0) + int(q) * quantity
        return out

    def _match_area(self, area: str) -> str | None:
        names = list(self.areas.index)
        lookup = {n.lower(): n for n in names}
        key = area.strip().lower()
        if key in lookup:
            return lookup[key]
        # Partial names ("gulshan") and small typos ("cliftn") are accepted, but a different
        # city that only looks similar ("islamabad" against "nazimabad") is not.
        partial = [n for k, n in lookup.items() if len(key) >= 4 and (k.startswith(key) or key in k.split("-"))]
        if len(partial) == 1:
            return partial[0]
        close = difflib.get_close_matches(key, list(lookup), n=1, cutoff=0.85)
        return lookup[close[0]] if close else None

    def _parse_date(self, value: str) -> date | None:
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None

    def _items_needed(self, bundle_id: str, bundle_quantity: int, extras: list[dict] | None) -> dict[str, int]:
        need = self._bundle_contents(bundle_id, bundle_quantity) if bundle_id else {}
        for e in extras or []:
            need[e["product_id"]] = need.get(e["product_id"], 0) + int(e["quantity"])
        return need

    def _free_trike(self, distributor_id: str, day: str, slot: str) -> str | None:
        for t in self.trikes[self.trikes["distributor_id"] == distributor_id]["trike_id"]:
            if (t, day, slot) not in self.trike_schedule:
                return t
        return None

    def _has_stock(self, distributor_id: str, need: dict[str, int]) -> bool:
        return all(self.stock.get((distributor_id, pid), 0) >= q for pid, q in need.items())

    def _candidates(self, area: str):
        a = self.areas.loc[area]
        dists = [
            (km_between(a.latitude, a.longitude, r.latitude, r.longitude), did)
            for did, r in self.distributors.iterrows()
        ]
        return [(km, did) for km, did in sorted(dists) if km <= MAX_DISTANCE_KM]

    # ------------------------------------------------------------------ tools
    def get_menu(self) -> dict:
        """Party bundles and individual products with prices."""
        return {
            "bundles": [
                {"bundle_id": b, "name": r["name"], "serves_children": int(r.serves_children),
                 "contents": r.contents, "price_pkr": int(r.price_pkr)}
                for b, r in self.bundles.iterrows()
            ],
            "products": [
                {"product_id": p, "name": r["name"], "unit_price_pkr": int(r.unit_price_pkr)}
                for p, r in self.products.iterrows()
            ],
            "time_slots": SLOTS,
            "service_areas": list(self.areas.index),
            "payment": "Cash on delivery",
        }

    def recommend_bundle(self, num_children: int) -> dict:
        """Smallest bundle (or combination) that serves the number of children."""
        n = int(num_children)
        if n <= 0:
            return {"error": "Number of children must be at least 1."}
        b = self.bundles.sort_values("serves_children")
        fits = b[b["serves_children"] >= n]
        if len(fits):
            best = fits.sort_values("price_pkr").iloc[0]
            return {"bundle_id": best.name, "name": best["name"], "quantity": 1,
                    "serves_children": int(best.serves_children), "price_pkr": int(best.price_pkr),
                    "contents": best.contents}
        biggest = b.iloc[-1]
        qty = math.ceil(n / biggest.serves_children)
        return {"bundle_id": biggest.name, "name": biggest["name"], "quantity": qty,
                "serves_children": int(biggest.serves_children) * qty, "price_pkr": int(biggest.price_pkr) * qty,
                "contents": biggest.contents}

    def check_availability(self, area: str, event_date: str, slot: str,
                           bundle_id: str | None = None, bundle_quantity: int = 1) -> dict:
        """Is a trike (and enough stock) free for this area, date and time slot?"""
        matched = self._match_area(area)
        if not matched:
            return {"available": False, "reason": f"We do not serve '{area}' yet.",
                    "service_areas": list(self.areas.index)}
        day = self._parse_date(event_date)
        if not day:
            return {"available": False, "reason": "Please give the date as YYYY-MM-DD."}
        if day < self.today + timedelta(days=MIN_LEAD_DAYS):
            return {"available": False, "reason": f"Bookings need at least {MIN_LEAD_DAYS} day of notice."}
        if slot not in SLOTS:
            return {"available": False, "reason": f"Time slot must be one of {SLOTS}."}
        need = self._items_needed(bundle_id, bundle_quantity, None) if bundle_id else {}
        for km, did in self._candidates(matched):
            trike = self._free_trike(did, day.isoformat(), slot)
            if trike and self._has_stock(did, need):
                return {"available": True, "area": matched, "date": day.isoformat(), "slot": slot,
                        "distributor_id": did, "distributor": self.distributors.loc[did, "name"],
                        "distance_km": round(km, 1)}
        others = [s for s in SLOTS if s != slot and any(
            self._free_trike(did, day.isoformat(), s) for _, did in self._candidates(matched))]
        return {"available": False, "reason": "No trike is free for that slot.", "other_free_slots": others}

    def quote_order(self, bundle_id: str, bundle_quantity: int = 1, extras: list[dict] | None = None) -> dict:
        """Price breakdown for a bundle plus optional extra products."""
        if bundle_id not in self.bundles.index:
            return {"error": f"Unknown bundle '{bundle_id}'."}
        lines = [{"item": self.bundles.loc[bundle_id, "name"], "quantity": int(bundle_quantity),
                  "amount_pkr": int(self.bundles.loc[bundle_id, "price_pkr"]) * int(bundle_quantity)}]
        for e in extras or []:
            if e["product_id"] not in self.products.index:
                return {"error": f"Unknown product '{e['product_id']}'."}
            p = self.products.loc[e["product_id"]]
            lines.append({"item": p["name"], "quantity": int(e["quantity"]),
                          "amount_pkr": int(p.unit_price_pkr) * int(e["quantity"])})
        total = sum(line["amount_pkr"] for line in lines) + DELIVERY_FEE_PKR
        return {"lines": lines, "trike_visit_fee_pkr": DELIVERY_FEE_PKR, "total_pkr": total,
                "payment": "Cash on delivery"}

    def create_booking(self, customer_name: str, phone: str, area: str, address: str, event_date: str,
                       slot: str, bundle_id: str, bundle_quantity: int = 1, floor: int = 0,
                       extras: list[dict] | None = None, decoration_theme: str = "") -> dict:
        """Book the event, reserve a trike and stock, and notify every team involved."""
        digits = "".join(ch for ch in str(phone) if ch.isdigit())
        if len(digits) < 10:
            return {"error": "Please provide a valid phone number."}
        if not customer_name.strip() or not address.strip():
            return {"error": "Customer name and full address are required."}
        quote = self.quote_order(bundle_id, bundle_quantity, extras)
        if "error" in quote:
            return quote
        avail = self.check_availability(area, event_date, slot, bundle_id, bundle_quantity)
        if not avail.get("available"):
            return {"error": avail.get("reason", "Not available."), **{k: v for k, v in avail.items() if k != "available"}}

        did = avail["distributor_id"]
        need = self._items_needed(bundle_id, bundle_quantity, extras)
        if not self._has_stock(did, need):
            return {"error": "Not enough stock at the nearest distributor for these extras. Please reduce extras."}
        trike = self._free_trike(did, avail["date"], slot)
        booking_id = f"BK{self._next_id:04d}"
        self._next_id += 1
        for pid, q in need.items():
            self.stock[(did, pid)] -= q
        self.trike_schedule[(trike, avail["date"], slot)] = booking_id

        booking = {
            "booking_id": booking_id,
            "status": "Confirmed",
            "customer_name": customer_name.strip(),
            "phone": digits,
            "area": avail["area"],
            "address": address.strip(),
            "floor": int(floor),
            "carry_box_needed": int(floor) > 0,
            "date": avail["date"],
            "slot": slot,
            "bundle_id": bundle_id,
            "bundle_quantity": int(bundle_quantity),
            "extras": extras or [],
            "decoration_theme": decoration_theme,
            "distributor_id": did,
            "distributor": avail["distributor"],
            "trike_id": trike,
            "total_pkr": quote["total_pkr"],
            "payment": "Cash on delivery",
            "items": need,
        }
        self.bookings[booking_id] = booking
        self._notify(booking)
        return {k: booking[k] for k in ["booking_id", "status", "date", "slot", "area", "distributor", "trike_id",
                                         "total_pkr", "payment", "carry_box_needed"]}

    def get_booking(self, booking_id: str) -> dict:
        b = self.bookings.get(booking_id.strip().upper())
        if not b:
            return {"error": f"No booking found with id '{booking_id}'."}
        return {k: b[k] for k in ["booking_id", "status", "date", "slot", "area", "bundle_id", "bundle_quantity",
                                   "total_pkr", "trike_id", "payment"]}

    def cancel_booking(self, booking_id: str) -> dict:
        b = self.bookings.get(booking_id.strip().upper())
        if not b:
            return {"error": f"No booking found with id '{booking_id}'."}
        if b["status"] == "Cancelled":
            return {"booking_id": b["booking_id"], "status": "Cancelled"}
        for pid, q in b["items"].items():
            self.stock[(b["distributor_id"], pid)] += q
        self.trike_schedule.pop((b["trike_id"], b["date"], b["slot"]), None)
        b["status"] = "Cancelled"
        for who in STAKEHOLDERS:
            self.outbox.append({"to": who, "booking_id": b["booking_id"], "message": f"Booking {b['booking_id']} cancelled."})
        return {"booking_id": b["booking_id"], "status": "Cancelled"}

    # ------------------------------------------------------------------ order routing
    def _notify(self, b: dict) -> None:
        """Pass the order to every team, the same routing the original process used."""
        bundle = self.bundles.loc[b["bundle_id"], "name"]
        summary = f"{b['booking_id']}: {b['bundle_quantity']} x {bundle}, {b['date']} {b['slot']}, {b['area']}"
        items = ", ".join(f"{q} x {self.products.loc[pid, 'name']}" for pid, q in b["items"].items())
        floor = "ground floor" if b["floor"] == 0 else f"floor {b['floor']}"
        messages = {
            "Distributor": f"New birthday event {summary}. Assign trike {b['trike_id']} and load stock.",
            "Cold chain team": f"Plan cold chain for {summary}. Items: {items}.",
            "Territory manager": f"Event booked in your territory: {summary}.",
            "Event staffing supervisor": (
                f"Staff event {summary}. Address: {b['address']}, {floor}. "
                f"Uniform check and trike decoration: {b['decoration_theme'] or 'standard'}."
                + (" Bring an insulated carry box (upper floor)." if b["carry_box_needed"] else "")
            ),
            "Head office project team": f"Booking logged {summary}. Total PKR {b['total_pkr']:,} cash on delivery.",
        }
        for who in STAKEHOLDERS:
            self.outbox.append({"to": who, "booking_id": b["booking_id"], "message": messages[who]})
        self.outbox.append({"to": "Customer", "booking_id": b["booking_id"],
                            "message": f"Confirmed {summary}. Pay PKR {b['total_pkr']:,} in cash on the day."})

    # ------------------------------------------------------------------ tool dispatch
    def run_tool(self, name: str, args: dict) -> dict:
        tools = {
            "get_menu": self.get_menu,
            "recommend_bundle": self.recommend_bundle,
            "check_availability": self.check_availability,
            "quote_order": self.quote_order,
            "create_booking": self.create_booking,
            "get_booking": self.get_booking,
            "cancel_booking": self.cancel_booking,
        }
        if name not in tools:
            return {"error": f"Unknown tool '{name}'."}
        try:
            return tools[name](**(args or {}))
        except TypeError as e:
            return {"error": f"Bad arguments for {name}: {e}"}


# JSON schemas the AI model sees. The model can ONLY act through these.
TOOL_SCHEMAS = [
    {
        "name": "get_menu",
        "description": "List party bundles, individual products, prices, time slots, service areas and payment method.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "recommend_bundle",
        "description": "Recommend the best party bundle for a number of children.",
        "input_schema": {
            "type": "object",
            "properties": {"num_children": {"type": "integer", "description": "Number of children at the party"}},
            "required": ["num_children"],
        },
    },
    {
        "name": "check_availability",
        "description": "Check whether an ice cream trike and stock are available for an area, date and 3 hour time slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {"type": "string", "description": "Neighbourhood of the event, for example Clifton"},
                "event_date": {"type": "string", "description": "Date as YYYY-MM-DD"},
                "slot": {"type": "string", "enum": SLOTS},
                "bundle_id": {"type": "string", "description": "Optional bundle to check stock for"},
                "bundle_quantity": {"type": "integer"},
            },
            "required": ["area", "event_date", "slot"],
        },
    },
    {
        "name": "quote_order",
        "description": "Price breakdown for a bundle and optional extra products.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bundle_id": {"type": "string"},
                "bundle_quantity": {"type": "integer"},
                "extras": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"product_id": {"type": "string"}, "quantity": {"type": "integer"}},
                              "required": ["product_id", "quantity"]},
                },
            },
            "required": ["bundle_id"],
        },
    },
    {
        "name": "create_booking",
        "description": "Create a confirmed booking. Only call after the customer has confirmed the summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "phone": {"type": "string"},
                "area": {"type": "string"},
                "address": {"type": "string", "description": "Full street address"},
                "floor": {"type": "integer", "description": "0 for ground floor"},
                "event_date": {"type": "string", "description": "YYYY-MM-DD"},
                "slot": {"type": "string", "enum": SLOTS},
                "bundle_id": {"type": "string"},
                "bundle_quantity": {"type": "integer"},
                "extras": {"type": "array", "items": {"type": "object", "properties": {
                    "product_id": {"type": "string"}, "quantity": {"type": "integer"}}, "required": ["product_id", "quantity"]}},
                "decoration_theme": {"type": "string"},
            },
            "required": ["customer_name", "phone", "area", "address", "event_date", "slot", "bundle_id"],
        },
    },
    {
        "name": "get_booking",
        "description": "Look up a booking by its id (for example BK0001).",
        "input_schema": {"type": "object", "properties": {"booking_id": {"type": "string"}}, "required": ["booking_id"]},
    },
    {
        "name": "cancel_booking",
        "description": "Cancel a booking by its id, releasing the trike and stock.",
        "input_schema": {"type": "object", "properties": {"booking_id": {"type": "string"}}, "required": ["booking_id"]},
    },
]
