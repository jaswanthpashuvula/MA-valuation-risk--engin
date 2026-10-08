"""
Scores the checker against synthetic Indian deal rooms where the planted problems are
known. A flag counts as correct if (kind, metric, period) matches a planted one.

    python eval_checker.py --n 100
"""
import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path

from diligence import extract, reconcile
from sample_deal.make_deal import ISSUES, build


def run(n=100, start=1000, hard=False, clean=False):
    tp = fp = fn = 0
    by_issue = Counter()
    seen_issue = Counter()
    wrong = []
    fn_total = fn_right = 0
    for seed in range(start, start + n):
        with tempfile.TemporaryDirectory() as tmp:
            planted = build(tmp, seed, issues=[] if clean else None, hard=hard)
            facts, _ = extract.read_deal_room(tmp)
            _, findings = reconcile.run_checks(facts)
        truth = {(t["kind"], t["metric"], t["period"]): t["issue"] for t in planted}
        want = {(t["kind"], t["metric"], t["period"]): t["explained"] for t in planted if t.get("explained")}
        got = {(f.kind, f.metric, f.period) for f in findings}
        for f in findings:
            k = (f.kind, f.metric, f.period)
            if k in want:
                fn_total += 1
                if f.explained == want[k]:
                    fn_right += 1
                else:
                    wrong.append((seed, "footnote check", truth[k], want[k], f.explained or "none"))
        for key, issue in truth.items():
            seen_issue[issue] += 1
            if key in got:
                tp += 1
                by_issue[issue] += 1
            else:
                fn += 1
                wrong.append((seed, "missed", issue))
        for key in got - set(truth):
            fp += 1
            wrong.append((seed, "false flag", key))
    return {"deals": n, "planted": tp + fn, "flags": tp + fp, "correct_flags": tp,
            "false_flags": fp, "missed": fn,
            "footnote_checks": f"{fn_right}/{fn_total}",
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "by_issue": {k: f"{by_issue[k]}/{seen_issue[k]}" for k in ISSUES if seen_issue[k]},
            "errors": wrong}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--start", type=int, default=1000)
    ap.add_argument("--hard", action="store_true")
    ap.add_argument("--clean", action="store_true", help="deals with nothing planted; any flag is a false flag")
    ap.add_argument("--out")
    a = ap.parse_args()
    res = run(a.n, a.start, a.hard, a.clean)
    print(f"{res['deals']} deals, {res['planted']} planted issues, {res['flags']} flags")
    if res["planted"]:
        print(f"precision {res['precision']:.3f}  recall {res['recall']:.3f}  "
              f"(missed {res['missed']}, false flags {res['false_flags']})")
    else:
        print(f"false flags on deals with nothing planted: {res['false_flags']}")
    if res["footnote_checks"] != "0/0":
        print(f"footnote check said the right thing (full/partial/noted) on {res['footnote_checks']}")
    for k, v in res["by_issue"].items():
        print(f"  {k:18} {v}")
    for e in res["errors"][:20]:
        print("  ", e)
    if a.out:
        Path(a.out).write_text(json.dumps({k: v for k, v in res.items() if k != "errors"}, indent=2))
