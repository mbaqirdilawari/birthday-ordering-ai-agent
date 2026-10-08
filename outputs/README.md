# Outputs

Everything in this folder is produced by `python run_all.py`. **All results come from simulated data** and only demonstrate the method. They are not real company figures.

## Tables (`tables/`)

### Listing quality checker

| File | What it contains |
|---|---|
| `listing_issue_log.csv` | One row per problem found: `account_id`, `sku_id` (product code), `product_name`, `issue`, `detail` and the `fix` to apply |
| `account_scorecard.csv` | One row per chain account on the platform: sales, `listing_health` (share of active products listed correctly), `total_issues`, a count for each issue type, `cumulative_sales_share`, `priority` ("Fix first" for the accounts that make up 80 percent of platform sales) and `listing_health_after` (health once priority accounts are fixed) |
| `onboarding_priority.csv` | Chain accounts not yet on the platform, ranked by sales (`onboarding_rank`), to plan who to onboard next |
| `listing_audit_summary.csv` | Headline numbers: accounts checked, listings checked, issues found, priority accounts, and sales weighted listing health before and after fixes |

### Business case

| File | What it contains |
|---|---|
| `business_case_monthly.csv` | One row per month: `orders`, `revenue`, `gross_margin`, cumulative revenue, cumulative margin, cumulative cost (launch plus running costs) and `net_position` (cumulative margin minus cumulative cost). Amounts in PKR |
| `business_case_sensitivity.csv` | Payback month (margin basis) for each combination of steady orders per month (rows) and average order value in PKR (columns) |

## Figures (`figures/`)

| File | What it shows |
|---|---|
| `chat_demo.png` | The web chat in demo mode: a full booking, the tools the agent called, and the order sent to each team |
| `listing_issues_by_type.png` | Number of listing problems found, by type |
| `account_sales_pareto.png` | Cumulative share of platform sales by chain account, and how many accounts make up 80 percent |
| `listing_health_before_after.png` | Listing health of the largest priority accounts, before and after fixes |
| `business_case_payback.png` | Cumulative revenue, margin and cost by month, with the revenue basis and margin basis payback points |

## Sample conversation (`transcripts/`)

`demo_conversation.md` is a full booking conversation in demo mode: each customer message, every tool the agent called with its inputs, each agent reply, and the instruction sent to every team after the booking.
