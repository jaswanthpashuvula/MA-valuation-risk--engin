# Diligence check

8 findings: 0 high, 5 medium, 3 low.

Reference order when documents disagree: audited statements, then model, then deck.

## F01  [medium]  audit emphasis, FY2024 (disclosure)

- Where: audited, audited_financials.pdf p.1
  - source text: "Emphasis of Matter"
- Ask: The auditor's report (p.1) includes an Emphasis of Matter paragraph. Ask what it concerns, whether it affects any figure in the deck, and for the auditor's management letter.

## F02  [medium]  contingent liabilities, FY2024 (disclosure)

- Where: audited, audited_financials.pdf p.5
  - source text: "Note 40. Contingent liabilities not provided for amounted to ₹52.10 crore as at 31 March 2024."
- Ask: The audited notes disclose contingent liabilities of ₹52.10 cr (p.5), 46% of audited EBITDA. Ask for the breakdown by matter (tax demands, litigation, guarantees), the stage of each and management's view on likelihood.

## F03  [medium]  gross margin, FY2024 (mismatch)

- Claim: 44.5% in deck, management_deck.pptx slide 2
  - source text: "Gross margin (%) | 40.2 | 44.5"
- Reference: 39.8% in audited, audited_financials.pdf p.3
  - source text: "(revenue - cost of materials) / revenue"
- Gap: +4.7 pp
- Ask: The deck shows gross margin of 44.5% for FY2024 (slide 2) but the audited statements show 39.8% (p.3). What explains the gap? Ask how cost of sales is defined in the deck, since Ind AS statements list expenses by nature (materials, purchases of stock-in-trade, changes in inventory, freight, job work).

## F04  [medium]  order book, FY2024 (unsupported)

- Claim: ₹470.80 cr in deck, management_deck.pptx slide 3
  - source text: "Order book (FY24): ₹470.8 Cr"
- Ask: The deck quotes order book of ₹470.80 cr for FY2024 (slide 3) and nothing in the statements or model backs it. How is it defined, and can we see the underlying schedule? Ask for the order book by customer with order dates, delivery schedule and cancellation terms, and how it ties to revenue recognition under Ind AS 115.

## F05  [medium]  revenue, FY2024 (internal)

- Claim: ₹851.16 cr in audited, audited_financials.pdf p.5
  - source text: "sum of segment revenue"
- Reference: ₹888.29 cr in audited, audited_financials.pdf p.3
  - source text: "Revenue from operations 23 888.29 822.10"
- Gap: -₹37.13 cr
- Ask: Segment revenue in the notes adds to ₹851.16 cr for FY2024 (p.5) but the income statement reports ₹888.29 cr (p.3). Which is right, and is a segment missing? Ask for a revenue bridge by segment, whether the figure is net of GST and trade discounts, and whether it includes pro-forma or acquired revenue.

## F06  [low]  capex, FY2024 (mismatch)

- Claim: ₹77.24 cr in model, operating_model.xlsx Summary!D7
  - source text: "Capex: 77.24"
- Reference: ₹69.94 cr in audited, audited_financials.pdf p.4
  - source text: "Purchase of property, plant and equipment (69.94) (40.19)"
- Gap: ₹7.30 cr
- Footnote (Summary!D7 (comment)): "Includes capitalised borrowing costs of ₹7.30 Cr."
- Footnote check: the amount in the footnote accounts for the whole gap (severity lowered)
- Ask: The model shows capex of ₹77.24 cr for FY2024 (Summary!D7) but the audited statements show ₹69.94 cr (p.4). A footnote (Summary!D7 (comment)) says: "Includes capitalised borrowing costs of ₹7.30 Cr." The amount it discloses accounts for the whole ₹7.30 cr gap. Ask for the schedule of those items with support, and whether they recur.

## F07  [low]  ebitda, FY2024 (mismatch)

- Claim: ₹121.60 cr in deck, management_deck.pptx slide 2
  - source text: "EBITDA † | 105.4 | 121.6"
- Reference: ₹114.00 cr in audited, audited_financials.pdf p.3, p.4
  - source text: "revenue from operations - (total expenses - finance costs - depreciation)"
- Gap: ₹7.60 cr
- Footnote (slide 2): "Adjusted EBITDA; excludes exceptional items of ₹5.2 Cr."
- Footnote check: the footnote accounts for part of the gap; ₹2.40 cr is unexplained
- Ask: The deck shows ebitda of ₹121.60 cr for FY2024 (slide 2) but the audited statements show ₹114.00 cr (p.3, p.4). A footnote (slide 2) says: "Adjusted EBITDA; excludes exceptional items of ₹5.2 Cr." It discloses ₹5.20 cr of the ₹7.60 cr gap, leaving ₹2.40 cr unexplained. Ask for the full bridge between the two figures.

## F08  [low]  net debt, FY2024 (mismatch)

- Claim: ₹171.50 cr in deck, management_deck.pptx slide 3
  - source text: "Net debt (FY24): ₹171.5 Cr"
- Reference: ₹189.17 cr in audited, audited_financials.pdf p.2
  - source text: "borrowings less cash and cash equivalents"
- Gap: -₹17.67 cr
- Footnote (p.2): "Includes lease liabilities of ₹17.70 crore recognised under Ind AS 116 and presented within borrowings."
- Footnote check: the amount in the footnote accounts for the whole gap (severity lowered)
- Ask: The deck shows net debt of ₹171.50 cr for FY2024 (slide 3) but the audited statements show ₹189.17 cr (p.2). A footnote (p.2) says: "Includes lease liabilities of ₹17.70 crore recognised under Ind AS 116 and presented within borrowings." The amount it discloses accounts for the whole ₹17.67 cr gap. Ask for the schedule of those items with support, and whether they recur.
