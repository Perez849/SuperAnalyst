"""The written analysis: one function per page, each returning the page's title block and prose.

All sentences are conditional on the numbers (see prose.Facts); a missing input drops the sentence,
never a placeholder. Blocks: P (paragraph), H (sub-heading), UL (bullets), CALL (call-out box),
TILES (stat strip), ANS (dark answer block). `opt=True` blocks are dropped when a page is too full;
`more=True` blocks appear only when a page has room (see the fit script in pages_template).
"""
from __future__ import annotations

from .clockdata import PHASE_EN, en as _en
from .prose import _neg, b, cap, g_txt, growth_word, join, lev_word, margin_word, money, num_word, ok, pct, pp, ps, spct, xm


# --------------------------------------------------------------------------- #
#  block constructors
# --------------------------------------------------------------------------- #
def P(html, lead=False, opt=False, more=False):
    return {"t": "p", "html": html, "lead": lead, "opt": opt, "more": more}


def H(text, opt=False, more=False):
    return {"t": "h", "html": text, "opt": opt, "more": more}


def UL(items, opt=False, more=False):
    return {"t": "ul", "items": items, "opt": opt, "more": more}


def CALL(title, items, opt=False, more=False):
    return {"t": "callout", "title": title, "items": items, "opt": opt, "more": more}


def TILES(items):
    return {"t": "tiles", "items": items}


def PULL(html, opt=False, more=False):
    return {"t": "pull", "html": html, "opt": opt, "more": more}


def _mult(f, key):
    return f.mult_by.get(key)


def _lens(f, *keys):
    for k in keys:
        if k in f.lens_by_key:
            return f.lens_by_key[k]
    return None


def _cyc_clause(f) -> str:
    c = f.cyc
    if not c:
        return ""
    s = f"The Reloj de inversión reads {b(f.phase_en)} with {_strength(c['strength'])} conviction"
    if c.get("tilt") is not None and f.asset_en:
        s += f"; the {f.asset_en} sleeve has a probability-weighted tilt of {b(pp(c['tilt']))} a year against the US market"
    return s + "."


def _strength(s):
    return {"Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}.get(s, s or "n/a").lower()


def _roic_story(f, roics) -> str:
    """How today's ROIC sits against its own history (never calls a decline a recovery)."""
    last, prev, mx, mn = roics[-1], roics[-2], max(roics), min(roics)
    if last <= 0:
        return "still negative"
    if prev < last * 0.7 and mn < last * 0.5:
        return "a recovery from a trough rather than a steady state: the thesis needs it to hold"
    if last >= 0.9 * mx and len(roics) >= 3:
        return "at the top of the range the business has delivered in the window, so the thesis needs it to hold"
    if last < 0.7 * mx:
        return f"below the {pct(mx, 0)} peak of the window" + (", though still above the cost of capital" if last > f.wacc else ", and not above the cost of capital")
    return "within the range the business has delivered before"


def _rev_verdict(r, kind: str) -> str:
    d = r["base_y1_growth"] - r["implied_y1_growth"]
    if abs(d) < 0.01:
        return {"cover": "about what we model", "thesis": "The market therefore needs about what we forecast: delivery at our base case is already in the price, so upside has to come from beating it.",
                "dcf": "The market is therefore pricing in about what we model: delivery at our base case is already in the price."}[kind]
    if d > 0:
        return {"cover": "less than we model", "thesis": "The market therefore needs less than we forecast; the gap is the upside if delivery is as we model.",
                "dcf": "The market is therefore pricing in less than we model."}[kind]
    return {"cover": "more than we model", "thesis": "The market therefore already needs more than we forecast; delivery at our base case would not be enough to justify the price on the DCF alone.",
            "dcf": "The market is therefore already pricing in more than we model; the shares need delivery above our base case to earn their cost of equity on this lens."}[kind]


def _lc(label: str) -> str:
    w = label.split(' ')[0]
    return label if (w.isupper() and len(w) > 1) else label[:1].lower() + label[1:]


def _ord(n: int) -> str:
    return {1: 'largest', 2: 'second-largest', 3: 'third-largest', 4: 'fourth-largest', 5: 'fifth-largest', 6: 'sixth-largest', 7: 'seventh-largest', 8: 'eighth-largest', 9: 'ninth-largest', 10: 'tenth-largest'}.get(n, f'number {n}')


def _risk_lines(f, n):
    out = []
    for r in f.ctx.get("risks", [])[:n]:
        out.append(r)
    return out


# --------------------------------------------------------------------------- #
#  headline
# --------------------------------------------------------------------------- #
def headline(f) -> str:
    if not f.rated:
        return "No defensible target: the lenses disagree, so we show a value, not a call"
    cyc_flag = f.cyc_info.is_cyclical and f.peak_ratio and f.peak_ratio > 2
    gw = growth_word(f.g_fy1)
    if f.ret >= 0.15:
        if cyc_flag:
            return "Cheap even after haircutting peak earnings — the cycle is the debate"
        if f.roic_spread is not None and f.roic_spread > 0.05:
            return "High returns on capital, priced as if growth will fade faster than we model"
        return "More earnings power than the price reflects"
    if f.ret >= 0.05:
        return "A fair price for a good business, with room left"
    if f.ret > -0.05:
        return "Priced about right: the debate is how durable the earnings are"
    if f.ret > -0.15:
        return "Good company, full price: the numbers leave little margin for error"
    return "Priced above what the fundamentals can support"


# --------------------------------------------------------------------------- #
#  p1 · cover / summary
# --------------------------------------------------------------------------- #
def cover(f) -> dict:
    tr, cur = f.tr, f.cur
    mm = []
    if f.rated:
        tot = (f" ({spct(f.ret)} including the {pct(f.yld, 1)} dividend yield)" if f.dps and abs(f.ret - f.upside) > 0.003 else "")
        anchor = (f"and gives the Street consensus a {pct(tr.street_weight, 0)} weight as a deliberate hedge against model error"
                  if tr.street_weight > 0 else "and is purely model-driven")
        mm.append(P(f"We rate {b(f.name)} {b(f.rating)} with a 12-month price target of {b(ps(f.pt))}, {b(pct(abs(f.upside), 0))} {'above' if f.upside >= 0 else 'below'} the "
                    f"{ps(f.price)} share price{tot}. The target starts from our blended fair value of {ps(f.fv)} a share, rolls it forward a year "
                    f"at the {pct(f.ke, 1)} cost of equity{', deducts ' + ps(f.dps) + ' of dividends' if f.dps else ''} {anchor}.", lead=True))
    else:
        mm.append(P(f"We do {b('not rate')} {b(f.name)}: {tr.rating_note}. The indicative value of {ps(f.fv)} a share is shown for reference only "
                    f"and should not be read as a call against the {ps(f.price)} share price.", lead=True))

    mm.append(H("Investment summary"))
    # fundamentals
    p = (f"{f.name} generated {b(money(f.rev_last, cur))} of revenue in FY{f.years[-1]}"
         + (f", {g_txt(f.g_last)} on the year" if ok(f.g_last) else "")
         + f", at a {b(pct(f.margin_last, 1))} EBIT margin ({margin_word(f.margin_last)}).")
    if ok(f.cagr_all) and f.span >= 2:
        p += f" Over the {f.span}-year window revenue compounded at {pct(f.cagr_all, 1)} a year"
        if f.worst_g and f.best_g and (f.best_g[0] - f.worst_g[0]) > 0.35:
            p += (f", but not smoothly: growth ranged from {g_txt(f.worst_g[0])} in FY{f.worst_g[1]} to {g_txt(f.best_g[0])} in FY{f.best_g[1]}"
                  + (f" and the EBIT margin from {g_txt(f.worst_m[0])} to {g_txt(f.best_m[0])}" if f.worst_m and f.best_m else "")
                  + ", which is why we handle the earnings base with care")
        p += "."
    if f.rev_fy1:
        p += (f" Consensus looks for revenue of {money(f.rev_fy1, cur)} in FY{f.fy1}" + (f" ({spct(f.g_fy1)})" if ok(f.g_fy1) else "")
              + (f" and EPS of {ps(f.eps_fy1)}" if f.eps_fy1 else "")
              + (f", rising to {ps(f.eps_fy2)} in FY{f.fy1 + 1}" if f.eps_fy2 else "") + ".")
    mm.append(P(p))
    # valuation
    pe, ev = _mult(f, "P/E"), _mult(f, "EV/EBITDA")
    p = ""
    if pe and ok(pe.get("now")) and pe.get("ref"):
        p += (f"At {ps(f.price)} the shares trade on {b(xm(pe['now']))} NTM earnings against a {xm(pe['ref'])} reference for {f.ref.label.lower()} "
              f"({spct(pe['prem'])})")
        if ev and ok(ev.get("now")) and ev.get("ref"):
            p += f" and on {xm(ev['now'])} EV/EBITDA against {xm(ev['ref'])} ({spct(ev['prem'])})"
        p += ". "
    elif f.pe_ntm:
        p += f"At {ps(f.price)} the shares trade on {b(xm(f.pe_ntm))} NTM earnings. "
    if f.durab < 0.999 and f.peak_ratio:
        p += (f"The headline discount is not the whole story: forward EPS is {xm(f.peak_ratio)} what the business has earned through the cycle, "
              f"so we scale target multiples by {f.durab:.2f}. The market pays less for peak earnings, and so do we. ")
    if p.strip():
        mm.append(P(p.rstrip()))
    # street
    if f.street:
        s = f.street
        rel = "above" if f.tr.model_target > s.mean else "below"
        mm.append(P(f"The Street's mean 12-month target is {ps(s.mean)} ({spct(s.upside)}"
                    + (f", {s.n} analysts" if s.n else "") + f"). Our model-only target of {ps(f.tr.model_target)} sits {abs(f.tr.divergence):.0%} {rel} it; "
                    + ("the published number blends the two so that neither a model error nor a consensus drift dominates." if f.tr.street_weight > 0
                       else "the Street figure is shown for reference and carries no weight in ours."), opt=True))
    # cycle
    if f.cyc:
        mm.append(P(_cyc_clause(f) + " The cycle is context for the call, not an input to the target (" + PGREF("p11") + ").", opt=True))
    if f.rev_dcf:
        mm.append(P(f"A reverse DCF shows the price discounts year-one revenue growth of {b(pct(f.rev_dcf['implied_y1_growth'], 1))} against our "
                    f"{pct(f.rev_dcf['base_y1_growth'], 1)} base, so the market is asking for {_rev_verdict(f.rev_dcf, 'cover')}. That is the cleanest single measure of how demanding the price is.", more=True))
    mm.append(H("Key risks"))
    rl = _risk_lines(f, 3)
    mm.append(UL(rl[:2]))
    if len(rl) > 2:
        mm.append(UL(rl[2:], opt=True))
    mm.append(CALL("What would change our mind", _change_mind(f), more=True))
    return dict(key="p1", nav="Summary", cover=True, main=mm, source=None)


def _change_mind(f) -> list:
    out = []
    if f.g_fy1 is not None:
        out.append(f"A sustained miss on FY{f.fy1} revenue (consensus {spct(f.g_fy1)}) or on the EBIT margin path; each 100bps of margin is worth "
                   f"{ps(f.ctx.get('margin_lever'))} a share in the DCF." if f.ctx.get("margin_lever") else
                   f"A sustained miss on FY{f.fy1} revenue (consensus {spct(f.g_fy1)}) or on the margin path.")
    out.append("A re-rating of the sector multiple the relative lenses are anchored on, in either direction.")
    out.append(f"A move in the cost of equity from today's {pct(f.ke, 1)}: rates and the equity risk premium are the largest single swing factor in the {'DCF' if f.has_dcf else 'valuation'}.")
    if f.cyc and f.cyc.get("tilt") is not None:
        out.append("A change in the Reloj's phase reading that turns the sector's historical tilt from headwind to tailwind, or the reverse.")
    return out


# --------------------------------------------------------------------------- #
#  p2 · thesis
# --------------------------------------------------------------------------- #
def thesis(f) -> dict:
    cur = f.cur
    legs = []
    if f.g_fy1 is not None and f.g_fy1 > 0.08 or (f.cagr_all or 0) > 0.08:
        legs.append("earnings power")
    if f.fv_gap is not None and f.fv_gap > 0.08:
        legs.append("a valuation that already discounts the cycle" if f.durab < 0.999 else "a valuation below fair value")
    if f.net_cash or (f.nd_ebitda is not None and f.nd_ebitda < 1):
        legs.append("a balance sheet that removes financing risk")
    if f.rated and f.ret > 0.05:
        sub = f"{spct(f.upside)} to a {ps(f.pt)} target rests on " + (join(legs) if legs else "valuation alone") + "."
    elif f.rated and f.ret < -0.05:
        sub = f"At {ps(f.price)} the shares discount more than our {ps(f.fv)} fair value supports; the debate is how much of the growth is already in the price."
    elif f.rated:
        sub = f"Our {ps(f.fv)} fair value brackets the {ps(f.price)} price: a neutral stance, with the earnings base the swing factor."
    else:
        sub = "The lenses do not converge on a number we can defend; this page sets out what we can and cannot say."
    mm = []
    # pillar 1 -- earnings power
    mm.append(H("1 · Earnings power and returns on capital"))
    p = ""
    if f.rev_fy1 and ok(f.g_fy1):
        p += (f"Consensus has revenue growing {b(spct(f.g_fy1))} in FY{f.fy1}" + (f" and {spct(f.g_fy2)} in FY{f.fy1 + 1}" if ok(f.g_fy2) else ""))
        p += ((f"; our DCF fades growth from {pct(f.dcf_g1, 0)} in year one to the {pct(f.dcf.terminal_growth, 1)} terminal rate over {f.dcf_horizon} years, so no single "
               f"year's step is extrapolated. ") if f.has_dcf else ". ")
    elif ok(f.cagr_all):
        p += f"Revenue has compounded at {pct(f.cagr_all, 1)} over {f.span} years. "
    if f.roic is not None:
        sp = f.roic_spread
        p += (f"The business earns {b(pct(f.roic, 1))} on invested capital against a {pct(f.wacc, 1)} cost of capital, "
              + (f"a spread of {sp * 1e4:,.0f}bps that means growth creates value." if sp > 0 else f"a shortfall of {abs(sp) * 1e4:,.0f}bps, so on today's returns growth destroys value."))
    mm.append(P(p))
    if f.cyc_info.is_cyclical and f.cyc_info.mid_margin is not None:
        mm.append(P(f"The margin is where the argument sits. The latest EBIT margin of {pct(f.margin_last, 0)} compares with a through-cycle average of "
                    f"{pct(f.cyc_info.mid_margin, 0)}; the model flags the business as cyclical ({'; '.join(_flat(r_) for r_ in f.cyc_info.reasons)}), so we credit only part of the current margin as "
                    f"durable" + (f" (a {pct(f.dcf_m_term, 0)} terminal margin in the DCF)." if f.has_dcf else ".")))
    elif ok(f.margin_vol):
        mm.append(P(f"Margins have been {'stable' if f.margin_vol < 0.03 else 'volatile'} (standard deviation {pct(f.margin_vol, 1)} across the window), "
                    f"which {'supports' if f.margin_vol < 0.03 else 'limits'} how much of the current profitability the model can treat as permanent."))
    roics = [v for v in f.rs["roic"] if ok(v)]
    if len(roics) >= 3:
        mm.append(P(f"{b('Return history.')} ROIC has run {series_txt_pct(roics)} over the window, so today's {pct(f.roic, 0)} is "
                    + _roic_story(f, roics) + f". The WACC we compare it with is {pct(f.wacc, 1)}.", more=True))
    # pillar 2 -- valuation
    mm.append(H("2 · Valuation"))
    p = (f"Our {num_word(len(f.used))} lenses blend to {b(ps(f.fv))} today, {abs(f.fv_gap):.0%} {'above' if f.fv_gap >= 0 else 'below'} the price"
         if ok(f.fv_gap) else "")
    if f.used:
        top = f.used[0]
        p += f"; the heaviest, {_lc(top.label)}, carries {top.eff_weight:.0%} of the weight at {ps(top.value)}."
    mm.append(P(p))
    pe = _mult(f, "P/E")
    if pe and ok(pe.get("target")):
        rel_ = (pe["target"] / pe["ref"] - 1) if pe.get("ref") else None
        if rel_ is None:
            tail = "."
        elif abs(rel_) < 0.05:
            tail = ", i.e. in line with the sector."
        elif rel_ < 0:
            tail = ", i.e. a discount that we think is justified " + ("given the durability haircut." if f.durab < 0.999 else "given its growth relative to the sector.")
        else:
            tail = ", i.e. a premium that we think is defensible given its growth and returns."
        mm.append(P(f"At our target the stock would trade on {b(xm(pe['target']))} NTM earnings" + (f" against {xm(pe['ref'])} for the sector" if pe.get("ref") else "") + tail))
    # pillar 3 -- balance sheet
    mm.append(H("3 · Balance sheet and cash conversion"))
    p = (f"{cap(f.name)} ends FY{f.years[-1]} with {money(f.cash, cur)} of cash against {money(f.debt, cur)} of debt, "
         + (f"a {b('net cash')} position of {money(abs(f.nd), cur)}" if f.net_cash else f"net debt of {money(f.nd, cur)}" + (f" ({xm(f.nd_ebitda)} EBITDA, {lev_word(f.nd_ebitda, False)})" if ok(f.nd_ebitda) else " (leverage ratios against EBITDA are not available)"))
         + (f"; EBIT covers interest {xm(f.cover)}" if ok(f.cover) and 0 < f.cover < 500 and f.debt > 0 else "") + ". ")
    if f.fcf_last is not None:
        p += (f"Free cash flow (operating cash flow less capex) was {money(f.fcf_last, cur)}"
              + (f", a {pct(f.fcf_yield, 1)} yield on the market cap" if ok(f.fcf_yield) else "")
              + (f", and capex ran at {xm(f.capex_da, 1)} depreciation" if ok(f.capex_da) else "") + ".")
    mm.append(P(p))
    if f.pio.get("available") or f.alt:
        bits = []
        if f.pio.get("available"):
            bits.append(f"a Piotroski F-score of {f.pio['score']} out of {f.pio['available']}")
        if f.alt:
            bits.append(f"an Altman Z of {f.alt['z']:.1f} ({f.alt['zone']} zone)")
        if ok(f.accr):
            bits.append(f"Sloan accruals of {pct(f.accr, 1)}")
        mm.append(P(f"{b('Quality screens.')} The accounting screens give {join(bits)}"
                    + (", which supports taking reported earnings at face value." if (f.pio.get('available') and f.pio['score'] >= 6 and (not ok(f.accr) or f.accr < 0.05)) else ", so we lean harder on cash flow than on reported profit.")
                    + " " + cap(PGREF("p8")) + " has the detail.", more=True))
    # what is priced in + Street
    mm.append(H("What the price discounts, and where we differ from the Street"))
    if f.rev_dcf:
        mm.append(P(f"Solving the DCF backwards for the current price gives year-one revenue growth of {b(pct(f.rev_dcf['implied_y1_growth'], 1))} "
                    f"(terminal growth {pct(f.rev_dcf['implied_terminal_growth'], 1)}) against our {pct(f.rev_dcf['base_y1_growth'], 1)} base. "
                    + _rev_verdict(f.rev_dcf, "thesis")))
    if f.street:
        s = f.street
        mm.append(P(f"Against a Street mean of {ps(s.mean)} ({spct(s.upside)}), our model-only target of {ps(f.tr.model_target)} is {abs(f.tr.divergence):.0%} "
                    f"{'higher' if f.tr.divergence > 0 else 'lower'}. "
                    + ("A discount to consensus is the natural outcome when the model haircuts peak earnings that analysts capitalise in full." if f.tr.divergence < 0 and f.durab < 0.999
                       else "We flag the gap rather than close it: where the model is right the stock has an information edge, where it is wrong the Street's inputs deserve more weight.")))
    mm.append(H("In summary"))
    take = []
    take.append((f"{f.rating}: {ps(f.pt)} target ({spct(f.upside)}), {ps(f.fv)} fair value, {pct(f.ke, 1)} cost of equity." if f.rated else f"Not rated: indicative value {ps(f.fv)}."))
    if f.rev_fy1 and ok(f.g_fy1):
        take.append(f"Consensus revenue {spct(f.g_fy1)} in FY{f.fy1}; EBIT margin {pct(f.margin_last, 0)} today, {pct(f.dcf_m_term, 0) if f.has_dcf else 'normalised'} in our terminal year.")
    pe_ = _mult(f, "P/E")
    if pe_ and ok(pe_.get("now")) and pe_.get("ref"):
        take.append(f"{xm(pe_['now'])} NTM P/E against {xm(pe_['ref'])} for the sector; {xm(pe_['target'])} at our target.")
    if f.cyc and f.cyc.get("tilt") is not None:
        take.append(f"Cycle: {f.phase_en} ({_strength(f.cyc['strength'])} signal), sector tilt {pp(f.cyc['tilt'])} a year.")
    mm.append(CALL("Key takeaways", take))
    if f.cyc:
        mm.append(P(f"{b('Cycle context.')} The Reloj's reading of the cycle and the sector's historical record in each phase are set out on pages [[pg:p11]] and [[pg:p12]]; they inform how we size the call, not the target itself.", more=True))
    return dict(key="p2", nav="Thesis", kicker="Investment thesis", title="Why this number, and what it rests on", sub=sub, main=mm)


# --------------------------------------------------------------------------- #
#  p3 · valuation framework
# --------------------------------------------------------------------------- #
def _profile_drivers(f) -> tuple:
    """(bear, bull) one-line drivers by valuation profile, for cases without a DCF."""
    k = f.profile.value
    table = {
        "bank": ("Credit losses above plan, net-interest-margin compression or a capital raise would cut sustainable ROE and with it the justified book multiple.",
                 "Better credit quality, a steeper curve or capital release would lift ROE above the cost of equity for longer than the model assumes."),
        "insurance": ("Reserve strengthening, catastrophe losses or weaker investment yields would pull ROE toward the cost of equity.",
                      "Disciplined pricing and a benign claims year would sustain ROE above the cost of equity."),
        "reit": ("Cap-rate expansion, falling occupancy or slower rent growth would cut FFO and the multiple investors pay for it.",
                 "Cap-rate compression, rent growth above plan or accretive acquisitions would lift FFO and the multiple."),
        "utility": ("A tougher rate case, higher funding costs or a lower allowed ROE would compress both earnings and the multiple.",
                    "Constructive regulation and rate-base growth above plan would support earnings growth and a higher multiple."),
        "cyclical": ("A lower commodity price or cost inflation would reset the mid-cycle earnings base the multiples are applied to.",
                     "Commodity prices holding near spot and disciplined costs would make today's margin more durable than the model assumes."),
        "high_growth": ("Growth that fades faster than consensus or margins that fail to converge would compress the revenue multiple.",
                        "Faster growth with operating leverage would justify a higher revenue multiple than the sector reference."),
        "standard": ("Consensus estimates cut and a de-rating of the sector multiple would lower both the earnings and the multiple.",
                     "Estimate upgrades and a re-rating toward the top of the sector range would lift both."),
    }
    return table.get(k, table["standard"])


def _flat(text: str) -> str:
    """Avoid nested parentheses: '(a (b))' -> 'a, b'."""
    import re
    return re.sub(r"\s*\(([^()]*)\)", r", \1", text).strip(" ,")


def _others_mean(f, key):
    vals = [l.value for l in f.used if l.key != key]
    return sum(vals) / len(vals) if vals else None


_LENS_NAMES = {"dcf": "DCF", "pe_fwd": "forward P/E", "ev_ebitda_fwd": "forward EV/EBITDA", "ev_sales_fwd": "forward EV/Sales", "pb_book": "price-to-book",
               "ddm": "dividend discount model", "residual_income": "residual income", "pb_roe": "justified P/B", "ffo_multiple": "P/FFO",
               "affo_yield": "AFFO yield", "normalized": "mid-cycle EBITDA"}


def _lens_story(f, l) -> str:
    rows = {k: v for k, v in (l.rows or [])}

    def g(*keys):
        for k, v in rows.items():
            kl = k.lower()
            if all(x in kl for x in keys):
                return v
        return None
    wt = f"{l.eff_weight:.0%}"
    head = f"{b(l.label)} ({ps(l.value)} a share, {wt} of the weight) "
    if l.key == "pe_fwd":
        tm, an, gr, du = g("target p/e"), g("anchor"), g("growth"), g("durability")
        s = head + f"applies a {b(tm)} target multiple to NTM EPS of {g('ntm eps') or g('forward eps')}. "
        if an:
            val, _, gloss = an.partition("—")
            s += f"The multiple starts from an anchor of {val.strip()}" + (f" ({_flat(gloss.strip())})" if gloss.strip() else "") + ", "
        if gr:
            num, _, det = gr.partition("(")
            s += f"is scaled by {num.replace('×', '').strip()} for durable growth" + (f" ({det.rstrip(')').strip()})" if det else "")
        if du and du.strip() != "×1.00":
            s += f" and by {du.split('(')[0].replace('×', '').strip()} for earnings durability"
        return s.rstrip(", ") + "."
    if l.key == "ev_ebitda_fwd":
        tm, an, nt = g("target ev/ebitda"), g("anchor"), g("ntm ebitda")
        s = head + f"capitalises NTM EBITDA of {nt} at {b(tm)}, then bridges to equity through net {'cash' if f.net_cash else 'debt'}. "
        if an:
            s += f"The anchor is {an.split('—')[0].strip()}; growth and durability adjustments follow the same logic as the P/E lens, which makes it a capital-structure-neutral cross-check."
        return s
    if l.key == "ev_sales_fwd":
        return head + f"applies {b(g('target ev/sales'))} to NTM revenue of {g('ntm revenue')}: the lens for companies whose earnings do not yet measure value."
    if l.key == "pb_book":
        return head + f"scales a {g('anchor p/b').split('—')[0].strip() if g('anchor p/b') else ''} book multiple by returns on equity relative to the cost of equity ({_flat(g('returns factor') or '')})."
    if l.key == "dcf":
        return head + (f"values ten years of free cash flow to the firm at a {g('wacc')} WACC with {g('terminal growth')} terminal growth; the terminal value is {g('pv of terminal') or ''}. "
                       "Growth fades toward the terminal rate and margins mean-revert, so it does not extrapolate today's profitability"
                       + (f"; here it sits {'below' if l.value < _others_mean(f, 'dcf') else 'above'} the multiples lenses." if _others_mean(f, 'dcf') else "."))
    return head.rstrip() + (": " + l.note[:1].lower() + l.note[1:] if l.note else ".")


def valuation_framework(f) -> dict:
    tr = f.tr
    mm = []
    mm.append(P(f"{f.spec.rationale} The profile for {b(f.tk)} is {b(f.spec.label)}; it prescribes {num_word(len(f.spec.weights))} methods, of which "
                f"{num_word(len(f.used))} produced a usable value.", lead=True))
    mm.append(H("The lenses, one by one"))
    for l in f.used:
        mm.append(P(_lens_story(f, l)))
    if f.excluded:
        mm.append(P(f"{join([l.label for l in f.excluded])} {'was' if len(f.excluded) == 1 else 'were'} excluded ("
                    + "; ".join(l.status_note for l in f.excluded if l.status_note) + ")."))
    if len(f.used) > 1:
        mm.append(P(f"{b('What the dispersion tells us.')} The lenses span {ps(f.lens_lo)} to {ps(f.lens_hi)}, a {f.lens_hi / f.lens_lo:.1f}x spread (coefficient of variation {pct(f.lens_cv, 0)}). "
                    + ("Agreement among independent methods is the strongest evidence a valuation can offer; here it is broad." if f.lens_cv < 0.15 else
                       "The spread is wide enough that the answer depends on which question is asked: a multiples lens capitalises today's consensus, while "
                       + ("the DCF" if f.has_dcf else "a balance-sheet or cash-flow lens") + " has to earn it. We report the disagreement rather than average it away.")))
    w0 = f.spec.weights
    if w0:
        mm.append(P(f"{b('Weights.')} The profile starts from " + join([f"{_LENS_NAMES.get(k, k.replace('_', ' '))} {v:.0%}" for k, v in w0.items()])
                    + ". After the guardrails and the lenses that could not be built are removed, the weights are renormalised over those that remain, which is why they differ from the profile's starting point.", more=True))
    mm.append(H("Guardrails: what the model is not allowed to do"))
    mm.append(P("Every intervention is explicit. A lens outside 0.2×–5× the share price is excluded (or winsorised if it is the only one); a lens more than 2.2× away from "
                "the median of the others is down-weighted by 60%; the published target is confined to 0.4×–2.5× the price; and with fewer than two usable lenses, or a "
                "result forced by a guardrail, the company is published NOT RATED rather than given a number we cannot defend."))
    if tr.guardrails:
        mm.append(UL([g for g in tr.guardrails]))
    else:
        mm.append(P("In this case no guardrail intervened: every lens landed inside the plausible band and no Street anchor was applied."))
    mm.append(H("From fair value to target"))
    steps = (f"Fair value today {ps(f.fv)} × (1 + {pct(f.ke, 2)} cost of equity)" + (f" − {ps(f.dps)} dividends" if f.dps else "")
             + f" = {b(ps(tr.model_target))} model target"
             + (f"; the Street mean of {ps(tr.street.mean)} at {pct(tr.street_weight, 0)} weight moves it to {b(ps(tr.target))}." if tr.street and tr.street_weight > 0
                else f"; published target {b(ps(tr.target))}."))
    mm.append(P(steps))
    mm.append(P(f"Confidence is graded {b(tr.confidence)}: " + "; ".join(tr.confidence_reasons) + ".", more=True))
    mm.append(P("Bear and bull values are the low and high ends of the lens ranges (the DCF's own bear and bull scenarios where it is present), rolled forward the same way. "
                "They bracket the model's uncertainty; they are not statistical confidence intervals.", more=True))
    return dict(key="p3", nav="Valuation", kicker="Valuation · method",
                title=f"How {ps(f.fv)} of fair value becomes a {ps(f.pt) if f.rated else 'value'} target",
                sub="Several independent answers to \"what is a share worth?\", weighted by what fits the business, filtered by explicit guardrails.", main=mm)


# --------------------------------------------------------------------------- #
#  p4 · relative valuation
# --------------------------------------------------------------------------- #
def relative_valuation(f) -> dict:
    cur = f.cur
    mm = []
    pe, ev, evs, pb = _mult(f, "P/E"), _mult(f, "EV/EBITDA"), _mult(f, "EV/Sales"), _mult(f, "P/B")
    lead = f"On the numbers the market pays today, {f.name} looks "
    if pe and pe.get("prem") is not None:
        lead += (f"{'cheap' if pe['prem'] < -0.10 else 'expensive' if pe['prem'] > 0.10 else 'in line'} on earnings ({xm(pe['now'])} NTM against {xm(pe['ref'])} "
                 f"for {f.ref.label.lower()}, {spct(pe['prem'])})")
    else:
        lead += "difficult to value on earnings"
    if ev and ev.get("prem") is not None:
        lead += f" and {'cheap' if ev['prem'] < -0.10 else 'expensive' if ev['prem'] > 0.10 else 'in line'} on enterprise value ({xm(ev['now'])} EV/EBITDA against {xm(ev['ref'])})"
    mm.append(P(lead + ".", lead=True))
    mm.append(H("Where the anchor comes from"))
    npe = len(f.peers)
    mm.append(P((f"The relative lenses are anchored on a curated set of {npe} peers" if npe >= 3 else
                 f"There is no usable peer set here (fewer than three peers with valid multiples), so the relative lenses are anchored on the {f.ref.label.lower()} reference table")
                + f": {xm(f.ref.pe, 1)} P/E, {xm(f.ref.ev_ebitda, 1)} EV/EBITDA, {xm(f.ref.ev_sales, 1)} EV/Sales and {xm(f.ref.pb, 1)} P/B, with a sector growth rate of {pct(f.ref.growth, 0)}. "
                  "A sector median is a starting point, not a verdict: each lens then adjusts it for the company in front of us."))
    mm.append(H("What we adjust, and why"))
    g_adj = None
    pel = _lens(f, "pe_fwd")
    if pel:
        rows = {k: v for k, v in pel.rows}
        gr = next((v for k, v in rows.items() if "growth" in k.lower()), None)
        du = next((v for k, v in rows.items() if "durab" in k.lower()), None)
        lv = next((v for k, v in rows.items() if "leverage" in k.lower()), None)
        tp = next((v for k, v in rows.items() if "target p/e" in k.lower()), None)
        if gr:
            mm.append(P(f"{b('Growth.')} The anchor is scaled {gr} — the market pays for growth that lasts, so we use durable earnings growth of {pct(f.fwd.growth, 1)} "
                        f"({_flat(f.fwd.growth_src)}) rather than a one-year consensus jump."))
        if du and f.durab < 0.999:
            mm.append(P(f"{b('Earnings durability.')} Forward EPS of {ps(f.eps_ntm)} is {xm(f.peak_ratio)} the through-cycle EPS of {ps(f.cyc_info.norm_eps)}, so the target multiple is scaled by {b('×' + format(f.durab, '.2f'))}. "
                        f"This is the single largest adjustment and the main reason our target sits {'below' if f.street and f.tr.divergence < 0 else 'away from'} consensus."))
        if lv and lv.strip() != "×1.00":
            mm.append(P(f"{b('Leverage.')} Net debt" + (f" of {xm(f.nd_ebitda)} EBITDA" if ok(f.nd_ebitda) else "") + f" trims the multiple by {lv.replace('×', '').strip()}."))
        if tp:
            mm.append(P(f"The result is a target P/E of {b(tp)} applied to NTM EPS, worth {ps(pel.value)} a share."))
    if not pel:
        others = [l for l in f.used if l.key != "pe_fwd"]
        if others:
            mm.append(P("There is no usable forward P/E lens here, so the multiples evidence comes from the lenses the profile prescribes: "
                        + "; ".join(f"{_lc(l.label)} at {ps(l.value)} ({l.eff_weight:.0%} of the weight)" for l in others) + ". "
                        + (f"Price-to-book is {xm(f.pb)} against a {xm(f.ref.pb)} sector reference, and return on equity of {pct(f.roe, 1)} against a {pct(f.ke, 1)} cost of equity is what decides whether a premium to book is earned. " if ok(f.pb) and ok(f.roe) else "")))
    mm.append(H("Cross-checks"))
    bits = []
    if evs and ok(evs.get("now")):
        bits.append(f"EV/Sales is {xm(evs['now'])} against {xm(evs['ref'])} for the sector")
    if pb and ok(pb.get("now")):
        bits.append(f"price-to-book is {xm(pb['now'])} against {xm(pb['ref'])}")
    if ok(f.fcf_yield):
        bits.append(f"free-cash-flow yield is {pct(f.fcf_yield, 1)}")
    if f.dps:
        bits.append(f"dividend yield is {pct(f.yld, 1)}")
    peg = _mult(f, "PEG")
    if peg and ok(peg.get("now")):
        bits.append(f"the PEG ratio is {xm(peg['now'], 2)}")
    if bits:
        mm.append(P(cap(join(bits)) + ". These do not enter the target unless a lens is built on them, but they show whether the headline multiple is flattered by one line of the accounts."))
    peg = _mult(f, "PEG")
    if peg and ok(peg.get("now")):
        mm.append(P(f"{b('Growth-adjusted view.')} The PEG ratio of {xm(peg['now'], 2)} divides the P/E by durable growth; below 1 the market is paying less than a point of multiple per point of growth. "
                    "Treat it with caution when growth is a cyclical rebound rather than a trend.", more=True))
    if ok(f.nd_ebitda):
        mm.append(P(f"{b('P/E versus EV/EBITDA.')} The two multiples disagree when capital structures differ. With "
                    + ("net cash" if f.net_cash else f"net debt of {xm(f.nd_ebitda)} EBITDA") + f", enterprise value is {'lower' if f.net_cash else 'higher'} than market capitalisation, so EV/EBITDA "
                    + ("flatters the shares slightly relative to P/E." if f.net_cash else "is the harsher test.") + " We use both for that reason.", more=True))
    mm.append(P("Relative valuation is only as good as the earnings it is applied to. When forward EPS is far above trailing, a low P/E can be a warning sign rather than a bargain: "
                "it is the market declining to capitalise a peak. That is why the financial analysis that follows tests the earnings base before the cash-flow model is built.", more=True))
    return dict(key="p4", nav="Multiples", kicker="Valuation · relative",
                title="What the multiples say, and what we adjust before using them",
                sub="Sector and peer anchors, scaled for growth, leverage and the durability of the earnings they are applied to.", main=mm)


# --------------------------------------------------------------------------- #
#  p5 · scenarios and sensitivity
# --------------------------------------------------------------------------- #
def scenarios_page(f) -> dict:
    sc = f.ctx["scen"]
    mm = []
    exp = sc.expected
    mm.append(P(f"We weight three outcomes 25 / 50 / 25: a {b('bear')} case of {ps(f.bear)}, a {b('base')} case of {ps(f.pt)} and a {b('bull')} case of {ps(f.bull)}. "
                f"The probability-weighted target is {b(ps(exp))} ({spct(sc.expected_ret)} including dividends), "
                f"{'close to' if abs(exp / f.pt - 1) < 0.02 else 'slightly ' + ('above' if exp > f.pt else 'below')} the base case because the range is {'roughly symmetric' if abs((f.bull - f.pt) - (f.pt - f.bear)) < 0.15 * f.pt else 'skewed ' + ('to the upside' if (f.bull - f.pt) > (f.pt - f.bear) else 'to the downside')}.", lead=True))
    mm.append(H("What each case needs to be true"))
    if f.has_dcf and f.dcf_bear and f.dcf_bull:
        mm.append(P(f"{b('Bear.')} The DCF's bear scenario values the shares at {ps(f.dcf_bear)}: slower revenue, margins that revert faster toward the through-cycle level "
                    f"and a higher reinvestment burden. Our published bear target of {ps(f.bear)} ({spct(f.bear / f.price - 1)} from today's price) blends that with the lower ends of the multiples lenses"
                    + (", so it is the multiples, not the cash-flow model, that set the floor of the range." if f.dcf_bear < f.bear else ".")
                    + (" On the DCF's own terms the shares offer no margin of safety in a downturn." if f.dcf_bear < f.price * 0.8 else "")))
        mm.append(P(f"{b('Base.')} Consensus for the near years, growth fading to {pct(f.dcf.terminal_growth, 1)}, margins mean-reverting from {pct(f.margin_last, 0)} toward {pct(f.dcf_m_term, 0)}, "
                    f"and a {pct(f.wacc, 1)} WACC: {ps(f.dcf_vps)} a share on the cash-flow lens, {ps(f.fv)} once the multiples lenses are blended."))
        mm.append(P(f"{b('Bull.')} The DCF's bull scenario reaches {ps(f.dcf_bull)}: growth that fades more slowly and margins that hold closer to today's level. "
                    f"Our published bull target of {ps(f.bull)} ({spct(f.bull / f.price - 1)}) is the upper end of the lens ranges rolled forward."))
    else:
        mm.append(P("Without a DCF the cases come straight from the lens ranges: the bear case is the low end of each lens and the bull case the high end, weighted as in the base case."))
        rng = [f"{_lc(l.label)} {ps(l.low)}–{ps(l.high)}" for l in f.used]
        if rng:
            mm.append(P(f"{b('How the range is built.')} Each lens carries a range that reflects the uncertainty in its key input: " + join(rng) + ". "
                        f"Weighting the low ends gives the bear case of {ps(f.bear)}, the high ends the bull case of {ps(f.bull)}, both rolled forward at the {pct(f.ke, 1)} cost of equity."))
        bear_s, bull_s = _profile_drivers(f)
        mm.append(P(f"{b('What would make the bear case.')} {bear_s}"))
        mm.append(P(f"{b('What would make the bull case.')} {bull_s}"))
    if f.has_dcf and f.sens:
        mm.append(H("How sensitive is the DCF?"))
        lo, hi = f.sens_lo, f.sens_hi
        lv = f.ctx.get("levers") or {}
        txt = (f"each {lv['wacc_bps']:.0f}bps of WACC moves the value by about {ps(lv['wacc_ps'])} ({lv['wacc_pct']:.0%}), against {ps(lv['g_ps'])} for {lv['g_bps']:.0f}bps of terminal growth"
               if lv.get("wacc_ps") and lv.get("g_ps") else "each step of WACC moves the value by several percent while a step of terminal growth moves it by far less")
        mm.append(P(f"Across a ±150bps range of WACC and ±100bps of terminal growth the DCF value per share runs from {ps(lo)} to {ps(hi)} ({XR('sens')}). "
                    f"The cost of capital matters more than terminal growth: {txt}."))
    if f.bear < f.price < f.bull:
        down, up = f.price - f.bear, f.bull - f.price
        mm.append(H("Risk and reward"))
        mm.append(P(f"Measured from {ps(f.price)}, the bull case adds {ps(up)} ({spct(up / f.price)}) and the bear case costs {ps(down)} ({spct(-down / f.price)}): an upside-to-downside ratio of {b(f'{up / down:.1f}x')}. "
                    "Asymmetry of that kind is what a rating should be built on, provided the bear case is credible."))
    elif f.bear >= f.price:
        mm.append(H("Risk and reward"))
        mm.append(P(f"The price sits below even our bear case ({ps(f.bear)}), which means every scenario we run is above today's price. We would treat that as a prompt to test whether the bear case is conservative enough rather than as free money."))
    stress = f.ctx.get("stress") or []
    if stress:
        st_sorted = sorted([x for x in stress if x[2] is not None], key=lambda x: x[2])
        mm.append(H("Stress tests"))
        mm.append(P(f"Shocking one input at a time to the DCF, the most damaging are {b(_lc(st_sorted[0][0]))} ({spct(st_sorted[0][2])}) and {_lc(st_sorted[1][0])} ({spct(st_sorted[1][2])}); "
                    f"the most helpful are {_lc(st_sorted[-1][0])} ({spct(st_sorted[-1][2])}) and {_lc(st_sorted[-2][0])} ({spct(st_sorted[-2][2])}) ({XR('stress')}). "
                    + (f"Only {_lc(st_sorted[-1][0])} lifts the DCF to the blended fair value on its own." if st_sorted[-1][1] >= f.fv else "None of the single shocks closes the gap to the blended fair value on its own, which is useful information about where the disagreement comes from."), more=True))
    g = f.ctx.get("lens_grid")
    if g:
        mm.append(H("How sensitive is the multiple-based value?"))
        mm.append(P(f"{('Forward earnings and the target multiple' if g['kind'] == 'pe' else 'Return on equity and the cost of equity')} are the inputs that matter most. "
                    + (f"A 10% change in either NTM EPS or the target multiple moves the forward P/E value by about {ps(g['d_eps'])} a share (they enter multiplicatively); " if g["kind"] == "pe" else
                       f"Two points of ROE move the justified P/B value by about {ps(g['d_mult'])} a share, and half a point of cost of equity by {ps(g['d_eps'])}; ")
                    + f"across the grid ({XR('multsens')}) the value runs from {ps(g['lo'])} to {ps(g['hi'])}.", more=f.has_dcf))
    levers = f.ctx.get("catalysts") or []
    if levers:
        mm.append(H("What each lever is worth"))
        mm.append(UL(levers))
    mm.append(P(f"The sensitivity tables are shaded against the current price (green above, terracotta below): when every cell is one colour the {'DCF' if f.has_dcf else 'valuation'} has a clear view; when the base case sits "
                "near the edge of a colour change, the conclusion depends on the inputs.", more=True))
    return dict(key="p5", nav="Scenarios", kicker="Valuation · scenarios and sensitivity",
                title="Range of outcomes, and the levers that move them",
                sub=("Bear, base and bull cases built from the lens ranges and the DCF scenarios, with the DCF's two most important dials." if f.has_dcf else
                     "Bear, base and bull cases built from the ranges of each lens, with the inputs that move them most."), main=mm)


# =========================================================================== #
#  Part 2 · financial analysis, DCF, cycle, risks, appendix
# =========================================================================== #
def _words(n: int) -> str:
    return {10: "ten", 11: "eleven", 12: "twelve", 15: "fifteen", 20: "twenty"}.get(n, num_word(n))


def PGREF(key: str) -> str:
    return f"page [[pg:{key}]]"


def XR(key: str) -> str:
    """Cross-reference to an exhibit; the number is filled in by pages.py (and fixed by the page script)."""
    return f'<span class="xr" data-ex="{key}">[[ex:{key}]]</span>'


def _yr(f, i):
    return f"FY{f.years[i]}"


def _g_series(f, n=4):
    pairs = [(y, g) for y, g in zip(f.years, f.growth) if ok(g)][-n:]
    return ", ".join(f"FY{y} {g_txt(g)}" for y, g in pairs)


def growth_margins(f) -> dict:
    cur = f.cur
    mm = []
    first, last = f.rev[0], f.rev[-1]
    lead = (f"Revenue went from {money(first, cur)} in {_yr(f, 0)} to {b(money(last, cur))} in {_yr(f, -1)}"
            + (f", a compound rate of {b(pct(f.cagr_all, 1))} a year" if ok(f.cagr_all) and f.span >= 2 else "") + ". ")
    gs = [g for g in f.growth if ok(g) and abs(g) < 20]
    swing = (max(gs) - min(gs)) if len(gs) >= 2 else 0
    if swing > 0.5:
        lead += (f"The path was anything but linear ({_g_series(f)}): " + (f"a swing of {swing * 100:,.0f} points in annual growth is" if swing < 5 else "swings of that size are")
                 + " the signature of a business whose revenue follows a cycle in pricing or volumes, or a very small base, rather than a steady compounding base.")
    elif swing > 0.15:
        lead += f"Growth was uneven ({_g_series(f)}), with {_yr(f, [g for g in f.growth].index(max(g for g in f.growth if ok(g))))} the strongest year."
    else:
        lead += f"Growth was steady ({_g_series(f)}), which makes the forward path easier to underwrite."
    mm.append(P(lead, lead=True))
    mm.append(H("Top line"))
    p = ""
    if f.rev_fy1:
        p += (f"Consensus looks for revenue of {b(money(f.rev_fy1, cur))} in FY{f.fy1} ({spct(f.g_fy1)})"
              + (f" and {money(f.rev_fy2, cur)} in FY{f.fy1 + 1} ({spct(f.g_fy2)})" if f.rev_fy2 and ok(f.g_fy2) else "") + ". ")
    if f.has_dcf:
        p += (f"Our DCF takes consensus for the first two years and then fades growth toward the {pct(f.dcf.terminal_growth, 1)} terminal rate, "
              f"so revenue reaches {money(f.dcf_rev_term, cur)} by year {f.dcf_horizon} ({pct(f.dcf_cagr, 1)} a year over the period). "
              "Large numbers compress growth and competition erodes it; we do not extrapolate any single year.")
    mm.append(P(p))
    mm.append(H("Margins"))
    mref = getattr(f.ref, "margin", None)
    cmp_ = ("" if not ok(mref) else (f", above the {pct(mref, 0)} sector reference" if f.margin_last > mref * 1.1 else f", below the {pct(mref, 0)} sector reference" if f.margin_last < mref * 0.9 else f", in line with the {pct(mref, 0)} sector reference"))
    p = f"The EBIT margin was {b(pct(f.margin_last, 1))} in {_yr(f, -1)} ({margin_word(f.margin_last)}{cmp_})"
    if f.worst_m and f.best_m and f.worst_m[1] != f.best_m[1]:
        p += f", within a range of {g_txt(f.worst_m[0])} (FY{f.worst_m[1]}) to {g_txt(f.best_m[0])} (FY{f.best_m[1]}) over the window"
    p += ". "
    if ok(f.gross_m[-1]):
        gm = [m for m in f.gross_m if ok(m)]
        p += f"Gross margin stood at {pct(f.gross_m[-1], 1)}" + (f" (from {pct(gm[0], 0)} at the start of the window)" if len(gm) >= 2 else "") + ", "
        p += f"and net margin at {pct(f.net_m[-1], 1)}. "
    if f.cyc_info.mid_margin is not None and f.cyc_info.is_cyclical:
        p += (f"Against a through-cycle EBIT margin of {pct(f.cyc_info.mid_margin, 0)}, today's level is "
              f"{'well above' if f.margin_last > f.cyc_info.mid_margin * 1.5 else 'above' if f.margin_last > f.cyc_info.mid_margin else 'below'} normal; the DCF reverts {pct(0.6, 0)} of the gap by the terminal year, landing at {pct(f.dcf_m_term, 0)}." if f.has_dcf else "")
    elif f.has_dcf:
        p += f"The DCF takes the margin from {pct(f.margin_last, 0)} to a peak of {pct(f.dcf_m_peak, 0)} and a terminal {pct(f.dcf_m_term, 0)}."
    mm.append(P(p))
    if f.ctx.get("levers", {}).get("margin_ps"):
        mm.append(P(f"The margin is the most valuable single input after the discount rate: each 100bps of EBIT margin across the forecast is worth about "
                    f"{b(ps(f.ctx['levers']['margin_ps']))} a share in the DCF."))
    mm.append(H("Earnings per share"))
    eps = [(y, e) for y, e in zip(f.years, f.eps) if ok(e)]
    p = (f"Diluted EPS was {ps(f.eps[-1])} in {_yr(f, -1)} (" + ", ".join(f"FY{y} {ps(e)}" for y, e in eps[-4:-1]) + " before). ") if ok(f.eps[-1]) and len(eps) >= 2 else ""
    if f.eps_fy1:
        p += (f"Consensus has {b(ps(f.eps_fy1))} for FY{f.fy1}" + (f" and {b(ps(f.eps_fy2))} for FY{f.fy1 + 1}" if f.eps_fy2 else "")
              + f", which blends to {b(ps(f.eps_ntm))} on a next-twelve-months basis. ")
    if f.peak_ratio and f.peak_ratio > 1.8 and f.cyc_info.norm_eps:
        p += (f"That NTM figure is {b(xm(f.peak_ratio))} the {ps(f.cyc_info.norm_eps)} the business has earned on average through the cycle, "
              + (f"so we capitalise it at a multiple scaled by {f.durab:.2f}: the market does not pay a full multiple for earnings that are a multiple of normal."
                 if f.durab < 0.999 else
                 "but the reported history shows no peak-to-trough pattern, so we read the step-up as growth rather than a peak and apply no durability haircut."))
    mm.append(P(p))
    ebit = [e for e in f.ebit if ok(e)]
    if len(ebit) >= 2 and ok(f.rev[-1]) and ok(f.rev[-2]) and (f.rev[-1] - f.rev[-2]) > 0 and abs(f.rev[-1] - f.rev[-2]) / f.rev[-2] > 0.05:
        inc = (f.ebit[-1] - f.ebit[-2]) / (f.rev[-1] - f.rev[-2])
        if inc < 0:
            mm.append(P(f"{b('Operating leverage.')} Revenue rose last year but EBIT fell, so the incremental margin was negative ({pct(inc, 0)}): growth was bought with lower profitability, which is the opposite of operating leverage.", more=True))
        elif ok(f.margin_last) and f.margin_last > 0:
            mm.append(P(f"{b('Operating leverage.')} Last year each extra {cur}1 of revenue brought {ps(inc, cur)} of EBIT ({'above' if inc > f.margin_last else 'below'} the {pct(f.margin_last, 0)} average margin), "
                        f"{'a sign of strong operating leverage as fixed costs were absorbed.' if inc > f.margin_last else 'which says growth came with lower incremental profitability.'}", more=True))
    mm.append(P("The table below the text sets out the income statement; forecast columns (shaded) are consensus where it exists and our DCF base case otherwise. "
                "Any line a provider does not report is shown as a dash rather than estimated.", more=True))
    mm.append(CALL("What to watch", [f"FY{f.fy1} revenue against the {money(f.rev_fy1, cur)} consensus path." if f.rev_fy1 else "Reported revenue against the consensus path.",
                                      f"The EBIT margin against the {pct(f.dcf_m_term, 0)} terminal level our DCF assumes." if f.has_dcf else "The EBIT margin against its through-cycle average.",
                                      "Gross-margin direction: it separates pricing power from volume."]))
    return dict(key="p6", nav="Financials", kicker="Financial analysis · growth and profitability",
                title="Growth, margins and earnings", sub=f"Revenue {pct(f.cagr_all, 1) if ok(f.cagr_all) else 'trend'} a year over {f.span} years; the EBIT margin is the swing factor.", main=mm)


def cash_balance(f) -> dict:
    cur = f.cur
    y = f.last
    mm = []
    mm.append(P(f"Operating cash flow of {money(y.operating_cash_flow, cur)} funded {money(y.capex, cur)} of capex in {_yr(f, -1)}, leaving free cash flow of "
                f"{b(money(f.fcf_last, cur))}" + (f" — {xm(f.cash_conv)} net income" if ok(f.cash_conv) else "")
                + (f" and a {pct(f.fcf_yield, 1)} yield on the market capitalisation" if ok(f.fcf_yield) else "") + ".", lead=True))
    mm.append(H("Capital intensity"))
    cp = [c for c in f.capex_pct if ok(c)]
    p = f"Capex ran at {b(pct(f.capex_pct[-1], 0))} of sales" if ok(f.capex_pct[-1]) else "Capex intensity is not available"
    if len(cp) >= 2:
        p += f" (from {pct(cp[0], 0)} in {_yr(f, 0)})"
    if ok(f.capex_da):
        p += f", {xm(f.capex_da, 2)} depreciation and amortisation. "
        p += ("Above 1x the company is investing for growth, so free cash flow trails earnings until that spending matures; " if f.capex_da > 1.15 else
              "Below 1x depreciation overstates the capital the business really needs, so cash conversion can run ahead of earnings for a while; " if f.capex_da < 0.9 else
              "Near 1x the business is broadly maintaining its asset base; ")
        if f.has_dcf and f.anch:
            p += f"our DCF converges capex to {1.10:.2f}x D&A by the terminal year so that growth is funded without permanent over- or under-investment."
        else:
            p = p.rstrip("; ") + "."
    mm.append(P(p))
    mm.append(H("Cash conversion"))
    p = ""
    if f.fcf_last is not None and f.fcf_last < 0:
        p += (f"Free cash flow was negative ({money(f.fcf_last, cur)}): the business is consuming cash rather than generating it, and that is funded from the balance sheet"
              + (f" ({money(f.cash, cur)} of cash)" if f.cash else "") + ". ")
    elif ok(f.cash_conv):
        p += f"Operating cash flow was {xm(f.cash_conv, 2)} net income, "
        p += ("comfortably above earnings, so reported profit is backed by cash" if f.cash_conv >= 1.0 else "below earnings, which is worth watching: profit is not yet turning into cash")
        p += f"; Sloan accruals of {pct(f.accr, 1)} of assets point the same way. " if ok(f.accr) else ". "
    if ok(f.fcf_yield):
        p += f"On free cash flow the shares yield {pct(f.fcf_yield, 1)}" + (f", and the {pct(f.yld, 1)} dividend is {'well' if f.fcf_last and f.dps * f.shares < f.fcf_last else 'not'} covered by it" if f.dps and f.yld >= 0.003 else "") + "."
    mm.append(P(p))
    mm.append(H("Balance sheet"))
    p = (f"{cap(f.name)} holds {b(money(f.cash, cur))} of cash and short-term investments against {money(f.debt, cur)} of debt: "
         + (f"a net cash position of {money(abs(f.nd), cur)}" if f.net_cash else f"net debt of {money(f.nd, cur)}" + (f", or {xm(f.nd_ebitda)} EBITDA ({lev_word(f.nd_ebitda, False)})" if ok(f.nd_ebitda) else " (leverage ratios against EBITDA are not available)")) + ". ")
    if ok(f.cover) and f.cover > 0 and f.debt > 0:
        p += f"EBIT covers interest {xm(f.cover)}, which our credit screen maps to {f.wacc_res.credit_label.split('(')[0].strip()}; "
    elif f.debt <= 0:
        p += "With no debt, interest cover is not a constraint; "
    if ok(f.current_ratio):
        p += f"the current ratio is {xm(f.current_ratio, 2)}. "
    p += (f"Shareholders' equity is {money(f.equity, cur)}" + (f", {xm(f.pb)} book at the current price" if ok(f.pb) else "") + ".")
    mm.append(P(p))
    mm.append(H("Returns on capital"))
    p = ""
    if f.roic is not None:
        p += (f"{b('ROIC')} is {b(pct(f.roic, 1))} against a {pct(f.wacc, 1)} WACC, a spread of {_neg(f"{f.roic_spread * 1e4:+,.0f}")}bps; ROE is {pct(f.roe, 1)}"
              + (f" and ROA {pct(f.roa, 1)}" if ok(f.roa) else "") + ". ")
        roics = [v for v in f.rs["roic"] if ok(v)]
        if len(roics) >= 3:
            p += f"Over the window ROIC moved {series_txt_pct(roics)}, so today's return is {_roic_story(f, roics)}. "
    if f.dupont:
        d = f.dupont
        p += (f"The DuPont split for FY{d['year']} is a {pct(d['net_margin'], 1)} net margin × {xm(d['turnover'], 2)} asset turnover × {xm(d['multiplier'], 2)} equity multiplier = {pct(d['roe'], 1)} ROE: "
              f"{'returns come from profitability, not from leverage' if (d['multiplier'] < 2 and d['roe'] > 0) else 'the loss, not leverage, drives the negative return' if d['roe'] < 0 else 'leverage is a meaningful part of the return'}.")
    mm.append(P(p))
    wc = f.wc or {}
    if wc.get("CCC") is not None:
        mm.append(P(f"{b('Working capital.')} The cash conversion cycle is {wc['CCC']:.0f} days (receivables {wc.get('DSO', 0):.0f}, inventory {wc.get('DIO', 0):.0f}, payables {wc.get('DPO', 0):.0f}). "
                    "In a growth phase that cycle consumes cash; if growth slows, the same cycle releases it, which is part of why free cash flow can run ahead of earnings in a downturn.", more=True))
    if f.dps:
        mm.append(P(f"{b('Capital return.')} The dividend is {ps(f.dps)} a share ({pct(f.yld, 1)} yield)" + (", too small to matter for returns, which come from the share price." if f.yld < 0.003 else ".")
                    + " Buybacks are not captured in the data we use, so total shareholder yield may be higher.", more=True))
    mm.append(P(f"Statements are shown on {PGREF('p14')}; forecast cash flow is unlevered (free cash flow to the firm) so that it can be discounted at the WACC without double-counting the interest tax shield.", more=True))
    mm.append(CALL("Key takeaways", [f"Free cash flow {money(f.fcf_last, cur)}; {xm(f.cash_conv)} net income." if ok(f.cash_conv) else f"Free cash flow {money(f.fcf_last, cur)}.",
                                      ("Net cash balance sheet." if f.net_cash else (f"Net debt {xm(f.nd_ebitda)} EBITDA." if ok(f.nd_ebitda) else f"Net debt {money(f.nd, cur)}.")),
                                      f"ROIC {pct(f.roic, 0)} against a {pct(f.wacc, 1)} WACC." if f.roic is not None else "ROIC not available."]))
    return dict(key="p7", nav="Cash flow", kicker="Financial analysis · cash flow and balance sheet",
                title="Cash generation, capital intensity and the balance sheet",
                sub=f"Free cash flow of {money(f.fcf_last, cur)}; {'net cash' if f.net_cash else (xm(f.nd_ebitda) + ' net debt/EBITDA' if ok(f.nd_ebitda) else 'net debt ' + money(f.nd, cur))}; ROIC {pct(f.roic, 0)} vs WACC {pct(f.wacc, 1)}.", main=mm)


def series_txt_pct(vals):
    return " → ".join(pct(v, 0) for v in vals)


def quality(f) -> dict:
    mm = []
    pio, alt = f.pio, f.alt
    bits = []
    if pio.get("available"):
        bits.append(f"a Piotroski F-score of {b(str(pio['score']))} out of {pio['available']} testable")
    if alt:
        bits.append(f"an Altman Z of {b(format(alt['z'], '.1f'))} ({alt['zone']})")
    if ok(f.accr):
        bits.append(f"Sloan accruals of {b(pct(f.accr, 1))} of assets")
    clean = (pio.get("available") and pio["score"] >= 6) and (not alt or alt["zone"] == "safe") and (not ok(f.accr) or f.accr < 0.05)
    mm.append(P(f"Accounting-based screens give {join(bits)}. " + ("Taken together they describe a business whose reported earnings are backed by cash and a balance sheet "
                "that is not under strain; the open question is durability, not integrity." if clean else
                "Taken together the signals are mixed, so we lean harder on cash-flow evidence than on reported earnings."), lead=True))
    mm.append(H("Piotroski F-score"))
    if pio.get("items"):
        passed = [l for l, ok_ in pio["items"] if ok_ is True]
        failed = [l for l, ok_ in pio["items"] if ok_ is False]
        na = [l for l, ok_ in pio["items"] if ok_ is None]
        p = f"The score counts nine binary tests of profitability, leverage and efficiency. {cap(f.name)} passes {num_word(len(passed))}"
        if passed:
            lst = [x.lower() for x in passed[:4]]
            p += " — " + (", ".join(lst) + f" and {num_word(len(passed) - 4)} more" if len(passed) > 4 else join(lst))
        p += (f"; it fails {num_word(len(failed))}: " + join([x.lower() for x in failed]) if failed else "")
        p += ("; " + num_word(len(na)) + " test" + ("s" if len(na) != 1 else "") + " could not be computed from the statement lines available and are excluded rather than counted as failures" if na else "") + "."
        mm.append(P(p))
        if failed:
            strong = any(x.lower() in ("positive return on assets", "positive operating cash flow") for x in failed)
            soft = all(("dilution" in x.lower() or "current ratio" in x.lower() or "leverage" in x.lower()) for x in failed)
            mm.append(P("The failures are worth reading in context: "
                        + ("failing the level tests means the business is not yet earning a positive return on its assets or generating operating cash, which is the failure that matters most." if strong else
                           "a weaker current ratio or a higher share count are typical of a company funding rapid growth, not of distress." if soft else
                           "these are year-on-year improvement tests, so they say the trend slipped in the latest year, not that the business is weak.")))
    if pio.get("items"):
        grp = {"Profitability": [], "Leverage and liquidity": [], "Efficiency": []}
        for l_, ok_ in pio["items"]:
            lk = l_.lower()
            g_ = ("Profitability" if any(k in lk for k in ("return on assets", "operating cash", "accrual", "cash flow exceeds")) else
                  "Leverage and liquidity" if any(k in lk for k in ("leverage", "current ratio", "dilution")) else "Efficiency")
            grp[g_].append((l_, ok_))
        lines = []
        for g_, items in grp.items():
            if items:
                n_ok = sum(1 for _, o in items if o is True)
                n_av = sum(1 for _, o in items if o is not None)
                lines.append(f"{b(g_)}: {n_ok} of {n_av} passed")
        if lines:
            mm.append(UL(lines, more=True))
    mm.append(H("Distress risk"))
    if alt:
        mm.append(P(f"Altman's Z-score combines working capital, retained earnings, operating profit, market value of equity relative to liabilities and sales to assets. "
                    f"At {b(format(alt['z'], '.1f'))} {f.name} sits in the {alt['zone']} zone (above 2.99 is safe, below 1.81 is distress). "
                    + ("A score this high is helped by a large market capitalisation relative to liabilities, so it mainly confirms the absence of balance-sheet stress rather than measuring quality of earnings." if alt["z"] > 6 else
                       "The score is a screen, not a forecast; it was calibrated on industrial companies.")))
    else:
        mm.append(P("Altman Z is not computed here: the company is a financial or the balance sheet lacks the lines the model needs."))
    mm.append(H("Accruals and the cash cycle"))
    wc = f.wc
    p = ""
    if ok(f.accr):
        p += (f"Sloan accruals — net income less operating cash flow, scaled by assets — are {pct(f.accr, 1)}. Readings below zero mean earnings are more than backed by cash; "
              "strongly positive readings are the classic marker of aggressive accounting. ")
    if wc:
        p += ("Working capital runs on " + ", ".join(f"{k} {v:.0f} days" for k, v in wc.items() if k in ("DSO", "DIO", "DPO")) + (f", a cash conversion cycle of {wc['CCC']:.0f} days" if "CCC" in wc else "") + ". ")
        if "CCC" in wc:
            p += (f"A cycle of that length ties up cash as the company grows, which is why the DCF charges {pct(f.anch.get('nwc_pct'), 1)} of incremental revenue to working capital." if f.has_dcf and f.anch and f.anch.get("nwc_pct") else "")
    mm.append(P(p))
    mm.append(H("Is the earnings base durable?"))
    ci = f.cyc_info
    if ci.is_cyclical:
        if ok(f.peak_ratio) and f.durab < 0.999:
            mm.append(P(f"{b('No, not in full.')} The model flags the earnings as cyclical: {'; '.join(_flat(r_) for r_ in ci.reasons)}. When forward EPS is {xm(f.peak_ratio)} the through-cycle average we scale the target multiple by {b(format(f.durab, '.2f'))}; "
                        f"that is a haircut, not a forecast of decline. Markets typically pay lower multiples for peak earnings, and our relative lenses do the same."))
        else:
            mm.append(P(f"{b('Not on the evidence of the history.')} The model flags the earnings as cyclical: {'; '.join(_flat(r_) for r_ in ci.reasons)}. Forward earnings cannot be compared with a through-cycle average here "
                        f"(the average is not positive or not available), so no durability haircut is applied to the multiples (factor {f.durab:.2f})."))
    else:
        mm.append(P(f"{b('Yes, on the evidence available.')} Revenue and margins show no peak-to-trough pattern in the reported history, so forward earnings are capitalised at the full target multiple "
                    f"(durability factor {f.durab:.2f}); growth source: {f.fwd.growth_src}."))
    for fl in [x for x in f.fwd.flags if "through-cycle" not in x][:2]:
        mm.append(P(fl, more=True))
    axes = f.ctx.get("scorecard") or []
    if axes:
        top = max(axes, key=lambda a: a["score"])
        low = min(axes, key=lambda a: a["score"])
        mm.append(P(f"{b('Scorecard.')} Of six factors scored 0–100, {top['axis'].lower()} ({top['score']}) is the strongest and {low['axis'].lower()} ({low['score']}) the weakest; "
                    "the scales are given in the appendix.", more=True))
    mm.append(CALL("Key takeaways", [
        (f"Piotroski {pio['score']}/{pio['available']}" + (f", Altman Z {alt['z']:.1f} ({alt['zone']})" if alt else "") + ".") if pio.get("available") else "Piotroski not computable from the statement lines available.",
        (f"Accruals {pct(f.accr, 1)} of assets: " + ("earnings are backed by cash." if f.accr < 0.03 else "watch the gap between profit and cash.")) if ok(f.accr) else "Accruals not computable.",
        (f"Durability factor {f.durab:.2f}: forward EPS is {xm(f.peak_ratio)} the through-cycle level." if f.peak_ratio and f.durab < 0.999 else "No durability haircut applied.")]))
    return dict(key="p8", nav="Quality", kicker="Financial analysis · earnings quality",
                title="Earnings quality and financial health",
                sub="Are the reported numbers backed by cash, is the balance sheet safe, and is the earnings base durable?", main=mm)


def dcf_assumptions(f) -> dict:
    w = f.wacc_res
    mm = []
    mm.append(P(f"The DCF is the cross-check that ignores what other investors pay. It values {b(_words(f.dcf_horizon) + ' years')} of unlevered free cash flow plus a terminal value, discounted at the "
                f"{b(pct(f.wacc, 2))} WACC. The early years follow consensus; thereafter growth fades toward the terminal rate and margins mean-revert, so the model cannot extrapolate a single strong year.", lead=True))
    mm.append(H("The drivers"))
    for drv, path, why in (f.drivers.rationale if f.drivers else []):
        mm.append(P(f"{b(drv)}: <span style='font-family:var(--mono);font-size:.9em;color:var(--ink-soft)'>{path}</span>. {why}"))
    mm.append(H("Cost of capital"))
    p = (f"The cost of equity is {b(pct(w.cost_of_equity, 2))}: a {pct(w.risk_free, 1)} risk-free rate plus a beta of {b(format(w.beta_used, '.2f'))} times a {pct(w.erp, 1)} equity risk premium"
         + (f" and a {pct(w.country_premium, 1)} country premium" if w.country_premium else "") + f". The beta is {w.beta_method}. ")
    p += (f"Debt costs {pct(w.cost_of_debt_pretax, 1)} before tax ({_flat(w.credit_label)}), {pct(w.cost_of_debt_after_tax, 1)} after tax, "
          + (f"and makes up {pct(w.weight_debt, 1)} of the capital structure at market values, so the WACC is {pct(w.wacc, 2)}." if w.weight_debt >= 0.01 else
             f"but carries almost no weight in the capital structure ({pct(w.weight_debt, 1)}), so the WACC is essentially the cost of equity at {pct(w.wacc, 2)}."))
    mm.append(P(p))
    for n in w.notes[:2]:
        mm.append(P(n, more=True))
    mm.append(H("Terminal value"))
    mm.append(P(f"Terminal growth is {b(pct(f.dcf.terminal_growth, 1))}, at or below long-run nominal GDP, with terminal reinvestment of g ÷ ROIC"
                + (f" ({pct(f.reinvest, 0)} of NOPAT at a {pct(f.roic_term, 0)} terminal ROIC)" if ok(f.reinvest) and ok(f.roic_term) and f.roic_term > 0 else "")
                + f". The terminal value is {b(pct(f.dcf_tv, 0))} of enterprise value" + (" — high enough that the result should be read with the sensitivity table, not alone." if f.dcf_tv > 0.75 else ".")))
    mm.append(P(f"{b('Conventions.')} Cash flows are discounted with a mid-year convention (flows arrive on average halfway through each year), net debt and minorities are deducted at the latest balance sheet, "
                f"and the horizon is {_words(f.dcf_horizon)} years for this profile. The sensitivity table varies the WACC by ±150bps and terminal growth by ±100bps around the base case.", more=True))
    return dict(key="p9", nav="DCF", kicker="Valuation · discounted cash flow (1/2)",
                title="DCF: the assumptions behind the cash flows",
                sub="Consensus for the near years, then a steady growth fade, mean-reverting margins and reinvestment tied to growth and returns.", main=mm)


def dcf_results(f) -> dict:
    cur, d = f.cur, f.dcf
    mm = []
    gap = f.dcf_vps / f.price - 1
    mm.append(P(f"The base case gives an enterprise value of {b(money(d.enterprise_value, cur))} and an equity value of {b(money(d.equity_value, cur))}, or {b(ps(f.dcf_vps))} a share "
                f"({spct(gap)} against the price). "
                + (("The cash-flow lens does not support a positive value" if f.dcf_vps <= 0 else f"That is the {'lowest' if f.dcf_vps == f.lens_lo else 'highest'} of our lenses" if f.dcf_vps in (f.lens_lo, f.lens_hi) else "That sits in the middle of our lenses")
                   + (f", and the triangulation {'down-weights' if _lens(f, 'dcf') and _lens(f, 'dcf').status_note else 'weights'} it accordingly" if _lens(f, 'dcf') else "") + "." if f.lens_lo else ""), lead=True))
    mm.append(H("Where the value sits"))
    mm.append(P(f"Explicit cash flows contribute {money(d.pv_explicit, cur)} and the terminal value {money(d.pv_tv, cur)} ({pct(f.dcf_tv, 0)} of EV). "
                + (f"The terminal value implies an exit multiple of {b(xm(f.exit_mult))} EBITDA" + (f" against {xm(f.ev_ebitda_ltm)} today" if ok(f.ev_ebitda_ltm) else "") + ", "
                   + ("a far lower multiple than the market pays now, which is where much of the gap to the multiples lenses comes from." if ok(f.ev_ebitda_ltm) and f.ev_ebitda_ltm > 0 and f.exit_mult < f.ev_ebitda_ltm * 0.5 else "a steady-state multiple for a mature business." if ok(f.exit_mult) else "") if (ok(f.exit_mult) and d.pv_tv > 0) else "")))
    if ok(f.roic_term):
        mm.append(P(f"Terminal ROIC is {pct(f.roic_term, 1)} against a {pct(f.wacc, 1)} WACC, "
                    + ("so growth in perpetuity still creates a little value; if returns fell to the cost of capital the terminal value would be worth less than shown." if f.roic_term > f.wacc else
                       "so growth in perpetuity destroys value, which is why we cap it near zero.")))
    if f.dcf_vps <= 0:
        mm.append(H("Why the DCF is negative"))
        mm.append(P("Free cash flow is negative through most of the forecast and the terminal value does not offset it: the business has not yet reached a scale at which it earns more than it reinvests. "
                    "A negative DCF does not make the shares worthless; it says the cash-flow lens cannot support a price today, so any value rests on the optionality the revenue- and book-based lenses try to capture, "
                    "which is also why the lenses disagree and the confidence grade is low."))
    om = _others_mean(f, "dcf")
    below = om is not None and f.dcf_vps < om
    mm.append(H(("Why the DCF sits below the multiples" if below else "Why the DCF sits above the multiples") if (f.dcf_vps > 0 and om) else "Reading the DCF against the other lenses"))
    if below or not om:
        p = ("Multiples capitalise consensus earnings as they are; the DCF has to earn them. "
             + (f"Here the margin the DCF carries falls from {pct(f.dcf_m_peak, 0)} at the peak to {pct(f.dcf_m_term, 0)} at the end, and capex stays above depreciation for years, "
                f"so free cash flow converts less of the headline earnings. " if f.has_dcf and f.dcf_m_peak > f.dcf_m_term + 0.08 else "")
             + "Neither answer is wrong; the gap measures how much of today's profitability the market is treating as permanent.")
    else:
        p = ("The DCF is the more generous lens here: it credits ten years of growth and a terminal value, while forward multiples capitalise one or two years of earnings at a sector-anchored multiple. "
             + (f"Terminal value is {pct(f.dcf_tv, 0)} of the DCF, so the premium to the multiples rests heavily on the long-run assumptions. " if f.dcf_tv > 0.6 else "")
             + "Neither answer is wrong; the gap measures how much the market is willing to pay today for growth that has not yet been delivered.")
    mm.append(P(p))
    if f.rev_dcf:
        r = f.rev_dcf
        mm.append(H("Reverse DCF: what the price needs"))
        mm.append(P(f"Holding our cost of capital and long-run assumptions, the current price requires year-one revenue growth of {b(pct(r['implied_y1_growth'], 1))} (terminal growth {pct(r['implied_terminal_growth'], 1)}) "
                    f"against our {pct(r['base_y1_growth'], 1)}. {_rev_verdict(r, 'dcf')}"))
    if f.eps_ntm and f.eps_ntm > 0:
        mm.append(P(f"{b('Implied multiples.')} At the DCF value of {ps(f.dcf_vps)} the shares would trade on {xm(f.dcf_vps / f.eps_ntm)} NTM EPS, against {xm(f.pe_ntm)} today and "
                    f"{xm(f.ref.pe)} for the sector. That is a useful sanity check: a DCF that implies a multiple far below any peer is usually telling us about its own conservatism as much as about the stock.", more=True))
    if f.diag.get("flags"):
        mm.append(H("Model diagnostics"))
        mm.append(UL([f"{k}: {v} — {st}" for k, v, st in f.diag["flags"]]))
    if f.dcf_bear and f.dcf_bull:
        mm.append(P(f"The bear and bull scenarios bracket the base value at {ps(f.dcf_bear)} and {ps(f.dcf_bull)}; the sensitivity table on {PGREF('p5')} shows the effect of the discount rate and terminal growth.", more=True))
    return dict(key="p10", nav="DCF result", kicker="Valuation · discounted cash flow (2/2)",
                title="DCF: what it values, and what the price requires",
                sub=f"{ps(f.dcf_vps)} a share on the cash-flow lens; the terminal value carries {pct(f.dcf_tv, 0)} of enterprise value.", main=mm)


def _top_playbook(f, phase, n=3):
    rows = (f.cyc.get("playbook_all") or {}).get(phase) or []
    rows = sorted(rows, key=lambda r: -(r[1] or 0))[:n]
    return join([f"{_en(nm)} ({w:.0f}%)" for nm, w in rows])


def cycle_macro(f) -> dict:
    c = f.cyc
    probs = c["probs"]
    order = sorted(probs.items(), key=lambda kv: -kv[1])
    top, second = order[0], order[1]
    mm = []
    mm.append(P(f"The Reloj de inversión — our own cycle model, published as a separate project — classifies the US economy each month into one of four phases from growth and inflation. "
                f"Its latest reading ({c['asof']}) is {b(f.phase_en)} (the Reloj's “{c['phase']}”) with {b(_strength(c['strength']))} conviction: {top[1]:.0%} against {second[1]:.0%} for {PHASE_EN.get(second[0], second[0])}.", lead=True))
    mm.append(H("How the Reloj reads the cycle"))
    mm.append(P("Twenty-eight FRED series are converted to robust z-scores and combined by principal components into a growth axis and an inflation axis; the month's position on that plane, "
                "and its uncertainty, give a probability for each phase. A phase is Recovery (growth above trend, inflation below), Overheat (both above), Stagflation (growth below, inflation above) "
                "or Reflation (both below)."))
    mm.append(H("The current reading"))
    mom = c.get("momentum") or {}
    p = (f"Growth sits at {b(f'{c['growth']:+.2f}σ')} and inflation at {b(f'{c['inflation']:+.2f}σ')} of their ten-year norms, "
         f"i.e. close to the centre of the plane, where phase calls are least reliable. "
         if abs(c["growth"]) < 0.5 and abs(c["inflation"]) < 0.5 else
         f"Growth sits at {b(f'{c['growth']:+.2f}σ')} and inflation at {b(f'{c['inflation']:+.2f}σ')} of their ten-year norms. ")
    if mom.get("growth_3m") is not None:
        p += f"Over three months growth has moved {mom['growth_3m']:+.2f}σ and inflation {mom['inflation_3m']:+.2f}σ. "
    if c.get("recession") is not None:
        p += f"The model's 12-month recession probability is {b(pct(c['recession'], 0))}."
    mm.append(P(p))
    mm.append(H("Why a weak signal changes how we use it"))
    margin_pts = (top[1] - second[1]) * 100
    mm.append(P(f"Only {margin_pts:.1f} percentage points separate the first and second phase. When the call is that close, naming one phase and acting on it would be false precision; "
                "the more honest estimate is the probability-weighted one. That is what we use on the next page: each phase's historical sector return, weighted by today's phase probabilities."
                if margin_pts < 8 else
                f"The leading phase is {margin_pts:.1f} percentage points ahead of the next, a reasonably clear call; we still weight every phase by its probability rather than acting on the label alone."))
    mm.append(H("What each phase has favoured"))
    lines = [f"{b(PHASE_EN[p])}: {_top_playbook(f, p)}" for p in PHASE_EN if (c.get('playbook_all') or {}).get(p)]
    if lines:
        mm.append(P(f"The Reloj's rotation playbook, built from the same history ({_en(c.get('playbook_label') or 'default scheme').lower()}), leans on different sleeves in each phase:"))
        mm.append(UL(lines))
    hist = (f.ctx.get("cycle_raw") or {}).get("history") or []
    if hist:
        run = 0
        for h_ in reversed(hist):
            if h_["p"] == c["phase"]:
                run += 1
            else:
                break
        share = sum(1 for h_ in hist if h_["p"] == c["phase"]) / len(hist)
        mm.append(P(f"{b('How long in this phase.')} The Reloj has called {f.phase_en} for {num_word(run) if run < 10 else run} consecutive month{'s' if run != 1 else ''}, and for {share:.0%} of the last {len(hist) // 12} years. "
                    + ("A phase that has just changed carries more uncertainty than one that has persisted." if run <= 3 else "A phase that has persisted for a long time is less likely to be a false read, though turning points are exactly where the model is weakest."), more=True))
    mm.append(P("The macro read is context for the valuation. It does not move our price target, but it does tell us whether the sector a company belongs to has historically had the wind at its back or in its face.", more=True))
    trail = c.get("trail") or []
    if len(trail) >= 12:
        g0, i0 = trail[-12][0], trail[-12][1]
        g1, i1 = trail[-1][0], trail[-1][1]
        mm.append(P(f"{b('Direction of travel.')} A year ago the Reloj plotted at growth {g0:+.2f}σ and inflation {i0:+.2f}σ; it now plots at {g1:+.2f}σ and {i1:+.2f}σ, "
                    f"{'a drift toward weaker growth' if g1 < g0 - 0.2 else 'a drift toward stronger growth' if g1 > g0 + 0.2 else 'little change in growth'} and "
                    f"{'hotter inflation' if i1 > i0 + 0.2 else 'cooler inflation' if i1 < i0 - 0.2 else 'little change in inflation'}.", more=True))
    mm.append(CALL("Key takeaways", [f"{f.phase_en}, {_strength(c['strength'])} signal: {top[1]:.0%} vs {second[1]:.0%} for {PHASE_EN.get(second[0], second[0])}.",
                                      f"Growth {c['growth']:+.2f}σ, inflation {c['inflation']:+.2f}σ; 12-month recession probability {pct(c['recession'], 0)}." if c.get("recession") is not None else f"Growth {c['growth']:+.2f}σ, inflation {c['inflation']:+.2f}σ.",
                                      "We weight phases by probability; the label alone is not a forecast."]))
    return dict(key="p11", nav="Cycle", kicker="Macro context · Reloj de inversión",
                title=f"Where the cycle is: {f.phase_en}, {_strength(c['strength'])} signal",
                sub="Growth and inflation read from 28 FRED series, expressed as probabilities of four phases rather than a single label.", main=mm)


def cycle_sector(f) -> dict:
    c = f.cyc
    st = c["stats"] or {}
    asset = f.asset_en
    mm = []
    if not asset:
        mm.append(P(f"{f.sector or 'This sector'} has no equivalent sleeve in the Reloj's asset universe, so we offer no sector tilt and say nothing the data cannot support.", lead=True))
        return dict(key="p12", nav="Sector", kicker="Macro context · sector evidence", title="No sector evidence for this company", sub=None, main=mm)
    etfs = join([t for t, _ in c["etfs"]])
    mm.append(P(f"We map {b(f.name)} to the Reloj's {b(asset)} sleeve" + (f", which it tracks through {etfs}" if etfs else "")
                + (f"; the Reloj's evidence for {asset} runs back to 1970 and covers {max(int(s.get('n') or 0) for s in st.values())} months in its longest phase." if st else "") , lead=True))
    mm.append(H("What the sector has paid in each phase"))
    lines = []
    for p in ("Recuperación", "Sobrecalentamiento", "Estanflación", "Reflación"):
        s = st.get(p) or {}
        if not s:
            continue
        rel = s.get("rel_shrunk")
        lines.append(f"{b(PHASE_EN[p])}{' (current)' if p == c['phase'] else ''}: {pct((s.get('ann') or 0) / 100, 1)} a year on average, "
                     f"{pp(rel)} a year versus the US market (t = {_neg(f"{s.get('t', 0):+.1f}")}, hit rate {pct(s.get('hit'), 0)}, {_rel_en(s.get('reliability'))} evidence)")
    mm.append(UL(lines))
    ast = c.get("asset_stats") or {}
    mm.append(P(f"Read these with the statistics in mind. A t-statistic smaller than about 2 in absolute value means the sector's return in that phase cannot be told from chance; "
                + (f"across all sector × phase cells the Reloj tests, only {ast.get('fdr_survivors')} of {ast.get('cells')} survive false-discovery control. " if ast.get("fdr_survivors") is not None else "")
                + "That is why the Reloj shrinks every estimate toward zero, and why we quote the shrunk figure."))
    mm.append(H("The probability-weighted tilt"))
    if c.get("tilt") is not None:
        t = c["tilt"]
        mm.append(P(f"Weighting each phase's shrunk excess return by today's phase probabilities gives a tilt of {b(pp(t))} a year for {asset} against the US market. "
                    + ("That is small relative to the noise in the estimates: a nudge, not a thesis." if abs(t) < 1.5 else "That is large enough to matter against our valuation call, though still within the statistical noise of the underlying estimates.")))
    if st and c.get("alt") and st.get(c["alt"]):
        alt_edge = (st.get(c["alt"]) or {}).get("rel_shrunk")
        cur_edge = (st.get(c["phase"]) or {}).get("rel_shrunk")
        best = max(st.items(), key=lambda kv: kv[1].get("rel_shrunk") or -99)
        worst = min(st.items(), key=lambda kv: kv[1].get("rel_shrunk") or 99)
        mm.append(P(f"{b('Scenario: the cycle tips.')} If the Reloj's runner-up, {PHASE_EN.get(c['alt'], c['alt'])}, took over, the sector's historical edge would move from {pp(cur_edge)} to {pp(alt_edge)} a year. "
                    f"Across the four phases {asset} has done best in {PHASE_EN[best[0]]} ({pp(best[1].get('rel_shrunk'))}) and worst in {PHASE_EN[worst[0]]} ({pp(worst[1].get('rel_shrunk'))}).", more=True))
    mm.append(H("Playbook and ETF exposure"))
    pn = c.get("playbook_now")
    p = (f"In the current phase the Reloj's playbook allocates {b(f'{pn['weight']:.1f}%')} to {asset}. " if pn else
         f"{asset} is not in the Reloj's playbook for the current phase" + (f", but would hold {c['playbook_alt']['weight']:.1f}% if the cycle tipped to {PHASE_EN.get(c['alt'], c['alt'])}. " if c.get("playbook_alt") else ". "))
    hold = c.get("holding") or {}
    hit = (hold.get("hits") or [None])[0]
    if hit:
        p += f"{f.tk} is the {_ord(hit['rank'])} holding of the sector ETF, with a {hit['weight']:.2f}% weight"
        g = hold.get("group")
        if g:
            p += f", inside the {g['group']} sub-sector ({g['group_weight']:.1f}% of the fund)"
        p += ". Owning the sector through its ETF carries that exposure at the weight shown; owning the stock adds single-name risk the sector evidence does not measure."
    mm.append(P(p))
    mm.append(H("Putting the cycle and the valuation together"))
    t = c.get("tilt")
    if f.rated and t is not None:
        if f.ret > 0.05 and t < -0.5:
            msg = (f"Valuation points up ({spct(f.ret)} expected return) while the cycle's historical tilt is a modest headwind ({pp(t)} a year). We read that as a reason to size positions with care and to watch the phase reading, not as a reason to override the valuation.")
        elif f.ret > 0.05 and t > 0.5:
            msg = f"Valuation ({spct(f.ret)}) and the cycle's historical tilt ({pp(t)} a year) point the same way, which is the configuration we find most comfortable."
        elif f.ret < -0.05 and t > 0.5:
            msg = f"The cycle's tilt ({pp(t)} a year) supports the sector while our valuation ({spct(f.ret)}) does not see upside in this stock: the sector, not the company, is the attraction."
        elif f.ret < -0.05 and t < -0.5:
            msg = f"Valuation ({spct(f.ret)}) and the cycle's tilt ({pp(t)} a year) are both negative, so we see no offsetting argument for the shares."
        else:
            msg = f"The tilt ({pp(t)} a year) is too small to alter a {f.rating.lower()} valuation call; the cycle is background rather than a driver."
        mm.append(P(msg))
    if c.get("tilt") is not None:
        mm.append(CALL("Key takeaways", [f"{asset} tilt {pp(c['tilt'])} a year, probability-weighted; current-phase edge {pp(c.get('edge_now'))}.",
                                          (f"Playbook weight {c['playbook_now']['weight']:.1f}% in {PHASE_EN[c['phase']]}." if c.get("playbook_now") else "Not in the playbook for the current phase."),
                                          "Context for the valuation, not an input to the target."]))
    mm.append(P("Source: Reloj de inversión, github.com/Perez849/reloj-inversion. The tilt describes historical behaviour; it is not an input to the target and not investment advice.", more=True))
    return dict(key="p12", nav="Sector", kicker="Macro context · sector evidence",
                title=f"What the {asset} sleeve has paid in each phase, and where that leaves us",
                sub="Excess returns against the US market by phase, shrunk toward zero, with the statistics that say how much to trust them.", main=mm)


def _rel_en(r):
    return {"Sin señal": "no-signal", "Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}.get(r, (r or "n/a").lower())


def risks_page(f) -> dict:
    cur = f.cur
    factors = f.ctx.get("factors") or []
    mm = []
    high = [x for x in factors if x["level"] == "High"]
    med = [x for x in factors if x["level"] == "Medium"]
    low = [x for x in factors if x["level"] == "Low"]
    p = f"We scored {num_word(len(factors))} macro and company-specific factors from the model and the reported history. "
    if high:
        p += f"{b('High exposure')}: {join([x['factor'].lower() for x in high])}. "
    if med:
        p += f"{b('Medium')}: {join([x['factor'].lower() for x in med])}. "
    if low:
        p += f"{b('Low')}: {join([x['factor'].lower() for x in low])}."
    mm.append(P(p, lead=True))
    top = (high + med)[:3]
    if top:
        mm.append(H("What moves the stock most"))
        for x in top:
            mm.append(P(f"{b(x['factor'])} ({x['level'].lower()}). {x['why']} Evidence: {x['evidence']}."))
    mm.append(H("Key risks"))
    mm.append(UL(f.ctx.get("risks", [])[:6]))
    stress = f.ctx.get("stress") or []
    if stress:
        worst = sorted([x for x in stress if x[2] is not None], key=lambda x: x[2])[:3]
        mm.append(H("How big are the risks?"))
        mm.append(P("The levers behind these exposures are quantified on page [[pg:p5]]. Translating the risks into the DCF: " + "; ".join(f"{_lc(x[0])} would cut the DCF value by {pct(abs(x[2]), 0)}" for x in worst)
                    + ". These are single-factor shocks; in practice they arrive together (a de-rating and an estimate cut usually do), so the combined effect is larger than any one of them."))
    mm.append(H("What we would monitor"))
    items = []
    if f.g_fy1 is not None:
        items.append(f"Delivery against the FY{f.fy1} revenue and EPS path in quarterly results, the cleanest re-rating trigger either way.")
    items.append("The EBIT margin, and whether pricing, mix and cost discipline hold it near the level the DCF assumes.")
    if f.cyc:
        items.append("The Reloj's phase and probabilities, monthly: a move of the leading phase changes the sector's historical tilt.")
    items.append("Changes to the cost of equity: rates and the equity risk premium are the single largest swing factor in the DCF.")
    mm.append(UL(items, more=True))
    mm.append(P("Risks are listed in the order the model ranks them, not in order of probability; several interact (a de-rating and an estimate cut usually arrive together).", more=True))
    return dict(key="p13", nav="Risks", kicker="Factors, catalysts and risks",
                title="What moves the stock, and what could go wrong",
                sub="Exposure scored from the model's sensitivities and the company's history; levers quantified in value per share.", main=mm)


def appendix_statements(f) -> dict:
    return dict(key="p14", nav="Statements", kicker="Appendix A", title="Financial statements",
                sub=f"Reported fiscal years with the DCF base case and consensus as shaded forecast columns. Currency {f.data.currency}; {f.ctx['ft'].unit_label.replace(f.cur, '')} unless noted.",
                main=[], wide=True)


def appendix_method(f) -> dict:
    mm = []
    mm.append(H("Method in one paragraph"))
    mm.append(P(f"The price target triangulates relative lenses (target multiples on consensus forward numbers, anchored on peers or a sector reference table and adjusted for durable growth, leverage and earnings durability), "
                f"a {f.dcf_horizon if f.has_dcf else 10}-year DCF (consensus for the near years, a steady growth fade, mean-reverting margins) and sector models (residual income, justified P/B, FFO/AFFO, dividends, mid-cycle EBITDA), "
                "weighted by company profile. Fair value is rolled forward at the cost of equity and reduced by dividends to give a 12-month target."))
    mm.append(H("Guardrails"))
    mm.append(P("A lens outside 0.2×–5× the share price is excluded; a lens more than 2.2× away from the median of the others is down-weighted by 60%; the published target is limited to 0.4×–2.5× the price; "
                "fewer than two usable lenses, or a result forced by a guardrail, is published NOT RATED. The Street consensus is anchored at up to 30% (scaled by analyst count; 15% when the count is unknown) and is always shown separately."))
    mm.append(H("Rating bands"))
    mm.append(P("On the 12-month expected total return: OVERWEIGHT above +15%, ADD +5% to +15%, NEUTRAL −5% to +5%, REDUCE −15% to −5%, UNDERWEIGHT below −15%."))
    mm.append(H("Scorecard scales"))
    mm.append(P("Valuation: expected return −30% to +50% mapped to 0–100. Growth: durable EPS growth 0–25% and FY+1 revenue −5% to +30%. Profitability: ROIC − WACC from −5 to +25 points and EBIT margin 0–35%. "
                "Earnings quality: Piotroski share of tests passed, OCF/net income 0.5–1.2 and accruals. Balance sheet: net debt/EBITDA, interest cover and Altman zone. Cycle fit: Reloj tilt −4 to +4 pp a year."))
    mm.append(H("Quality screens"))
    mm.append(P("Piotroski F: nine binary tests of profitability, leverage/liquidity and efficiency; tests that cannot be computed from the available statement lines are excluded, not failed. "
                "Altman Z (original industrial form): above 2.99 safe, 1.81–2.99 grey, below 1.81 distress. Sloan accruals: (net income − operating cash flow) ÷ average assets."))
    mm.append(H("Reloj de inversión"))
    mm.append(P("Phase probabilities and sector evidence come from the Reloj de inversión project's published data (github.com/Perez849/reloj-inversion). Tilt = Σ phase probability × shrunk excess return of the sector in that phase. "
                "It describes historical behaviour and is not an input to the price target."))
    mm.append(H("Data and limits"))
    mm.append(P(f"Fundamentals and consensus come from {'the ' if f.data.provider.startswith('Yahoo snapshot') else ''}{f.data.provider}; the company was classified as {b(f.spec.label)}. Forward numbers are analyst consensus where available and reported figures otherwise. "
                "A single third-party source can contain restatements, one-off items or classification differences that move the output; the model flags what it can detect and refuses to publish a number it cannot defend."))
    mm.append(H("Definitions"))
    mm.append(P("EV: enterprise value = market capitalisation + net debt + minorities. NTM: next twelve months, a time-weighted blend of the two nearest forecast fiscal years. FCFF: free cash flow to the firm = NOPAT + D&A − capex − change in working capital. "
                "WACC: weighted average cost of capital. ROIC: NOPAT ÷ invested capital (debt + equity − cash). PEG: P/E ÷ durable earnings growth. Tilt: probability-weighted excess return of a sector against the US market, in percentage points a year.", more=True))
    mm.append(H("Disclaimer"))
    mm.append(P("This research note is generated by an automated, sector-aware valuation engine from public data. It is an analytical tool, not investment advice, a recommendation or an offer to transact, and it is no substitute for "
                "fundamental judgement. Past performance and historical sector behaviour are not guides to future returns. Do your own due diligence."))
    return dict(key="p15", nav="Method", kicker="Appendix B", title="Methodology, definitions and disclosures", sub=None, main=mm, cols2=True)
