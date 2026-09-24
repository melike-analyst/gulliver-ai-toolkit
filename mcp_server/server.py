"""
gulliver-liveops-mcp: a small MCP server that lets an agent explore a
mobile-game live-ops SQLite database safely.

Tools exposed:
  list_tables()                       - what's in the DB
  profile_table(table)                - row count, nulls, dtypes, duplicates
  run_sql(query)                      - read-only SELECT queries only
  detect_anomalies(table, column, method)  - v1_zscore or v2_robust

Design choices worth flagging (this is the "hard part" of the build):
  - run_sql only allows SELECT statements. An agent with a raw SQL tool
    against a real analytics DB is a data-loss incident waiting to happen,
    so write/DDL statements are rejected before they ever reach sqlite3.
  - profile_table exists because "just run SQL" isn't how a human analyst
    actually starts - you profile first (nulls, dtypes, dupes), THEN query.
    Giving the agent that same tool means it follows the same good habit
    instead of guessing column types from a SELECT * LIMIT 5.
  - detect_anomalies takes a `method` argument specifically so this server
    doubles as the harness for the eval suite in evals/ - the eval calls
    the same function the agent calls, on the same data, and compares
    v1 vs v2 against labeled ground truth.

Run standalone for local testing:
    python server.py --selftest

Run as an MCP server (stdio transport, e.g. from Claude Code config):
    python server.py
"""
from __future__ import annotations
import argparse
import os
import re
import sqlite3
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anomaly import METHODS  # noqa: E402

DB_PATH = os.environ.get(
    "LIVEOPS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "liveops.db"),
)

_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|PRAGMA)\b", re.IGNORECASE)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_tables() -> dict[str, Any]:
    """List every table available in the live-ops database."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {"tables": [r["name"] for r in rows]}
    finally:
        conn.close()


def profile_table(table: str) -> dict[str, Any]:
    """Profile a table before querying it: row count, columns, dtypes,
    null counts per column, and duplicate row count. Always call this
    before run_sql on a table you haven't seen yet."""
    conn = _connect()
    try:
        cols = conn.execute(f"PRAGMA table_info({_safe_ident(table)})").fetchall()
        if not cols:
            return {"error": f"table '{table}' not found"}
        col_names = [c["name"] for c in cols]

        total = conn.execute(f"SELECT COUNT(*) AS n FROM {_safe_ident(table)}").fetchone()["n"]

        null_counts = {}
        for c in col_names:
            n_null = conn.execute(
                f"SELECT COUNT(*) AS n FROM {_safe_ident(table)} WHERE {_safe_ident(c)} IS NULL"
            ).fetchone()["n"]
            null_counts[c] = n_null

        # SQLite has no multi-column COUNT(DISTINCT a, b, ...), so count
        # duplicate full-row combinations via GROUP BY instead.
        group_cols = ", ".join(_safe_ident(c) for c in col_names)
        dup_count = conn.execute(
            f"""SELECT COALESCE(SUM(cnt - 1), 0) AS dups FROM (
                    SELECT COUNT(*) AS cnt FROM {_safe_ident(table)}
                    GROUP BY {group_cols}
                    HAVING COUNT(*) > 1
                )"""
        ).fetchone()["dups"]

        return {
            "table": table,
            "row_count": total,
            "columns": col_names,
            "dtypes": {c["name"]: c["type"] for c in cols},
            "null_counts": null_counts,
            "duplicate_rows": dup_count,
        }
    finally:
        conn.close()


def run_sql(query: str) -> dict[str, Any]:
    """Run a single read-only SELECT query against the live-ops database.
    INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH/PRAGMA are rejected.
    Returns at most 500 rows."""
    if not _SELECT_ONLY.match(query) or _FORBIDDEN.search(query):
        return {"error": "only single read-only SELECT statements are allowed"}
    conn = _connect()
    try:
        cur = conn.execute(query)
        rows = [dict(r) for r in cur.fetchmany(500)]
        return {"row_count": len(rows), "rows": rows}
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()


def detect_anomalies(table: str, column: str, method: str = "v2_robust") -> dict[str, Any]:
    """Detect anomalous values in a numeric column, ordered by date.
    method='v2_robust' (default) uses a rolling-median + IQR fence, robust
    to trend and seasonality. method='v1_zscore' is the naive mean+-3std
    baseline, kept only for comparison in evals."""
    if method not in METHODS:
        return {"error": f"unknown method '{method}', choose from {list(METHODS)}"}
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT date, {_safe_ident(column)} AS v FROM {_safe_ident(table)} ORDER BY date"
        ).fetchall()
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()

    values = [r["v"] for r in rows]
    dates = [r["date"] for r in rows]
    results = METHODS[method](values)
    return {
        "method": method,
        "column": column,
        "anomalies": [
            {"date": dates[r.index], "index": r.index, "value": r.value, "reason": r.reason}
            for r in results
        ],
    }


def _safe_ident(name: str) -> str:
    """Whitelist table/column identifiers (alnum + underscore only) to
    prevent SQL injection through f-string interpolation above."""
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"unsafe identifier: {name}")
    return name


# --- MCP wiring -------------------------------------------------------

def build_mcp_server():
    # NOTE: mcp==2.2.0 renamed FastMCP -> MCPServer (mcp.server.mcpserver).
    # Pinned/imported the current name deliberately rather than `mcp<2`,
    # since a portfolio piece pinned to a library's old API is exactly the
    # kind of silent rot this role exists to catch.
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("gulliver-liveops")

    mcp.tool()(list_tables)
    mcp.tool()(profile_table)
    mcp.tool()(run_sql)
    mcp.tool()(detect_anomalies)

    return mcp


def _selftest():
    print("list_tables ->", list_tables())
    print("profile_table ->", profile_table("liveops_daily"))
    print("run_sql ->", run_sql("SELECT date, revenue_usd FROM liveops_daily LIMIT 3"))
    print("run_sql (blocked) ->", run_sql("DROP TABLE liveops_daily"))
    v1 = detect_anomalies("liveops_daily", "revenue_usd", "v1_zscore")
    v2 = detect_anomalies("liveops_daily", "revenue_usd", "v2_robust")
    print(f"detect_anomalies v1_zscore -> {len(v1['anomalies'])} flagged")
    print(f"detect_anomalies v2_robust -> {len(v2['anomalies'])} flagged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
    else:
        server = build_mcp_server()
        server.run()
