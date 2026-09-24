"""
Generates a synthetic mobile-game live-ops dataset (DAU, revenue, session
length, crash rate) with KNOWN, LABELED anomalies injected at specific rows.

Why synthetic-but-labeled: to write an eval that *proves* an anomaly
detector improved, we need ground truth. Real exported analytics data has
no such labels, so we generate a realistic-looking series and inject
anomalies ourselves, then keep the injected indices as the answer key.

Output:
  data/liveops_daily.csv        -> the dataset an agent would analyze
  data/liveops_ground_truth.csv -> which rows are true anomalies (for evals only)
"""
import csv
import random
import math
from datetime import date, timedelta

random.seed(42)

N_DAYS = 120
START = date(2026, 1, 1)

rows = []
ground_truth = []  # (row_index, column, is_anomaly)

base_dau = 8000
base_session = 6.2  # minutes
base_crash = 0.4    # percent

# Rows deliberately chosen to inject anomalies into (mixed columns, mixed
# directions, some subtle/some obvious - so a naive detector and a robust
# detector will disagree on the hard ones).
# Keys MUST match the final CSV/DB column names exactly (revenue_usd, not
# revenue) - a mismatch here silently breaks every eval that reads this
# ground truth, because "actual" comes back empty and every prediction
# looks like a false positive. This bit us once during development; see
# README.md "hardest part" section.
INJECTED = {
    14: ("revenue_usd", "spike", 6.0),      # viral UA spike day
    15: ("revenue_usd", "spike", 4.5),      # spillover
    30: ("dau", "drop", -0.55),             # server outage
    31: ("crash_rate_pct", "spike", 8.0),   # outage-related crash spike
    55: ("avg_session_length_min", "drop", -0.6),  # bad build shipped
    56: ("avg_session_length_min", "drop", -0.5),
    72: ("revenue_usd", "drop", -0.7),      # payment provider outage
    90: ("dau", "spike", 0.9),              # featured on App Store
    91: ("revenue_usd", "spike", 1.8),
    108: ("crash_rate_pct", "spike", 5.0),  # bad patch
}

# Days 45-51: a real 7-day UA marketing campaign. DAU and revenue rise
# ~45% and STAY there for a week - this is normal, expected, non-anomalous
# business activity, and it is deliberately left OUT of ground truth.
# It exists to stress-test v1_zscore: a sustained shift drags the global
# mean/std used by z-score, which then (a) may flag the *legitimate*
# campaign days as "anomalies" (false positives) and/or (b) makes the
# std wide enough that later, smaller *real* anomalies fall under the
# 3-std threshold and get missed (false negatives). A local/robust
# detector should do neither, because it compares each point to its
# nearby window, not the whole series.
CAMPAIGN_DAYS = set(range(45, 52))

for i in range(N_DAYS):
    d = START + timedelta(days=i)
    weekday_boost = 1.15 if d.weekday() >= 5 else 1.0  # weekend bump
    trend = 1 + (i / N_DAYS) * 0.5  # steady organic growth over 120 days

    campaign_boost = 2.2 if i in CAMPAIGN_DAYS else 1.0

    dau = base_dau * weekday_boost * trend * campaign_boost * random.gauss(1.0, 0.04)
    arpdau = 0.085 * random.gauss(1.0, 0.10)
    revenue = dau * arpdau
    session_length = base_session * random.gauss(1.0, 0.06)
    crash_rate = max(0.05, base_crash * random.gauss(1.0, 0.15))

    if i in INJECTED:
        col, kind, magnitude = INJECTED[i]
        if col == "dau":
            dau = dau * (1 + magnitude)
        elif col == "revenue_usd":
            revenue = revenue * (1 + magnitude)
        elif col == "avg_session_length_min":
            session_length = session_length * (1 + magnitude)
        elif col == "crash_rate_pct":
            crash_rate = crash_rate * (1 + magnitude) if kind == "spike" else crash_rate * max(0.1, 1 + magnitude)
        ground_truth.append((i, col, True))

    rows.append({
        "date": d.isoformat(),
        "dau": round(dau),
        "revenue_usd": round(revenue, 2),
        "avg_session_length_min": round(session_length, 2),
        "crash_rate_pct": round(crash_rate, 3),
    })

with open("/home/claude/gulliver-ai-toolkit/data/liveops_daily.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "dau", "revenue_usd", "avg_session_length_min", "crash_rate_pct"])
    writer.writeheader()
    writer.writerows(rows)

with open("/home/claude/gulliver-ai-toolkit/data/liveops_ground_truth.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["row_index", "column", "is_injected_anomaly"])
    for r in ground_truth:
        writer.writerow(r)

print(f"Wrote {len(rows)} rows, {len(ground_truth)} labeled anomalies -> data/liveops_daily.csv")
