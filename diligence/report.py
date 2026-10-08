import csv
from pathlib import Path

from .reconcile import fmt


def gap(f):
    return f"{f.diff:+.1f} pp" if f.claim.unit == "pct" else fmt(f.diff, f.claim.unit)


def write_report(findings, skipped, out_dir, overrides=0):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts = {s: sum(f.severity == s for f in findings) for s in ("high", "medium", "low")}

    with open(out / "findings.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "severity", "kind", "metric", "period", "claim_doc", "claim_value", "claim_location",
                    "reference_doc", "reference_value", "reference_location", "difference", "question"])
        for f in findings:
            r = f.ref
            w.writerow([f.id, f.severity, f.kind, f.metric, f.period, f.claim.doc, fmt(f.claim), f.claim.loc,
                        r.doc if r else "", fmt(r) if r else "", r.loc if r else "",
                        gap(f) if r else "", f.question])

    lines = ["# Diligence check", "",
             f"{len(findings)} findings: {counts['high']} high, {counts['medium']} medium, {counts['low']} low.", ""]
    if overrides:
        lines += [f"{overrides} analyst override(s) applied; see audit_log.jsonl.", ""]
    if skipped:
        lines += ["Files not read (unsupported type): " + ", ".join(skipped), ""]
    lines += ["Reference order when documents disagree: audited statements, then model, then deck.", ""]
    for f in findings:
        lines += [f"## {f.id}  [{f.severity}]  {f.metric.replace('_', ' ')}, {f.period} ({f.kind})", ""]
        lines.append(f"- Claim: {fmt(f.claim)} in {f.claim.doc}, {f.claim.file} {f.claim.loc}")
        if f.claim.text:
            lines.append(f'  - source text: "{f.claim.text}"')
        if f.ref:
            lines.append(f"- Reference: {fmt(f.ref)} in {f.ref.doc}, {f.ref.file} {f.ref.loc}")
            lines.append(f"  - source text: \"{f.ref.text}\"")
            lines.append(f"- Gap: {gap(f)}")
        lines += [f"- Ask: {f.question}", ""]
    (out / "report.md").write_text("\n".join(lines))
