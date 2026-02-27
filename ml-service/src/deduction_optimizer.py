"""
Deduction Optimizer — Section 80C / 80D / HRA and beyond
Analyses the user's current deduction utilisation and returns prioritised
suggestions to maximise tax savings under the old regime.

Sections covered:
  80C   — ₹1.5L aggregate limit: PPF, ELSS, LIC, NSC, tuition, home loan principal
  80CCC — Annuity plan premium (part of 80C limit)
  80CCD(1)  — NPS employee contribution (part of 80C limit)
  80CCD(1B) — NPS additional self contribution, ₹50K over-and-above 80C
  80CCD(2)  — Employer NPS contribution — not subject to limits
  80D   — Medical insurance premiums (self/family + parents)
  80DD  — Disability of dependent, ₹75K / ₹1.25L
  80E   — Interest on education loan (unlimited)
  80EEA — Interest on affordable housing loan (₹1.5L additional)
  80G   — Donations (50% / 100%)
  80GG  — Rent paid without HRA (₹60K annual cap)
  80TTA — SB interest ≤ ₹10K (non-senior)
  80TTB — SB/FD interest ≤ ₹50K (senior citizens)
  HRA   — Least-of-three exemption calculator
  LTA   — Leave Travel Allowance (twice in 4-year block)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Section limits
# ---------------------------------------------------------------------------

LIMITS: Dict[str, float] = {
    "80C_aggregate": 150_000,
    "80CCD_1B_nps":   50_000,
    "80D_self":        25_000,   # ₹50K for senior self
    "80D_self_senior": 50_000,
    "80D_parents":     25_000,   # ₹50K for senior parents
    "80D_parents_senior": 50_000,
    "80DD_moderate":   75_000,
    "80DD_severe":    125_000,
    "80E":          math.inf,
    "80EEA":         150_000,
    "80G_50pct":    math.inf,   # capped at 10% of adj GTI in practice
    "80GG":          60_000,
    "80TTA":         10_000,
    "80TTB":         50_000,
}

# 80C sub-instruments and their typical lock-in / features
_80C_INSTRUMENTS = [
    {"name": "PPF",          "max": 150_000, "lock_in": "15 years", "return": "7.1% tax-free", "risk": "None"},
    {"name": "ELSS",         "max": 150_000, "lock_in": "3 years",  "return": "Market-linked (12-15% hist.)", "risk": "Moderate"},
    {"name": "NSC",          "max": 150_000, "lock_in": "5 years",  "return": "7.7% taxable",  "risk": "None"},
    {"name": "Life Insurance Premium", "max": 150_000, "lock_in": "Policy term", "return": "Varies", "risk": "None"},
    {"name": "5-yr Tax Saver FD",     "max": 150_000, "lock_in": "5 years",  "return": "6.5-7.5%",    "risk": "None"},
    {"name": "Home Loan Principal",   "max": 150_000, "lock_in": "N/A (loan EMI)", "return": "N/A", "risk": "None"},
    {"name": "Tuition Fees (children)", "max": 150_000, "lock_in": "N/A", "return": "N/A",         "risk": "None"},
    {"name": "SCSS",         "max": 150_000, "lock_in": "5 years",  "return": "8.2% taxable",  "risk": "None"},
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CurrentDeductions:
    """User's existing investment / payment amounts."""
    ppf: float = 0.0
    elss: float = 0.0
    nsc: float = 0.0
    lic_premium: float = 0.0
    tax_saver_fd: float = 0.0
    home_loan_principal: float = 0.0
    tuition_fees: float = 0.0
    scss: float = 0.0
    other_80c: float = 0.0

    nps_self_80ccd1b: float = 0.0    # additional NPS

    health_insurance_self: float = 0.0
    health_insurance_parents: float = 0.0
    preventive_health_checkup: float = 0.0  # max ₹5K within 80D limit

    education_loan_interest: float = 0.0    # 80E
    housing_loan_interest_80eea: float = 0.0  # 80EEA (affordable housing)
    donations_80g: float = 0.0

    sb_interest: float = 0.0          # 80TTA / 80TTB

    # HRA inputs
    gross_salary: float = 0.0
    basic_salary: float = 0.0         # If 0, approximated as 40% of gross
    hra_received: float = 0.0
    rent_paid_annual: float = 0.0
    metro_city: bool = True

    age: int = 30
    parents_senior: bool = False


@dataclass
class SuggestionItem:
    section: str
    instrument: str
    current_amount: float
    max_eligible: float
    gap: float                 # how much more can be invested
    additional_tax_saving: float
    priority: int              # 1 = highest
    rationale: str


@dataclass
class OptimizerResult:
    current_total_deduction: float
    max_possible_deduction: float
    current_tax_saving: float          # vs no deductions
    max_possible_tax_saving: float
    additional_tax_saving_possible: float
    utilisation_pct: float
    suggestions: List[SuggestionItem]
    hra_breakdown: Dict
    regime_note: str


# ---------------------------------------------------------------------------
# HRA calculator
# ---------------------------------------------------------------------------

def compute_hra_exemption(
    basic_salary: float,
    hra_received: float,
    rent_paid_annual: float,
    metro_city: bool = True,
) -> Dict:
    """
    HRA exemption = min(a, b, c)
      a = Actual HRA received
      b = 50% basic (metro) / 40% basic (non-metro)
      c = Rent paid - 10% of basic salary
    """
    if hra_received <= 0 or rent_paid_annual <= 0:
        return {"exempt": 0.0, "a": 0, "b": 0, "c": 0, "binding": "N/A"}
    a = hra_received
    b = basic_salary * (0.50 if metro_city else 0.40)
    c = max(0, rent_paid_annual - 0.10 * basic_salary)
    exempt = min(a, b, c)
    binding = ["a (actual HRA)", "b (50%/40% basic)", "c (rent - 10% basic)"][
        [a, b, c].index(exempt)
    ]
    return {
        "exempt": round(exempt),
        "a_actual_hra": round(a),
        "b_percent_basic": round(b),
        "c_rent_minus_10pct_basic": round(c),
        "binding_condition": binding,
        "taxable_hra": round(hra_received - exempt),
    }


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

class DeductionOptimizer:
    """
    Analyses current deduction utilisation and generates a prioritised
    action plan to maximise tax savings under the old regime.
    """

    def __init__(self, marginal_tax_rate: float = 0.30):
        """
        Args:
            marginal_tax_rate: The user's marginal slab rate (for saving calc).
                               Add 4% cess: effective saving = rate * 1.04.
        """
        self.effective_rate = marginal_tax_rate * 1.04  # include cess

    def _saving(self, amount: float) -> float:
        """Tax saved on a given additional deduction amount."""
        return round(amount * self.effective_rate)

    def optimize(self, current: CurrentDeductions) -> OptimizerResult:
        suggestions: List[SuggestionItem] = []
        priority = 1

        # Derive basic salary
        basic = current.basic_salary or current.gross_salary * 0.40

        # ── HRA ─────────────────────────────────────────────────────────
        hra_info = compute_hra_exemption(
            basic, current.hra_received, current.rent_paid_annual, current.metro_city
        )

        # ── Section 80C ──────────────────────────────────────────────────
        total_80c = (
            current.ppf + current.elss + current.nsc + current.lic_premium
            + current.tax_saver_fd + current.home_loan_principal
            + current.tuition_fees + current.scss + current.other_80c
        )
        cap_80c = LIMITS["80C_aggregate"]
        gap_80c = max(0, cap_80c - total_80c)

        if gap_80c > 0:
            # Suggest best instrument(s) for the gap
            best = "ELSS" if gap_80c >= 500 else "PPF"
            suggestions.append(SuggestionItem(
                section="80C",
                instrument=best,
                current_amount=round(total_80c),
                max_eligible=cap_80c,
                gap=round(gap_80c),
                additional_tax_saving=self._saving(gap_80c),
                priority=priority,
                rationale=(
                    f"₹{gap_80c/1000:.0f}K of the ₹1.5L 80C limit is unused. "
                    f"Investing in {best} saves ₹{self._saving(gap_80c)/1000:.1f}K in tax. "
                    f"ELSS offers lowest lock-in (3 yrs) and market-linked returns; "
                    f"PPF is risk-free with 7.1% tax-free interest."
                ),
            ))
            priority += 1

        # ── Section 80CCD(1B) — NPS ──────────────────────────────────────
        cap_nps = LIMITS["80CCD_1B_nps"]
        gap_nps = max(0, cap_nps - current.nps_self_80ccd1b)
        if gap_nps > 0:
            suggestions.append(SuggestionItem(
                section="80CCD(1B)",
                instrument="NPS (Tier-1)",
                current_amount=round(current.nps_self_80ccd1b),
                max_eligible=cap_nps,
                gap=round(gap_nps),
                additional_tax_saving=self._saving(gap_nps),
                priority=priority,
                rationale=(
                    f"Additional NPS contribution of ₹{gap_nps/1000:.0f}K saves "
                    f"₹{self._saving(gap_nps)/1000:.1f}K — over and above the ₹1.5L 80C limit. "
                    "Partial withdrawal allowed after 3 years; 60% lump-sum at retirement is tax-free."
                ),
            ))
            priority += 1

        # ── Section 80D — Health Insurance ───────────────────────────────
        d_self_cap = LIMITS["80D_self_senior"] if current.age >= 60 else LIMITS["80D_self"]
        d_par_cap  = LIMITS["80D_parents_senior"] if current.parents_senior else LIMITS["80D_parents"]
        phc_within_self = min(current.preventive_health_checkup, 5_000)

        self_paid = current.health_insurance_self + phc_within_self
        gap_self = max(0, d_self_cap - self_paid)
        gap_par  = max(0, d_par_cap  - current.health_insurance_parents)

        if gap_self > 0:
            suggestions.append(SuggestionItem(
                section="80D (self/family)",
                instrument="Health Insurance Premium",
                current_amount=round(self_paid),
                max_eligible=d_self_cap,
                gap=round(gap_self),
                additional_tax_saving=self._saving(gap_self),
                priority=priority,
                rationale=(
                    f"You can claim ₹{gap_self/1000:.0f}K more under 80D for self/family "
                    f"health insurance (limit ₹{d_self_cap/1000:.0f}K). "
                    "Preventive health check-up up to ₹5K counts within this limit."
                ),
            ))
            priority += 1

        if gap_par > 0:
            suggestions.append(SuggestionItem(
                section="80D (parents)",
                instrument="Parents Health Insurance Premium",
                current_amount=round(current.health_insurance_parents),
                max_eligible=d_par_cap,
                gap=round(gap_par),
                additional_tax_saving=self._saving(gap_par),
                priority=priority,
                rationale=(
                    f"Parents' health insurance premium up to ₹{d_par_cap/1000:.0f}K "
                    f"({'senior' if current.parents_senior else 'non-senior'} parents). "
                    f"Unused capacity: ₹{gap_par/1000:.0f}K → saves ₹{self._saving(gap_par)/1000:.1f}K."
                ),
            ))
            priority += 1

        # ── Section 80E — Education Loan ─────────────────────────────────
        if current.education_loan_interest > 0:
            suggestions.append(SuggestionItem(
                section="80E",
                instrument="Education Loan Interest",
                current_amount=round(current.education_loan_interest),
                max_eligible=math.inf,
                gap=0,
                additional_tax_saving=self._saving(current.education_loan_interest),
                priority=99,
                rationale="Interest on education loan is fully deductible (no upper limit) for 8 years.",
            ))

        # ── Section 80TTA / 80TTB ────────────────────────────────────────
        if current.age >= 60:
            gap_ttb = max(0, LIMITS["80TTB"] - current.sb_interest)
            if gap_ttb == 0 and current.sb_interest > 0:
                suggestions.append(SuggestionItem(
                    section="80TTB",
                    instrument="Senior Citizen Bank Interest Deduction",
                    current_amount=round(current.sb_interest),
                    max_eligible=LIMITS["80TTB"],
                    gap=0,
                    additional_tax_saving=self._saving(min(current.sb_interest, LIMITS["80TTB"])),
                    priority=99,
                    rationale="Up to ₹50K interest from bank savings/FD/RD is deductible for senior citizens.",
                ))
        else:
            gap_tta = max(0, LIMITS["80TTA"] - current.sb_interest)
            if current.sb_interest > 0 or gap_tta == 0:
                suggestions.append(SuggestionItem(
                    section="80TTA",
                    instrument="Savings Bank Interest Deduction",
                    current_amount=round(current.sb_interest),
                    max_eligible=LIMITS["80TTA"],
                    gap=round(gap_tta),
                    additional_tax_saving=self._saving(min(current.sb_interest, LIMITS["80TTA"])),
                    priority=99,
                    rationale="Up to ₹10K savings bank interest is deductible u/s 80TTA.",
                ))

        # ── Totals ───────────────────────────────────────────────────────
        current_total = (
            min(total_80c, cap_80c)
            + min(current.nps_self_80ccd1b, cap_nps)
            + min(self_paid, d_self_cap)
            + min(current.health_insurance_parents, d_par_cap)
            + current.education_loan_interest
            + hra_info["exempt"]
            + (min(current.sb_interest, LIMITS["80TTB"]) if current.age >= 60
               else min(current.sb_interest, LIMITS["80TTA"]))
        )
        max_possible = (
            cap_80c + cap_nps + d_self_cap + d_par_cap
            + current.education_loan_interest + hra_info["exempt"]
            + (LIMITS["80TTB"] if current.age >= 60 else LIMITS["80TTA"])
        )
        additional_possible = sum(s.additional_tax_saving for s in suggestions if s.gap > 0)

        return OptimizerResult(
            current_total_deduction=round(current_total),
            max_possible_deduction=round(max_possible),
            current_tax_saving=self._saving(current_total),
            max_possible_tax_saving=self._saving(max_possible),
            additional_tax_saving_possible=round(additional_possible),
            utilisation_pct=round(current_total / max_possible * 100, 1) if max_possible > 0 else 0.0,
            suggestions=sorted(suggestions, key=lambda s: s.priority),
            hra_breakdown=hra_info,
            regime_note=(
                "These deductions apply under the OLD TAX REGIME only. "
                "Compare total tax under both regimes using the Tax Calculator before choosing."
            ),
        )


# ---------------------------------------------------------------------------
# Convenience serialiser
# ---------------------------------------------------------------------------

def optimize_deductions(params: Dict) -> Dict:
    """JSON-serialisable wrapper for Flask endpoint."""
    cd = CurrentDeductions(**{k: v for k, v in params.items() if hasattr(CurrentDeductions, k)})
    marginal = params.get("marginal_tax_rate", 0.30)
    optimizer = DeductionOptimizer(marginal_tax_rate=marginal)
    result = optimizer.optimize(cd)
    return {
        "current_total_deduction": result.current_total_deduction,
        "max_possible_deduction": result.max_possible_deduction,
        "current_tax_saving": result.current_tax_saving,
        "max_possible_tax_saving": result.max_possible_tax_saving,
        "additional_tax_saving_possible": result.additional_tax_saving_possible,
        "utilisation_pct": result.utilisation_pct,
        "hra_breakdown": result.hra_breakdown,
        "regime_note": result.regime_note,
        "suggestions": [
            {
                "section": s.section,
                "instrument": s.instrument,
                "current_amount": s.current_amount,
                "max_eligible": s.max_eligible if s.max_eligible != math.inf else None,
                "gap": s.gap,
                "additional_tax_saving": s.additional_tax_saving,
                "priority": s.priority,
                "rationale": s.rationale,
            }
            for s in result.suggestions
        ],
    }
