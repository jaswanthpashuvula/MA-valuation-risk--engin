"""
Makes a fake deal room for an invented company: a management deck, audited
statements and an operating model, with a few planted inconsistencies and a
truth.json saying exactly what was planted. Nothing here is real company data.

    python sample_deal/make_deal.py sample_deal --seed 7
"""
import argparse
import json
import random
from pathlib import Path

import openpyxl
from pptx import Presentation
from pptx.util import Inches
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

YEARS = ["FY2022", "FY2023", "FY2024"]
ISSUES = {
    "deck_revenue": ("mismatch", "revenue", "FY2024"),
    "deck_ebitda": ("mismatch", "ebitda", "FY2024"),
    "deck_net_debt": ("mismatch", "net_debt", "FY2024"),
    "deck_gross_margin": ("mismatch", "gross_margin", "FY2024"),
    "model_capex": ("mismatch", "capex", "FY2024"),
    "model_revenue_py": ("mismatch", "revenue", "FY2023"),
    "customer_conc": ("mismatch", "customer_concentration", "FY2024"),
    "arr_unsupported": ("unsupported", "arr", "FY2024"),
    "segment_sum": ("internal", "revenue", "FY2024"),
    "deck_margin_math": ("internal", "ebitda_margin", "FY2024"),
}


def company(rng):
    r0 = rng.uniform(70e3, 120e3)
    g = [rng.uniform(0.04, 0.14) for _ in range(2)]
    rev = [r0, r0 * (1 + g[0]), r0 * (1 + g[0]) * (1 + g[1])]
    em, gm = rng.uniform(0.14, 0.24), rng.uniform(0.30, 0.42)
    d = {"rev": [round(x) for x in rev]}
    d["gp"] = [round(x * (gm + rng.uniform(-.01, .01))) for x in rev]
    d["da"] = [round(x * rng.uniform(0.03, 0.04)) for x in rev]
    d["ebitda"] = [round(x * (em + rng.uniform(-.01, .01))) for x in rev]
    d["ebit"] = [e - a for e, a in zip(d["ebitda"], d["da"])]
    d["interest"] = [round(x * rng.uniform(0.01, 0.02)) for x in rev]
    d["ni"] = [round((e - i) * 0.75) for e, i in zip(d["ebit"], d["interest"])]
    d["capex"] = [round(x * rng.uniform(0.05, 0.09)) for x in rev]
    d["wc"] = [round(x * rng.uniform(-0.02, 0.02)) for x in rev]
    d["cfo"] = [n + a + w for n, a, w in zip(d["ni"], d["da"], d["wc"])]
    d["cash"] = [round(rev[1] * rng.uniform(.05, .15)), round(rev[2] * rng.uniform(.05, .15))]
    d["debt"] = [round(rev[1] * rng.uniform(.20, .45)), round(rev[2] * rng.uniform(.20, .45))]
    d["other_assets"] = [round(x * 0.9) for x in rev[1:]]
    d["other_liab"] = [round(x * 0.2) for x in rev[1:]]
    sh = [rng.uniform(.3, .5), rng.uniform(.25, .35)]
    sh.append(1 - sum(sh))
    d["shares"] = sh
    d["top_customer"] = round(rng.uniform(10, 25))
    return d


def build(out_dir, seed=7, issues=None, hard=False):
    # hard: other label wordings, smaller gaps, and a whole-$M rounded figure
    # that is correct and should not be flagged
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = company(rng)
    if issues is None:
        issues = [k for k in ISSUES if rng.random() < 0.5]
        while len(issues) < 2:
            issues = sorted(set(issues + [rng.choice(list(ISSUES))]))
    has = set(issues).__contains__

    aud_nd = d["debt"][1] - d["cash"][1]
    aud_gm = [100 * g / r for g, r in zip(d["gp"], d["rev"])]

    # deck figures in $M, one decimal
    deck_rev = [round(x / 1000, 1) for x in d["rev"]]
    deck_ebitda = [round(x / 1000, 1) for x in d["ebitda"]]
    deck_gm = [round(x, 1) for x in aud_gm]
    deck_nd = round(aud_nd / 1000, 1)
    deck_top = d["top_customer"]
    if has("deck_revenue"):
        deck_rev[2] = round(d["rev"][2] / 1000 * (1 + (rng.uniform(.01, .03) if hard else rng.uniform(.04, .15))), 1)
    if has("deck_ebitda"):
        deck_ebitda[2] = round(d["ebitda"][2] / 1000 * (1 + (rng.uniform(.012, .04) if hard else rng.uniform(.05, .20))), 1)
    if has("deck_net_debt"):
        deck_nd = round(aud_nd / 1000 * (1 - rng.uniform(.25, .6)), 1)
    if has("deck_gross_margin"):
        deck_gm[2] = round(aud_gm[2] + (rng.uniform(.8, 2.0) if hard else rng.uniform(2.5, 6)), 1)
    if has("customer_conc"):
        deck_top = max(d["top_customer"] - round(rng.uniform(6, 12)), 2)
    deck_margin = [round(100 * e / r, 1) for e, r in zip(deck_ebitda, deck_rev)]
    if has("deck_margin_math"):
        deck_margin[2] = round(deck_margin[2] + rng.uniform(2, 5), 1)

    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = "Halden Precision Components"
    s.placeholders[1].text = "Management presentation (fictional company, synthetic data)"
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Financial highlights"
    rev_lab = rng.choice(["Total revenue", "Net sales"]) if hard else "Revenue"
    rows = [["", *YEARS],
            [f"{rev_lab} ($M)", *[f"{x:.1f}" for x in deck_rev]],
            ["EBITDA ($M)", *[f"{x:.1f}" for x in deck_ebitda]],
            ["EBITDA margin (%)", *[f"{x:.1f}" for x in deck_margin]],
            ["Gross margin (%)", *[f"{x:.1f}" for x in deck_gm]]]
    t = s.shapes.add_table(len(rows), 4, Inches(0.7), Inches(1.8), Inches(8.6), Inches(2.6)).table
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            t.cell(i, j).text = v
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Balance sheet and customers"
    box = s.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(8.6), Inches(3)).text_frame
    bullets = [f"Net debt (FY2024): ${deck_nd:.1f}M",
               f"Cash (FY2024): ${d['cash'][1] / 1000:.1f}M",
               f"Top customer: {deck_top}% of FY2024 revenue"]
    if hard:
        bullets.append(f"{rev_lab} (FY2023): ${round(d['rev'][1] / 1000)}M")
    if has("arr_unsupported"):
        bullets.append(f"ARR (FY2024): ${d['rev'][2] * rng.uniform(.25, .4) / 1000:.1f}M")
    box.text = bullets[0]
    for b in bullets[1:]:
        box.add_paragraph().text = b
    prs.save(out / "management_deck.pptx")

    # audited statements
    seg = [round(d["rev"][i] * 1.0) for i in range(3)]
    segs = [[round(d["rev"][i] * sh) for i in range(3)] for sh in d["shares"]]
    for i in range(3):
        segs[2][i] = d["rev"][i] - segs[0][i] - segs[1][i]
    if has("segment_sum"):
        k = rng.uniform(.02, .06)
        segs[2][2] = round(segs[2][2] - d["rev"][2] * k)
    c = canvas.Canvas(str(out / "audited_financials.pdf"), pagesize=letter)

    def page(title, header, unit, rows, extra=()):
        y = 740
        c.setFont("Helvetica-Bold", 13); c.drawString(72, y, title); y -= 22
        c.setFont("Helvetica", 9)
        if unit:
            c.drawString(72, y, unit); y -= 16
        if header:
            for x, h in zip((330, 410, 490)[:len(header)], header):
                c.drawRightString(x, y, h)
            y -= 18
        c.setFont("Helvetica", 10)
        for label, vals in rows:
            c.drawString(72, y, label)
            for x, v in zip((330, 410, 490), vals):
                c.drawRightString(x, y, f"({abs(v):,})" if v < 0 else f"{v:,}")
            y -= 16
        for line in extra:
            c.drawString(72, y, line); y -= 14
        c.showPage()

    r = lambda k: list(reversed(d[k]))
    page("Independent auditor's report", [], "", [], ["In our opinion the statements present fairly, in all material",
         "respects, the financial position of the company (fictional, synthetic data)."])
    ud = "(in thousands of US dollars)"
    page("Income statement", ["FY2024", "FY2023", "FY2022"], ud,
         [("Revenue", r("rev")), ("Cost of sales", [-(a - b) for a, b in zip(r("rev"), r("gp"))]),
          ("Gross profit", r("gp")), ("Operating income", r("ebit")), ("Interest expense", [-x for x in r("interest")]),
          ("Net income", r("ni"))])
    page("Balance sheet", ["FY2024", "FY2023"], ud,
         [("Cash and cash equivalents", [d["cash"][1], d["cash"][0]]), ("Other assets", [d["other_assets"][1], d["other_assets"][0]]),
          ("Borrowings", [d["debt"][1], d["debt"][0]]), ("Other liabilities", [d["other_liab"][1], d["other_liab"][0]])])
    page("Cash flow statement", ["FY2024", "FY2023", "FY2022"], ud,
         [("Net income", r("ni")), ("Depreciation and amortization", r("da")), ("Change in working capital", r("wc")),
          ("Cash from operations", r("cfo")), ("Capital expenditures", [-x for x in r("capex")])])
    page("Notes", ["FY2024", "FY2023", "FY2022"], "Note 12. Segment information " + ud,
         [("Segment Aerospace", segs[0][::-1]), ("Segment Industrial", segs[1][::-1]), ("Segment Medical", segs[2][::-1]),
          ("Total segment revenue", [sum(s_[i] for s_ in segs) for i in (2, 1, 0)])],
         [f"Note 14. One customer accounted for {d['top_customer']}% of revenue in FY2024."])
    c.save()

    # model, in thousands
    def jitter(x):
        return round(x * (1 + rng.uniform(-4e-4, 4e-4)))
    m_rev = [jitter(x) for x in d["rev"]]
    m_capex = [jitter(x) for x in d["capex"]]
    if has("model_revenue_py"):
        m_rev[1] = round(d["rev"][1] * (1 + rng.choice([-1, 1]) * (rng.uniform(.012, .03) if hard else rng.uniform(.03, .08))))
    if has("model_capex"):
        m_capex[2] = round(d["capex"][2] * (1 + rng.choice([-1, 1]) * (rng.uniform(.03, .08) if hard else rng.uniform(.2, .4))))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Operating model, USD thousands"
    ws.append([]); ws.append(["Line item", *YEARS])
    for label, vals in ((rev_lab, m_rev), ("EBITDA", [jitter(x) for x in d["ebitda"]]),
                        ("Net income", [jitter(x) for x in d["ni"]]), (rng.choice(["Capital expenditure", "Capex"]) if hard else "Capex", m_capex)):
        ws.append([label, *vals])
    w2 = wb.create_sheet("Debt")
    w2["A1"] = "USD thousands"
    w2.append([]); w2.append(["Line item", "FY2023", "FY2024"])
    w2.append(["Cash", jitter(d["cash"][0]), jitter(d["cash"][1])])
    w2.append(["Total debt", jitter(d["debt"][0]), jitter(d["debt"][1])])
    wb.save(out / "operating_model.xlsx")

    truth = [{"issue": k, "kind": ISSUES[k][0], "metric": ISSUES[k][1], "period": ISSUES[k][2]} for k in issues]
    (out / "truth.json").write_text(json.dumps({"seed": seed, "planted": truth}, indent=2))
    return truth


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    for t in build(a.out, a.seed):
        print("planted:", t["issue"])
