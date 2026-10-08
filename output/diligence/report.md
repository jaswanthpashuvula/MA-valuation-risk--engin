# Diligence check

6 findings: 2 high, 4 medium, 0 low.

Reference order when documents disagree: audited statements, then model, then deck.

## F01  [high]  capex, FY2024 (mismatch)

- Claim: ₹46.50 cr in model, operating_model.xlsx Summary!D7
  - source text: "Capex: 46.5"
- Reference: ₹69.94 cr in audited, audited_financials.pdf p.4
  - source text: "Purchase of property, plant and equipment (69.94) (40.19)"
- Gap: -₹23.44 cr
- Ask: The model shows capex of ₹46.50 cr for FY2024 (Summary!D7) but the audited statements show ₹69.94 cr (p.4). What explains the gap? Ask for the fixed asset schedule and whether capital work in progress, capitalised borrowing costs and intangibles are in the model figure.

## F02  [high]  net debt, FY2024 (mismatch)

- Claim: ₹92.80 cr in deck, management_deck.pptx slide 3
  - source text: "Net debt (FY24): ₹92.8 Cr"
- Reference: ₹171.47 cr in audited, audited_financials.pdf p.2
  - source text: "borrowings less cash and cash equivalents"
- Gap: -₹78.67 cr
- Ask: The deck shows net debt of ₹92.80 cr for FY2024 (slide 3) but the audited statements show ₹171.47 cr (p.2). What explains the gap? Ask which debt-like items are in each figure (lease liabilities under Ind AS 116, promoter loans, bill discounting, deferred consideration) and which cash balances count (cash and cash equivalents versus other bank balances and deposits).

## F03  [medium]  ebitda, FY2024 (mismatch)

- Claim: ₹123.40 cr in deck, management_deck.pptx slide 2
  - source text: "EBITDA | 105.4 | 123.4"
- Reference: ₹114.00 cr in audited, audited_financials.pdf p.3, p.4
  - source text: "revenue from operations - (total expenses - finance costs - depreciation)"
- Gap: ₹9.40 cr
- Ask: The deck shows ebitda of ₹123.40 cr for FY2024 (slide 2) but the audited statements show ₹114.00 cr (p.3, p.4). What explains the gap? Ask for the bridge from profit before tax (add finance costs and depreciation, strip other income and exceptional items) and every add-back with support.

## F04  [medium]  order book, FY2024 (unsupported)

- Claim: ₹796.30 cr in deck, management_deck.pptx slide 3
  - source text: "Order book (FY24): ₹796.3 Cr"
- Ask: The deck quotes order book of ₹796.30 cr for FY2024 (slide 3) and nothing in the statements or model backs it. How is it defined, and can we see the underlying schedule? Ask for the order book by customer with order dates, delivery schedule and cancellation terms, and how it ties to revenue recognition under Ind AS 115.

## F05  [medium]  revenue, FY2023 (mismatch)

- Claim: ₹795.77 cr in model, operating_model.xlsx Summary!C4
  - source text: "Revenue: 795.77"
- Reference: ₹822.10 cr in audited, audited_financials.pdf p.3
  - source text: "Revenue from operations 23 888.29 822.10"
- Gap: -₹26.33 cr
- Ask: The model shows revenue of ₹795.77 cr for FY2023 (Summary!C4) but the audited statements show ₹822.10 cr (p.3). What explains the gap? Ask for a revenue bridge by segment, whether the figure is net of GST and trade discounts, and whether it includes pro-forma or acquired revenue.

## F06  [medium]  revenue, FY2024 (internal)

- Claim: ₹838.08 cr in audited, audited_financials.pdf p.5
  - source text: "sum of segment revenue"
- Reference: ₹888.29 cr in audited, audited_financials.pdf p.3
  - source text: "Revenue from operations 23 888.29 822.10"
- Gap: -₹50.21 cr
- Ask: Segment revenue in the notes adds to ₹838.08 cr for FY2024 (p.5) but the income statement reports ₹888.29 cr (p.3). Which is right, and is a segment missing? Ask for a revenue bridge by segment, whether the figure is net of GST and trade discounts, and whether it includes pro-forma or acquired revenue.
