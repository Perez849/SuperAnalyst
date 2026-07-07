"""Cost of capital.

Builds the discount rate with a fully transparent, auditable trail:

  Cost of equity (CAPM):  Ke = Rf + beta_relevered * ERP  (+ country + size premia)
  Cost of debt:           Kd = (Rf + credit_spread) * (1 - tax)   [pre-tax option too]
  WACC = We*Ke + Wd*Kd_after_tax

Beta can be:
  - the provider's reported (levered) beta, or
  - a BOTTOM-UP beta: average unlevered peer betas (Hamada), relevered at the
    target's own D/E. Bottom-up is the institutional default because reported
    betas are noisy single-name regressions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData


# Damodaran-style synthetic credit spread over risk-free, keyed on interest
# coverage ratio (EBIT / interest). Large-cap grid.
_COVERAGE_SPREAD = [
    (8.50, 0.0060),   # AAA
    (6.50, 0.0080),   # AA
    (5.50, 0.0100),   # A+
    (4.25, 0.0120),   # A
    (3.00, 0.0150),   # A-
    (2.50, 0.0190),   # BBB
    (2.25, 0.0250),   # BB+
    (2.00, 0.0310),   # BB
    (1.75, 0.0400),   # B+
    (1.50, 0.0510),   # B
    (1.25, 0.0650),   # B-
    (0.80, 0.0850),   # CCC
    (0.50, 0.1000),   # CC
    (-1e9, 0.1400),   # C/D
]


def synthetic_spread(ebit: float, interest_expense: float) -> tuple[float, str]:
    if interest_expense <= 0:
        return 0.0075, "AA (no meaningful debt)"
    cov = ebit / interest_expense
    labels = ["AAA", "AA", "A+", "A", "A-", "BBB", "BB+", "BB", "B+", "B", "B-", "CCC", "CC", "C/D"]
    for (thresh, spread), label in zip(_COVERAGE_SPREAD, labels):
        if cov >= thresh:
            return spread, f"{label} (EBIT/int = {cov:.1f}x)"
    return 0.14, "C/D"


@dataclass
class WACCResult:
    wacc: float
    cost_of_equity: float
    cost_of_debt_after_tax: float
    cost_of_debt_pretax: float
    beta_used: float
    risk_free: float
    erp: float
    country_premium: float
    size_premium: float
    weight_equity: float
    weight_debt: float
    tax_rate: float
    credit_label: str
    beta_method: str
    notes: list[str] = field(default_factory=list)

    def as_rows(self):
        return [
            ("Risk-free rate (Rf)", f"{self.risk_free:.2%}"),
            ("Equity risk premium (ERP)", f"{self.erp:.2%}"),
            ("Country risk premium", f"{self.country_premium:.2%}"),
            ("Beta ({})".format(self.beta_method), f"{self.beta_used:.2f}"),
            ("Size premium", f"{self.size_premium:.2%}"),
            ("Cost of equity (Ke)", f"{self.cost_of_equity:.2%}"),
            ("Pre-tax cost of debt", f"{self.cost_of_debt_pretax:.2%}"),
            ("After-tax cost of debt", f"{self.cost_of_debt_after_tax:.2%}"),
            ("Marginal tax rate", f"{self.tax_rate:.1%}"),
            ("Weight of equity", f"{self.weight_equity:.1%}"),
            ("Weight of debt", f"{self.weight_debt:.1%}"),
            ("Credit assessment", self.credit_label),
            ("WACC", f"{self.wacc:.2%}"),
        ]


def hamada_unlever(beta_l: float, de: float, tax: float) -> float:
    return beta_l / (1 + (1 - tax) * de)


def hamada_relever(beta_u: float, de: float, tax: float) -> float:
    return beta_u * (1 + (1 - tax) * de)


def compute_wacc(
    data: CompanyData,
    risk_free: float = 0.043,
    erp: float = 0.046,
    country_premium: float = 0.0,
    tax_rate: Optional[float] = None,
    beta_override: Optional[float] = None,
    peer_betas: Optional[list[tuple[float, float]]] = None,  # (beta_l, D/E) per peer
    size_premium: float = 0.0,
) -> WACCResult:
    """Returns a fully documented WACCResult.

    peer_betas, if supplied, triggers bottom-up beta: each peer beta is
    unlevered, averaged, and relevered at the target's own D/E.
    """
    y = data.latest
    notes: list[str] = []

    # Tax rate: use trailing effective, floored/capped to sane marginal band.
    if tax_rate is None:
        eff = [yy.effective_tax_rate for yy in data.years if yy.effective_tax_rate is not None]
        eff = [e for e in eff if 0 <= e <= 0.6]
        tax_rate = sum(eff) / len(eff) if eff else 0.25
        tax_rate = min(max(tax_rate, 0.10), 0.35)
        notes.append(f"Marginal tax rate set to trailing effective ({tax_rate:.1%}).")

    # Capital weights at market value. Debt approximated at book (standard when
    # no market quotes); equity at market cap.
    E = data.market_cap
    D = y.total_debt
    de = D / E if E > 0 else 0.0
    we = E / (E + D) if (E + D) > 0 else 1.0
    wd = 1 - we

    # Beta
    if beta_override is not None:
        beta_used, method = beta_override, "manual"
    elif peer_betas:
        unlev = [hamada_unlever(bl, d, tax_rate) for bl, d in peer_betas]
        beta_u = sum(unlev) / len(unlev)
        beta_used = hamada_relever(beta_u, de, tax_rate)
        method = f"bottom-up, {len(peer_betas)} peers"
        notes.append(f"Bottom-up beta: peers unlevered (avg βu={beta_u:.2f}) then "
                     f"relevered at D/E={de:.2f}.")
    elif data.beta:
        beta_used, method = data.beta, "reported"
    else:
        beta_used, method = 1.0, "default 1.0"
        notes.append("No beta available; defaulted to 1.0.")

    ke = risk_free + beta_used * (erp) + country_premium + size_premium

    # Cost of debt: synthetic spread off interest coverage.
    spread, credit_label = synthetic_spread(y.ebit, y.interest_expense)
    kd_pre = risk_free + spread + country_premium
    kd_after = kd_pre * (1 - tax_rate)

    wacc = we * ke + wd * kd_after

    return WACCResult(
        wacc=wacc, cost_of_equity=ke, cost_of_debt_after_tax=kd_after,
        cost_of_debt_pretax=kd_pre, beta_used=beta_used, risk_free=risk_free,
        erp=erp, country_premium=country_premium, size_premium=size_premium,
        weight_equity=we, weight_debt=wd, tax_rate=tax_rate,
        credit_label=credit_label, beta_method=method, notes=notes,
    )
