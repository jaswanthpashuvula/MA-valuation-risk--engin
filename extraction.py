"""
================================================================================
 EXTRACTION MODULE  —  Week 1 / Day 1
 "Pull live Income Statement, Balance Sheet, and Cash Flow data for a target
  company and its peer set via yfinance."
================================================================================

DESIGN NOTES (why the module is shaped this way)
--------------------------------------------------------------------------
1. WIDE vs. TIDY outputs
   yfinance natively returns "wide" DataFrames: rows = line items, columns =
   period-end dates. That shape is convenient for financial *calculation*
   (Day 2/3 modules consume it directly), but it's a poor fit for a SQL
   table because line items differ across companies (a bank has no "Capital
   Expenditure" the way an industrial does) and yfinance's label set drifts
   over time. So this module also produces a "tidy" / long-format table:

        ticker | statement_type | period_type | period_end | line_item | value

   That schema never needs a migration when a new line item shows up — it's
   the standard EAV-style shape for heterogeneous financial statement data
   and maps 1:1 onto `DataFrame.to_sql(..., if_exists="append")`.

2. PER-TICKER FAULT ISOLATION
   In a peer-comp run, one bad/delisted ticker should not kill the batch.
   `extract_universe()` wraps each ticker in try/except and logs + skips
   failures, returning whatever succeeded.

3. MODULARITY
   Every function does exactly one job (fetch profile, fetch statements,
   melt to tidy) so Day 2/3 modules — and later, a SQL loader — can import
   and reuse them independently.
================================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. COMPANY PROFILE  (single row of descriptive + market data per ticker)
# ==============================================================================
def fetch_company_profile(ticker: str) -> dict:
    """
    Pulls descriptive + live market data needed later for WACC/DCF (beta,
    market cap, share count, price) plus sector/industry for peer grouping.

    Financial purpose: this is the "market-observable" input set — as
    opposed to the statement data below, which is *reported/historical* —
    so it's kept in its own table (one row per ticker, not time-series).
    """
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    profile = {
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
    return profile


# ==============================================================================
# 2. RAW STATEMENT EXTRACTION  (wide format — used for calculation)
# ==============================================================================
def fetch_raw_statements(ticker: str, period_type: str = "annual") -> dict[str, pd.DataFrame]:
    """
    Pulls the three core financial statements for `ticker` and returns them
    as wide DataFrames (index = line item, columns = period-end date),
    sorted chronologically ascending so that later .diff()/.pct_change()
    growth math (Day 2) reads left-to-right = oldest -> newest, matching how
    an analyst would read a model.

    period_type: "annual" -> uses income_stmt / balance_sheet / cashflow
                 "quarterly" -> uses quarterly_income_stmt / etc.
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


# ==============================================================================
# 3. TIDY / LONG-FORMAT TRANSFORM  (SQL-ready)
# ==============================================================================
def melt_statement_to_tidy(
    df: pd.DataFrame,
    ticker: str,
    statement_type: str,
    period_type: str = "annual",
) -> pd.DataFrame:
    """
    Reshapes one wide statement DataFrame into the tidy long format described
    at the top of this module.

    Programming logic: `DataFrame.melt` is the pandas primitive for wide ->
    long reshaping; we first move the line-item index into a column
    (`reset_index`) so melt can treat every period column uniformly.

    Financial purpose: produces one fact row per (ticker, statement,
    line-item, period) — the atomic grain a SQL analyst or downstream BI
    tool would query ("give me Total Revenue for AAPL by year"), independent
    of how many/which line items a given company reports.
    """
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

    # Drop rows with no reported value (common for line items that don't
    # apply to a given company/period) — keeps the SQL fact table dense.
    tidy = tidy.dropna(subset=["value"]).reset_index(drop=True)
    return tidy


# ==============================================================================
# 4. UNIVERSE-LEVEL ORCHESTRATION  (target + peers, fault-isolated)
# ==============================================================================
def extract_universe(
    tickers: list[str], period_type: str = "annual"
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    """
    Runs the full Day-1 extraction across a list of tickers (target + peers).

    Returns
    -------
    profiles_df   : one row per ticker (market/descriptive data)
    raw_tidy_df   : long-format fact table, all statements, all tickers
                    (this is what gets loaded into SQL)
    raw_wide_dict : {ticker: {"income_stmt": df, "balance_sheet": df, "cash_flow": df}}
                    (this is what Day 2/3 calculation modules consume directly —
                    no need to re-fetch or pivot back out of SQL mid-pipeline)
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
            # Fault isolation: log and continue so one bad ticker (e.g. a
            # delisting or a rate-limit blip) doesn't abort the whole batch.
            logger.warning("Skipping '%s' — extraction failed: %s", ticker, exc)
            continue

    profiles_df = pd.DataFrame(profiles)
    raw_tidy_df = pd.concat(tidy_frames, ignore_index=True) if tidy_frames else pd.DataFrame()

    return profiles_df, raw_tidy_df, raw_wide_dict


if __name__ == "__main__":
    # Quick standalone smoke test: `python extraction.py`
    from config import UNIVERSE, PERIOD_TYPE

    profiles_df, raw_tidy_df, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    print("\n--- Company Profiles ---")
    print(profiles_df)
    print(f"\n--- Tidy Fact Table: {len(raw_tidy_df):,} rows ---")
    print(raw_tidy_df.head(10))
