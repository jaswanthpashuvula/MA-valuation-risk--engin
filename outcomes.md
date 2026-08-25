## What this actually produces

This isn't just a script that prints numbers to a terminal — every run of `main.py` ends by generating three charts straight from the pipeline's own output tables (`visualize.py` handles this, no manual plotting). These are real, regenerable output, not mockups — run it yourself against any ticker and they get rebuilt from scratch.

### 5-year revenue & FCFF forecast

![FCFF forecast](output/charts/aapl_fcff_forecast.png)

Revenue and FCFF projected five years out for the target ticker, holding historical margins at their averages. Bars are revenue, the line is FCFF — makes it obvious how much of top-line growth actually turns into free cash the business could hand back to investors.

### Monte Carlo valuation spread

![Monte Carlo distribution](output/charts/aapl_monte_carlo.png)

A single DCF gives you one valuation for one guess at growth and WACC, which isn't very informative on its own. This runs the Gordon-growth valuation 10,000 times instead, drawing growth and WACC from a normal distribution each pass, and plots the resulting spread — median, 25th/75th percentile, and a rough 5% Value-at-Risk, all marked on the chart. (The view is clipped at the 99th percentile since the tail runs long whenever a draw happens to put WACC close to growth — the stats themselves still reflect the full distribution.)

### Peer comparison

![Peer comparison](output/charts/peer_comparison.png)

Revenue growth, EBITDA margin, and CapEx intensity side by side across the whole ticker universe — a quick sanity check on whether the assumptions driving one company's forecast look reasonable next to its peers.

## Why this over just a spreadsheet DCF

Most DCF templates are one static case. This treats growth and WACC as distributions instead of point guesses, and keeps ingestion / valuation math / output as separate modules so the assumptions are easy to swap without touching the calculation logic. It's still a simplified model — no WACC build-out or terminal value bridge yet (see the "what's not done yet" note in `main.py`) — but the forecasting and risk-simulation pieces are real and run end to end.
