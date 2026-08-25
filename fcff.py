"""
Free Cash Flow to Firm calculations — the formula itself plus a historical
version (reconciles against reported statements, good sanity check) and a
forecast version (5-year projection built on metrics.py's averages).

    FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC

FCFF is unlevered — cash available to both debt and equity holders before
any financing effects — which is why it gets discounted at WACC rather than
cost of equity on its own.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from metrics import find_line_item


def calculate_nopat(ebit: float | pd.Series, tax_rate: float | pd.Series) -> float | pd.Series:
    """NOPAT = EBIT x (1 - tax rate)."""
    return ebit * (1 - tax_rate)


def calculate_fcff(
    ebit: float | pd.Series,
    tax_rate: float | pd.Series,
    d_and_a: float | pd.Series,
    capex: float | pd.Series,
    delta_nwc: float | pd.Series,
) -> float | pd.Series:
    """
    FCFF = EBIT(1-t) + D&A - CapEx + delta_nwc

    capex should be a positive magnitude. delta_nwc keeps the cash-flow-
    statement sign (positive = cash inflow), so it gets added, not subtracted.
    """
    nopat = calculate_nopat(ebit, tax_rate)
    return nopat + d_and_a - capex + delta_nwc


def calculate_historical_fcff(statements: dict[str, pd.DataFrame], tax_rate_series: pd.Series) -> pd.DataFrame:
    """
    Reconstructs actual FCFF for every period the company reported, using
    real line items rather than averages — worth checking this against the
    cash flow statement before trusting the forecast built on top of it.
    """
    income_stmt, cash_flow = statements["income_stmt"], statements["cash_flow"]

    ebit = find_line_item(income_stmt, ["EBIT", "Operating Income"])
    d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
    capex = find_line_item(cash_flow, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"]).abs()
    delta_nwc = find_line_item(cash_flow, ["Change In Working Capital", "Changes In Working Capital"])

    df = pd.DataFrame({"ebit": ebit, "d_and_a": d_and_a, "capex": capex, "delta_nwc": delta_nwc})
    df["tax_rate"] = tax_rate_series.reindex(df.index)
    df["tax_rate"] = df["tax_rate"].fillna(df["tax_rate"].mean() if df["tax_rate"].notna().any() else 0.21)

    df["nopat"] = calculate_nopat(df["ebit"], df["tax_rate"])
    df["fcff"] = calculate_fcff(df["ebit"], df["tax_rate"], df["d_and_a"], df["capex"], df["delta_nwc"])

    return df.dropna(subset=["ebit"])


def project_fcff(last_revenue: float, averages: dict, years: int = 5) -> pd.DataFrame:
    """
    Projects Revenue -> EBITDA -> EBIT -> NOPAT -> FCFF forward `years`
    periods, holding every driver at its historical average (steady-state
    base case — a reasonable starting point before layering in analyst
    overrides like margin expansion or a growth fade toward the terminal rate).
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
        revenue_t = revenue_t * (1 + g)
        ebitda_t = revenue_t * ebitda_margin
        da_t = revenue_t * da_pct
        ebit_t = ebitda_t - da_t
        capex_t = revenue_t * capex_pct
        delta_nwc_t = revenue_t * nwc_pct

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


def historical_fcff_to_tidy(ticker: str, hist_fcff_df: pd.DataFrame) -> pd.DataFrame:
    """Long format: ticker | period_end | line_item | value."""
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
    """Long format: ticker | forecast_year | line_item | value."""
    tidy = forecast_df.reset_index().melt(id_vars="Year", var_name="line_item", value_name="value")
    tidy.insert(0, "ticker", ticker.upper())
    tidy = tidy.rename(columns={"Year": "forecast_year"})
    tidy["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()
    return tidy


def build_fcff_universe(
    raw_wide_dict: dict[str, dict[str, pd.DataFrame]],
    bundles_by_ticker: dict,
    years: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Runs historical reconciliation + forecast for every ticker, returns two SQL-ready tidy tables."""
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
    from config import PERIOD_TYPE, PROJECTION_YEARS, UNIVERSE
    from extraction import extract_universe
    from metrics import build_metrics_universe

    _, _, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    bundles_by_ticker, _ = build_metrics_universe(raw_wide_dict)

    for ticker, statements in raw_wide_dict.items():
        bundle = bundles_by_ticker[ticker]
        hist_df = calculate_historical_fcff(statements, bundle["series"]["effective_tax_rate"])
        print(f"\n--- {ticker}: historical FCFF (reported actuals) ---")
        print(hist_df[["ebit", "d_and_a", "capex", "delta_nwc", "fcff"]])

        revenue = find_line_item(statements["income_stmt"], ["Total Revenue"])
        forecast_df = project_fcff(revenue.dropna().iloc[-1], bundle["averages"], years=PROJECTION_YEARS)
        print(f"\n--- {ticker}: 5-year FCFF forecast ---")
        print(forecast_df[["Revenue", "EBITDA", "EBIT", "NOPAT", "CapEx", "FCFF"]])
