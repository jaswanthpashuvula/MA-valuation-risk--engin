# Valuation Engine

A Python pipeline for pulling company financials and building a discounted cash flow model. Given a ticker and a list of peers, it fetches Income Statement, Balance Sheet, and Cash Flow data through `yfinance`, works out historical margins and growth rates, projects Free Cash Flow to Firm (FCFF) five years out, and runs a Monte Carlo sensitivity check on top of the forecast.

I put this together to practice building something closer to how a valuation model would actually get assembled at a bank or in equity research — separate stages for data ingestion, valuation math, and output, with results that land in a database instead of just printing to a terminal.

## Structure

- `main.py` — entry point; tickers and assumptions live here, and it orchestrates the other three modules
- `ingestion.py` — pulls Income Statement, Balance Sheet, and Cash Flow data from yfinance for a target + peer group
- `valuation.py` — the valuation math: historical margins (revenue growth, EBITDA margin, CapEx/revenue, D&A/revenue, working capital swings, tax rate), the FCFF formula applied to both historical actuals and a 5-year forecast, and a Monte Carlo sensitivity check
- `export.py` — writes the resulting tables to SQLite

## Getting started

```bash
pip install -r requirements.txt
python main.py
```

Edit `TARGET_TICKER` and `PEER_TICKERS` at the top of `main.py` first if you want to run it on something other than AAPL/MSFT/GOOGL/DELL.

Each module can also be run on its own for testing (`python ingestion.py`, `python valuation.py`).

## FCFF formula

```
FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC
```

FCFF is unlevered cash flow — before any debt or equity financing effects — so it gets discounted at WACC rather than cost of equity when building out the full DCF.

## Risk simulation

A single DCF gives you one number for one set of growth/WACC assumptions, which isn't very informative on its own. `run_monte_carlo()` in `valuation.py` runs the valuation a few thousand times instead, drawing growth and WACC from a normal distribution each pass, and reports the spread (median, 25th/75th percentile, and a rough 95% Value-at-Risk). It pulls the average forecasted FCFF for whichever ticker `main.py` is pointed at straight out of the `fcff_forecast` table, so it reflects the actual pipeline output rather than a fixed number. `main.py` runs it automatically after each full pipeline run.

## Output tables

Everything gets written to a SQLite file (`mna_valuation.db`) as long/tidy tables, which made it easy to query and also easy to swap for a real Postgres instance later without touching the calculation code:

| Table | What's in it |
|---|---|
| `company_profiles` | one row per ticker — beta, market cap, sector |
| `raw_financials` | every line item, every period, every ticker |
| `historical_metrics` | the calculated ratios above, by period |
| `fcff_actuals` | reconstructed FCFF from reported numbers |
| `fcff_forecast` | the 5-year projection |
| `risk_simulation` | one row per Monte Carlo run — median/percentile/VaR valuation estimates |

## What's not done yet

WACC estimation, terminal value, and the enterprise-value-to-share-price bridge aren't built yet — the forecast table this produces is meant to feed into that next. Also on the list: sensitivity tables and a proper trading comps cross-check against the peer set.

## Notes

Data comes from Yahoo Finance via yfinance, which is free but occasionally inconsistent — some tickers report line items under different labels, and a few smaller companies are missing fields entirely. Worth double-checking against the actual 10-K before trusting any output for real. Not investment advice, obviously.
