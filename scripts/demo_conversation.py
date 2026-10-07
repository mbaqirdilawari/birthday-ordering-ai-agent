"""Run a scripted conversation in demo mode and save the transcript (outputs/transcripts/).

Terminal:
    python scripts/demo_conversation.py
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import DemoAgent, OrderingSystem  # noqa: E402

SCRIPT = [
    "Hi! I want an ice cream trike for my daughter's birthday",
    "About 18 kids, on 17 October",
    "Evening please, we live in Gulshan-e-Iqbal",
    "My name is Sara Ahmed, phone 0300 1234567",
    "Address is House 12, Block 5, Gulshan-e-Iqbal. It is on the 2nd floor, theme is Unicorns",
    "yes",
    "Can you check BK0001?",
]


def main() -> None:
    system = OrderingSystem(today=date(2026, 10, 7))
    agent = DemoAgent(system)
    lines = ["# Sample conversation (demo mode, simulated data)", ""]
    for text in SCRIPT:
        reply, activity = agent.reply(text)
        lines += [f"**Customer:** {text}", ""]
        for a in activity:
            lines.append(f"> tool `{a['tool']}` called with `{a['input']}`")
        if activity:
            lines.append("")
        lines += [f"**Agent:** {reply}", ""]
    lines += ["## Order routing after the booking", "", "| Sent to | Message |", "|---|---|"]
    lines += [f"| {m['to']} | {m['message']} |" for m in system.outbox]
    out = ROOT / "outputs" / "transcripts" / "demo_conversation.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print("Saved", out)


if __name__ == "__main__":
    main()
