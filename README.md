# AI-Driven M&A Valuation Engine — Week 1, Days 1-3

## Structure
- `config.py`      — target/peer universe, valuation assumptions, DB path (edit this first)
- `extraction.py`  — Day 1: pulls Income Statement / Balance Sheet / Cash Flow via yfinance for target + peers, in both wide (calculation) and tidy long (SQL) formats
- `metrics.py`     — Day 2: historical revenue growth, EBITDA margin, CapEx/Revenue, D&A/Revenue, NWC change/Revenue, effective tax rate
- `fcff.py`        — Day 3: FCFF formula functions (historical actuals reconciliation + 5-year forecast)
- `pipeline.py`    — orchestrates Days 1-3 end-to-end and loads all tidy tables into SQL (SQLite demo; swap `get_sql_engine()` for Postgres/MySQL/Snowflake later)

## Run
    pip install -r requirements.txt
    python pipeline.py

Each module is also independently runnable for smoke-testing (`python extraction.py`, `python metrics.py`, `python fcff.py`).

## SQL tables produced
| table | grain |
|---|---|
| `company_profiles` | one row per ticker |
| `raw_financials` | ticker x statement_type x period_end x line_item |
| `historical_metrics` | ticker x period_end x metric_name |
| `fcff_actuals` | ticker x period_end x line_item (reported-actuals reconciliation) |
| `fcff_forecast` | ticker x forecast_year x line_item |

## Next (Week 1, Days 4-5)
WACC (CAPM cost of equity via live beta + hardcoded ERP, cost of debt from interest expense/total debt), Gordon Growth terminal value, and the Enterprise Value / Equity Value / Implied Share Price bridge — discounting the `fcff_forecast` table produced here.
