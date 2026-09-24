# gulliver-ai-toolkit

A small, complete example of the loop I think an "AI enablement" role
actually runs day to day: **build a tool an agent can use → give the agent
a skill that tells it how to use the tool well → write an eval that proves
a change to either one actually helped, not just "feels" better.**

Built as a portfolio piece for the AI Enablement Engineer role, scoped to
something concrete: a mobile-game live-ops dataset (DAU, revenue, session
length, crash rate) — the kind of data a studio's marketing/live-ops/data
people look at every day.

## What's in here

```
mcp_server/
  server.py        - MCP server: list_tables, profile_table, run_sql (read-only),
                      detect_anomalies (pluggable method)
  anomaly.py        - v1_zscore (naive baseline) vs v2_robust (rolling-median + IQR)
skills/game-data-analysis/
  v1_SKILL.md       - the "before" skill: 4 vague lines
  SKILL.md          - the "after" skill: a concrete, checkable workflow
evals/
  test_mcp_tools.py       - tool correctness/safety tests + anomaly precision/recall/F1
  eval_skill_quality.py   - rubric scorer for the skill document, v1 vs v2
  run_evals.py             - runs both, writes evals/results/report.md
data/
  generate_liveops_data.py - synthetic dataset generator with LABELED ground truth
.github/workflows/evals.yml - CI: regenerates data, runs the full eval suite on every push
```

Run it yourself:
```bash
pip install -r requirements.txt
python data/generate_liveops_data.py && python data/load_db.py
python mcp_server/server.py --selftest      # sanity-check the tools directly
pytest evals/ -v                             # run the eval suite
python evals/run_evals.py                    # write evals/results/report.md
```

## The hard part

The skill's whole job is to tell an agent: "use `detect_anomalies` with
`method="v2_robust"`, not the naive one." So before I could write that
skill honestly, I had to actually prove `v2_robust` deserved that
recommendation — not just assume a fancier-sounding method is better.

First attempt: I generated 120 days of DAU/revenue/session/crash data with
10 labeled anomalies and ran both methods. v1 (naive z-score) *won* on F1
(0.89 vs 0.87). My "improved" version wasn't actually better — the eval
caught that immediately, which is the entire point of writing one.

Digging into why: the injected anomalies were big, isolated spikes, which
is exactly what z-score is good at. That's not a realistic test — real
live-ops data has legitimate sustained shifts (a UA campaign week, a
seasonal bump) that aren't anomalies at all. So I added a 7-day marketing
campaign to the dataset — a real, non-anomalous ~2x DAU/revenue bump,
deliberately *excluded* from the ground truth. That single change flipped
the result: v1's global mean/std gets dragged by the campaign week badly
enough that it (a) flags all 7 legitimate campaign days as false
anomalies, and (b) simultaneously *misses* 2 of the real injected
anomalies elsewhere, because the inflated standard deviation pushes their
z-scores back under the 3-sigma threshold. On the `dau` column specifically,
v1 goes 0-for-2 (F1 = 0.00). v2's local window is unaffected by a shift
40 days away, so it scores 1.00 on the same column.

Overall F1: **0.55 → 0.87** ([full breakdown](evals/results/report.md)).

That's the actual finding worth writing a skill instruction around: not
"use a better algorithm" in the abstract, but "the naive method fails
specifically when there's a real marketing campaign in the window, which
there always eventually is" — so `SKILL.md` explicitly tells the agent
which method to use and *why the other one is a trap*, not just which one
scores higher on a benchmark nobody will ever see.

Second hard part, smaller but very "this is the actual job": early on, the
anomaly eval reported v1 catching 100% of anomalies with 0 false positives
in every run — suspiciously perfect. Turned out the ground-truth CSV used
column names (`revenue`, `crash_rate`) that didn't match the actual
dataset's column names (`revenue_usd`, `crash_rate_pct`), so every
"actual" anomaly set was silently empty and precision/recall were
computing against nothing. The eval wasn't failing — it just wasn't
testing anything. Fixed by making the generator write the ground truth
with the exact same column names as the CSV it labels, with a comment
explaining why the mismatch is easy to introduce silently. This is the
failure mode I'd worry about most in a real eval suite: not a crashing
test, but a green test that isn't checking anything.

## Design decisions worth flagging

- **`run_sql` is read-only by construction**, not by convention — it
  regex-rejects anything that isn't a bare `SELECT`, and table/column
  names are whitelisted against a strict identifier pattern before being
  interpolated into SQL, closing the injection path an f-string-built
  query would otherwise open. An agent with unrestricted SQL access to a
  real analytics DB is a data-loss incident waiting to happen.
- **`profile_table` exists as its own tool**, not folded into `run_sql`,
  because that's the actual habit a careful analyst has: profile first,
  query second. Giving the agent the same tool a human would reach for
  first nudges it toward the same order of operations — `SKILL.md` makes
  this explicit rather than hoping the agent infers it.
- **Two evals, not one**, because a toolkit like this has two different
  things that can silently regress: the *tool's* logic (graded against
  ground truth — precision/recall/F1) and the *skill's* instructions
  (graded against a rubric of known failure modes, since there's no
  ground truth for prose). Shipping only one would miss regressions in
  the other.

## If this were a real production skill

Two things I'd add next, out of scope for a 3-hour-shaped portfolio piece
but the first things I'd bring up with a team: (1) the skill rubric here
is keyword-based, which is a reasonable cheap proxy but doesn't catch a
skill that mentions the right words in the wrong order or context — an
LLM-graded rubric would catch more; (2) the synthetic dataset has exactly
one distractor pattern (the campaign week) — a real eval suite should
have several, covering seasonality, holidays, and multi-metric correlated
incidents, so a method can't overfit to beating one specific trick.
