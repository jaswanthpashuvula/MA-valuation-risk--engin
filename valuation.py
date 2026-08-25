"""
All the valuation math lives here: historical margin/ratio calculations,
the FCFF formula (applied to both actuals and a 5-year forecast), and a
Monte Carlo sensitivity check on top of the forecast.

    FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC

FCFF is unlevered — cash available to both debt and equity holders before
any financing effects — which is why it gets discounted at WACC rather than
cost of equity on its own.

find_line_item() is the one place that deals with yfinance's label drift
(e.g. some tickers report "Capital Expenditure", others "Capital
Expenditures"). Everything below goes through it instead of indexing a
DataFrame with a hardcoded string, so a missing/renamed line item degrades
to NaN for that one metric instead of crashing the whole run.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# line-item lookup
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# historical margins / ratios
# ---------------------------------------------------------------------------
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
    sign convention (positive = cash inflow) so the FCFF formula can just add it.
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
    """Long format: ticker | period_end | metric_name | value."""
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


# ---------------------------------------------------------------------------
# FCFF — historical reconciliation + forecast
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Monte Carlo sensitivity check
# ---------------------------------------------------------------------------
def get_avg_forecast_fcff(ticker: str, db_path) -> float:
    """Average forecasted FCFF for a ticker, pulled from the fcff_forecast table export.py writes."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT AVG(value) FROM fcff_forecast WHERE ticker = ? AND line_item = 'FCFF'",
            (ticker.upper(),),
        ).fetchone()
    finally:
        conn.close()

    if not row or row[0] is None:
        raise ValueError(
            f"No forecast FCFF found for '{ticker}' in {db_path}. Run main.py first."
        )
    return float(row[0])


def run_monte_carlo(
    ticker: str,
    db_path,
    iterations: int = 10000,
    growth_mean: float = 0.04,
    growth_std: float = 0.015,
    wacc_mean: float = 0.095,
    wacc_std: float = 0.01,
    seed: int | None = None,
    return_distribution: bool = False,
) -> dict:
    """
    Runs a Gordon-growth valuation `iterations` times with randomized growth
    and WACC each pass, rather than one fixed scenario. seed is left as None
    by default on purpose — a fixed seed would make every run produce the
    identical result, defeating the point of a stochastic simulation. Pass a
    seed explicitly if you need a reproducible run for testing.

    return_distribution=True adds the full array of simulated valuations to
    the result under "distribution" — visualize.py uses it to plot the
    histogram. export.append_risk_result() strips that key back out before
    writing the row to SQL, since a 10,000-element array isn't a SQL cell.
    """
    baseline_fcff = get_avg_forecast_fcff(ticker, db_path)

    rng = np.random.default_rng(seed)
    simulated_growth = rng.normal(growth_mean, growth_std, iterations)
    simulated_wacc = np.clip(rng.normal(wacc_mean, wacc_std, iterations), 0.01, None)

    # keep the denominator away from zero/negative when a draw puts WACC below growth
    spread = np.clip(simulated_wacc - simulated_growth, 0.005, None)
    valuations = np.clip(baseline_fcff * (1 + simulated_growth) / spread, 0, None)

    results = {
        "ticker": ticker.upper(),
        "iterations": iterations,
        "baseline_fcff": baseline_fcff,
        "median_valuation": float(np.percentile(valuations, 50)),
        "p25_valuation": float(np.percentile(valuations, 25)),
        "p75_valuation": float(np.percentile(valuations, 75)),
        "var_95": float(np.percentile(valuations, 5)),
    }

    print(f"Ran {iterations:,} simulation paths for {results['ticker']}")
    print(f"  Baseline forecast FCFF : {baseline_fcff:,.0f}")
    print(f"  Median valuation       : {results['median_valuation']:,.0f}")
    print(f"  25th / 75th percentile : {results['p25_valuation']:,.0f} / {results['p75_valuation']:,.0f}")
    print(f"  5th percentile (VaR)   : {results['var_95']:,.0f}")

    if return_distribution:
        results["distribution"] = valuations

    return results


if __name__ == "__main__":
    # quick standalone check — real run is driven from main.py
    from ingestion import extract_universe

    test_universe = ["AAPL", "MSFT"]
    _, _, raw_wide_dict = extract_universe(test_universe, period_type="annual")
    bundles_by_ticker, _ = build_metrics_universe(raw_wide_dict)

    for ticker, statements in raw_wide_dict.items():
        bundle = bundles_by_ticker[ticker]
        hist_df = calculate_historical_fcff(statements, bundle["series"]["effective_tax_rate"])
        print(f"\n--- {ticker}: historical FCFF (reported actuals) ---")
        print(hist_df[["ebit", "d_and_a", "capex", "delta_nwc", "fcff"]])

        revenue = find_line_item(statements["income_stmt"], ["Total Revenue"])
        forecast_df = project_fcff(revenue.dropna().iloc[-1], bundle["averages"], years=5)
        print(f"\n--- {ticker}: 5-year FCFF forecast ---")
        print(forecast_df[["Revenue", "EBITDA", "EBIT", "NOPAT", "CapEx", "FCFF"]])
