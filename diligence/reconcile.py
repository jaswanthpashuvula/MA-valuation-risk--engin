"""
Compares facts across documents and checks a few things inside single
documents. The audited statements are treated as the reference, then the
model, then the deck (the deck is the document most likely to be rounded up).
"""
import re
from collections import defaultdict
from dataclasses import dataclass

from .extract import Fact

PRIORITY = {"audited": 0, "model": 1, "deck": 2}
NO_CROSS = {"ebitda_margin", "segment_revenue", "segment_total", "gross_profit", "operating_income", "da", "total_debt",
            "total_expenses", "finance_costs", "material_cost", "debt_noncurrent", "debt_current"}
NO_UNSUPPORTED = {"ebitda_margin"}
REL_TOL = 0.005      # 0.5% on money
PCT_TOL = 0.5        # half a percentage point on ratios


@dataclass
class Finding:
    id: str
    kind: str            # mismatch / unsupported / internal
    metric: str
    period: str
    severity: str
    claim: Fact
    ref: Fact = None
    diff: float = 0.0
    note: str = ""
    question: str = ""


VERB = {"deck": "shows", "audited": "show", "model": "shows"}
DOCNAME = {"deck": "the deck", "audited": "the audited statements", "model": "the model"}
LOC = re.compile(r"p\.\d+|slide \d+|[A-Za-z0-9_ ]+![A-Z]+\d+")


def merge_locs(*locs):
    found = []
    for loc in locs:
        for m in LOC.findall(loc):
            if m.strip() not in found:
                found.append(m.strip())
    return ", ".join(found)


def fmt(f_or_v, unit=None):
    v, u = (f_or_v.value, f_or_v.unit) if isinstance(f_or_v, Fact) else (f_or_v, unit)
    if u == "pct":
        return f"{v:.1f}%"
    a = abs(v)
    s = f"₹{a/1e7:,.2f} cr" if a >= 1e6 else f"₹{a/1e5:,.2f} lakh" if a >= 1e4 else f"₹{a:,.0f}"
    return "-" + s if v < 0 else s


def derive(facts):
    """fills in ebitda, debt, net debt and gross margin where a document only gives the pieces.

    Ind AS statements list expenses by nature and have no EBITDA or gross profit line, so those
    are built from the lines that are there and the components are cited."""
    idx = {(f.doc, f.metric, f.period): f for f in facts if f.metric not in ("segment_revenue",)}
    out = []

    def add(f):
        out.append(f)
        idx[(f.doc, f.metric, f.period)] = f

    for doc, period in sorted({(f.doc, f.period) for f in facts}):
        g = lambda m: idx.get((doc, m, period))
        if not g("ebitda") and g("revenue") and g("total_expenses") and g("finance_costs") and g("da"):
            r, te, fc, d = g("revenue"), g("total_expenses"), g("finance_costs"), g("da")
            add(Fact("ebitda", period, r.value - (te.value - fc.value - d.value), "inr", doc, r.file,
                     merge_locs(r.loc, te.loc, fc.loc, d.loc),
                     "revenue from operations - (total expenses - finance costs - depreciation)",
                     r.precision + te.precision + fc.precision + d.precision, derived=True))
        if not g("ebitda") and g("operating_income") and g("da"):
            a, b = g("operating_income"), g("da")
            add(Fact("ebitda", period, a.value + b.value, "inr", doc, a.file, merge_locs(a.loc, b.loc),
                     "operating income + D&A", a.precision + b.precision, derived=True))
        if not g("total_debt") and g("debt_noncurrent") and g("debt_current"):
            a, b = g("debt_noncurrent"), g("debt_current")
            add(Fact("total_debt", period, a.value + b.value, "inr", doc, a.file, merge_locs(a.loc, b.loc),
                     "non-current + current borrowings", a.precision + b.precision, derived=True))
        if not g("net_debt") and g("total_debt") and g("cash"):
            a, b = g("total_debt"), g("cash")
            add(Fact("net_debt", period, a.value - b.value, "inr", doc, a.file, merge_locs(a.loc, b.loc),
                     "borrowings less cash and cash equivalents", a.precision + b.precision, derived=True))
        if not g("gross_profit") and g("revenue") and g("material_cost"):
            a, b = g("revenue"), g("material_cost")
            add(Fact("gross_profit", period, a.value - b.value, "inr", doc, a.file, merge_locs(a.loc, b.loc),
                     "revenue - cost of materials consumed", a.precision + b.precision, derived=True))
        if not g("gross_margin") and g("gross_profit") and g("revenue"):
            a, b = g("gross_profit"), g("revenue")
            add(Fact("gross_margin", period, 100 * a.value / b.value, "pct", doc, a.file, merge_locs(a.loc, b.loc),
                     "(revenue - cost of materials) / revenue", 0.0, derived=True))
    return facts + out


def allowed(ref, other):
    if ref.unit == "pct":
        return max(PCT_TOL, ref.precision + other.precision)
    return max(REL_TOL * abs(ref.value), ref.precision + other.precision)


def severity(ref, diff):
    if ref.unit == "pct":
        d = abs(diff)
        return "high" if d >= 5 else "medium" if d >= 2 else "low"
    r = abs(diff) / abs(ref.value) if ref.value else 1
    return "high" if r >= 0.10 else "medium" if r >= 0.03 else "low"


HINTS = {
    "revenue": "Ask for a revenue bridge by segment, whether the figure is net of GST and trade discounts, and whether it includes pro-forma or acquired revenue.",
    "ebitda": "Ask for the bridge from profit before tax (add finance costs and depreciation, strip other income and exceptional items) and every add-back with support.",
    "net_debt": "Ask which debt-like items are in each figure (lease liabilities under Ind AS 116, promoter loans, bill discounting, deferred consideration) and which cash balances count (cash and cash equivalents versus other bank balances and deposits).",
    "gross_margin": "Ask how cost of sales is defined in the deck, since Ind AS statements list expenses by nature (materials, purchases of stock-in-trade, changes in inventory, freight, job work).",
    "capex": "Ask for the fixed asset schedule and whether capital work in progress, capitalised borrowing costs and intangibles are in the model figure.",
    "customer_concentration": "Ask for revenue by top 10 customers, and the contract terms and renewal dates for the largest.",
    "cash": "Ask for the bank reconciliation and whether any balances are lien-marked, held as margin money or otherwise restricted.",
    "net_income": "Ask for the bridge from EBITDA to profit after tax, including exceptional items, deferred tax and any 'adjusted PAT' definition.",
    "order_book": "Ask for the order book by customer with order dates, delivery schedule and cancellation terms, and how it ties to revenue recognition under Ind AS 115.",
}


def question(f):
    c, r = f.claim, f.ref
    if f.kind == "mismatch":
        q = (f"{DOCNAME[c.doc].capitalize()} {VERB[c.doc]} {f.metric.replace('_', ' ')} of {fmt(c)} for {f.period} ({c.loc}) but "
             f"{DOCNAME[r.doc]} {VERB[r.doc]} {fmt(r)} ({r.loc}). What explains the gap?")
    elif f.kind == "unsupported":
        q = (f"The deck quotes {f.metric.replace('_', ' ')} of {fmt(c)} for {f.period} ({c.loc}) and nothing in the "
             f"statements or model backs it. How is it defined, and can we see the underlying schedule?")
    else:
        q = f.note
    return q + " " + HINTS.get(f.metric, "")


def compare(facts):
    by = defaultdict(list)
    for f in sorted(facts, key=lambda x: x.derived):
        by[(f.metric, f.period)].append(f)
    found = []
    for (metric, period), group in sorted(by.items()):
        docs = {}
        for f in group:
            docs.setdefault(f.doc, f)
        if metric not in NO_CROSS and len(docs) >= 2:
            ref = docs[min(docs, key=PRIORITY.get)]
            for d, f in docs.items():
                if f is ref:
                    continue
                diff = f.value - ref.value
                if abs(diff) > allowed(ref, f):
                    found.append(Finding("", "mismatch", metric, period, severity(ref, diff), f, ref, diff))
        elif len(docs) == 1 and "deck" in docs and metric not in NO_UNSUPPORTED and metric not in NO_CROSS:
            found.append(Finding("", "unsupported", metric, period, "medium", docs["deck"]))
    return found


def internal_checks(facts):
    found = []
    # segment note should add up to reported revenue
    for period in sorted({f.period for f in facts if f.metric == "segment_revenue"}):
        segs = [f for f in facts if f.metric == "segment_revenue" and f.period == period]
        rev = next((f for f in facts if f.metric == "revenue" and f.period == period and f.doc == segs[0].doc), None)
        if not rev:
            continue
        total = sum(s.value for s in segs)
        if abs(total - rev.value) > allowed(rev, segs[0]) * 2:
            c = Fact("revenue", period, total, "inr", segs[0].doc, segs[0].file, segs[0].loc,
                     "sum of segment revenue", sum(s.precision for s in segs), derived=True)
            note = (f"Segment revenue in the notes adds to {fmt(total, 'usd')} for {period} ({segs[0].loc}) but the income "
                    f"statement reports {fmt(rev)} ({rev.loc}). Which is right, and is a segment missing?")
            found.append(Finding("", "internal", "revenue", period, severity(rev, total - rev.value), c, rev,
                                 total - rev.value, note))
    # stated margin should match ebitda / revenue in the same document
    for f in [x for x in facts if x.metric == "ebitda_margin"]:
        e = next((x for x in facts if x.metric == "ebitda" and x.period == f.period and x.doc == f.doc), None)
        r = next((x for x in facts if x.metric == "revenue" and x.period == f.period and x.doc == f.doc), None)
        if e and r:
            calc = 100 * e.value / r.value
            if abs(calc - f.value) > max(PCT_TOL, f.precision):
                c = Fact("ebitda_margin", f.period, calc, "pct", f.doc, f.file, merge_locs(e.loc, r.loc),
                         "ebitda / revenue", 0.0, derived=True)
                note = (f"The {f.doc} states an EBITDA margin of {f.value:.1f}% for {f.period} ({f.loc}) but its own "
                        f"EBITDA and revenue give {calc:.1f}%. Which figure is the one being marketed?")
                found.append(Finding("", "internal", "ebitda_margin", f.period, severity(f, calc - f.value), c, f,
                                     calc - f.value, note))
    return found


def run_checks(facts):
    facts = derive(facts)
    findings = compare(facts) + internal_checks(facts)
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda x: (order[x.severity], x.metric, x.period))
    for i, f in enumerate(findings, 1):
        f.id = f"F{i:02d}"
        f.question = question(f)
    return facts, findings
