"""
Indian Income Tax Calculator — AY 2025-26 (FY 2024-25)
Supports ITR-1 (salaried / single house property / other sources) and
ITR-2 (capital gains, multiple house properties, foreign income).

Key rules encoded:
  - Old regime: slab rates with all deductions/exemptions
  - New regime (default post-Budget 2023): revised slabs, limited deductions,
    standard deduction ₹75,000 restored from FY 2024-25
  - Surcharge (10%/15%/25%/37%) and Health & Education Cess 4%
  - Rebate u/s 87A: ₹25,000 for new regime (income ≤ ₹7L),
                     ₹12,500 for old regime (income ≤ ₹5L)
  - AMT (Alternative Minimum Tax) for partnership firms — not applicable ITR-1/2
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Tax slabs — FY 2024-25 / AY 2025-26
# ---------------------------------------------------------------------------

# Old regime slabs (without cess/surcharge) — same as prior years
OLD_REGIME_SLABS: List[Tuple[float, float, float]] = [
    # (lower, upper, rate)
    (0,        250_000,   0.00),
    (250_000,  500_000,   0.05),
    (500_000,  1_000_000, 0.20),
    (1_000_000, math.inf, 0.30),
]

# Senior citizen (60–80) old regime
OLD_REGIME_SENIOR_SLABS: List[Tuple[float, float, float]] = [
    (0,        300_000,   0.00),
    (300_000,  500_000,   0.05),
    (500_000,  1_000_000, 0.20),
    (1_000_000, math.inf, 0.30),
]

# Super senior citizen (80+) old regime
OLD_REGIME_SUPER_SENIOR_SLABS: List[Tuple[float, float, float]] = [
    (0,        500_000,   0.00),
    (500_000,  1_000_000, 0.20),
    (1_000_000, math.inf, 0.30),
]

# New regime slabs — revised w.e.f. FY 2023-24 (Budget 2023)
NEW_REGIME_SLABS: List[Tuple[float, float, float]] = [
    (0,          300_000,   0.00),
    (300_000,    700_000,   0.05),
    (700_000,  1_000_000,   0.10),
    (1_000_000, 1_200_000,  0.15),
    (1_200_000, 1_500_000,  0.20),
    (1_500_000,  math.inf,  0.30),
]

# Surcharge brackets (same for both regimes)
SURCHARGE_BRACKETS: List[Tuple[float, float, float]] = [
    (0,          5_000_000,   0.00),
    (5_000_000,  10_000_000,  0.10),
    (10_000_000, 20_000_000,  0.15),
    (20_000_000, 50_000_000,  0.25),
    (50_000_000,  math.inf,   0.37),
]
# Note: Surcharge on LTCG and STCG on equity capped at 15%

CESS_RATE = 0.04  # Health & Education Cess

# Standard deduction
STD_DEDUCTION_NEW_REGIME = 75_000    # restored from FY 2024-25
STD_DEDUCTION_OLD_REGIME = 50_000    # unchanged


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IncomeDetails:
    """All income head inputs for ITR-1 or ITR-2."""
    # Salary / Pension
    gross_salary: float = 0.0
    hra_received: float = 0.0
    lta_received: float = 0.0
    other_allowances: float = 0.0          # taxable portion

    # House property
    annual_rental_income: float = 0.0
    home_loan_interest: float = 0.0        # Section 24(b), max ₹2L for self-occupied
    self_occupied: bool = True

    # Other sources
    savings_bank_interest: float = 0.0
    fd_interest: float = 0.0
    dividend_income: float = 0.0
    other_income: float = 0.0

    # Capital gains (ITR-2)
    stcg_111a: float = 0.0    # STCG on equity/equity MF @ 20% (post Jul 2024)
    stcg_other: float = 0.0   # Other STCG @ slab rate
    ltcg_112a: float = 0.0    # LTCG on equity/equity MF @ 12.5% (post Jul 2024), exempt up to ₹1.25L
    ltcg_other: float = 0.0   # Other LTCG @ 20% with indexation

    # Age category for slab selection
    age: int = 30

    # Regime preference
    regime: str = "new"   # "new" | "old"


@dataclass
class DeductionDetails:
    """Section VI-A deductions applicable under old regime."""
    sec_80c: float = 0.0       # Max ₹1.5L (PPF, ELSS, LIC, home loan principal, tuition)
    sec_80ccd1b: float = 0.0   # NPS self contribution, max ₹50K additional
    sec_80d_self: float = 0.0  # Medical insurance — self/family, max ₹25K (₹50K if senior)
    sec_80d_parents: float = 0.0  # Medical insurance — parents, max ₹25K (₹50K if senior parents)
    sec_80e: float = 0.0       # Interest on education loan (no limit)
    sec_80g: float = 0.0       # Donations (50%/100% as applicable, max 10% of adj GTI)
    sec_80tta: float = 0.0     # Savings bank interest, max ₹10K (not available if senior)
    sec_80ttb: float = 0.0     # Senior citizen bank interest, max ₹50K (replaces 80TTA)
    hra_exempt: float = 0.0    # Calculated separately via HRA calculator
    lta_exempt: float = 0.0    # Leave Travel Allowance exemption
    home_loan_principal: float = 0.0  # Part of 80C


@dataclass
class TaxBreakdown:
    """Complete tax computation output."""
    regime: str
    gross_total_income: float
    total_deductions: float
    taxable_income: float

    # Capital gains tax (computed separately at special rates)
    stcg_111a_tax: float = 0.0   # @ 20%
    stcg_other_tax: float = 0.0  # @ slab
    ltcg_112a_tax: float = 0.0   # @ 12.5%
    ltcg_other_tax: float = 0.0  # @ 20%

    base_tax: float = 0.0        # Tax on regular income at slab rates
    total_tax_before_cess: float = 0.0
    surcharge: float = 0.0
    rebate_87a: float = 0.0
    cess: float = 0.0
    total_tax: float = 0.0       # Final payable (after rebate, surcharge, cess)
    effective_rate: float = 0.0  # % of gross total income
    marginal_rate: float = 0.0

    slab_breakdown: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core computation helpers
# ---------------------------------------------------------------------------

def _compute_slab_tax(income: float, slabs: List[Tuple[float, float, float]]) -> Tuple[float, List[Dict], float]:
    """
    Compute tax from slab table. Returns (tax, breakdown, marginal_rate).
    """
    tax = 0.0
    breakdown = []
    marginal = 0.0
    for lower, upper, rate in slabs:
        if income <= lower:
            break
        taxable = min(income, upper) - lower
        slab_tax = taxable * rate
        tax += slab_tax
        if rate > 0 or taxable > 0:
            breakdown.append({
                "slab": f"₹{lower/100000:.1f}L – {'₹'+str(upper/100000)+'L' if upper != math.inf else 'above'}",
                "taxable_amount": round(taxable),
                "rate_pct": rate * 100,
                "tax": round(slab_tax),
            })
        if taxable > 0:
            marginal = rate
    return round(tax), breakdown, marginal


def _surcharge(income: float, base_tax: float) -> float:
    rate = 0.0
    for lower, upper, r in SURCHARGE_BRACKETS:
        if income > lower:
            rate = r
    return round(base_tax * rate)


def _rebate_87a(taxable_income: float, base_tax: float, regime: str) -> float:
    if regime == "new" and taxable_income <= 700_000:
        return min(base_tax, 25_000)
    if regime == "old" and taxable_income <= 500_000:
        return min(base_tax, 12_500)
    return 0.0


def _select_slabs(age: int, regime: str) -> List[Tuple[float, float, float]]:
    if regime == "new":
        return NEW_REGIME_SLABS
    if age >= 80:
        return OLD_REGIME_SUPER_SENIOR_SLABS
    if age >= 60:
        return OLD_REGIME_SENIOR_SLABS
    return OLD_REGIME_SLABS


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------

class IndiaTaxCalculator:
    """
    ITR-1 and ITR-2 income tax calculator for FY 2024-25 / AY 2025-26.

    Usage:
        calc = IndiaTaxCalculator()
        result = calc.compute(income, deductions)
    """

    def _house_property_income(self, inc: IncomeDetails) -> float:
        """Net annual value of house property after 30% standard deduction + loan interest."""
        if inc.annual_rental_income <= 0:
            # Self-occupied: loss up to ₹2L on home loan interest claimable in old regime
            return -min(inc.home_loan_interest, 200_000)
        nav = inc.annual_rental_income - inc.annual_rental_income * 0.30  # 30% std deduction on rental
        nav -= inc.home_loan_interest  # no cap on let-out property
        return nav

    def _hra_exemption(self, inc: IncomeDetails) -> float:
        """
        HRA exemption = min of:
          a) Actual HRA received
          b) 50% of basic (metro) / 40% of basic (non-metro) — assume metro
          c) Rent paid - 10% of basic

        We approximate basic as 40% of gross salary when not provided separately.
        """
        if inc.hra_received <= 0:
            return 0.0
        basic = inc.gross_salary * 0.40  # approximation
        return min(inc.hra_received, basic * 0.50)

    def _cap_deductions(self, ded: DeductionDetails, age: int) -> float:
        """Apply statutory caps and return total deduction amount."""
        total = 0.0
        # 80C cap ₹1.5L
        total += min(ded.sec_80c + ded.home_loan_principal, 150_000)
        # 80CCD(1B) NPS cap ₹50K
        total += min(ded.sec_80ccd1b, 50_000)
        # 80D
        self_cap = 50_000 if age >= 60 else 25_000
        parent_cap = 50_000  # assume parents senior
        total += min(ded.sec_80d_self, self_cap) + min(ded.sec_80d_parents, parent_cap)
        # 80E — no cap
        total += ded.sec_80e
        # 80G — approximate 50% of donated amount (simplified)
        total += ded.sec_80g * 0.50
        # 80TTA / 80TTB
        if age >= 60:
            total += min(ded.sec_80ttb, 50_000)
        else:
            total += min(ded.sec_80tta, 10_000)
        # HRA + LTA
        total += ded.hra_exempt + ded.lta_exempt
        return total

    def compute(
        self,
        income: IncomeDetails,
        deductions: Optional[DeductionDetails] = None,
        compare_both: bool = False,
    ) -> TaxBreakdown | Dict[str, TaxBreakdown]:
        """
        Compute income tax for the specified (or both) regime(s).

        Args:
            income:      IncomeDetails with all income head values
            deductions:  DeductionDetails (ignored in new regime except std ded)
            compare_both: if True, returns dict {"old": ..., "new": ...}
        """
        if compare_both:
            old = self._compute_single(income, deductions, "old")
            new = self._compute_single(income, deductions, "new")
            return {"old": old, "new": new}
        return self._compute_single(income, deductions, income.regime)

    def _compute_single(
        self,
        income: IncomeDetails,
        deductions: Optional[DeductionDetails],
        regime: str,
    ) -> TaxBreakdown:
        ded = deductions or DeductionDetails()

        # ── Gross Total Income ──────────────────────────────────────────
        # Salary income
        std_ded = STD_DEDUCTION_NEW_REGIME if regime == "new" else STD_DEDUCTION_OLD_REGIME
        salary_income = max(0, income.gross_salary - std_ded)

        # HRA exemption (old regime only)
        hra_exempt = self._hra_exemption(income) if regime == "old" else 0.0

        # House property
        hp_income = self._house_property_income(income) if regime == "old" else 0.0
        hp_income = max(hp_income, -200_000)  # cap loss at ₹2L

        # Other sources
        other = (
            income.savings_bank_interest
            + income.fd_interest
            + income.dividend_income
            + income.other_income
        )

        regular_income = salary_income - hra_exempt + hp_income + other

        # ── Deductions (old regime only) ─────────────────────────────────
        vi_a_deductions = 0.0
        if regime == "old":
            ded.hra_exempt = hra_exempt
            vi_a_deductions = self._cap_deductions(ded, income.age)

        taxable_income = max(0, regular_income - vi_a_deductions)

        # ── Capital gains (special rates, not added to regular slab income) ─
        ltcg_exempt = 125_000  # ₹1.25L exemption on LTCG u/s 112A
        ltcg_112a_taxable = max(0, income.ltcg_112a - ltcg_exempt)

        stcg_111a_tax = round(income.stcg_111a * 0.20)       # 20% post Jul 23 2024
        ltcg_112a_tax = round(ltcg_112a_taxable * 0.125)     # 12.5% post Jul 23 2024
        stcg_other_tax = 0.0  # computed in slab below with combined income
        ltcg_other_tax = round(income.ltcg_other * 0.20)     # 20% with indexation

        # Other STCG added to slab income
        total_slab_income = taxable_income + income.stcg_other

        # ── Slab tax ─────────────────────────────────────────────────────
        slabs = _select_slabs(income.age, regime)
        base_tax, slab_breakdown, marginal = _compute_slab_tax(total_slab_income, slabs)

        # ── Capital gains tax ─────────────────────────────────────────────
        cg_tax = stcg_111a_tax + ltcg_112a_tax + ltcg_other_tax

        total_before_rebate = base_tax + cg_tax

        # ── Rebate 87A (on regular income tax only, not CG tax) ───────────
        rebate = _rebate_87a(taxable_income, base_tax, regime)
        tax_after_rebate = max(0, total_before_rebate - rebate)

        # ── Surcharge (on total income including CG) ──────────────────────
        total_income_for_surcharge = (
            taxable_income
            + income.stcg_111a + income.stcg_other
            + ltcg_112a_taxable + income.ltcg_other
        )
        surcharge = _surcharge(total_income_for_surcharge, tax_after_rebate)

        # ── Cess ─────────────────────────────────────────────────────────
        cess = round((tax_after_rebate + surcharge) * CESS_RATE)
        total_tax = tax_after_rebate + surcharge + cess

        gti = income.gross_salary + income.annual_rental_income + other
        effective_rate = round(total_tax / gti * 100, 2) if gti > 0 else 0.0

        return TaxBreakdown(
            regime=regime,
            gross_total_income=round(gti),
            total_deductions=round(vi_a_deductions + std_ded),
            taxable_income=round(taxable_income),
            stcg_111a_tax=stcg_111a_tax,
            stcg_other_tax=round(stcg_other_tax),
            ltcg_112a_tax=ltcg_112a_tax,
            ltcg_other_tax=ltcg_other_tax,
            base_tax=base_tax,
            total_tax_before_cess=tax_after_rebate + surcharge,
            surcharge=surcharge,
            rebate_87a=round(rebate),
            cess=cess,
            total_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=round(marginal * 100, 1),
            slab_breakdown=slab_breakdown,
        )


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

def compute_india_tax(
    gross_salary: float,
    age: int = 30,
    regime: str = "both",
    **income_kwargs,
) -> Dict:
    """
    Quick-compute helper for the Flask /india-tax endpoint.

    regime: "new" | "old" | "both"
    Returns JSON-serialisable dict.
    """
    calc = IndiaTaxCalculator()
    income = IncomeDetails(gross_salary=gross_salary, age=age, regime=regime if regime != "both" else "new", **income_kwargs)
    ded = DeductionDetails()

    if regime == "both":
        results = calc.compute(income, ded, compare_both=True)
        return {
            "old": _breakdown_to_dict(results["old"]),
            "new": _breakdown_to_dict(results["new"]),
            "recommended": "new" if results["new"].total_tax <= results["old"].total_tax else "old",
            "savings": abs(results["old"].total_tax - results["new"].total_tax),
        }
    result = calc.compute(income, ded)
    return _breakdown_to_dict(result)


def _breakdown_to_dict(b: TaxBreakdown) -> Dict:
    return {
        "regime": b.regime,
        "gross_total_income": b.gross_total_income,
        "total_deductions": b.total_deductions,
        "taxable_income": b.taxable_income,
        "base_tax": b.base_tax,
        "stcg_111a_tax": b.stcg_111a_tax,
        "ltcg_112a_tax": b.ltcg_112a_tax,
        "ltcg_other_tax": b.ltcg_other_tax,
        "rebate_87a": b.rebate_87a,
        "surcharge": b.surcharge,
        "cess": b.cess,
        "total_tax": b.total_tax,
        "effective_rate_pct": b.effective_rate,
        "marginal_rate_pct": b.marginal_rate,
        "slab_breakdown": b.slab_breakdown,
    }
