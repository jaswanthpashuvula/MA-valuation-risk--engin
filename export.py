"""
Writes the tidy DataFrames the rest of the pipeline produces into a SQL
database. Using SQLite so the project runs with zero setup — to point this
at Postgres/MySQL instead, swap out get_connection() for a real connection
and everything else (plain to_sql calls) keeps working unmodified.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd


def get_connection(db_path) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def load_tables(tables: dict[str, pd.DataFrame], db_path) -> None:
    """Writes each tidy DataFrame to its own table, replacing on each run."""
    conn = get_connection(db_path)
    try:
        for table_name, df in tables.items():
            if df is None or df.empty:
                continue
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"  -> loaded {len(df):>6,} rows into '{table_name}'")
    finally:
        conn.close()


def append_risk_result(result: dict, db_path) -> None:
    """Appends one Monte Carlo run to the risk_simulation table instead of overwriting it, so history builds up run over run."""
    row = pd.DataFrame([{**result, "run_timestamp": datetime.now(timezone.utc).isoformat()}])
    conn = get_connection(db_path)
    try:
        row.to_sql("risk_simulation", conn, if_exists="append", index=False)
    finally:
        conn.close()
