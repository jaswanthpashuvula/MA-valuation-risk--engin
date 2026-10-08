"""
Checks a folder of Indian deal documents (management deck, audited Ind AS
statements, operating model) for numbers that disagree, and writes a report
with the source of every claim.

    python dealcheck.py sample_deal
    python dealcheck.py sample_deal --overrides overrides.csv --out output/diligence

overrides.csv (optional): doc,metric,period,value,unit,reason,analyst
  doc is deck/audited/model, period like FY2024, unit is crore, lakh, inr or pct
  (blank means crore for money). Use it when the extractor read a number wrong;
  the override is written to the audit log.
"""
import argparse
import csv
from pathlib import Path

from diligence import audit, extract, reconcile, report, scenarios


UNITS = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "inr": 1.0, "": 1e7}


def apply_overrides(facts, path):
    n = 0
    for row in csv.DictReader(open(path)):
        pct = row["metric"] in extract.PCT_METRICS
        value = float(row["value"]) * (1.0 if pct else UNITS[(row.get("unit") or "").strip().lower()])
        hit = [f for f in facts if f.doc == row["doc"] and f.metric == row["metric"] and f.period == row["period"]]
        for f in hit:
            f.value, f.overridden, f.text = value, True, f"override by {row['analyst']}: {row['reason']}"
        if not hit:
            facts.append(extract.Fact(row["metric"], row["period"], value, "pct" if pct else "inr", row["doc"],
                                      "override", "analyst entry", row["reason"], overridden=True))
        n += 1
    return n


def check(folder, out_dir, overrides=None, with_scenarios=True, quiet=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    facts, skipped = extract.read_deal_room(folder)
    n_over = apply_overrides(facts, overrides) if overrides else 0
    facts, findings = reconcile.run_checks(facts)
    report.write_report(findings, skipped, out, n_over)
    audit.append(out / "audit_log.jsonl", {
        "action": "check", "inputs": {p.name: audit.sha256_file(p) for p in sorted(Path(folder).iterdir())
                                      if p.suffix.lower() in extract.READERS},
        "facts": len(facts), "findings": len(findings), "overrides": n_over})
    res = None
    if with_scenarios:
        periods = sorted({f.period for f in facts})
        res = scenarios.run(facts, periods[-1], periods)
        if res:
            scenarios.plot(res, out / "scenario_summary.png", periods[-1])
    if not quiet:
        for f in findings:
            print(f"{f.id} [{f.severity:6}] {f.kind:11} {f.metric} {f.period}")
        if res:
            gap = (res["equity_deck"] - res["equity_audited"]) / 1e7
            print(f"equity value as pitched vs audited: {gap:+,.1f} crore (wacc {res['wacc']:.0%}, growth {res['growth']:.1%})")
    return facts, findings, res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="output/diligence")
    ap.add_argument("--overrides")
    ap.add_argument("--no-scenarios", action="store_true")
    a = ap.parse_args()
    check(a.folder, a.out, a.overrides, not a.no_scenarios)
