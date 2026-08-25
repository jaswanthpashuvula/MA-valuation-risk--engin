"""
Entry point. Runs ingestion -> valuation -> export end to end for the
target/peer universe defined below, then a Monte Carlo pass on top of the
resulting forecast.
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
