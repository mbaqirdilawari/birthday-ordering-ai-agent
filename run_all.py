"""Rebuild every output in this repository.

Terminal:
    python run_all.py
"""
import subprocess
import sys

STEPS = [
    ["scripts/simulate_data.py"],
    ["-m", "omnichannel.audit"],
    ["-m", "business_case.model"],
    ["-m", "business_case.excel_model"],
    ["scripts/make_charts.py"],
    ["scripts/demo_conversation.py"],
]

if __name__ == "__main__":
    for step in STEPS:
        print(f"\n=== python {' '.join(step)}")
        subprocess.run([sys.executable, *step], check=True)
    print("\nDone. Start the chat with: python app.py")
