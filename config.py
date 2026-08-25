"""
Run parameters for the valuation pipeline. Keeping these in one place means
ingestion.py, metrics.py, valuation.py, and main.py never hardcode a ticker
or assumption directly.
"""

from pathlib import Path

# Target company + peer group. Peers get pulled through the same pipeline so
# they can be used for comps/cross-checks later.
TARGET_TICKER: str = "AAPL"
PEER_TICKERS: list[str] = ["MSFT", "GOOGL", "DELL"]
UNIVERSE: list[str] = [TARGET_TICKER] + PEER_TICKERS

PERIOD_TYPE: str = "annual"  # or "quarterly" — picks which yfinance statements to pull

# Valuation assumptions
RISK_FREE_RATE: float = 0.045          # proxy for the 10Y Treasury yield
MARKET_RISK_PREMIUM: float = 0.055     # equity risk premium used in CAPM
DEFAULT_TAX_RATE: float = 0.21         # fallback if a company's effective rate looks noisy
TERMINAL_GROWTH_RATE: float = 0.025    # perpetuity growth rate for the terminal value
PROJECTION_YEARS: int = 5

# Using SQLite for now so the project runs with zero setup. To point this at
# Postgres/MySQL instead, just swap the connection in main.py's
# get_sql_engine() — everything else writes plain DataFrames via to_sql and
# doesn't care what's on the other end.
DB_PATH: Path = Path(__file__).parent / "mna_valuation.db"
