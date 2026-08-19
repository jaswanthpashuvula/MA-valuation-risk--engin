"""
================================================================================
 FCFF MODULE  —  Week 1 / Day 3
 "The exact financial formulas coded into functions to calculate Free Cash
  Flow to Firm (FCFF)" — both the HISTORICAL (actuals, for sanity-checking
  the model against reported cash flow) and FORECAST (5-year projection that
  feeds the DCF in Week 1 Day 4-5) versions.
================================================================================

THE CORE FORMULA
--------------------------------------------------------------------------
    FCFF = EBIT x (1 - Tax Rate)      <- NOPAT: after-tax operating profit
         + D&A                        <- add back non-cash depreciation/amortization
         - CapEx                      <- subtract cash reinvested in fixed assets
         + Delta_NWC                  <- add the cash-flow-signed change in working capital
                                          (source's sign convention: +ve = cash inflow)

FCFF is *unlevered* — cash flow available to ALL capital providers (debt +
equity) before any financing effects (interest, dividends, buybacks, debt
paydown). That's precisely why it's discounted at WACC (blended cost of all
capital) rather than at the cost of equity alone — a distinction the Day 4/5
DCF module will rely on directly.
================================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from metrics import find_line_item


# ==============================================================================
# 1. ATOMIC FORMULA FUNCTIONS
# ==============================================================================
def calculate_nopat(ebit: float | pd.Series, tax_rate: float | pd.Series) -> float | pd.Series:
    """
    NOPAT (Net Operating Profit After Tax) = EBIT x (1 - Tax Rate)

    Strips out the financing-driven tax shield from interest expense so the
    resulting profit figure is capital-structure-neutral — the starting
    point for any unlevered cash flow metric.
    """
    return ebit * (1 - tax_rate)


def calculate_fcff(
    ebit: float | pd.Series,
    tax_rate: float | pd.Series,
    d_and_a: float | pd.Series,
    capex: float | pd.Series,
    delta_nwc: float | pd.Series,
) -> float | pd.Series:
    """
    FCFF = EBIT(1 - t) + D&A - CapEx + Delta_NWC

    Parameters
    ----------
    ebit        : Earnings Before Interest & Tax
    tax_rate    : effective or statutory tax rate (decimal, e.g. 0.21)
    d_and_a     : Depreciation & Amortization (non-cash add-back), positive
    capex       : Capital Expenditure, POSITIVE magnitude (cash outflow)
    delta_nwc   : Change in Net Working Capital, CASH-FLOW-STATEMENT SIGN
                  (+ve = cash inflow from working capital, -ve = cash used
                  funding working-capital growth) — added, not subtracted,
                  because the sign already encodes the cash direction.
    """
    nopat = calculate_nopat(ebit, tax_rate)
    return nopat + d_and_a - capex + delta_nwc


# ==============================================================================
# 2. HISTORICAL (ACTUAL) FCFF — sanity-check against reported statements
# ==============================================================================
def calculate_historical_fcff(statements: dict[str, pd.DataFrame], tax_rate_series: pd.Series) -> pd.DataFrame:
    """
    Reconstructs actual FCFF for every historical period a company reported,
    using the exact line items (not averages) — this is the "did our formula
    reconcile to reality" check before trusting the forecast built on top of it.

    Returns a wide DataFrame indexed by period-end with EBIT, D&A, CapEx,
    Delta_NWC, NOPAT, and FCFF columns.
    """
    income_stmt, cash_flow = statements["income_stmt"], statements["cash_flow"]

    ebit = find_line_item(income_stmt, ["EBIT", "Operating Income"])
    d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
    capex = find_line_item(cash_flow, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"]).abs()
    delta_nwc = find_line_item(cash_flow, ["Change In Working Capital", "Changes In Working Capital"])

    # Align every series to EBIT's periods (the anchor) and to the supplied
    # tax-rate series so arithmetic below is index-safe even if a line item
    # is missing a period some other statement reports.
    df = pd.DataFrame({"ebit": ebit, "d_and_a": d_and_a, "capex": capex, "delta_nwc": delta_nwc})
    df["tax_rate"] = tax_rate_series.reindex(df.index)
    df["tax_rate"] = df["tax_rate"].fillna(df["tax_rate"].mean() if df["tax_rate"].notna().any() else 0.21)

    df["nopat"] = calculate_nopat(df["ebit"], df["tax_rate"])
    df["fcff"] = calculate_fcff(df["ebit"], df["tax_rate"], df["d_and_a"], df["capex"], df["delta_nwc"])

    return df.dropna(subset=["ebit"])


# ==============================================================================
# 3. FORECAST FCFF — 5-year projection driven by Day 2's historical averages
# ==============================================================================
def project_fcff(
    last_revenue: float,
    averages: dict,
    years: int = 5,
) -> pd.DataFrame:
    """
    Projects Revenue -> EBITDA -> EBIT -> NOPAT -> FCFF for `years` forward
    periods using the constant historical-average operating assumptions
    computed in Day 2 (`metrics.build_metrics_bundle`).

    This is a "steady-state" base case: every driver (growth, margin, CapEx
    intensity, NWC intensity, tax rate) is held at its historical average
    for the full explicit horizon. It is the standard starting point before
    layering in analyst overrides (e.g. fading growth toward the terminal
    rate, or margin expansion assumptions) in a later iteration.

    Returns a wide DataFrame indexed Year 1..N — this is what the Day 4/5
    DCF module discounts at WACC.
    """
    g = averages["avg_revenue_growth"]
    ebitda_margin = averages["avg_ebitda_margin"]
    da_pct = averages["avg_da_to_revenue"]
    capex_pct = averages["avg_capex_to_revenue"]
    nwc_pct = averages["avg_nwc_change_to_revenue"]
    tax_rate = averages["avg_tax_rate"]

    rows = []
    revenue_t = last_revenue
    for yr in range(1, years + 1):
        revenue_t = revenue_t * (1 + g)                  # top-line driver
        ebitda_t = revenue_t * ebitda_margin              # operating profitability
        da_t = revenue_t * da_pct                          # non-cash charge, scaled to revenue
        ebit_t = ebitda_t - da_t                            # EBITDA -> EBIT bridge
        capex_t = revenue_t * capex_pct                    # reinvestment in fixed assets
        delta_nwc_t = revenue_t * nwc_pct                  # working-capital cash impact (signed)

        nopat_t = calculate_nopat(ebit_t, tax_rate)
        fcff_t = calculate_fcff(ebit_t, tax_rate, da_t, capex_t, delta_nwc_t)

        rows.append(
            {
                "Year": yr,
                "Revenue": revenue_t,
                "EBITDA": ebitda_t,
                "D&A": da_t,
                "EBIT": ebit_t,
                "NOPAT": nopat_t,
                "CapEx": capex_t,
                "Delta_NWC": delta_nwc_t,
                "FCFF": fcff_t,
            }
        )

    return pd.DataFrame(rows).set_index("Year")


# ==============================================================================
# 4. TIDY / LONG-FORMAT TRANSFORMS  (SQL-ready)
# ==============================================================================
def historical_fcff_to_tidy(ticker: str, hist_fcff_df: pd.DataFrame) -> pd.DataFrame:
    """Long-format actuals: ticker | period_end | line_item | value."""
    tidy = (
        hist_fcff_df.reset_index()
        .rename(columns={"index": "period_end"})
        .melt(id_vars="period_end", var_name="line_item", value_name="value")
    )
    tidy.insert(0, "ticker", ticker.upper())
    tidy["period_end"] = pd.to_datetime(tidy["period_end"]).dt.date
    tidy["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()
    return tidy.dropna(subset=["value"])


def forecast_fcff_to_tidy(ticker: str, forecast_df: pd.DataFrame) -> pd.DataFrame:
    """Long-format forecast: ticker | forecast_year | line_item | value."""
    tidy = forecast_df.reset_index().melt(id_vars="Year", var_name="line_item", value_name="value")
    tidy.insert(0, "ticker", ticker.upper())
    tidy = tidy.rename(columns={"Year": "forecast_year"})
    tidy["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()
    return tidy


# ==============================================================================
# 5. UNIVERSE-LEVEL ORCHESTRATION
# ==============================================================================
def build_fcff_universe(
    raw_wide_dict: dict[str, dict[str, pd.DataFrame]],
    bundles_by_ticker: dict,
    years: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Runs historical reconciliation + 5-year forecast FCFF for every ticker,
    returning two SQL-ready tidy tables (historical actuals, forward forecast).
    """
    hist_tidy_frames, forecast_tidy_frames = [], []

    for ticker, statements in raw_wide_dict.items():
        bundle = bundles_by_ticker[ticker]
        tax_rate_series = bundle["series"]["effective_tax_rate"]

        hist_fcff_df = calculate_historical_fcff(statements, tax_rate_series)
        hist_tidy_frames.append(historical_fcff_to_tidy(ticker, hist_fcff_df))

        revenue = find_line_item(statements["income_stmt"], ["Total Revenue", "Operating Revenue", "Revenue"])
        last_revenue = revenue.dropna().iloc[-1]
        forecast_df = project_fcff(last_revenue, bundle["averages"], years=years)
        forecast_tidy_frames.append(forecast_fcff_to_tidy(ticker, forecast_df))

    hist_tidy_df = pd.concat(hist_tidy_frames, ignore_index=True) if hist_tidy_frames else pd.DataFrame()
    forecast_tidy_df = pd.concat(forecast_tidy_frames, ignore_index=True) if forecast_tidy_frames else pd.DataFrame()
    return hist_tidy_df, forecast_tidy_df


if __name__ == "__main__":
    # Standalone smoke test: `python fcff.py` (chains off extraction.py + metrics.py)
    from config import UNIVERSE, PERIOD_TYPE, PROJECTION_YEARS
    from extraction import extract_universe
    from metrics import build_metrics_universe

    _, _, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    bundles_by_ticker, _ = build_metrics_universe(raw_wide_dict)

    for ticker, statements in raw_wide_dict.items():
        bundle = bundles_by_ticker[ticker]
        hist_df = calculate_historical_fcff(statements, bundle["series"]["effective_tax_rate"])
        print(f"\n--- {ticker}: Historical FCFF (reported actuals) ---")
        print(hist_df[["ebit", "d_and_a", "capex", "delta_nwc", "fcff"]])

        revenue = find_line_item(statements["income_stmt"], ["Total Revenue"])
        forecast_df = project_fcff(revenue.dropna().iloc[-1], bundle["averages"], years=PROJECTION_YEARS)
        print(f"\n--- {ticker}: 5-Year FCFF Forecast ---")
        print(forecast_df[["Revenue", "EBITDA", "EBIT", "NOPAT", "CapEx", "FCFF"]])
