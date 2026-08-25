"""
Turns the pipeline's output into a handful of charts instead of leaving
everything as rows in SQLite. Three views, one per PNG:

    {ticker}_fcff_forecast.png   revenue + FCFF trajectory over the 5-year forecast
    {ticker}_monte_carlo.png     distribution of the Monte Carlo valuation runs,
                                  with median / IQR / 5th-percentile VaR marked
    peer_comparison.png          growth, margin, and CapEx intensity across the
                                  whole ticker universe, side by side

Matplotlib is set to the non-interactive Agg backend since this runs
headless (no display) — the charts get written straight to disk.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


def plot_fcff_forecast(ticker: str, forecast_fcff_tidy_df: pd.DataFrame, out_path) -> None:
    """Bar chart of forecast Revenue with the FCFF trajectory overlaid on a second axis."""
    ticker = ticker.upper()
    subset = forecast_fcff_tidy_df[forecast_fcff_tidy_df["ticker"] == ticker]
    pivot = subset.pivot(index="forecast_year", columns="line_item", values="value").sort_index()

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.bar(pivot.index, pivot["Revenue"], alpha=0.35, color="steelblue", label="Revenue")
    ax1.set_xlabel("Forecast Year")
    ax1.set_ylabel("Revenue ($)")
    ax1.set_xticks(pivot.index)

    ax2 = ax1.twinx()
    ax2.plot(pivot.index, pivot["FCFF"], color="darkorange", marker="o", linewidth=2, label="FCFF")
    ax2.set_ylabel("FCFF ($)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax1.set_title(f"{ticker} — 5-Year Revenue & FCFF Forecast")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_monte_carlo_distribution(ticker: str, distribution: np.ndarray, risk_result: dict, out_path) -> None:
    """Histogram of the simulated valuations with median / IQR / VaR marked."""
    ticker = ticker.upper()
    # Gordon-growth blows up whenever a draw puts WACC close to growth, so the
    # raw distribution has a long thin tail that flattens the interesting part
    # of the histogram. Clip the *view* at the 99th percentile — the tail is
    # real and reflected in the stats below, just not worth the plot's width.
    view_max = np.percentile(distribution, 99)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(distribution[distribution <= view_max], bins=60, color="steelblue", alpha=0.75, edgecolor="white")

    markers = [
        ("median_valuation", "black", "-", "Median"),
        ("p25_valuation", "gray", "--", "25th pct"),
        ("p75_valuation", "gray", "--", "75th pct"),
        ("var_95", "firebrick", ":", "5th pct (VaR)"),
    ]
    for key, color, style, label in markers:
        ax.axvline(risk_result[key], color=color, linestyle=style, linewidth=1.5,
                   label=f"{label}: {risk_result[key]:,.0f}")

    ax.set_xlim(0, view_max)
    ax.set_title(f"{ticker} — Monte Carlo Valuation Distribution ({risk_result['iterations']:,} paths)")
    ax.set_xlabel("Implied Valuation ($) — view clipped at 99th pct; tail excluded from plot only")
    ax.set_ylabel("Frequency")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_peer_margin_comparison(bundles_by_ticker: dict, out_path) -> None:
    """Grouped bar chart comparing revenue growth, EBITDA margin, and CapEx/revenue across the universe."""
    metrics = ["avg_revenue_growth", "avg_ebitda_margin", "avg_capex_to_revenue"]
    tickers = list(bundles_by_ticker.keys())

    x = np.arange(len(tickers))
    width = 0.8 / len(metrics)

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, metric in enumerate(metrics):
        values = [bundles_by_ticker[t]["averages"][metric] for t in tickers]
        ax.bar(x + i * width, values, width, label=metric.replace("avg_", "").replace("_", " ").title())

    ax.set_xticks(x + width * (len(metrics) - 1) / 2)
    ax.set_xticklabels(tickers)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
    ax.set_ylabel("Historical average")
    ax.set_title("Peer Comparison — Historical Growth & Margin Profile")
    ax.legend(fontsize=9)
    ax.axhline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_all_charts(
    target_ticker: str,
    bundles_by_ticker: dict,
    forecast_fcff_tidy_df: pd.DataFrame,
    risk_result: dict,
    distribution: np.ndarray,
    out_dir,
) -> dict[str, Path]:
    """Runs all three chart functions and saves them to out_dir. Returns the paths written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "forecast": out_dir / f"{target_ticker.lower()}_fcff_forecast.png",
        "monte_carlo": out_dir / f"{target_ticker.lower()}_monte_carlo.png",
        "peer_comparison": out_dir / "peer_comparison.png",
    }

    plot_fcff_forecast(target_ticker, forecast_fcff_tidy_df, paths["forecast"])
    plot_monte_carlo_distribution(target_ticker, distribution, risk_result, paths["monte_carlo"])
    plot_peer_margin_comparison(bundles_by_ticker, paths["peer_comparison"])

    for name, path in paths.items():
        print(f"  -> saved {name} chart to {path}")

    return paths
