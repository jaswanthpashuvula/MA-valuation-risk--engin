"""
================================================================================
 CONFIG — AI-Driven M&A Valuation Engine
 Week 1 / Days 1-3: Data Extraction -> Historical Metrics -> FCFF
================================================================================
Central place for run parameters so nothing is hardcoded inside the pipeline
modules. Edit this file per engagement; everything downstream reads from here.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# DEAL UNIVERSE
# --------------------------------------------------------------------------
# The acquisition/valuation target and its comparable-company (peer) set.
# Peers are used later (Week 1 Day 4-5) for trading-comp cross-checks against
# the intrinsic DCF value built in Days 1-3.
TARGET_TICKER: str = "AAPL"
PEER_TICKERS: list[str] = ["MSFT", "GOOGL", "DELL"]

UNIVERSE: list[str] = [TARGET_TICKER] + PEER_TICKERS

# --------------------------------------------------------------------------
# STATEMENT PERIODICITY
# --------------------------------------------------------------------------
PERIOD_TYPE: str = "annual"  # "annual" or "quarterly" -> controls which yfinance endpoint is used

# --------------------------------------------------------------------------
# VALUATION ASSUMPTIONS (used starting Day 3 for FCFF, and Day 4+ for WACC/DCF)
# --------------------------------------------------------------------------
RISK_FREE_RATE: float = 0.045          # 10-Year US Treasury yield proxy
MARKET_RISK_PREMIUM: float = 0.055     # Hardcoded US Equity Risk Premium (CAPM input)
DEFAULT_TAX_RATE: float = 0.21         # US federal statutory rate — fallback if effective rate is noisy
TERMINAL_GROWTH_RATE: float = 0.025    # Perpetuity growth rate (~long-run nominal GDP)
PROJECTION_YEARS: int = 5              # Explicit FCFF forecast horizon

# --------------------------------------------------------------------------
# STORAGE / SQL STAGING
# --------------------------------------------------------------------------
# SQLite is used here as a zero-config stand-in for the production warehouse.
# Every module writes clean, tidy (long-format) DataFrames via pandas.to_sql,
# so swapping this for a real Postgres/MySQL connection later is a one-line
# change in pipeline.py (see get_sql_engine()) — no changes needed upstream.
DB_PATH: Path = Path(__file__).parent / "mna_valuation.db"
