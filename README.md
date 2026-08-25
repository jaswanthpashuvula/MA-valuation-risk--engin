# Valuation Engine

A Python pipeline for pulling company financials and building a discounted cash flow model. Given a ticker and a list of peers, it fetches Income Statement, Balance Sheet, and Cash Flow data through `yfinance`, works out historical margins and growth rates, and projects Free Cash Flow to Firm (FCFF) five years out.

I put this together to practice building something closer to how a valuation model would actually get assembled at a bank or in equity research — separate stages for data extraction, ratio analysis, and forecasting, with output that lands in a database instead of just printing to a terminal.

## Structure

- `config.py` — tickers and valuation assumptions live here
- `extraction.py` — pulls the three statements from yfinance for a target + peer group
- `metrics.py` — revenue growth, EBITDA margin, CapEx/revenue, D&A/revenue, working capital swings, effective tax rate
- `fcff.py` — the FCFF formula, applied both to historical actuals (as a sanity check) and to the 5-year forecast
- `pipeline.py` — runs all of the above and loads the results into SQLite

## Getting started

```bash
pip install -r requirements.txt
python pipeline.py
```

Edit `TARGET_TICKER` and `PEER_TICKERS` in `config.py` first if you want to run it on something other than AAPL/MSFT/GOOGL/DELL.

Each file can also be run on its own for testing (`python extraction.py`, etc.).

## FCFF formula

```
FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC
```

FCFF is unlevered cash flow — before any debt or equity financing effects — so it gets discounted at WACC rather than cost of equity when building out the full DCF.

## Output tables

Everything gets written to a SQLite file (`mna_valuation.db`) as long/tidy tables, which made it easy to query and also easy to swap for a real Postgres instance later without touching the calculation code:

| Table | What's in it |
|---|---|
| `company_profiles` | one row per ticker — beta, market cap, sector |
| `raw_financials` | every line item, every period, every ticker |
| `historical_metrics` | the calculated ratios above, by period |
| `fcff_actuals` | reconstructed FCFF from reported numbers |
| `fcff_forecast` | the 5-year projection |

## What's not done yet

WACC estimation, terminal value, and the enterprise-value-to-share-price bridge aren't built yet — the forecast table this produces is meant to feed into that next. Also on the list: sensitivity tables and a proper trading comps cross-check against the peer set.

## Notes

Data comes from Yahoo Finance via yfinance, which is free but occasionally inconsistent — some tickers report line items under different labels, and a few smaller companies are missing fields entirely. Worth double-checking against the actual 10-K before trusting any output for real. Not investment advice, obviously.
