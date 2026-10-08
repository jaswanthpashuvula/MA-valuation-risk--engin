"""
Small DCF used to put a dollar figure on a discrepancy. Gordon-growth terminal
value, flat margins, WACC and growth are assumptions you pass in, not outputs.
"""
import numpy as np


def enterprise_value(rev0, growth, margin, da_pct, capex_pct, wacc, tg=0.025, years=5, tax=0.25, nwc_pct=0.10):
    prev, pv, fcff = rev0, 0.0, 0.0
    for t in range(1, years + 1):
        rev = prev * (1 + growth)
        da = rev * da_pct
        ebit = rev * margin - da
        fcff = ebit * (1 - tax) + da - rev * capex_pct - (rev - prev) * nwc_pct
        pv += fcff / (1 + wacc) ** t
        prev = rev
    tv = fcff * (1 + tg) / (max(wacc, tg + 0.005) - tg)
    return pv + tv / (1 + wacc) ** years


def _get(facts, doc, metric, period):
    for f in facts:
        if f.doc == doc and f.metric == metric and f.period == period:
            return f.value
    return None


def base_inputs(facts, period):
    """audited numbers where they exist; deck numbers for revenue/ebitda/net debt for the 'as pitched' case."""
    aud = {m: _get(facts, "audited", m, period) for m in ("revenue", "ebitda", "da", "capex", "net_debt")}
    deck = {m: _get(facts, "deck", m, period) for m in ("revenue", "ebitda", "net_debt")}
    return aud, deck


def cagr(facts, periods):
    revs = [_get(facts, "audited", "revenue", p) for p in periods]
    revs = [r for r in revs if r]
    if len(revs) < 2:
        return 0.05
    return float(np.clip((revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1, -0.1, 0.25))


def run(facts, period, periods, wacc=0.10, tg=0.025):
    aud, deck = base_inputs(facts, period)
    if None in aud.values():
        return None
    g = cagr(facts, periods)

    def ev_for(rev, ebitda):
        return enterprise_value(rev, g, ebitda / rev, aud["da"] / aud["revenue"], aud["capex"] / aud["revenue"], wacc, tg)

    ev_aud = ev_for(aud["revenue"], aud["ebitda"])
    rev_d = deck["revenue"] or aud["revenue"]
    ebitda_d = deck["ebitda"] or aud["ebitda"]
    nd_d = deck["net_debt"] if deck["net_debt"] is not None else aud["net_debt"]
    ev_deck = ev_for(rev_d, ebitda_d)
    grid_g = np.arange(max(g - 0.04, -0.05), g + 0.0401, 0.02)
    grid_w = np.arange(wacc - 0.02, wacc + 0.0201, 0.01)
    grid = np.array([[enterprise_value(aud["revenue"], gg, aud["ebitda"] / aud["revenue"], aud["da"] / aud["revenue"],
                                       aud["capex"] / aud["revenue"], ww, tg) for gg in grid_g] for ww in grid_w])
    return {"growth": g, "wacc": wacc, "tg": tg, "ev_audited": ev_aud, "ev_deck": ev_deck,
            "equity_audited": ev_aud - aud["net_debt"], "equity_deck": ev_deck - nd_d,
            "grid": grid, "grid_g": grid_g, "grid_w": grid_w}


def plot(res, out_path, period):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1.2, 1]})
    im = a.imshow(res["grid"] / 1e6, cmap="Blues", aspect="auto", origin="lower")
    a.set_xticks(range(len(res["grid_g"])), [f"{x:.1%}" for x in res["grid_g"]])
    a.set_yticks(range(len(res["grid_w"])), [f"{x:.1%}" for x in res["grid_w"]])
    for i in range(res["grid"].shape[0]):
        for j in range(res["grid"].shape[1]):
            a.text(j, i, f"{res['grid'][i, j] / 1e6:,.0f}", ha="center", va="center", fontsize=8,
                   color="white" if res["grid"][i, j] > 0.75 * res["grid"].max() else "black")
    a.set_xlabel("revenue growth"); a.set_ylabel("WACC")
    a.set_title("EV on audited numbers ($M)")
    labels = ["audited", "as pitched in deck"]
    vals = [res["equity_audited"] / 1e6, res["equity_deck"] / 1e6]
    b.bar(labels, vals, color=["#3b6ea5", "#c8793b"], width=0.5)
    for i, v in enumerate(vals):
        b.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
    gap = vals[1] - vals[0]
    b.set_title(f"Equity value, {period} base: deck is {gap:+,.0f}M vs audited")
    b.set_ylabel("$M")
    for ax in (a, b):
        ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
