# M&A valuation and diligence checker

Two parts in one repo. The first is a deal diligence checker: point it at a folder of deal documents and it lists the numbers that don't agree across the management deck, the audited statements and the operating model, with the exact slide, page or cell behind each one and a question to put to management. The second is the valuation pipeline I built first: pull public financials, project free cash flow, run a Monte Carlo on the result.

I'm a student from a small town and I built this to learn how analysts actually work through a deal, not to compete with commercial tools. The diligence checker came from one specific, boring problem: reconciling a deck against the statements by hand.

## Diligence checker

```
python sample_deal/make_deal.py sample_deal --seed 7
python dealcheck.py sample_deal
```

On the included fictional company (Halden Precision Components, invented data) it finds all six problems I planted, for example:

> Deck shows EBITDA of $17.3M for FY2024 (slide 2) but the audited statements give $15.5M (operating income p.2 + D&A p.4). What explains the gap? Ask for the EBITDA reconciliation from operating income and every add-back with support.

Full output is in `output/diligence/`: `report.md` (readable), `findings.csv`, `scenario_summary.png`, `audit_log.jsonl`.

What it does:

- Reads a .pptx deck, a .pdf set of statements and an .xlsx model, and records every figure with its file and location (slide, page, sheet and cell).
- Treats audited statements as the reference, then the model, then the deck. Where a document only gives the pieces, it derives EBITDA (operating income plus D&A), net debt and gross margin and cites the components.
- Flags three kinds of problem: a figure that disagrees with a higher-ranked document, a deck claim nothing else supports (for example ARR), and a document that contradicts itself (segment notes that don't add to revenue, a stated margin that doesn't match its own EBITDA and revenue).
- Allows for rounding. A deck showing $98M against $98.4M in the statements is not flagged.
- Turns each finding into a follow-up question, tailored by metric.
- Lets an analyst correct a misread number with an overrides file (`--overrides overrides.csv`, columns `doc,metric,period,value,reason,analyst`). Overrides are applied, marked in the report and written to the audit log.
- Keeps an append-only, hash-chained log of each run with SHA-256 of every input file, so a result can be tied to the exact documents it came from.
- Shows what the gap is worth: a small five-year DCF on audited numbers versus the deck's numbers, and a growth by WACC grid. WACC, terminal growth and the margin path are assumptions, not forecasts.

### How accurate is it

`eval_checker.py` generates synthetic deal rooms with a random mix of ten planted problems, runs the checker, and counts a flag as correct if kind, metric and period match something planted.

| Test | Deals | Planted | Missed | False flags |
|---|---|---|---|---|
| Default | 200 | 1,014 | 0 | 0 |
| Hard (other label wording, gaps of 1 to 3%, correct rounded figures as decoys) | 200 | 1,014 | 0 | 0 |

Read this carefully: I wrote the generator and the checker, and the generator makes documents laid out the way the extractor expects. 100% here shows the logic works, not that it will work on a real data room. The honest number is the one I don't have yet, which is how it does on real, messy documents.

### Limits

- Synthetic data only. No real company documents have been used.
- Extraction is label and regex based. Different layouts, merged cells, footnoted figures, scanned PDFs (no OCR) and spreadsheets with formulas that have no cached values will be missed or misread. "No finding" does not mean "checked".
- It matches figures by metric and period. It does not understand adjusted versus reported definitions; that is what the follow-up questions are for.
- The valuation scenarios are deliberately simple and are not an opinion on what a company is worth.
- It is a tool for an analyst to look at, not something that decides anything.

### Using it on a live deal

Not without a firm's own controls. Running locally is not the same as being approved. At minimum that means sign-off from the firm's security and compliance teams, access limited to people on the deal, encryption at rest, a firm-approved environment, and review of the audit log. The hash-chained log here is a starting point, not a replacement for any of that. The diligence checker makes no network calls and has no LLM in the checking path: the questions are templates.

## Valuation pipeline

A Python pipeline that pulls Income Statement, Balance Sheet and Cash Flow data through yfinance for a target and peers, works out historical margins and growth, projects free cash flow to the firm five years out, and runs a Monte Carlo on growth and WACC.

```
pip install -r requirements.txt
python main.py
```

Set `TARGET_TICKER` and `PEER_TICKERS` at the top of `main.py` first. Charts land in `output/charts/`.

![FCFF forecast](output/charts/aapl_fcff_forecast.png)

Revenue and FCFF five years out, holding historical margins at their averages.

![Monte Carlo distribution](output/charts/aapl_monte_carlo.png)

10,000 Gordon-growth valuations with growth and WACC drawn from normal distributions. Shows median, 25th and 75th percentile and a rough 5% value at risk. The view is clipped at the 99th percentile because the tail runs long when a draw puts WACC near growth.

![Peer comparison](output/charts/peer_comparison.png)

Revenue growth, EBITDA margin and capex intensity across the ticker set.

FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC

Files: `main.py` (entry point and assumptions), `ingestion.py`, `valuation.py`, `export.py` (writes tidy tables to SQLite), `visualize.py`.

Yahoo Finance data is free but inconsistent, and some tickers label line items differently, so check against the 10-K before trusting an output. Not investment advice.

## Not built yet

Proper WACC estimation, a trading comps cross-check, support for messier real-world documents, and testing on real (permitted) deal documents.

## Layout

```
dealcheck.py          run the diligence check
eval_checker.py       accuracy test on synthetic deals
diligence/            extract, reconcile, report, scenarios, audit
sample_deal/          synthetic deal room and its generator
main.py ...           valuation pipeline
```
