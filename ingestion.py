"""
Pulls Income Statement, Balance Sheet, and Cash Flow data from yfinance for a
target ticker plus its peer group, and reshapes it into a long/tidy format
that's easy to load into a SQL table.

Statements come back from yfinance as "wide" DataFrames — line items as rows,
period dates as columns. That's fine for the actual math (metrics.py and
valuation.py both use it directly), but it's a bad fit for a database table since
companies don't all report the same line items and yfinance's labels change
between versions. So this module also melts everything into:

    ticker | statement_type | period_type | period_end | line_item | value

which is just a standard fact-table shape — one row per data point, no
schema changes needed when a new line item shows up.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def fetch_company_profile(ticker: str) -> dict:
    """Market/descriptive data for one ticker — beta, market cap, sector, etc."""
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    return {
        "ticker": ticker.upper(),
        "short_name": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency", "USD"),
        "beta": info.get("beta") or info.get("beta3Year"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def fetch_raw_statements(ticker: str, period_type: str = "annual") -> dict[str, pd.DataFrame]:
    """
    Returns the three core statements as wide DataFrames, sorted so columns
    run oldest -> newest (makes pct_change()/diff() calls read naturally
    later on).
    """
    tk = yf.Ticker(ticker)

    if period_type == "quarterly":
        income_stmt = tk.quarterly_income_stmt
        balance_sheet = tk.quarterly_balance_sheet
        cash_flow = tk.quarterly_cashflow
    else:
        income_stmt = tk.income_stmt
        balance_sheet = tk.balance_sheet
        cash_flow = tk.cashflow

    if income_stmt is None or income_stmt.empty:
        raise ValueError(f"No {period_type} income statement returned for '{ticker}'.")

    return {
        "income_stmt": income_stmt.sort_index(axis=1),
        "balance_sheet": balance_sheet.sort_index(axis=1),
        "cash_flow": cash_flow.sort_index(axis=1),
    }


def melt_statement_to_tidy(
    df: pd.DataFrame,
    ticker: str,
    statement_type: str,
    period_type: str = "annual",
) -> pd.DataFrame:
    """Reshapes one wide statement into the long format described up top."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["ticker", "statement_type", "period_type", "period_end", "line_item", "value"]
        )

    tidy = (
        df.reset_index()
        .rename(columns={"index": "line_item"})
        .melt(id_vars="line_item", var_name="period_end", value_name="value")
    )
    tidy.insert(0, "ticker", ticker.upper())
    tidy.insert(1, "statement_type", statement_type)
    tidy.insert(2, "period_type", period_type)
    tidy["period_end"] = pd.to_datetime(tidy["period_end"]).dt.date
    tidy["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()

    # drop line items a company didn't report for a given period, keeps the table dense
    return tidy.dropna(subset=["value"]).reset_index(drop=True)


def extract_universe(
    tickers: list[str], period_type: str = "annual"
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    """
    Runs extraction across a list of tickers. One bad/delisted ticker doesn't
    stop the rest of the batch — it just gets logged and skipped.

    Returns company profiles, the combined tidy fact table (ready for SQL),
    and a dict of the wide statements per ticker (what the metrics/fcff
    modules actually calculate off of).
    """
    profiles, tidy_frames = [], []
    raw_wide_dict: dict[str, dict[str, pd.DataFrame]] = {}

    for ticker in tickers:
        try:
            logger.info("Extracting %s ...", ticker)
            profiles.append(fetch_company_profile(ticker))

            statements = fetch_raw_statements(ticker, period_type=period_type)
            raw_wide_dict[ticker.upper()] = statements

            for statement_type, df in statements.items():
                tidy_frames.append(melt_statement_to_tidy(df, ticker, statement_type, period_type))

        except Exception as exc:
            logger.warning("Skipping '%s' — extraction failed: %s", ticker, exc)
            continue

    profiles_df = pd.DataFrame(profiles)
    raw_tidy_df = pd.concat(tidy_frames, ignore_index=True) if tidy_frames else pd.DataFrame()

    return profiles_df, raw_tidy_df, raw_wide_dict


if __name__ == "__main__":
    from config import PERIOD_TYPE, UNIVERSE

    profiles_df, raw_tidy_df, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    print("\n--- Company Profiles ---")
    print(profiles_df)
    print(f"\n--- Tidy Fact Table: {len(raw_tidy_df):,} rows ---")
    print(raw_tidy_df.head(10))
