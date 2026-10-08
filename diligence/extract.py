"""
Reads a folder of Indian deal documents (management deck .pptx, audited
Ind AS statements .pdf, operating model .xlsx) and turns every number it can
recognise into a Fact with its source location.

Money is stored in rupees whatever the document used (crore, lakh, million).
Periods are Indian financial years (April to March), stored as FY2024 for the
year ended 31 March 2024, whether the document wrote FY24, FY2023-24 or
"31 March 2024". Projection columns (FY25E, FY26P) are ignored.

Footnotes are read too: markers on row labels ((1), *, a superscript), the footnote
text under the table, "Note:" lines and Excel cell comments. Each footnote is
linked to the figures it qualifies, and the amounts and wording in it (adjusted,
excludes, includes, pro forma, unaudited) are kept with the figure so the
reconciliation can say whether a gap is explained by what the footnote discloses.

It is regex/label based, so it works on documents laid out like the sample
deal room and will miss things on messier files. Anything it can't read is
skipped quietly, which means "no finding" is not the same as "checked".
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

ROLE_BY_EXT = {".pptx": "deck", ".pdf": "audited", ".xlsx": "model"}

LABELS = {
    "revenue": {"revenue from operations", "total revenue from operations", "revenue", "revenues", "total revenue",
                "net sales", "net revenue", "sales"},
    "material_cost": {"cost of materials consumed", "cost of materials", "raw material cost"},
    "total_expenses": {"total expenses"},
    "gross_profit": {"gross profit"},
    "gross_margin": {"gross margin", "gross margin %"},
    "ebitda": {"ebitda"},
    "ebitda_margin": {"ebitda margin", "ebitda margin %"},
    "operating_income": {"operating income", "ebit", "income from operations"},
    "da": {"depreciation and amortisation expense", "depreciation and amortisation", "depreciation & amortisation",
           "depreciation and amortization", "d&a"},
    "finance_costs": {"finance costs", "finance cost", "interest expense"},
    "net_income": {"profit for the year", "profit for the period", "profit after tax", "pat", "net profit", "net income"},
    "cash": {"cash and cash equivalents", "cash & cash equivalents", "cash"},
    "debt_noncurrent": {"non-current borrowings", "long-term borrowings", "long term borrowings"},
    "debt_current": {"current borrowings", "short-term borrowings", "short term borrowings"},
    "total_debt": {"total debt", "total borrowings", "gross debt", "borrowings", "debt"},
    "net_debt": {"net debt"},
    "capex": {"purchase of property, plant and equipment", "purchase of property, plant & equipment",
              "purchase of property, plant and equipment and intangible assets", "capital expenditure",
              "capital expenditures", "capex"},
    "customer_concentration": {"top customer", "largest customer"},
    "order_book": {"order book", "order backlog", "orders on hand"},
    "contingent_liabilities": set(),
    "audit_emphasis": set(), "going_concern": set(), "audit_qualified": set(),
}
LABEL_TO_METRIC = {lab: m for m, labs in LABELS.items() for lab in labs}
PCT_METRICS = {"gross_margin", "ebitda_margin", "customer_concentration"}

SCALE = {"cr": 1e7, "crore": 1e7, "crores": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
         "m": 1e6, "mm": 1e6, "mn": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9,
         "k": 1e3, "thousand": 1e3}
NUM = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?")
AMOUNT = re.compile(r"(?:₹|rs\.?|inr)?\s?(\d[\d,]*(?:\.\d+)?)\s*"
                    r"(%|crores?|cr|lakhs?|lacs?|million|billion|thousand|mm|mn|bn|m|b|k)?(?![A-Za-z])", re.I)

PERIOD = re.compile(r"""
    (?:FY|F\.Y\.?)\s?(?P<a>\d{4})\s?[-–/]\s?(?P<b>\d{4}|\d{2})(?P<s1>[A-Za-z]?)(?![\d])
  | (?:FY|F\.Y\.?)\s?(?P<c>\d{4}|\d{2})(?P<s2>[A-Za-z]?)(?![\d])
  | (?<![\d-])(?P<d>\d{4})\s?[-–]\s?(?P<e>\d{2})(?![\d-])
  | (?:31(?:st)?\s+March,?\s+|March\s+31,?\s+)(?P<f>\d{4})
""", re.I | re.X)
PROJECTION = set("EPFB")


@dataclass
class Note:
    """a footnote, cell comment or 'Note:' line, with what it says about the figures."""
    key: str            # normalised marker: "1", "*", "†"; "" when unmarked
    text: str
    doc: str
    file: str
    loc: str
    amounts: list = field(default_factory=list)   # rupee amounts mentioned
    tags: list = field(default_factory=list)      # adjusted, excludes, includes, pro_forma, unaudited, ...


@dataclass
class Fact:
    metric: str
    period: str
    value: float        # rupees for money, percentage points for pct (1.0 for a flag)
    unit: str           # inr / pct / flag
    doc: str            # deck / audited / model
    file: str
    loc: str
    text: str = ""
    precision: float = 0.0
    derived: bool = False
    overridden: bool = False
    mark: str = ""      # footnote marker on the label, if any
    notes: list = field(default_factory=list)


def periods_in(text):
    """financial years mentioned in text, in order. None marks a projection (FY25E)."""
    out = []
    for m in PERIOD.finditer(str(text)):
        suffix = (m.group("s1") or m.group("s2") or "").upper()
        if m.group("a"):
            start, end = int(m.group("a")), m.group("b")
            end = int(end) if len(end) == 4 else start // 100 * 100 + int(end)
            if end != start + 1:
                continue
        elif m.group("c"):
            end = int(m.group("c"))
            end = end if end > 99 else 2000 + end
        elif m.group("d"):
            start = int(m.group("d"))
            end = start // 100 * 100 + int(m.group("e"))
            if end != start + 1:
                continue
        elif m.group("f"):
            end = int(m.group("f"))
        out.append(None if suffix in PROJECTION else f"FY{end}")
    return out


SUP = str.maketrans("¹²³⁴⁵⁶⁷⁸⁹⁰", "1234567890")
MARKER = r"(\(\d{1,2}\)|\[\d{1,2}\]|\*{1,3}|†|‡|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)"
TRAILING_MARK = re.compile(r"^(.*?\S)\s*" + MARKER + r"\s*$")
FN_LINE = re.compile(r"^\s*" + MARKER + r"\s+(\S.*?)\s*$")
UNMARKED_NOTE = re.compile(r"^\s*(?:notes?|source|sources)\s*:\s*(\S.*?)\s*$", re.I)
AMT_CUR = re.compile(r"(?:₹|rs\.?|inr)?\s?(\d[\d,]*(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|million|mn)\b", re.I)
TAGS = {
    "adjusted": r"\badjusted\b",
    "excludes": r"\b(?:excludes?|excluding|exclusive of|before|net of|other than)\b",
    "includes": r"\b(?:includes?|including|inclusive of|incl\.)",
    "pro_forma": r"pro[- ]?forma",
    "unaudited": r"unaudited|management accounts|provisional|limited review",
    "run_rate": r"run[- ]?rate|annuali[sz]ed",
    "standalone": r"standalone",
}


def norm_marker(m):
    m = m.strip().translate(SUP)
    return m.strip("()[]") if m[:1] in "([" else m


def split_marker(text):
    """'EBITDA (1)' -> ('EBITDA', '1'); 'Net debt*' -> ('Net debt', '*'); no marker -> (text, '')."""
    m = TRAILING_MARK.match(str(text))
    if m and not re.fullmatch(r"\(\s*\d{1,2}\s*\)", str(text).strip()):
        return m.group(1), norm_marker(m.group(2))
    return str(text), ""


def analyse_note(text):
    amounts = []
    for m in AMT_CUR.finditer(text):
        amounts.append(float(m.group(1).replace(",", "")) * SCALE[m.group(2).lower()])
    tags = [t for t, rx in TAGS.items() if re.search(rx, text, re.I)]
    return amounts, tags


def make_note(key, text, doc, file, loc):
    amounts, tags = analyse_note(text)
    return Note(key, text.strip()[:300], doc, file, loc, amounts, tags)


def note_from_line(line, doc, file, loc):
    """a footnote definition ('(1) Excludes ...', '* Adjusted ...', 'Note: ...') or None."""
    m = FN_LINE.match(line)
    if m:
        return make_note(norm_marker(m.group(1)), m.group(2), doc, file, loc)
    m = UNMARKED_NOTE.match(line)
    if m:
        return make_note("", m.group(1), doc, file, loc)
    return None


def mention_rx(metric):
    words = sorted(LABELS.get(metric, ()), key=len, reverse=True)
    words = [w for w in words if len(w) > 2]
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.I) if words else None


def link_notes(facts, notes):
    """attach each note to the figures it is marked on, or that its text names."""
    for f in facts:
        for n in notes:
            marked = f.mark and n.key == f.mark
            rx = mention_rx(f.metric)
            named = (not n.key) and (n.amounts or n.tags) and rx and rx.search(n.text)
            if (marked or named) and n not in f.notes:
                f.notes.append(n)


def clean_label(s):
    s = re.sub(r"\(.*?\)", "", str(s)).replace("$", "").replace("₹", "").replace(":", "")
    s = re.sub(r"[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def scale_word(text):
    """crore / lakh / million / thousand from a header or label, else None."""
    t = str(text).lower().replace(" ", "")
    for words, mult in ((("crore", "crores", "cr", "inrcr", "₹cr", "rscr", "rs.cr"), 1e7),
                        (("lakh", "lakhs", "lac", "lacs"), 1e5),
                        (("million", "mn", "mm", "m"), 1e6),
                        (("thousand", "'000", "000", "000s", "k"), 1e3)):
        if any(t.endswith(w) or ("in" + w) in t for w in words):
            return mult
    return None


def unit_hint(label):
    """scale or '%' from a label like 'Revenue (₹ Cr)' or 'EBITDA margin (%)'."""
    m = re.search(r"\((.*?)\)", str(label))
    if not m:
        return None
    h = re.sub(r"(₹|rs\.?|inr|usd|\$)", "", m.group(1).lower()).replace(" ", "")
    if "%" in h:
        return "%"
    return scale_word(h)


def header_scale(text):
    """'(₹ in crore)', 'Rs. in lakhs', 'INR million' in a header line."""
    m = re.search(r"(crores?|lakhs?|lacs?|million|thousand)", str(text), re.I)
    return SCALE[m.group(1).lower()] if m else None


def parse_cell(s):
    """returns (value, decimals, is_pct) or None."""
    s = str(s).strip()
    m = NUM.fullmatch(s.replace("₹", "").replace(" ", ""))
    if not m:
        return None
    raw = m.group(0)
    neg = raw.startswith("(") or raw.startswith("-")
    pct = raw.endswith("%")
    digits = raw.strip("()-%").replace(",", "")
    dec = len(digits.split(".")[1]) if "." in digits else 0
    v = float(digits)
    return (-v if neg else v), dec, pct


def make_fact(metric, period, num, dec, scale_or_pct, doc, file, loc, text):
    pct = metric in PCT_METRICS or scale_or_pct == "%"
    if pct:
        value, unit, prec = num, "pct", 0.5 * 10 ** -dec
    else:
        scale = scale_or_pct if isinstance(scale_or_pct, (int, float)) else 1.0
        value, unit, prec = num * scale, "inr", 0.5 * 10 ** -dec * scale
    if metric == "capex":
        value = abs(value)
    return Fact(metric, period, value, unit, doc, file, loc, text.strip()[:160], prec)


def scan_text(line, doc, file, loc, default_scale=1.0):
    """'Net debt (FY24): ₹18.0 Cr' style lines and 'x% of revenue' customer notes."""
    out = []
    line, mark = split_marker(line)
    low = line.lower()
    if "customer" in low and "%" in line and "revenue" in low:
        per = [p for p in periods_in(line) if p]
        if per:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            dec = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
            out.append(make_fact("customer_concentration", per[0], float(m.group(1)), dec, "%", doc, file, loc, line))
        for f in out:
            f.mark = mark
        return out
    m = re.match(r"^\s*[•\-\*]?\s*([A-Za-z][A-Za-z ,&/\-]*?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$", line)
    if not m:
        return out
    metric = LABEL_TO_METRIC.get(clean_label(m.group(1)))
    if not metric:
        return out
    pers = periods_in(m.group(2) if m.group(2) else line)
    a = AMOUNT.search(m.group(3))
    if not pers or pers[0] is None or not a:
        return out
    num_s, unit = a.group(1).replace(",", ""), (a.group(2) or "").lower()
    dec = len(num_s.split(".")[1]) if "." in num_s else 0
    hint = "%" if unit == "%" else SCALE.get(unit, default_scale)
    out.append(make_fact(metric, pers[0], float(num_s), dec, hint, doc, file, loc, line))
    out[-1].mark = mark
    return out


DISCLOSURE_FLAGS = (
    ("audit_emphasis", re.compile(r"emphasis of matter", re.I)),
    ("going_concern", re.compile(r"material uncertainty related to going concern", re.I)),
    ("audit_qualified", re.compile(r"basis for (?:qualified|adverse) opinion|basis for disclaimer of opinion", re.I)),
)


def scan_disclosure(line, doc, file, loc, scale=1.0):
    """facts that only live in the notes or the auditor's report: contingent liabilities and audit flags."""
    out = []
    for metric, rx in DISCLOSURE_FLAGS:
        if rx.search(line):
            out.append(Fact(metric, "CURRENT", 1.0, "flag", doc, file, loc, line.strip()[:160]))
    if re.search(r"contingent liabilit", line, re.I):
        m = AMT_CUR.search(line)
        if m:
            per = [p for p in periods_in(line) if p]
            num = m.group(1).replace(",", "")
            dec = len(num.split(".")[1]) if "." in num else 0
            f = make_fact("contingent_liabilities", per[0] if per else "CURRENT", float(num), dec,
                          SCALE[m.group(2).lower()], doc, file, loc, line)
            out.append(f)
    return out


FILLER = {"particulars", "note", "notes", "no", "year", "ended", "as", "at", "for", "the", "march", "fy", "in", "of", "and"}


def is_header(line):
    """a line that is just a row of year labels, e.g. 'Particulars Note FY2023-24 FY2022-23'."""
    ps = periods_in(line)
    if len(ps) < 2:
        return False
    rest = PERIOD.sub(" ", line).lower()
    words = [w for w in re.findall(r"[a-z]{3,}", rest) if w not in FILLER]
    return not words


def read_pdf(path, doc):
    import pdfplumber
    facts = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            lines = (page.extract_text() or "").splitlines()
            periods, scale = [], 1.0
            for ln in lines:
                if is_header(ln):
                    periods = periods_in(ln)
                hs = header_scale(ln) if re.search(r"(in|₹|rs|inr)", ln, re.I) and len(ln) < 90 else None
                if hs:
                    scale = hs
            page_facts, notes, last = [], [], None
            for ln in lines:
                got = scan_text(ln, doc, path.name, f"p.{pno}")
                page_facts += got
                page_facts += scan_disclosure(ln, doc, path.name, f"p.{pno}", scale)
                m = re.match(r"^(.*?[A-Za-z\)\*†‡¹²³⁴⁵⁶⁷⁸⁹⁰\]])\s+((?:\(?-?\d[\d,]*(?:\.\d+)?\)?%?\s*)+)$", ln.strip())
                row_ok = bool(m and periods)
                n = None if (got or row_ok) else note_from_line(ln, doc, path.name, f"p.{pno}")
                if n:
                    notes.append(n)
                    last = n
                    continue
                if last is not None and not got and not row_ok and not is_header(ln) and ln.strip() \
                        and not FN_LINE.match(ln) and len(last.text) < 280 and not re.match(r"^\s*note \d+\.", ln, re.I):
                    # a footnote wrapped onto the next line
                    cont = make_note(last.key, last.text + " " + ln.strip(), doc, path.name, last.loc)
                    last.text, last.amounts, last.tags = cont.text, cont.amounts, cont.tags
                    continue
                last = None
                if not row_ok:
                    continue
                label_raw, mark = split_marker(m.group(1))
                label, nums = clean_label(label_raw), NUM.findall(m.group(2))
                if not mark and len(nums) > len(periods) and re.fullmatch(r"\(\d{1,2}\)", nums[0]):
                    mark, nums = norm_marker(nums[0]), nums[1:]    # "(1)" sat between the label and the figures
                if len(nums) > len(periods):
                    nums = nums[-len(periods):]      # drop the note-number column
                if label.startswith("segment ") or label == "total segment revenue":
                    metric = "segment_revenue" if label.startswith("segment ") else "segment_total"
                else:
                    metric = LABEL_TO_METRIC.get(label)
                if not metric:
                    continue
                for per, num in zip(periods, nums):
                    c = parse_cell(num)
                    if c and per:
                        f = make_fact(metric, per, c[0], c[1], "%" if c[2] else scale, doc, path.name, f"p.{pno}", ln)
                        f.mark = mark
                        page_facts.append(f)
            link_notes(page_facts, notes)
            facts += page_facts
    return facts


def read_pptx(path, doc):
    from pptx import Presentation
    facts = []
    for sno, slide in enumerate(Presentation(str(path)).slides, 1):
        slide_facts, notes = [], []
        for shape in slide.shapes:
            if shape.has_table:
                rows = [[c.text for c in r.cells] for r in shape.table.rows]
                periods = [(periods_in(c) or [None])[0] for c in rows[0][1:]]
                for r in rows[1:]:
                    label_raw, mark = split_marker(r[0])
                    metric = LABEL_TO_METRIC.get(clean_label(label_raw))
                    hint = unit_hint(label_raw) or unit_hint(rows[0][0])
                    if not metric:
                        continue
                    for per, cell in zip(periods, r[1:]):
                        c = parse_cell(cell)
                        if c and per:
                            f = make_fact(metric, per, c[0], c[1], hint or 1.0, doc, path.name,
                                          f"slide {sno}", " | ".join(r))
                            f.mark = mark
                            slide_facts.append(f)
            elif shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    txt = "".join(r.text for r in para.runs)
                    got = scan_text(txt, doc, path.name, f"slide {sno}")
                    slide_facts += got
                    n = None if got else note_from_line(txt, doc, path.name, f"slide {sno}")
                    if n:
                        notes.append(n)
        link_notes(slide_facts, notes)
        facts += slide_facts
    return facts


def read_xlsx(path, doc):
    import openpyxl
    facts = []
    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        scale, header_row, cols = 1.0, None, {}
        sheet_facts, notes = [], []
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 6)):
            for c in row:
                if isinstance(c.value, str):
                    hs = header_scale(c.value)
                    if hs:
                        scale = hs
        for row in ws.iter_rows():
            toks = {c.column: periods_in(c.value) for c in row if isinstance(c.value, str) and periods_in(c.value)}
            if len(toks) >= 2 and header_row is None:
                header_row = row[0].row
                cols = {k: v[0] for k, v in toks.items() if v[0]}
                continue
            if header_row is None or row[0].row <= header_row:
                continue
            label = next((c.value for c in row if isinstance(c.value, str)), None)
            if label:
                n = note_from_line(label, doc, path.name, f"{ws.title}!{row[0].coordinate}")
                if n:
                    notes.append(n)
                    continue
            label_raw, mark = split_marker(label) if label else ("", "")
            metric = LABEL_TO_METRIC.get(clean_label(label_raw)) if label else None
            if not metric:
                continue
            for c in row:
                if c.column in cols and isinstance(c.value, (int, float)):
                    dec = len(str(c.value).split(".")[1]) if "." in str(c.value) else 0
                    f = make_fact(metric, cols[c.column], float(c.value), dec, scale, doc, path.name,
                                  f"{ws.title}!{c.coordinate}", f"{label}: {c.value}")
                    f.mark = mark
                    if c.comment and c.comment.text:
                        f.notes.append(make_note("", c.comment.text, doc, path.name, f"{ws.title}!{c.coordinate} (comment)"))
                    sheet_facts.append(f)
        link_notes(sheet_facts, notes)
        facts += sheet_facts
    return facts


READERS = {".pptx": read_pptx, ".pdf": read_pdf, ".xlsx": read_xlsx}


def read_deal_room(folder):
    facts, skipped = [], []
    for p in sorted(Path(folder).iterdir()):
        ext = p.suffix.lower()
        if ext in READERS:
            facts += READERS[ext](p, ROLE_BY_EXT[ext])
        elif p.is_file() and p.name != "truth.json" and not p.name.endswith(".py"):
            skipped.append(p.name)
    return facts, skipped
