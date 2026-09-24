---
name: game-data-analysis
description: Use when the user asks to analyze, review, or find issues in mobile-game live-ops data (DAU, revenue, session length, crash rate) — whether from a CSV export or the liveops SQLite database via the gulliver-liveops MCP server. Produces a structured findings report, not just a summary.
---

# Game Data Analysis

This skill turns a raw live-ops export into a report a founder or PM can
act on in under a minute. Follow these steps **in order** — skipping the
profiling step is the #1 cause of wrong conclusions (e.g. reporting a
"revenue drop" that's actually a null-filled day from a broken ETL job).

## 1. Profile before you analyze

If the `gulliver-liveops` MCP server is available, call `profile_table`
before anything else. If working from a raw CSV instead, do the
equivalent by hand: row count, column dtypes, null counts per column,
duplicate rows, and date range covered.

**Stop and flag to the user, don't silently proceed, if:**
- any column has >5% nulls
- the date range has gaps (missing days) — check this explicitly, a
  silent gap looks identical to "nothing happened that day"
- there are duplicate rows for the same date

## 2. Detect anomalies per metric, don't eyeball it

For each numeric column (dau, revenue_usd, avg_session_length_min,
crash_rate_pct), run `detect_anomalies` with `method="v2_robust"`.

Do **not** use `v1_zscore` for reporting — it's kept in the toolkit only
as a baseline for evals. It over-flags on any column with a growth trend
or weekly seasonality (which live-ops data always has), and it can miss
real anomalies because the outlier itself drags the mean/std it's
measured against.

For every flagged anomaly, look at the *other* columns on that same date
before writing it up — a crash_rate spike and a DAU drop on the same day
is one incident (an outage), not two separate findings.

## 3. Distinguish trend from event

Before calling something an anomaly, check: is this a single-day event,
or the start/end of a multi-day trend (e.g. session length declining for
5 days straight after a build ships)? Report trends separately from
point anomalies — they need different responses (a trend needs a root
cause investigation, a point anomaly needs a "was this expected"
sanity check).

## 4. Report format

Structure the output as:

```
## Summary
[1-2 sentences: overall health, biggest thing that changed]

## Anomalies found
- [date] [metric]: [value] vs local baseline [range] — [likely
  co-occurring factor, if any, e.g. "coincides with crash_rate spike
  same day"]

## Data quality notes
[nulls / gaps / duplicates found in step 1, or "none found"]

## Suggested next step
[one concrete follow-up, e.g. "check release log for Jan 15" — not a
generic "investigate further"]
```

Never present an anomaly without the local baseline it's being compared
to — "revenue was $5,767" means nothing without "vs ~$1,000-1,400 on
neighboring days."
