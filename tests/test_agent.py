"""Tests for the ordering system, the demo agent and the Claude agent loop."""
import copy
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.demo_agent import DemoAgent  # noqa: E402
from agent.llm_agent import ClaudeAgent  # noqa: E402
from agent.ordering import SLOTS, STAKEHOLDERS, OrderingSystem  # noqa: E402

TODAY = date(2026, 10, 7)


@pytest.fixture
def system():
    return OrderingSystem(today=TODAY)


def book(system, **overrides):
    args = dict(customer_name="Test Customer", phone="03001234567", area="Clifton", address="House 1, Street 2",
                event_date="2026-10-17", slot=SLOTS[2], bundle_id="B2")
    args.update(overrides)
    return system.create_booking(**args)


def test_recommend_bundle_fits_the_party(system):
    assert system.recommend_bundle(8)["bundle_id"] == "B1"
    assert system.recommend_bundle(18)["serves_children"] >= 18
    big = system.recommend_bundle(80)
    assert big["serves_children"] >= 80 and big["quantity"] > 1


def test_booking_rules(system):
    assert not system.check_availability("Clifton", "2026-10-07", SLOTS[0])["available"]  # same day: too late
    assert not system.check_availability("Islamabad", "2026-10-17", SLOTS[0])["available"]  # outside service area
    assert not system.check_availability("Clifton", "2026-10-17", "09:00-12:00")["available"]  # not a slot
    ok = system.check_availability("clifton", "2026-10-17", SLOTS[0])  # area names are matched case insensitively
    assert ok["available"] and ok["area"] == "Clifton"
    assert system.check_availability("gulshan", "2026-10-17", SLOTS[0])["area"] == "Gulshan-e-Iqbal"
    assert system.check_availability("Cliftn", "2026-10-17", SLOTS[0])["area"] == "Clifton"


def test_no_double_booking_when_trikes_run_out(system):
    results = [book(system) for _ in range(12)]
    confirmed = [r for r in results if "booking_id" in r]
    trikes = {r["trike_id"] for r in confirmed}
    assert len(trikes) == len(confirmed)  # every confirmed event got its own trike
    assert any("error" in r for r in results)  # eventually no trike is free nearby


def test_stock_is_reserved_and_released(system):
    before = dict(system.stock)
    out = book(system)
    did = out and system.bookings[out["booking_id"]]["distributor_id"]
    assert system.stock[(did, "P03")] == before[(did, "P03")] - 20
    system.cancel_booking(out["booking_id"])
    assert system.stock == before
    assert system.get_booking(out["booking_id"])["status"] == "Cancelled"


def test_upper_floor_and_order_routing(system):
    out = book(system, floor=3)
    assert out["carry_box_needed"] is True
    sent_to = {m["to"] for m in system.outbox if m["booking_id"] == out["booking_id"]}
    assert set(STAKEHOLDERS) | {"Customer"} == sent_to
    supervisor = [m for m in system.outbox if m["to"] == "Event staffing supervisor"][0]
    assert "carry box" in supervisor["message"]


def test_invalid_details_are_rejected(system):
    assert "error" in book(system, phone="123")
    assert "error" in book(system, bundle_id="B9")
    assert "error" in system.run_tool("does_not_exist", {})


def test_demo_agent_books_a_party(system):
    agent = DemoAgent(system)
    script = [
        "Hi, I want a trike for a birthday",
        "18 kids on 17 October",
        "Evening please, in Gulshan-e-Iqbal",
        "My name is Sara Ahmed, phone 0300 1234567",
        "Address is House 12, Block 5, Gulshan-e-Iqbal. Ground floor",
        "yes",
    ]
    for line in script:
        reply, _ = agent.reply(line)
    assert "Booked" in reply
    b = list(system.bookings.values())[0]
    assert b["slot"] == SLOTS[2]  # house and block numbers were not mistaken for a time
    assert b["date"] == "2026-10-17" and b["area"] == "Gulshan-e-Iqbal" and b["floor"] == 0


class FakeClient:
    """Stands in for the Anthropic client: first asks for a tool, then answers in text."""

    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if len(self.calls) == 1:
            block = SimpleNamespace(type="tool_use", id="tool_1", name="recommend_bundle", input={"num_children": 18})
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="I suggest the Classic Party Pack.")])


def test_claude_agent_runs_tools_and_returns_results(system):
    client = FakeClient()
    agent = ClaudeAgent(system, client=client, model="test-model")
    reply, activity = agent.reply("18 kids, what do you suggest?")
    assert reply == "I suggest the Classic Party Pack."
    assert activity[0]["tool"] == "recommend_bundle" and activity[0]["output"]["bundle_id"] == "B2"
    # The tool result was sent back to the model in the second call
    tool_result = client.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tool_1"
    assert {t["name"] for t in client.calls[0]["tools"]} >= {"check_availability", "create_booking"}


def test_demo_agent_cancels_a_booking(system):
    out = book(system)
    stock_after_booking = dict(system.stock)
    agent = DemoAgent(system)
    reply, activity = agent.reply(f"Please cancel {out['booking_id']}")
    assert activity[0]["tool"] == "cancel_booking"
    assert "cancelled" in reply.lower()
    assert system.bookings[out["booking_id"]]["status"] == "Cancelled"
    assert system.stock != stock_after_booking  # stock was released
    reply, _ = agent.reply(f"cancel {out['booking_id']}")  # cancelling twice is safe
    assert "cancelled" in reply.lower()


def test_demo_agent_handles_unserved_area(system):
    agent = DemoAgent(system)
    agent.reply("20 kids on 17 October")
    reply, activity = agent.reply("Evening please, we live in Hyderabad")
    assert "area" not in agent.d and not activity  # nothing is checked or booked for an unknown area
    assert "area of Karachi" in reply  # the agent asks again
    reply, _ = agent.reply("Then Clifton please")
    assert "trike is free" in reply


def test_unserved_area_reply_lists_served_areas(system):
    out = system.check_availability("Hyderabad", "2026-10-17", SLOTS[2])
    assert out["available"] is False and "do not serve" in out["reason"]
    assert "Clifton" in out["service_areas"]
