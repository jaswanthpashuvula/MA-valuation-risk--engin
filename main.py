"""
Runs ingestion -> metrics -> valuation end to end for the target/peer universe
in config.py, then loads the results into a SQL database.

Using SQLite here so the project runs without any setup. Everything upstream
already outputs plain tidy DataFrames, so pointing this at Postgres/MySQL
later just means swapping get_sql_engine() for a real connection — no other
changes needed.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from config import DB_PATH, PERIOD_TYPE, PROJECTION_YEARS, UNIVERSE
from ingestion import extract_universe
from valuation import build_fcff_universe
from metrics import build_metrics_universe


def get_sql_engine() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def load_tables_to_sql(tables: dict[str, pd.DataFrame], conn: sqlite3.Connection) -> None:
    for table_name, df in tables.items():
        if df is None or df.empty:
            continue
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  -> loaded {len(df):>6,} rows into '{table_name}'")


def run_pipeline(tickers: list[str] = UNIVERSE, period_type: str = PERIOD_TYPE, years: int = PROJECTION_YEARS):
    print(f"\nExtracting: {tickers}")
    profiles_df, raw_tidy_df, raw_wide_dict = extract_universe(tickers, period_type=period_type)
    print(f"Extracted {len(raw_wide_dict)}/{len(tickers)} tickers successfully.")

    print("\nCalculating historical metrics...")
    bundles_by_ticker, metrics_tidy_df = build_metrics_universe(raw_wide_dict)
    for ticker, bundle in bundles_by_ticker.items():
        avg = bundle["averages"]
        print(f"  {ticker:6s} | Rev Growth {avg['avg_revenue_growth']:>7.2%} | "
              f"EBITDA Margin {avg['avg_ebitda_margin']:>7.2%} | "
              f"CapEx/Rev {avg['avg_capex_to_revenue']:>6.2%}")

    print(f"\nRunning FCFF (actuals + {years}-year forecast)...")
    hist_fcff_tidy_df, forecast_fcff_tidy_df = build_fcff_universe(raw_wide_dict, bundles_by_ticker, years=years)
    forecast_summary = (
        forecast_fcff_tidy_df[forecast_fcff_tidy_df["line_item"] == "FCFF"]
        .pivot(index="ticker", columns="forecast_year", values="value")
    )
    print("\nForecast FCFF by year ($):")
    print(forecast_summary.to_string())

    print(f"\nLoading to SQL ({DB_PATH.name})...")
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
    run_pipeline()
