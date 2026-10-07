"""Demo mode: a rule based agent that runs with no API key.

It uses exactly the same tools as the Claude agent (agent/ordering.py), so anyone can
try the full booking flow for free. Instead of an AI model deciding what to do,
simple rules read the message, fill in the booking details it finds, call the tools,
and ask for the next missing detail.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .ordering import SLOTS, OrderingSystem

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def parse_date(text: str, today: date) -> str | None:
    t = text.lower()
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", t)
    if m:
        return m.group(0)
    if "day after tomorrow" in t:
        return (today + timedelta(days=2)).isoformat()
    if "tomorrow" in t:
        return (today + timedelta(days=1)).isoformat()
    for i, wd in enumerate(WEEKDAYS):
        if re.search(rf"\b{wd}\b", t):
            ahead = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=ahead)).isoformat()
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\b", t) or re.search(
        r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m:
        a, b = m.groups()
        day, month = (int(a), b) if a.isdigit() else (int(b), a)
        year = today.year
        try:
            d = date(year, MONTHS.index(month) + 1, day)
        except ValueError:
            return None
        if d < today:
            d = date(year + 1, d.month, d.day)
        return d.isoformat()
    return None


def parse_slot(text: str) -> str | None:
    """Read a time slot only from clear time words, so house or block numbers are never mistaken for a time."""
    t = text.lower()
    if re.search(r"\b(noon|lunch|midday|12\s*(pm|to 3|-\s*3)|12:00)\b", t):
        return SLOTS[0]
    if re.search(r"\b(afternoon|3\s*(pm|to 6|-\s*6)|15:00)\b", t):
        return SLOTS[1]
    if re.search(r"\b(evening|night|6\s*(pm|to 9|-\s*9)|18:00)\b", t):
        return SLOTS[2]
    return None


class DemoAgent:
    """Rule based conversation that fills in a booking step by step."""

    mode = "Demo (no API key)"

    def __init__(self, system: OrderingSystem):
        self.system = system
        self.d: dict = {"floor": None}
        self.awaiting_confirmation = False
        self.activity: list[dict] = []

    def _tool(self, name: str, **args) -> dict:
        out = self.system.run_tool(name, args)
        self.activity.append({"tool": name, "input": args, "output": out})
        return out

    def _extract(self, text: str) -> None:
        t = text.lower()
        d = self.d
        m = re.search(r"(\d+)\s*(kids|children|guests|child|people)", t)
        if m:
            d["children"] = int(m.group(1))
        when = parse_date(text, self.system.today)
        if when:
            d["date"] = when
        cleaned = re.sub(r"\d+\s*(kids|children|guests|child|people)", "", t)
        cleaned = re.sub(r"\b20\d\d-\d\d-\d\d\b", "", cleaned)
        cleaned = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\b", "", cleaned)
        cleaned = re.sub(r"\b(" + "|".join(MONTHS) + r")\s+\d{1,2}(?:st|nd|rd|th)?\b", "", cleaned)
        cleaned = re.sub(r"\+?\d[\d\- ]{9,15}\d", "", cleaned)
        cleaned = re.sub(r"\d+(?:st|nd|rd|th)?\s+floor", "", cleaned)
        slot = parse_slot(cleaned)
        if slot and slot != d.get("slot"):
            d["slot"] = slot
            d.pop("available", None)  # a new slot must be checked again
        if when and when != d.get("date"):
            d.pop("available", None)
        for area in self.system.areas.index:
            if area.lower() in t:
                d["area"] = area
        m = re.search(r"(?:my name is|i am|i[\u2019\x27]m|this is|name:)\s+([a-z][a-z ]{1,40}?)(?:[,.]|$| and)", t)
        if m:
            d["name"] = m.group(1).strip().title()
        phone = re.search(r"(\+?\d[\d\- ]{9,15}\d)", text)
        if phone and len(re.sub(r"\D", "", phone.group(1))) >= 10:
            d["phone"] = re.sub(r"\D", "", phone.group(1))
        m = re.search(r"address(?: is)?:?\s+(.+?)(?:\.\s|$)", text, re.I)
        if m:
            d["address"] = m.group(1).strip()
        elif re.search(r"\b(house|street|block|flat|apartment|road)\b", t) and "address" not in d:
            d["address"] = text.strip()
        if "ground floor" in t:
            d["floor"] = 0
        m = re.search(r"(\d+)(?:st|nd|rd|th)?\s+floor", t)
        if m:
            d["floor"] = int(m.group(1))
        m = re.search(r"theme(?: is)?:?\s+([a-z0-9 ]{2,40})", t)
        if m:
            d["theme"] = m.group(1).strip().title()

    def reply(self, text: str) -> tuple[str, list[dict]]:
        self.activity = []
        t = text.lower().strip()

        m = re.search(r"\bbk\d{4}\b", t)
        if m and "cancel" in t:
            out = self._tool("cancel_booking", booking_id=m.group(0).upper())
            return (out.get("error") or f"Booking {out['booking_id']} is now cancelled."), self.activity
        if m:
            out = self._tool("get_booking", booking_id=m.group(0).upper())
            if "error" in out:
                return out["error"], self.activity
            return (f"Booking {out['booking_id']} is {out['status']}: {out['date']}, {out['slot']}, "
                    f"{out['area']}. Total PKR {out['total_pkr']:,}, cash on delivery."), self.activity

        if "menu" in t or "price" in t and "bundle" not in self.d:
            menu = self._tool("get_menu")
            lines = [f"- {b['name']} (up to {b['serves_children']} children): PKR {b['price_pkr']:,}" for b in menu["bundles"]]
            return "Here are our party bundles:\n" + "\n".join(lines) + "\nHow many children are coming?", self.activity

        if self.awaiting_confirmation:
            if re.search(r"\b(yes|confirm|ok|okay|sure|go ahead|book it)\b", t):
                return self._book(), self.activity
            if re.search(r"\b(no|change|wait)\b", t):
                self.awaiting_confirmation = False
                return "No problem. Tell me what you would like to change.", self.activity

        self._extract(text)
        return self._next_step(), self.activity

    def _next_step(self) -> str:
        d = self.d
        if "children" not in d:
            return ("Hello! I can book an ice cream trike for your birthday party. "
                    "How many children are coming, and on which date?")
        if "bundle" not in d:
            rec = self._tool("recommend_bundle", num_children=d["children"])
            d["bundle"], d["qty"] = rec["bundle_id"], rec["quantity"]
            qty = f"{rec['quantity']} x " if rec["quantity"] > 1 else ""
            intro = (f"For {d['children']} children I suggest {qty}{rec['name']} ({rec['contents']}), "
                     f"PKR {rec['price_pkr']:,}. ")
            if "date" not in d:
                return intro + "Which date is the party?"
            if "slot" not in d or "area" not in d:
                return intro + "Which time slot (12 to 3, 3 to 6, or 6 to 9) and which area of Karachi?"
        if "date" not in d:
            return "Which date is the party?"
        if "slot" not in d or "area" not in d:
            missing = [x for x, k in [("time slot (12 to 3, 3 to 6, or 6 to 9)", "slot"), ("area of Karachi", "area")] if k not in d]
            return "Which " + " and which ".join(missing) + "?"
        if not d.get("available"):
            out = self._tool("check_availability", area=d["area"], event_date=d["date"], slot=d["slot"],
                             bundle_id=d["bundle"], bundle_quantity=d["qty"])
            if not out.get("available"):
                if out.get("other_free_slots"):
                    d.pop("slot")
                    return f"Sorry, {out['reason']} Free slots that day: {', '.join(out['other_free_slots'])}."
                if "serve" in out.get("reason", ""):
                    d.pop("area")
                    return f"Sorry, {out['reason']} We currently serve: {', '.join(out['service_areas'])}."
                d.pop("date", None)
                d.pop("slot", None)
                return f"Sorry, {out['reason']} Could you choose another date?"
            d["available"] = True
            prefix = f"Good news: a trike is free on {d['date']}, {d['slot']} in {d['area']}. "
        else:
            prefix = ""
        missing = [label for key, label in [("name", "your name"), ("phone", "a phone number"),
                                            ("address", "the full address")] if key not in d]
        if missing:
            listed = missing[0] if len(missing) == 1 else ", ".join(missing[:-1]) + " and " + missing[-1]
            return prefix + "To book it, please share " + listed + "."
        if d.get("floor") is None:
            return prefix + "Is the party on the ground floor, or which floor?"
        quote = self._tool("quote_order", bundle_id=d["bundle"], bundle_quantity=d["qty"])
        self.awaiting_confirmation = True
        theme = f", theme: {d['theme']}" if d.get("theme") else ""
        floor = "ground floor" if d["floor"] == 0 else f"floor {d['floor']}"
        return (prefix + f"Please confirm: {d['qty']} x {self.system.bundles.loc[d['bundle'], 'name']} on {d['date']}, "
                f"{d['slot']}, at {d['address']} ({d['area']}, {floor}{theme}) for {d['name']}, {d['phone']}. "
                f"Total PKR {quote['total_pkr']:,}, cash on delivery. Shall I book it?")

    def _book(self) -> str:
        d = self.d
        out = self._tool("create_booking", customer_name=d["name"], phone=d["phone"], area=d["area"],
                         address=d["address"], event_date=d["date"], slot=d["slot"], bundle_id=d["bundle"],
                         bundle_quantity=d["qty"], floor=d["floor"], decoration_theme=d.get("theme", ""))
        self.awaiting_confirmation = False
        if "error" in out:
            d.pop("available", None)
            return f"Sorry, I could not book it: {out['error']}"
        self.d = {"floor": None}
        extra = " Our team will bring an insulated carry box for the upper floor." if out["carry_box_needed"] else ""
        return (f"Booked! Your booking id is {out['booking_id']}. The trike arrives on {out['date']} at the start of "
                f"{out['slot']}. Please pay PKR {out['total_pkr']:,} in cash on the day.{extra}")


def make_agent(system: OrderingSystem):
    """Use Claude when an API key is set, otherwise demo mode."""
    import os

    if os.environ.get("ANTHROPIC_API_KEY"):
        from .llm_agent import ClaudeAgent

        return ClaudeAgent(system)
    return DemoAgent(system)


def _today() -> date:
    return datetime.now().date()
