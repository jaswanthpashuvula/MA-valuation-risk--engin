# Diligence check

6 findings: 2 high, 4 medium, 0 low.

Reference order when documents disagree: audited statements, then model, then deck.

## F01  [high]  capex, FY2024 (mismatch)

- Claim: $8.2M in model, operating_model.xlsx Summary!D7
  - source text: "Capex: 8161"
- Reference: $6.6M in audited, audited_financials.pdf p.4
  - source text: "Capital expenditures (6,619) (6,646) (7,577)"
- Gap: $1.5M
- Ask: Model shows capex of $8.2M for FY2024 (Summary!D7) but the audited shows $6.6M (p.4). What explains the gap? Ask whether the model splits maintenance and growth capex and whether capitalised development costs are included.

## F02  [high]  ebitda, FY2024 (mismatch)

- Claim: $17.3M in deck, management_deck.pptx slide 2
  - source text: "EBITDA ($M) | 12.0 | 13.3 | 17.3"
- Reference: $15.5M in audited, audited_financials.pdf p.2 + p.4
  - source text: "operating income + D&A"
- Gap: $1.8M
- Ask: Deck shows ebitda of $17.3M for FY2024 (slide 2) but the audited shows $15.5M (p.2 + p.4). What explains the gap? Ask for the EBITDA reconciliation from operating income, and list every add-back with support.

## F03  [medium]  arr, FY2024 (unsupported)

- Claim: $37.1M in deck, management_deck.pptx slide 3
  - source text: "ARR (FY2024): $37.1M"
- Ask: The deck quotes arr of $37.1M for FY2024 (slide 3) and nothing in the statements or model backs it. How is it defined, and can we see the underlying schedule? 

## F04  [medium]  gross margin, FY2024 (mismatch)

- Claim: 40.0% in deck, management_deck.pptx slide 2
  - source text: "Gross margin (%) | 36.2 | 35.5 | 40.0"
- Reference: 36.4% in audited, audited_financials.pdf p.2 / p.2
  - source text: "gross profit / revenue"
- Gap: +3.6 pp
- Ask: Deck shows gross margin of 40.0% for FY2024 (slide 2) but the audited shows 36.4% (p.2 / p.2). What explains the gap? Ask how cost of sales is defined in the deck versus the statements (freight, depreciation, allocations).

## F05  [medium]  revenue, FY2023 (mismatch)

- Claim: $87.7M in model, operating_model.xlsx Summary!C4
  - source text: "Revenue: 87674"
- Reference: $90.9M in audited, audited_financials.pdf p.2
  - source text: "Revenue 100,497 90,939 86,192"
- Gap: -$3.3M
- Ask: Model shows revenue of $87.7M for FY2023 (Summary!C4) but the audited shows $90.9M (p.2). What explains the gap? Ask for a revenue bridge by segment, and whether the figure includes pro-forma or acquired revenue.

## F06  [medium]  revenue, FY2024 (internal)

- Claim: $95.7M in audited, audited_financials.pdf p.5
  - source text: "sum of segment revenue"
- Reference: $100.5M in audited, audited_financials.pdf p.2
  - source text: "Revenue 100,497 90,939 86,192"
- Gap: -$4.8M
- Ask: Segment revenue in the notes adds to $95.7M for FY2024 (p.5) but the income statement reports $100.5M (p.2). Which is right, and is a segment missing? Ask for a revenue bridge by segment, and whether the figure includes pro-forma or acquired revenue.
