#al-toolkit

An open-source Model Context Protocol (MCP) server, agent skill workflow, and evaluation suite designed for mobile game live-ops analytics and autonomous AI agents.

A production-grade demonstration of the core AI engineering loop: **build a tool an agent can use → give the agent a skill that tells it how to use the tool well → write an eval that proves a change to either one actually helped, not just "feels" better.**

Scoped to a concrete mobile-game live-ops dataset (DAU, revenue, session length, crash rate) — the core operational metrics marketing, live-ops, and data teams analyze daily.

---

##  Key Features

- **Model Context Protocol (MCP) Server**: Exposes database profiling, read-only SQL querying, and time-series anomaly detection tools directly to AI agents.
- **Robust Anomaly Detection**: Implements a rolling-median + Interquartile Range (IQR) algorithm (`v2_robust`) resilient to sustained marketing campaigns, outperforming standard Z-score baselines.
- **Structured Agent Skill Workflow**: Clear, checkable instructions guiding AI agents to profile data before querying and select appropriate detection algorithms.
- **Dual-Tier Automated Evaluation**:
  - **Tool Evals**: Measures anomaly detection Precision, Recall, and F1-score against ground-truth data.
  - **Skill Evals**: Evaluates skill documentation clarity and compliance against structured quality rubrics.
- **Continuous Integration**: GitHub Actions workflow automatically regenerates datasets, tests MCP tool safety, and runs full eval suites on every commit.

---

##  Repository Structure

```
gulliver-ai-toolkit/
├── mcp_server/
│   ├── server.py             # MCP server implementation (list_tables, profile_table, run_sql, detect_anomalies)
│   └── anomaly.py            # Anomaly detection engines (v1_zscore vs v2_robust)
├── skills/
│   └── game-data-analysis/
│       ├── v1_SKILL.md       # Baseline skill specification
│       └── SKILL.md          # Optimized, checkable workflow specification
├── evals/
│   ├── test_mcp_tools.py     # Tool correctness, safety, and anomaly F1 benchmarks
│   ├── eval_skill_quality.py # Rubric-based skill quality evaluator
│   └── run_evals.py          # Master evaluation runner & markdown report generator
├── data/
│   ├── generate_liveops_data.py # Synthetic live-ops dataset generator with labeled ground truth
│   └── load_db.py            # SQLite database initialization script
└── workflows/
    └── evals.yml             # CI pipeline for automated evaluation runs
```

---

##  Quickstart

### Prerequisites
- Python 3.12+
- `pip`

### Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/gulliver-ai-toolkit.git
   cd gulliver-ai-toolkit
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize dataset and database**:
   ```bash
   python data/generate_liveops_data.py && python data/load_db.py
   ```

4. **Sanity-check MCP server tools**:
   ```bash
   python mcp_server/server.py --selftest
   ```

---

##  Running Evaluations

Run unit and tool safety tests:
```bash
pytest evals/ -v
```

Execute the full evaluation suite and generate a detailed report:
```bash
python evals/run_evals.py
```
This produces a comprehensive report at `evals/results/report.md`.

---

##  Engineering Insights & Lessons Learned

### The Hard Part: Proving Method Superiority
The skill's whole job is to tell an agent: *"use `detect_anomalies` with `method="v2_robust"`, not the naive one."* Before writing that skill, `v2_robust` had to be empirically proven to outperform baselines—not just assumed to be better.

- **First Attempt**: Testing on 120 days of DAU/revenue/session/crash data with 10 labeled anomalies resulted in `v1_zscore` winning on F1 score (**0.89 vs 0.87**). The "improved" version was initially worse because the injected anomalies were isolated spikes—ideal for global Z-scores.
- **Realistic Scenario**: Real live-ops data includes legitimate, sustained business shifts (e.g., a 7-day UA marketing campaign) that aren't anomalies. Adding a 7-day marketing campaign (~2x DAU/revenue bump excluded from anomaly ground truth) flipped the results dramatically:
  - `v1_zscore`'s global mean/std was dragged up by the campaign week, flagging all 7 campaign days as false anomalies while simultaneously missing 2 true anomalies elsewhere. On the `dau` column, `v1` dropped to **F1 = 0.00**.
  - `v2_robust`'s local rolling window remained unaffected by the shift 40 days away, scoring **1.00** on the same column.
  - **Overall F1 Score**: **`0.55 → 0.87`** ([full breakdown](evals/results/report.md)).

> **Takeaway**: The naive method fails specifically when a marketing campaign occurs in the dataset window. The `SKILL.md` explicitly instructs the agent which method to use and explains *why the naive approach fails in production*.

### Silent Failures in Evaluation Pipelines
Early in development, the anomaly evaluation reported `v1` catching 100% of anomalies with 0 false positives—a suspiciously perfect result.

Investigation revealed that the ground-truth CSV used column names (`revenue`, `crash_rate`) that differed from the actual dataset (`revenue_usd`, `crash_rate_pct`). Every "actual" anomaly set was silently empty, causing precision/recall to calculate against nothing.

**Fix**: Updated the dataset generator to write ground truth with exact column matching and added schema validation to prevent silent green tests in evaluation suites.

---

##  Security & Safety Design

- **Read-Only SQL Execution**: `run_sql` rejects non-SELECT queries via strict regex validation to prevent data modification.
- **Query Parameter Whitelisting**: Table and column identifiers are validated against strict regex patterns to prevent SQL injection.
- **Guided Order of Operations**: Dedicated `profile_table` tool encourages AI agents to inspect schema and distributions before executing raw queries—a practice codified in `SKILL.md`.
- **Dual-Tier Evaluation**: Evaluates both **tool logic** (against quantitative ground truth) and **skill documentation** (against structured quality rubrics).

---

##  Production Roadmap

To scale this toolkit for enterprise production environments:

1. **LLM-Graded Skill Rubrics**: Upgrade skill evaluation from keyword heuristics to LLM-as-a-judge scoring to capture contextual nuances in agent instructions.
2. **Expanded Distractor Scenarios**: Introduce seasonality, holiday surges, and multi-metric correlated outages into synthetic data generation.
3. **Multi-Database Connectors**: Extend database access beyond SQLite to PostgreSQL, Snowflake, and BigQuery.

---

##  License

Distributed under the MIT License. See `LICENSE` for details.
