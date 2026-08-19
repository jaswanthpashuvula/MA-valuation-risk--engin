"""
================================================================================
 METRICS MODULE  —  Week 1 / Day 2
 "Calculate historical margins" (revenue growth, EBITDA margin, CapEx/Revenue,
  D&A/Revenue, Change-in-NWC/Revenue, effective tax rate) for the target and
  every peer, from the wide statement data Day 1 extracted.
================================================================================

DESIGN NOTES
--------------------------------------------------------------------------
- `find_line_item()` is the single point of contact with yfinance's label
  drift. Every calculation function below goes through it rather than
  indexing statements directly with a hardcoded string — this is what makes
  the module resilient to a company not reporting "EBIT" line-by-line, or a
  yfinance version renaming "Capital Expenditure" to "Capital Expenditures".
- Every metric function returns a full historical pandas Series (so you can
  inspect trend/volatility, not just an average) AND the module exposes a
  `summarize_averages()` helper that collapses each Series to the single
  number Day 3's forecast will actually consume.
- `build_metrics_tidy()` mirrors extraction.py's tidy pattern
  (ticker | period_end | metric_name | value) so historical margins land in
  their own clean SQL fact table, joinable to the raw statement facts on
  (ticker, period_end).
================================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ==============================================================================
# 1. DEFENSIVE LINE-ITEM LOOKUP
# ==============================================================================
def find_line_item(df: pd.DataFrame, aliases: list[str]) -> pd.Series:
    """
    Scans `df.index` for the first case-insensitive exact or substring match
    against a prioritized list of `aliases`, returning that row as a float
    Series indexed by period-end date.

    Programming logic: avoids a hard KeyError crash when a label varies by
    issuer/version; instead fails soft (returns an all-NaN Series aligned to
    df's columns) so downstream ratio math produces NaN for that one metric
    rather than halting the whole pipeline.
    """
    if df is None or df.empty:
        return pd.Series(dtype=float)

    idx_lower = {str(i).lower(): i for i in df.index}

    for alias in aliases:  # Pass 1: exact match
        if alias.lower() in idx_lower:
            return df.loc[idx_lower[alias.lower()]].astype(float)

    for alias in aliases:  # Pass 2: substring match (catches minor label variants)
        for lower_label, original_label in idx_lower.items():
            if alias.lower() in lower_label:
                return df.loc[original_label].astype(float)

    return pd.Series(np.nan, index=df.columns)


# ==============================================================================
# 2. INDIVIDUAL METRIC CALCULATIONS
# ==============================================================================
def calculate_revenue_growth(income_stmt: pd.DataFrame) -> pd.Series:
    """
    YoY Revenue Growth = (Revenue_t / Revenue_t-1) - 1

    Financial purpose: the primary top-line driver for the FCFF forecast —
    everything in a simple 3-statement-lite model (EBITDA, CapEx, NWC) is
    scaled off projected revenue, so this is the single most important
    historical average the model computes.
    """
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    return revenue.pct_change()


def calculate_ebitda_margin(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """
    EBITDA Margin = EBITDA / Revenue

    EBITDA is used directly if Yahoo reports it; otherwise reconstructed as
    EBIT + D&A (D&A is added back because EBIT already has it deducted as an
    operating expense — reversing nets out to earnings before that non-cash
    charge).
    """
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    ebitda = find_line_item(income_stmt, ["EBITDA", "Normalized EBITDA"])

    if ebitda.isna().all():
        ebit = find_line_item(income_stmt, ["EBIT", "Operating Income"])
        d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
        ebitda = ebit.add(d_and_a, fill_value=0)

    return ebitda / revenue


def calculate_capex_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """
    CapEx / Revenue — capital intensity ratio.

    CapEx is reported by yfinance as a negative number (cash outflow in the
    investing section); we take the absolute value so the ratio reads as a
    positive percentage of revenue, matching how it's discussed in IC memos
    ("CapEx runs ~5% of revenue").
    """
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    capex = find_line_item(cash_flow, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"])
    return capex.abs() / revenue


def calculate_da_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """D&A / Revenue — feeds both the EBITDA->EBIT bridge and the FCFF non-cash add-back."""
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
    return d_and_a / revenue


def calculate_nwc_change_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """
    Change in Net Working Capital / Revenue.

    Sign convention: yfinance's "Change In Working Capital" is already a
    *cash-flow-statement* figure (positive = cash inflow from working
    capital releasing, negative = cash tied up funding growth) — this
    module preserves that sign so Day 3's FCFF formula can add it directly
    rather than re-deriving the sign convention.
    """
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    delta_nwc = find_line_item(cash_flow, ["Change In Working Capital", "Changes In Working Capital"])
    return delta_nwc / revenue


def calculate_effective_tax_rate(income_stmt: pd.DataFrame) -> pd.Series:
    """
    Effective Tax Rate = Tax Provision / Pretax Income.

    Used (rather than the 21% statutory rate) to NOPAT-ize EBIT, since it
    reflects the company's actual historical cash tax burden including
    credits, foreign mix, and other permanent differences.
    """
    pretax_income = find_line_item(income_stmt, ["Pretax Income", "Income Before Tax"])
    tax_provision = find_line_item(income_stmt, ["Tax Provision", "Income Tax Expense"])
    return (tax_provision / pretax_income).replace([np.inf, -np.inf], np.nan)


# ==============================================================================
# 3. PER-TICKER METRICS BUNDLE
# ==============================================================================
def build_metrics_bundle(ticker: str, statements: dict[str, pd.DataFrame]) -> dict:
    """
    Runs every metric function above for one ticker and packages:
      - the full historical Series for each metric (for trend/QA review)
      - guardrailed historical averages (used directly by Day 3's forecast)

    Guardrails (`floor`/`cap`) exist because a single noisy year (e.g. a
    one-off impairment or divestiture-driven working-capital swing) can
    otherwise distort a 3-4 year average into an unusable forecast input —
    standard practice is to bound ratios to a plausible operating range
    rather than let outliers pass straight through.
    """
    income_stmt, cash_flow = statements["income_stmt"], statements["cash_flow"]

    series = {
        "revenue_growth": calculate_revenue_growth(income_stmt),
        "ebitda_margin": calculate_ebitda_margin(income_stmt, cash_flow),
        "capex_to_revenue": calculate_capex_to_revenue(income_stmt, cash_flow),
        "da_to_revenue": calculate_da_to_revenue(income_stmt, cash_flow),
        "nwc_change_to_revenue": calculate_nwc_change_to_revenue(income_stmt, cash_flow),
        "effective_tax_rate": calculate_effective_tax_rate(income_stmt),
    }

    def _safe_mean(s: pd.Series, floor=None, cap=None, fallback=0.0) -> float:
        clean = s.replace([np.inf, -np.inf], np.nan).dropna()
        if clean.empty:
            return fallback
        val = float(clean.mean())
        if floor is not None:
            val = max(val, floor)
        if cap is not None:
            val = min(val, cap)
        return val

    averages = {
        "avg_revenue_growth": _safe_mean(series["revenue_growth"], floor=-0.20, cap=0.60),
        "avg_ebitda_margin": _safe_mean(series["ebitda_margin"], floor=0.0, cap=0.80),
        "avg_capex_to_revenue": _safe_mean(series["capex_to_revenue"], floor=0.0, cap=0.50),
        "avg_da_to_revenue": _safe_mean(series["da_to_revenue"], floor=0.0, cap=0.50),
        "avg_nwc_change_to_revenue": _safe_mean(series["nwc_change_to_revenue"], floor=-0.30, cap=0.30),
        "avg_tax_rate": _safe_mean(series["effective_tax_rate"], floor=0.0, cap=0.45, fallback=0.21),
    }

    return {"ticker": ticker.upper(), "series": series, "averages": averages}


# ==============================================================================
# 4. TIDY / LONG-FORMAT TRANSFORM  (SQL-ready)
# ==============================================================================
def build_metrics_tidy(metrics_bundle: dict) -> pd.DataFrame:
    """
    Melts one ticker's metric Series dict into the long format:
        ticker | period_end | metric_name | value
    joinable to the Day-1 raw fact table on (ticker, period_end).
    """
    rows = []
    for metric_name, series in metrics_bundle["series"].items():
        for period_end, value in series.items():
            if pd.isna(value):
                continue
            rows.append(
                {
                    "ticker": metrics_bundle["ticker"],
                    "period_end": pd.to_datetime(period_end).date(),
                    "metric_name": metric_name,
                    "value": float(value),
                }
            )
    df = pd.DataFrame(rows)
    df["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()
    return df


# ==============================================================================
# 5. UNIVERSE-LEVEL ORCHESTRATION
# ==============================================================================
def build_metrics_universe(raw_wide_dict: dict[str, dict[str, pd.DataFrame]]) -> tuple[dict, pd.DataFrame]:
    """
    Runs the metrics pipeline across every ticker Day 1 successfully extracted.

    Returns
    -------
    bundles_by_ticker : {ticker: metrics_bundle}  — consumed directly by Day 3 (FCFF)
    metrics_tidy_df   : concatenated long-format table across the universe — SQL-ready
    """
    bundles_by_ticker, tidy_frames = {}, []

    for ticker, statements in raw_wide_dict.items():
        bundle = build_metrics_bundle(ticker, statements)
        bundles_by_ticker[ticker] = bundle
        tidy_frames.append(build_metrics_tidy(bundle))

    metrics_tidy_df = pd.concat(tidy_frames, ignore_index=True) if tidy_frames else pd.DataFrame()
    return bundles_by_ticker, metrics_tidy_df


if __name__ == "__main__":
    # Standalone smoke test: `python metrics.py` (chains off extraction.py)
    from config import UNIVERSE, PERIOD_TYPE
    from extraction import extract_universe

    _, _, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    bundles_by_ticker, metrics_tidy_df = build_metrics_universe(raw_wide_dict)

    for ticker, bundle in bundles_by_ticker.items():
        print(f"\n--- {ticker}: Historical Average Metrics ---")
        for k, v in bundle["averages"].items():
            print(f"  {k:28s}: {v:>8.2%}")
