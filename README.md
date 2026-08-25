# Valuation Engine

A Python pipeline for pulling company financials and building a discounted cash flow model. Given a ticker and a list of peers, it fetches Income Statement, Balance Sheet, and Cash Flow data through `yfinance`, works out historical margins and growth rates, and projects Free Cash Flow to Firm (FCFF) five years out.

I put this together to practice building something closer to how a valuation model would actually get assembled at a bank or in equity research — separate stages for data extraction, ratio analysis, and forecasting, with output that lands in a database instead of just printing to a terminal.

## Structure

- `config.py` — tickers and valuation assumptions live here
- `ingestion.py` — pulls the three statements from yfinance for a target + peer group
- `metrics.py` — revenue growth, EBITDA margin, CapEx/revenue, D&A/revenue, working capital swings, effective tax rate
- `valuation.py` — the FCFF formula, applied both to historical actuals (as a sanity check) and to the 5-year forecast
- `main.py` — runs all of the above and loads the results into SQLite
- `risk_simulation.py` — Monte Carlo sensitivity check on top of the forecast (see below)

## Getting started

```bash
pip install -r requirements.txt
python main.py
```

Edit `TARGET_TICKER` and `PEER_TICKERS` in `config.py` first if you want to run it on something other than AAPL/MSFT/GOOGL/DELL.

Each file can also be run on its own for testing (`python ingestion.py`, etc.).

## FCFF formula

```
FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC
```

FCFF is unlevered cash flow — before any debt or equity financing effects — so it gets discounted at WACC rather than cost of equity when building out the full DCF.

## Risk simulation

A single DCF gives you one number for one set of growth/WACC assumptions, which isn't very informative on its own — `risk_simulation.py` runs the valuation a few thousand times instead, drawing growth and WACC from a normal distribution each pass, and reports the spread (median, 25th/75th percentile, and a rough 95% Value-at-Risk). It pulls the average forecasted FCFF for whichever ticker is set in `config.py` straight out of the `fcff_forecast` table, so it reflects the actual pipeline output rather than a fixed number:

```bash
python risk_simulation.py
```

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
