# Eval Report: game-data-analysis skill + gulliver-liveops MCP server

Generated: 2026-09-24T20:53:34+00:00Z

Dataset: `data/liveops_daily.csv` (120 days, 10 labeled anomalies, 1 non-anomalous 7-day marketing campaign as a distractor)

## Eval 1 — Anomaly detection method: v1_zscore (before) vs v2_robust (after)

| Column | v1 Precision | v1 Recall | v1 F1 | v2 Precision | v2 Recall | v2 F1 |
|---|---|---|---|---|---|---|
| dau | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| revenue_usd | 1.00 | 0.50 | 0.67 | 0.80 | 1.00 | 0.89 |
| avg_session_length_min | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 0.67 |
| crash_rate_pct | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| **overall** | **0.50** | **0.60** | **0.55** | **0.77** | **1.00** | **0.87** |

**Overall F1 change: 0.55 -> 0.87 (+0.32)**

Worst case for v1: the `dau` column scores F1=0.00 (0 true positives). The 7-day marketing campaign inflates the global mean/std enough that z-score both flags every campaign day as a false positive AND misses the 2 real injected anomalies (their z-scores now fall under the widened 3-std threshold). v2_robust's local window isn't affected by a shift 40+ days away, so it gets `dau` perfectly right.

## Eval 2 — Skill document quality: v1_SKILL.md (before) vs SKILL.md (after)

Rubric score: v1 = 0/8, v2 = 8/8

| Rubric item | v1 | v2 | Why it matters |
|---|---|---|---|
| Instructs profiling (nulls/dtypes/dupes) before drawing conclusions | ❌ | ✅ | Without this, a bad ETL run (nulls) gets reported as a real metric drop. |
| Instructs checking for missing/gapped dates | ❌ | ✅ | A silent gap in daily data looks identical to 'nothing happened' if unchecked. |
| Names a specific anomaly-detection method to use (not just 'look for anomalies') | ❌ | ✅ | 'Look for anomalies' with no method = the agent invents its own, unverified approach. |
| Explicitly warns against the naive/baseline method and explains why | ❌ | ✅ | Without this, nothing stops the agent from picking the worse method by default. |
| Instructs checking co-occurring anomalies across metrics on the same date | ❌ | ✅ | Reporting a DAU drop and a crash spike as two findings instead of one incident. |
| Distinguishes a sustained trend from a single-day anomaly | ❌ | ✅ | A trend needs root-cause investigation; a point anomaly needs a sanity check. Conflating them wastes the reader's time. |
| Requires reporting the local baseline alongside any anomaly value | ❌ | ✅ | "Revenue was $5,767" means nothing without "vs ~$1,000-1,400 normally." |
| Specifies a concrete report structure/template, not just 'write a summary' | ❌ | ✅ | Unstructured summaries are inconsistent between runs and hard for a PM to scan quickly. |

## CI gate
- Anomaly F1 did not regress: PASS
- Skill rubric score improved: PASS
