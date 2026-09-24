"""Loads liveops_daily.csv into a SQLite db so the MCP server has something
realistic to query (this mirrors how a real internal analytics DB would look)."""
import csv
import sqlite3
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "liveops.db")

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
CREATE TABLE liveops_daily (
    date TEXT PRIMARY KEY,
    dau INTEGER,
    revenue_usd REAL,
    avg_session_length_min REAL,
    crash_rate_pct REAL
)
""")

with open(os.path.join(HERE, "liveops_daily.csv")) as f:
    reader = csv.DictReader(f)
    rows = [
        (r["date"], int(r["dau"]), float(r["revenue_usd"]),
         float(r["avg_session_length_min"]), float(r["crash_rate_pct"]))
        for r in reader
    ]

cur.executemany(
    "INSERT INTO liveops_daily VALUES (?, ?, ?, ?, ?)", rows
)
conn.commit()
conn.close()
print(f"Loaded {len(rows)} rows into {DB_PATH}")
