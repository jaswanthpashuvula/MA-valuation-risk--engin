"""
Valuation engine — pulls company financials and builds a discounted cash
flow model.

Given a ticker and a list of peers, this fetches Income Statement, Balance
Sheet, and Cash Flow data through yfinance (ingestion.py), works out
historical margins and growth rates, projects Free Cash Flow to Firm (FCFF)
five years out, and runs a Monte Carlo sensitivity check on top of the
forecast (all in valuation.py). Results get written to a local SQLite
database (export.py) as long/tidy tables, easy to query and easy to swap
for a real Postgres instance later without touching the calculation code.

FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC

FCFF is unlevered cash flow — before any debt or equity financing effects —
so it gets discounted at WACC rather than cost of equity when building out
the full DCF. WACC estimation, terminal value, and the enterprise-value-to-
share-price bridge aren't built yet; the forecast table this produces feeds
into that next.

Usage:
    pip install -r requirements.txt
    python main.py

Edit TARGET_TICKER and PEER_TICKERS below to run this on a different
company. Each of ingestion.py and valuation.py can also be run standalone
for a quick check (python ingestion.py, python valuation.py).

Output tables (in mna_valuation.db):
    company_profiles    one row per ticker — beta, market cap, sector
    raw_financials       every line item, every period, every ticker
    historical_metrics   the calculated ratios above, by period
    fcff_actuals          reconstructed FCFF from reported numbers
    fcff_forecast         the 5-year projection
    risk_simulation       one row per Monte Carlo run — median/percentile/VaR

Data comes from Yahoo Finance via yfinance, which is free but occasionally
inconsistent — some tickers report line items under different labels, and a
few smaller companies are missing fields entirely. Worth double-checking
against the actual 10-K before trusting any output for real. Not investment
advice.
"""

from pathlib import Path

from ingestion import extract_universe
from valuation import build_fcff_universe, build_metrics_universe, run_monte_carlo
import export

# --- target company + peer group -------------------------------------------
TARGET_TICKER = "AAPL"
PEER_TICKERS = ["MSFT", "GOOGL", "DELL"]
UNIVERSE = [TARGET_TICKER] + PEER_TICKERS

PERIOD_TYPE = "annual"  # or "quarterly"
PROJECTION_YEARS = 5
MONTE_CARLO_ITERATIONS = 10000

DB_PATH = Path(__file__).parent / "mna_valuation.db"


def run_pipeline(tickers=UNIVERSE, period_type=PERIOD_TYPE, years=PROJECTION_YEARS):
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
    export.load_tables(
        {
            "company_profiles": profiles_df,
            "raw_financials": raw_tidy_df,
            "historical_metrics": metrics_tidy_df,
            "fcff_actuals": hist_fcff_tidy_df,
            "fcff_forecast": forecast_fcff_tidy_df,
        },
        DB_PATH,
    )

    print(f"\nRunning Monte Carlo sensitivity check for {TARGET_TICKER}...")
    risk_result = run_monte_carlo(TARGET_TICKER, DB_PATH, iterations=MONTE_CARLO_ITERATIONS)
    export.append_risk_result(risk_result, DB_PATH)

    return {
        "profiles_df": profiles_df,
        "raw_tidy_df": raw_tidy_df,
        "raw_wide_dict": raw_wide_dict,
        "bundles_by_ticker": bundles_by_ticker,
        "metrics_tidy_df": metrics_tidy_df,
        "hist_fcff_tidy_df": hist_fcff_tidy_df,
        "forecast_fcff_tidy_df": forecast_fcff_tidy_df,
        "risk_result": risk_result,
    }


if __name__ == "__main__":
    run_pipeline()
