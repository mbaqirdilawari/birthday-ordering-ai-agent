"""Charts for the README (saved to outputs/figures). All data is simulated."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from business_case import model as bc  # noqa: E402
from omnichannel import audit  # noqa: E402

FIG = ROOT / "outputs" / "figures"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GREY, GREY_LIGHT, INK, INK_2, INK_3 = "#b8b6b0", "#e4e2dc", "#0b0b0b", "#52514e", "#8a8984"
NOTE = "Simulated data for illustration only. Not real company data."
plt.rcParams.update({
    "font.family": ["Inter", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "axes.edgecolor": GREY, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 13,
    "axes.titleweight": "semibold", "axes.titlelocation": "left", "axes.spines.top": False,
    "axes.spines.right": False, "xtick.color": INK_2, "ytick.color": INK_2, "legend.frameon": False,
    "savefig.dpi": 160, "savefig.bbox": "tight",
})
thousands = FuncFormatter(lambda v, _: f"{v:,.0f}")


def save(fig, name):
    fig.text(0.01, -0.02, NOTE, fontsize=8, color=INK_3, ha="left", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name)
    plt.close(fig)


def issues_by_type(issues):
    counts = issues["issue"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.barh(counts.index, counts.values, color=BLUE, height=0.6)
    for y, v in enumerate(counts.values):
        ax.text(v, y, f"  {v:,}", va="center", fontsize=9, color=INK)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title(f"{len(issues):,} listing problems found across live chain accounts")
    save(fig, "listing_issues_by_type.png")


def pareto(card):
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = range(1, len(card) + 1)
    ax.plot(x, card["cumulative_sales_share"], color=BLUE, linewidth=2)
    n = int((card["priority"] == "Fix first").sum())
    ax.axhline(audit.PRIORITY_SALES_SHARE, color=INK_3, linestyle="--", linewidth=1)
    ax.axvline(n, color=INK_3, linestyle=":", linewidth=1)
    ax.annotate(f"{n} of {len(card)} accounts make up\n{audit.PRIORITY_SALES_SHARE:.0%} of platform sales: fix these first",
                xy=(n, audit.PRIORITY_SALES_SHARE), xytext=(15, -55), textcoords="offset points", fontsize=9, color=INK,
                arrowprops={"arrowstyle": "-", "color": INK_3, "linewidth": 0.8})
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Live chain accounts, ranked by sales")
    ax.set_ylabel("Cumulative share of sales")
    ax.set_title("A few large chains drive most online sales")
    save(fig, "account_sales_pareto.png")


def health_before_after(card, top=15):
    d = card[card["priority"] == "Fix first"].head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    y = range(len(d))
    for yi, (b, a) in enumerate(zip(d["listing_health"], d["listing_health_after"])):
        ax.plot([b, a], [yi, yi], color=GREY_LIGHT, linewidth=3, zorder=1)
    ax.scatter(d["listing_health"], y, color=GREY, s=50, zorder=2, label="Before fixes", edgecolor="white")
    ax.scatter(d["listing_health_after"], y, color=BLUE, s=50, zorder=3, label="After fixes", edgecolor="white")
    ax.set_yticks(list(y), d["account_name"])
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlim(-0.02, 1.05)
    ax.set_xlabel("Listing health: share of active products listed correctly")
    ax.set_title(f"Largest {top} accounts: listing health before and after fixes", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=9)
    save(fig, "listing_health_before_after.png")


def payback(result):
    t = bc.monthly_table({**bc.ASSUMPTIONS, "months": 30})
    pm = result["payback_month_margin_basis"]
    rev_month = int(t[t["cumulative_revenue"] >= bc.launch_cost()]["month"].iloc[0])
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(t["month"], t["cumulative_revenue"], color=GREY, linewidth=2, linestyle="--", label="Cumulative revenue")
    ax.plot(t["month"], t["cumulative_margin"], color=BLUE, linewidth=2, label="Cumulative gross margin")
    ax.plot(t["month"], t["cumulative_cost"], color=ORANGE, linewidth=2, label="Cumulative cost (launch and running)")
    ax.axhline(bc.launch_cost(), color=INK_3, linewidth=0.8, linestyle=":")
    ax.annotate(f"Revenue covers launch cost\nin month {rev_month}", xy=(rev_month, bc.launch_cost()), xytext=(-10, 40),
                textcoords="offset points", fontsize=8.5, color=INK_2, ha="right",
                arrowprops={"arrowstyle": "-", "color": INK_3, "linewidth": 0.8})
    if pm and pm <= 30:
        y = float(t.loc[t["month"] == pm, "cumulative_cost"].iloc[0])
        ax.annotate(f"Margin pays back all costs\nin month {pm}", xy=(pm, y), xytext=(20, -55), textcoords="offset points",
                    fontsize=8.5, color=INK, ha="left", arrowprops={"arrowstyle": "-", "color": INK_3, "linewidth": 0.8})
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M"))
    ax.set_xlabel("Month after launch")
    ax.set_ylabel("PKR")
    ax.set_title("When does the birthday trike service pay back?")
    ax.legend(loc="upper left", fontsize=9)
    save(fig, "business_case_payback.png")


def main():
    a = audit.run(save=False)
    issues_by_type(a["issues"])
    pareto(a["scorecard"])
    health_before_after(a["scorecard"])
    payback(bc.run(save=False))
    print("Charts saved to", FIG)


if __name__ == "__main__":
    main()
