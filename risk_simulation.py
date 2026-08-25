"""
Monte Carlo overlay on top of the FCFF forecast. Instead of relying on one
fixed growth/WACC pair, this draws both from a normal distribution a few
thousand times and looks at the resulting spread of valuations — gives a
sense of how sensitive the number actually is to those assumptions, plus a
rough 95% Value-at-Risk estimate.

Pulls its baseline straight from the fcff_forecast table pipeline.py writes,
so it reflects whatever ticker config.py is pointed at rather than a fixed
number.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import DB_PATH, TARGET_TICKER


def get_avg_forecast_fcff(ticker: str, db_path=DB_PATH) -> float:
    """Average forecasted FCFF for a ticker, pulled from the fcff_forecast table."""
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
            f"No forecast FCFF found for '{ticker}' in {db_path}. Run pipeline.py first."
        )
    return float(row[0])


def run_monte_carlo(
    ticker: str = TARGET_TICKER,
    iterations: int = 10000,
    growth_mean: float = 0.04,
    growth_std: float = 0.015,
    wacc_mean: float = 0.095,
    wacc_std: float = 0.01,
    seed: int | None = None,
    save_to_db: bool = True,
) -> dict:
    """
    Runs a Gordon-growth valuation `iterations` times with randomized growth
    and WACC each pass, rather than one fixed scenario. seed is left as None
    by default on purpose — a fixed seed would make every run produce the
    identical result, defeating the point of a stochastic simulation. Pass a
    seed explicitly if you need a reproducible run for testing.
    """
    baseline_fcff = get_avg_forecast_fcff(ticker)

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

    if save_to_db:
        _save_results(results)

    return results


def _save_results(results: dict, db_path=DB_PATH) -> None:
    """Appends one row to a risk_simulation table, same tidy-table pattern as the rest of the pipeline."""
    row = pd.DataFrame([{**results, "run_timestamp": datetime.now(timezone.utc).isoformat()}])
    conn = sqlite3.connect(db_path)
    row.to_sql("risk_simulation", conn, if_exists="append", index=False)
    conn.close()


if __name__ == "__main__":
    run_monte_carlo()
