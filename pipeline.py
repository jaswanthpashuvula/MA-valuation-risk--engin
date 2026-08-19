"""
================================================================================
 PIPELINE ORCHESTRATOR  —  Week 1 / Days 1-3 end-to-end
 Extraction (Day 1) -> Historical Metrics (Day 2) -> FCFF actuals + forecast
 (Day 3) -> load every tidy table into a SQL database.
================================================================================

SQL STAGING NOTE
--------------------------------------------------------------------------
This uses SQLite as a zero-config stand-in for whatever production warehouse
you land on (Postgres/MySQL/Snowflake). Because every upstream module already
outputs tidy, long-format DataFrames, swapping the destination is a one-line
change: replace `get_sql_engine()`'s body with, e.g.

    from sqlalchemy import create_engine
    return create_engine("postgresql+psycopg2://user:pass@host:5432/mna_valuation")

...and every `df.to_sql(...)` call below works unmodified.
================================================================================
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from config import DB_PATH, PERIOD_TYPE, PROJECTION_YEARS, UNIVERSE
from extraction import extract_universe
from fcff import build_fcff_universe
from metrics import build_metrics_universe


def get_sql_engine() -> sqlite3.Connection:
    """
    Single point of change to swap SQLite -> Postgres/MySQL/Snowflake later
    (see module docstring). Kept as a plain sqlite3.Connection here since
    pandas.to_sql accepts either a DBAPI connection or a SQLAlchemy engine.
    """
    return sqlite3.connect(DB_PATH)


def load_tables_to_sql(tables: dict[str, pd.DataFrame], conn: sqlite3.Connection) -> None:
    """Writes each tidy DataFrame to its own table, replacing on each run (idempotent for dev/demo)."""
    for table_name, df in tables.items():
        if df is None or df.empty:
            continue
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  -> loaded {len(df):>6,} rows into '{table_name}'")


def run_days_1_to_3(tickers: list[str] = UNIVERSE, period_type: str = PERIOD_TYPE, years: int = PROJECTION_YEARS):
    """
    Full Week 1 / Day 1-3 pipeline for a target + peer universe.

    Day 1 : extract_universe()      -> company profiles, raw statement facts
    Day 2 : build_metrics_universe()-> historical margin/ratio facts
    Day 3 : build_fcff_universe()   -> historical FCFF actuals + 5yr forecast
    Finally: load all five tidy tables into SQL.
    """
    print(f"\n{'='*78}\nDAY 1 — EXTRACTION: {tickers}\n{'='*78}")
    profiles_df, raw_tidy_df, raw_wide_dict = extract_universe(tickers, period_type=period_type)
    print(f"Extracted {len(raw_wide_dict)}/{len(tickers)} tickers successfully.")

    print(f"\n{'='*78}\nDAY 2 — HISTORICAL METRICS\n{'='*78}")
    bundles_by_ticker, metrics_tidy_df = build_metrics_universe(raw_wide_dict)
    for ticker, bundle in bundles_by_ticker.items():
        avg = bundle["averages"]
        print(f"  {ticker:6s} | Rev Growth {avg['avg_revenue_growth']:>7.2%} | "
              f"EBITDA Margin {avg['avg_ebitda_margin']:>7.2%} | "
              f"CapEx/Rev {avg['avg_capex_to_revenue']:>6.2%}")

    print(f"\n{'='*78}\nDAY 3 — FCFF (ACTUALS + {years}-YEAR FORECAST)\n{'='*78}")
    hist_fcff_tidy_df, forecast_fcff_tidy_df = build_fcff_universe(raw_wide_dict, bundles_by_ticker, years=years)
    forecast_summary = (
        forecast_fcff_tidy_df[forecast_fcff_tidy_df["line_item"] == "FCFF"]
        .pivot(index="ticker", columns="forecast_year", values="value")
    )
    print("\nForecast FCFF by year ($):")
    print(forecast_summary.to_string())

    print(f"\n{'='*78}\nLOADING TO SQL ({DB_PATH.name})\n{'='*78}")
    conn = get_sql_engine()
    load_tables_to_sql(
        {
            "company_profiles": profiles_df,
            "raw_financials": raw_tidy_df,
            "historical_metrics": metrics_tidy_df,
            "fcff_actuals": hist_fcff_tidy_df,
            "fcff_forecast": forecast_fcff_tidy_df,
        },
        conn,
    )
    conn.close()

    return {
        "profiles_df": profiles_df,
        "raw_tidy_df": raw_tidy_df,
        "raw_wide_dict": raw_wide_dict,
        "bundles_by_ticker": bundles_by_ticker,
        "metrics_tidy_df": metrics_tidy_df,
        "hist_fcff_tidy_df": hist_fcff_tidy_df,
        "forecast_fcff_tidy_df": forecast_fcff_tidy_df,
    }


if __name__ == "__main__":
    run_days_1_to_3()
