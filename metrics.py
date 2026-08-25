"""
Historical margin/ratio calculations — revenue growth, EBITDA margin, CapEx
intensity, D&A intensity, working capital swings, and effective tax rate —
built from the wide statements ingestion.py returns.

find_line_item() is the one place that deals with yfinance's label drift
(e.g. some tickers report "Capital Expenditure", others "Capital
Expenditures"). Every calc below goes through it instead of indexing a
DataFrame with a hardcoded string, so a missing/renamed line item degrades
to NaN for that one metric instead of crashing the whole run.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


def find_line_item(df: pd.DataFrame, aliases: list[str]) -> pd.Series:
    """Looks up a row by trying each alias, case-insensitive, exact then substring match."""
    if df is None or df.empty:
        return pd.Series(dtype=float)

    idx_lower = {str(i).lower(): i for i in df.index}

    for alias in aliases:
        if alias.lower() in idx_lower:
            return df.loc[idx_lower[alias.lower()]].astype(float)

    for alias in aliases:
        for lower_label, original_label in idx_lower.items():
            if alias.lower() in lower_label:
                return df.loc[original_label].astype(float)

    return pd.Series(np.nan, index=df.columns)


def calculate_revenue_growth(income_stmt: pd.DataFrame) -> pd.Series:
    """YoY revenue growth — the main driver the forecast scales off of."""
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    return revenue.pct_change()


def calculate_ebitda_margin(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """EBITDA / Revenue. Falls back to EBIT + D&A if EBITDA isn't reported directly."""
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    ebitda = find_line_item(income_stmt, ["EBITDA", "Normalized EBITDA"])

    if ebitda.isna().all():
        ebit = find_line_item(income_stmt, ["EBIT", "Operating Income"])
        d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
        ebitda = ebit.add(d_and_a, fill_value=0)

    return ebitda / revenue


def calculate_capex_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """CapEx / Revenue. yfinance reports CapEx as a negative cash outflow, so take abs()."""
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    capex = find_line_item(cash_flow, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"])
    return capex.abs() / revenue


def calculate_da_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """D&A / Revenue — used both for the EBITDA->EBIT bridge and the FCFF add-back."""
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    d_and_a = find_line_item(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
    return d_and_a / revenue


def calculate_nwc_change_to_revenue(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.Series:
    """
    Change in net working capital / revenue. Keeps the cash-flow-statement
    sign convention (positive = cash inflow) so valuation.py can just add it.
    """
    revenue = find_line_item(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"])
    delta_nwc = find_line_item(cash_flow, ["Change In Working Capital", "Changes In Working Capital"])
    return delta_nwc / revenue


def calculate_effective_tax_rate(income_stmt: pd.DataFrame) -> pd.Series:
    """Tax Provision / Pretax Income — used instead of the statutory rate where available."""
    pretax_income = find_line_item(income_stmt, ["Pretax Income", "Income Before Tax"])
    tax_provision = find_line_item(income_stmt, ["Tax Provision", "Income Tax Expense"])
    return (tax_provision / pretax_income).replace([np.inf, -np.inf], np.nan)


def build_metrics_bundle(ticker: str, statements: dict[str, pd.DataFrame]) -> dict:
    """
    Runs all the metric calcs for one ticker and returns both the full
    historical series (for a sanity check) and floored/capped averages
    (what the forecast actually uses). The floor/cap guards against a single
    weird year — a one-off writedown or working-capital swing — skewing a
    3-4 year average into something unusable.
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


def build_metrics_tidy(metrics_bundle: dict) -> pd.DataFrame:
    """Long format: ticker | period_end | metric_name | value. Joins to the raw facts table on ticker + period_end."""
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


def build_metrics_universe(raw_wide_dict: dict[str, dict[str, pd.DataFrame]]) -> tuple[dict, pd.DataFrame]:
    """Runs the metrics calc for every ticker ingestion.py pulled and returns per-ticker bundles + one combined tidy table."""
    bundles_by_ticker, tidy_frames = {}, []

    for ticker, statements in raw_wide_dict.items():
        bundle = build_metrics_bundle(ticker, statements)
        bundles_by_ticker[ticker] = bundle
        tidy_frames.append(build_metrics_tidy(bundle))

    metrics_tidy_df = pd.concat(tidy_frames, ignore_index=True) if tidy_frames else pd.DataFrame()
    return bundles_by_ticker, metrics_tidy_df


if __name__ == "__main__":
    from config import PERIOD_TYPE, UNIVERSE
    from ingestion import extract_universe

    _, _, raw_wide_dict = extract_universe(UNIVERSE, period_type=PERIOD_TYPE)
    bundles_by_ticker, metrics_tidy_df = build_metrics_universe(raw_wide_dict)

    for ticker, bundle in bundles_by_ticker.items():
        print(f"\n--- {ticker}: historical average metrics ---")
        for k, v in bundle["averages"].items():
            print(f"  {k:28s}: {v:>8.2%}")
