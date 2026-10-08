# Deal diligence checker for Indian M&A

Point it at a folder of deal documents (the management deck, the audited Ind AS financial statements and the company's operating model) and it lists the numbers that don't agree, with the exact slide, page or cell behind each one and a question to put to management.

This is the manual job every analyst on an Indian deal ends up doing: the deck says one EBITDA, the audited statements imply another, and the model has a third. The checker does the first pass of that and shows its working so a person can verify every flag.

It also reads the footnotes. In a deal the explanation for a gap is usually sitting in small print ("Adjusted EBITDA, excludes exceptional items of ₹5.2 Cr", "Includes lease liabilities of ₹17.7 crore"), and the contingent liabilities and the auditor's emphasis paragraphs are in the back of the audited statements. A mismatch is checked against the footnote on either figure, and the report says whether the disclosed amount covers the gap, covers part of it, or can't be checked.

I'm a student from a small town building this to learn how deals are actually diligenced. It is a prototype tested on invented data, not a product.

## Run it

```
pip install -r requirements.txt
python sample_deal/make_deal.py sample_deal --seed 26
python dealcheck.py sample_deal
```

To regenerate the exact sample in the repo: `python sample_deal/make_deal.py sample_deal --seed 26 --issues fn_ebitda_partial,fn_audited_lease,fn_capex_comment,deck_gross_margin,orderbook_unsupported,segment_sum,fn_contingent,fn_emphasis`.

The sample is a fictional company (Nilgiri Precision Components Limited) with eight planted problems, and the checker finds all eight. One of its findings:

> The deck shows ebitda of ₹121.60 cr for FY2024 (slide 2) but the audited statements show ₹114.00 cr (p.3, p.4). A footnote (slide 2) says: "Adjusted EBITDA; excludes exceptional items of ₹5.2 Cr." It discloses ₹5.20 cr of the ₹7.60 cr gap, leaving ₹2.40 cr unexplained. Ask for the full bridge between the two figures.

Everything it produced is in `output/diligence/`: `report.md`, `findings.csv`, `scenario_summary.png` and `audit_log.jsonl`.

## Built for Indian documents

- Rupee amounts in crore, lakh or million, converted to one unit. The deck can say ₹ Cr while the statements are in lakhs and the model in crore.
- Indian digit grouping (12,34,567.89).
- Indian financial years, April to March, whether written FY24, FY2023-24, 2023-24 or "31 March 2024". Projection columns such as FY25E are ignored rather than flagged as unsupported.
- Schedule III / Ind AS statement layout: expenses by nature, no EBITDA or gross profit line, a note-number column beside the figures, borrowings split into non-current and current. EBITDA, gross margin and net debt are built from the lines that exist and the components are cited.
- Follow-up questions that mention the things that cause these gaps in India: lease liabilities under Ind AS 116, GST, capital work in progress, restricted bank balances, adjusted PAT, order book recognition under Ind AS 115.

## Footnotes

- Reads footnote markers ((1), [1], *, †, ‡, ¹) and the text they point to, in the deck (slide text and table cells), the audited PDF (including footnotes that wrap onto a second line), and the model (cell comments). Unmarked "Note:" and "Source:" lines are kept too.
- Links a footnote to the figure it belongs to by its marker, or, if it has none, by the metric it names.
- Picks out the rupee amounts and wording (adjusted, excludes, includes, pro forma, unaudited, run-rate, standalone) and compares the amounts with the gap. Whole gap covered: severity is lowered and the question asks for the schedule behind it. Part covered: the unexplained remainder is quoted and the severity is set from that. A footnote with wording but no amount is shown and left as "noted".
- Derived figures (EBITDA, net debt) carry the footnotes of the lines they are built from.
- Flags contingent liabilities from the audited notes with the amount and its share of EBITDA, and the auditor's report flags: Emphasis of Matter, Material Uncertainty Related to Going Concern, and qualified or adverse opinions. These are listed whenever present, since they matter whether or not a number in the deck disagrees.

## What it checks

- A figure that disagrees with a higher-ranked document. Audited statements are the reference, then the model, then the deck.
- A deck claim that nothing else supports (for example an order book figure).
- A document that contradicts itself: segment note not adding to revenue, a stated EBITDA margin that doesn't match its own EBITDA and revenue.
- Rounding is allowed for. A deck showing ₹812 Cr against ₹812.4 Cr in the statements is not flagged.

Other pieces: an analyst overrides file for numbers the extractor misread (`--overrides overrides.csv`, columns `doc,metric,period,value,unit,reason,analyst`, applied and logged); a hash-chained audit log of each run with the SHA-256 of every input file; and a small DCF that shows what the gap is worth, for example equity value on audited numbers versus the numbers as pitched. WACC (12%) and terminal growth (5%) in that DCF are assumptions I picked, not forecasts, and the output is an illustration rather than a valuation.

## How accurate is it

`eval_checker.py` builds synthetic Indian deal rooms with a random mix of twenty planted problem types (eleven number problems, six footnote cases, three audit-report and note disclosures) and counts a flag as correct when the kind, metric and period match something planted. For the footnote cases it also checks that the footnote verdict (whole gap, part of it, noted) is the planted one. The deal rooms also carry decoy footnotes and standard audit wording that should not be flagged.

| Test | Deals | Planted | Missed | False flags | Footnote verdict right |
|---|---|---|---|---|---|
| Default | 200 | 1,036 | 0 | 0 | 192 of 192 |
| Hard (other label wording, gaps of 1 to 3%, projection columns, correct rounded decoys) | 200 | 1,036 | 0 | 0 | 192 of 192 |
| Nothing planted (hard layout) | 200 | 0 | n/a | 0 | n/a |

Read this carefully. I wrote the generator and the checker, and the generator produces documents laid out the way the extractor expects, so a perfect score shows the logic is sound and does not show it will cope with a real data room. The number I don't have yet is how it does on real, messy documents.

## Limits

- Synthetic data only. No real company's documents have been used.
- Extraction is label and pattern based. Different layouts, merged cells, scanned PDFs (there is no OCR), and spreadsheets with formulas that have no saved values will be missed or misread. "No finding" does not mean "checked".
- Footnote reading is wording based. It matches a footnote's rupee amounts to the size of the gap and ignores direction, so an add-back that points the wrong way can still look like an explanation, which is why the report quotes the footnote instead of just ticking it off. Footnotes written as prose across several paragraphs, tables of footnotes, superscript numbers that the PDF text layer drops, and amounts in words are not handled. Contingent liabilities are only picked up when the note states a total amount.
- It does not understand definitions. "Adjusted EBITDA" with add-backs, EBITDA including other income, or a different net debt definition will show up as a mismatch; the follow-up question is how an analyst resolves it.
- Gross margin is computed as revenue less cost of materials consumed. A company that reports differently needs a different definition.
- Consolidated and standalone statements are not told apart.
- It is a tool for an analyst to look at, not something that decides anything, and nothing here is investment or legal advice.

## Using it on a live deal

Not without the firm's own controls. Running locally is not the same as being approved. At minimum that means sign-off from the firm's information security and compliance teams, access limited to the deal team, encryption at rest, a firm-approved environment, and review of the audit log. For a listed target, deal documents can be unpublished price sensitive information under SEBI's insider trading regulations, which the firm's own policies will already cover. The hash-chained log here is a starting point and not a replacement for any of that. The checker makes no network calls and has no LLM in the checking path; the follow-up questions are templates.

## Valuation pipeline

This repo started as a public-company valuation pipeline: it pulls Income Statement, Balance Sheet and Cash Flow data through yfinance for a target and peers, projects free cash flow to the firm five years out, and runs a Monte Carlo on growth and WACC.

```
python main.py
```

Set `TARGET_TICKER` and `PEER_TICKERS` at the top of `main.py`. The charts below were produced with US tickers because that is what I could run when I built it. yfinance does carry NSE tickers (the `.NS` suffix) but I have not run this pipeline on them, so I am not claiming it works for Indian companies yet. That is next.

![FCFF forecast](output/charts/aapl_fcff_forecast.png)

![Monte Carlo distribution](output/charts/aapl_monte_carlo.png)

![Peer comparison](output/charts/peer_comparison.png)

FCFF = EBIT x (1 - tax rate) + D&A - CapEx + change in NWC. The Monte Carlo draws growth and WACC from normal distributions over 10,000 Gordon-growth valuations; the chart is clipped at the 99th percentile because the tail runs long when a draw puts WACC near growth. Files: `main.py`, `ingestion.py`, `valuation.py`, `export.py` (SQLite tables), `visualize.py`. Yahoo Finance data is free but inconsistent, so check against the annual report before trusting an output.

## Not built yet

Running the valuation pipeline on NSE-listed companies, a trading comps cross-check, consolidated versus standalone handling, support for messier real documents, and testing on real (permitted) deal documents.

## Layout

```
dealcheck.py          run the diligence check
eval_checker.py       accuracy test on synthetic deals
diligence/            extract, reconcile, report, scenarios, audit
sample_deal/          synthetic deal room and its generator
main.py ...           valuation pipeline
```
