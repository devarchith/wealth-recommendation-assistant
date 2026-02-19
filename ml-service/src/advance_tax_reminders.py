"""
Advance Tax Reminder System — India FY 2024-25
Quarterly installment schedule per Sec 208–210 of the Income Tax Act.
Computes estimated liability, installment amounts, and interest under
Sections 234B (default in payment) and 234C (deferment of installment).

Who must pay advance tax:
  • Tax liability (after TDS) exceeds ₹10,000 in a financial year.
  • Salaried individuals: TDS on salary by employer usually covers this,
    but side income (freelancing, capital gains, rent) triggers obligation.
  • Presumptive scheme (Sec 44AD/44ADA): single installment by March 15.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import math


# ---------------------------------------------------------------------------
# Installment schedule — FY 2024-25 deadlines (Sec 211)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InstallmentDeadline:
    quarter:          str       # Q1 / Q2 / Q3 / Q4
    due_date:         date
    cumulative_pct:   float     # % of total liability due by this date
    description:      str


ADVANCE_TAX_SCHEDULE_2024_25: Tuple[InstallmentDeadline, ...] = (
    InstallmentDeadline("Q1", date(2024, 6, 15), 0.15,
                        "15% of estimated annual tax due by June 15"),
    InstallmentDeadline("Q2", date(2024, 9, 15), 0.45,
                        "45% of estimated annual tax (cumulative) due by Sep 15"),
    InstallmentDeadline("Q3", date(2024, 12, 15), 0.75,
                        "75% of estimated annual tax (cumulative) due by Dec 15"),
    InstallmentDeadline("Q4", date(2025, 3, 15), 1.00,
                        "100% of estimated annual tax (cumulative) due by Mar 15"),
)

# Presumptive scheme — single installment
PRESUMPTIVE_DEADLINE = InstallmentDeadline(
    "Q4", date(2025, 3, 15), 1.00,
    "100% advance tax by March 15 (Sec 44AD/44ADA presumptive taxpayers)"
)

# Interest rates
INTEREST_RATE_234B  = 0.01   # 1% per month (simple) for default in payment
INTEREST_RATE_234C  = 0.01   # 1% per month (simple) for deferment of installment


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IncomeEstimate:
    """Estimated income components for the financial year."""
    salary:           float = 0.0
    house_property:   float = 0.0   # Net annual value (after 30% standard deduction)
    business_profit:  float = 0.0
    capital_gains:    float = 0.0
    other_income:     float = 0.0
    deductions_80c:   float = 0.0
    deductions_80d:   float = 0.0
    other_deductions: float = 0.0
    tds_deducted:     float = 0.0   # TDS already deducted by employer/banks
    regime:           str  = "new"  # "new" | "old"

    @property
    def gross_total_income(self) -> float:
        return (self.salary + self.house_property + self.business_profit
                + self.capital_gains + self.other_income)

    @property
    def total_deductions(self) -> float:
        if self.regime == "new":
            return 0.0   # No Chapter VI-A in new regime (except 80CCD(2))
        return self.deductions_80c + self.deductions_80d + self.other_deductions

    @property
    def taxable_income(self) -> float:
        return max(0.0, self.gross_total_income - self.total_deductions)


@dataclass
class InstallmentRecord:
    """One quarterly installment."""
    quarter:           str
    due_date:          date
    cumulative_pct:    float
    cumulative_amount: float    # Total liability due cumulatively
    installment_due:   float    # Amount due this installment (incremental)
    amount_paid:       float    # Amount actually paid
    payment_date:      Optional[date]
    shortfall:         float
    excess:            float
    interest_234c:     float    # Interest for this installment shortfall
    is_overdue:        bool
    days_to_due:       int      # Negative if overdue


@dataclass
class Interest234B:
    """Interest for default/short payment of advance tax (Sec 234B)."""
    applicable:           bool
    outstanding_tax:      float    # Tax liability - TDS - advance_tax_paid
    months_outstanding:   int
    interest_amount:      float
    explanation:          str


@dataclass
class Interest234C:
    """Interest for deferment of installment (Sec 234C)."""
    total_interest: float
    per_quarter:    List[Dict]


@dataclass
class AdvanceTaxResult:
    """Complete advance tax analysis output."""
    financial_year:       str
    estimated_tax:        float
    tds_credit:           float
    net_tax_after_tds:    float
    advance_tax_paid:     float
    balance_tax:          float
    is_advance_tax_required: bool
    installments:         List[InstallmentRecord]
    interest_234b:        Interest234B
    interest_234c:        Interest234C
    total_interest:       float
    self_assessment_tax:  float
    suggestions:          List[str]
    reminders:            List[Dict]   # Upcoming / overdue reminders


# ---------------------------------------------------------------------------
# Tax computation helpers (simplified slab rates)
# ---------------------------------------------------------------------------

_NEW_SLABS = [
    (300_000,  0.00),
    (700_000,  0.05),
    (1_000_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]

_OLD_SLABS = [
    (250_000,  0.00),
    (500_000,  0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]


def _compute_basic_tax(taxable_income: float, regime: str) -> float:
    slabs = _NEW_SLABS if regime == "new" else _OLD_SLABS
    prev = 0.0
    tax  = 0.0
    for threshold, rate in slabs:
        if taxable_income <= prev:
            break
        taxable_in_slab = min(taxable_income, threshold) - prev
        tax += taxable_in_slab * rate
        prev = threshold
    # Rebate 87A
    if taxable_income <= 700_000 and regime == "new":
        tax = max(0.0, tax - 25_000)
    elif taxable_income <= 500_000 and regime == "old":
        tax = max(0.0, tax - 12_500)
    # 4% cess
    return round(tax * 1.04, 2)


# ---------------------------------------------------------------------------
# Advance Tax Reminder Engine
# ---------------------------------------------------------------------------

class AdvanceTaxReminder:
    """
    Computes advance tax installment schedule, tracks payments,
    and calculates interest under Sections 234B and 234C.

    Usage:
        engine = AdvanceTaxReminder(financial_year="2024-25")
        engine.set_income(IncomeEstimate(salary=800_000, tds_deducted=65_000))
        engine.record_payment("Q1", 8_000, date(2024, 6, 10))
        result = engine.compute()
    """

    def __init__(
        self,
        financial_year: str = "2024-25",
        presumptive:    bool = False,
        today:          Optional[date] = None,
    ):
        self.financial_year = financial_year
        self.presumptive    = presumptive
        self.today          = today or date.today()
        self._income:       Optional[IncomeEstimate] = None
        self._payments:     Dict[str, Tuple[float, Optional[date]]] = {}
        self._estimated_tax: Optional[float] = None

    def set_income(self, income: IncomeEstimate) -> None:
        self._income = income

    def set_estimated_tax(self, tax: float) -> None:
        """Override auto-computed tax (e.g. when capital gains are complex)."""
        self._estimated_tax = tax

    def record_payment(
        self,
        quarter: str,
        amount: float,
        payment_date: Optional[date] = None,
    ) -> None:
        """Record an advance tax payment for a quarter."""
        self._payments[quarter] = (amount, payment_date)

    def compute(self) -> AdvanceTaxResult:
        # Resolve estimated tax
        if self._estimated_tax is not None:
            estimated_tax = self._estimated_tax
        elif self._income is not None:
            estimated_tax = _compute_basic_tax(
                self._income.taxable_income, self._income.regime
            )
        else:
            estimated_tax = 0.0

        tds = self._income.tds_deducted if self._income else 0.0
        net_tax = max(0.0, estimated_tax - tds)

        # Advance tax required only if net > ₹10,000
        required = net_tax > 10_000

        schedule = PRESUMPTIVE_DEADLINE if self.presumptive else ADVANCE_TAX_SCHEDULE_2024_25

        installments: List[InstallmentRecord] = []
        total_paid = 0.0

        prev_cumulative = 0.0
        i234c_quarters: List[Dict] = []

        for inst in (schedule if isinstance(schedule, tuple) else (schedule,)):
            cumulative_amount = round(net_tax * inst.cumulative_pct, 2)
            installment_due   = round(cumulative_amount - prev_cumulative, 2)
            prev_cumulative   = cumulative_amount

            paid_amt, paid_date = self._payments.get(inst.quarter, (0.0, None))
            total_paid_so_far = sum(v[0] for k, v in self._payments.items()
                                    if k <= inst.quarter)

            shortfall = max(0.0, cumulative_amount - total_paid_so_far)
            excess    = max(0.0, total_paid_so_far - cumulative_amount)
            is_overdue = self.today > inst.due_date

            # 234C interest: 1% per month for 3 months on shortfall
            # (no 234C if shortfall < 10% of cumulative)
            interest_234c = 0.0
            if required and shortfall > 0 and shortfall > 0.10 * cumulative_amount:
                months = 3  # Fixed 3-month interest per Sec 234C
                interest_234c = round(shortfall * INTEREST_RATE_234C * months, 2)
            i234c_quarters.append({
                "quarter": inst.quarter,
                "due_date": inst.due_date.isoformat(),
                "shortfall": shortfall,
                "interest_234c": interest_234c,
            })

            installments.append(InstallmentRecord(
                quarter           = inst.quarter,
                due_date          = inst.due_date,
                cumulative_pct    = inst.cumulative_pct,
                cumulative_amount = cumulative_amount,
                installment_due   = installment_due,
                amount_paid       = paid_amt,
                payment_date      = paid_date,
                shortfall         = shortfall,
                excess            = excess,
                interest_234c     = interest_234c,
                is_overdue        = is_overdue,
                days_to_due       = (inst.due_date - self.today).days,
            ))

        total_paid = sum(v[0] for v in self._payments.values())
        balance    = max(0.0, net_tax - total_paid)

        # 234C total
        total_234c = sum(q["interest_234c"] for q in i234c_quarters)
        interest_234c_obj = Interest234C(
            total_interest = total_234c,
            per_quarter    = i234c_quarters,
        )

        # 234B: if advance tax paid < 90% of assessed tax by March 31
        paid_by_mar31 = total_paid
        threshold_90  = 0.90 * net_tax
        i234b_applicable = required and paid_by_mar31 < threshold_90
        i234b_outstanding = max(0.0, net_tax - paid_by_mar31) if i234b_applicable else 0.0
        # Months from April 1 of next FY to date of filing (approx 4 months to July 31)
        i234b_months = max(1, (self.today - date(2025, 4, 1)).days // 30 + 1) if self.today > date(2025, 4, 1) else 0
        i234b_amount = round(i234b_outstanding * INTEREST_RATE_234B * i234b_months, 2) if i234b_applicable else 0.0

        interest_234b = Interest234B(
            applicable         = i234b_applicable,
            outstanding_tax    = i234b_outstanding,
            months_outstanding = i234b_months,
            interest_amount    = i234b_amount,
            explanation        = (
                f"Interest @1%/month on ₹{i234b_outstanding:,.0f} outstanding for "
                f"{i234b_months} month(s)." if i234b_applicable else
                "No 234B interest — advance tax paid ≥90% of assessed tax."
            ),
        )

        total_interest = total_234c + i234b_amount
        sat = round(balance + total_interest, 2)  # Self-assessment tax

        suggestions = self._generate_suggestions(
            required, net_tax, total_paid, balance,
            total_234c, i234b_amount, installments
        )
        reminders = self._build_reminders(installments)

        return AdvanceTaxResult(
            financial_year          = self.financial_year,
            estimated_tax           = estimated_tax,
            tds_credit              = tds,
            net_tax_after_tds       = net_tax,
            advance_tax_paid        = total_paid,
            balance_tax             = balance,
            is_advance_tax_required = required,
            installments            = installments,
            interest_234b           = interest_234b,
            interest_234c           = interest_234c_obj,
            total_interest          = total_interest,
            self_assessment_tax     = sat,
            suggestions             = suggestions,
            reminders               = reminders,
        )

    # ------------------------------------------------------------------
    # Suggestions & reminders
    # ------------------------------------------------------------------

    def _generate_suggestions(
        self,
        required: bool,
        net_tax: float,
        paid: float,
        balance: float,
        i234c: float,
        i234b: float,
        installments: List[InstallmentRecord],
    ) -> List[str]:
        suggestions = []
        if not required:
            suggestions.append(
                f"Your net tax liability after TDS (₹{net_tax:,.0f}) is ≤₹10,000 — "
                f"advance tax payment is NOT required. Pay any balance as self-assessment tax "
                f"before filing ITR."
            )
            return suggestions

        if balance > 0:
            suggestions.append(
                f"Pay ₹{balance:,.0f} as self-assessment tax (Challan 280, Code 300) "
                f"before filing ITR to avoid interest under Sec 234B."
            )
        if i234c > 0:
            suggestions.append(
                f"You incurred ₹{i234c:,.0f} in 234C interest due to installment shortfalls. "
                f"Set quarterly reminders to avoid this next year."
            )
        if i234b > 0:
            suggestions.append(
                f"₹{i234b:,.0f} in 234B interest applicable for default in advance tax. "
                f"Pay outstanding tax immediately to stop interest accumulation."
            )

        upcoming = [inst for inst in installments
                    if not inst.is_overdue and inst.days_to_due <= 15 and inst.installment_due > 0]
        for inst in upcoming:
            suggestions.append(
                f"URGENT: {inst.quarter} advance tax of ₹{inst.installment_due:,.0f} "
                f"due in {inst.days_to_due} day(s) ({inst.due_date.strftime('%d %b %Y')})."
            )

        suggestions.append(
            "Pay via Challan 280 on the Income Tax e-filing portal (challan type: 100 for advance tax)."
        )
        return suggestions

    def _build_reminders(self, installments: List[InstallmentRecord]) -> List[Dict]:
        reminders = []
        for inst in installments:
            status = "overdue" if inst.is_overdue else (
                "due_soon" if inst.days_to_due <= 15 else "upcoming"
            )
            reminders.append({
                "quarter":          inst.quarter,
                "due_date":         inst.due_date.isoformat(),
                "days_to_due":      inst.days_to_due,
                "amount_due":       inst.installment_due,
                "cumulative_due":   inst.cumulative_amount,
                "amount_paid":      inst.amount_paid,
                "shortfall":        inst.shortfall,
                "status":           status,
                "interest_234c":    inst.interest_234c,
            })
        return reminders


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def compute_advance_tax(params: dict) -> dict:
    """
    JSON-serializable wrapper for Flask endpoint.

    params keys:
        financial_year (str)
        presumptive (bool): True for Sec 44AD/44ADA assessees
        estimated_tax (float): Override auto-computed tax
        income (dict): IncomeEstimate fields
        payments (list[dict]): [{quarter, amount, payment_date}]
        today (str): Override today's date (YYYY-MM-DD) for testing
    """
    from datetime import datetime as _dt

    today_str = params.get("today")
    today = _dt.strptime(today_str, "%Y-%m-%d").date() if today_str else None

    engine = AdvanceTaxReminder(
        financial_year = params.get("financial_year", "2024-25"),
        presumptive    = bool(params.get("presumptive", False)),
        today          = today,
    )

    if "estimated_tax" in params:
        engine.set_estimated_tax(float(params["estimated_tax"]))
    elif "income" in params:
        inc = params["income"]
        engine.set_income(IncomeEstimate(
            salary           = float(inc.get("salary", 0)),
            house_property   = float(inc.get("house_property", 0)),
            business_profit  = float(inc.get("business_profit", 0)),
            capital_gains    = float(inc.get("capital_gains", 0)),
            other_income     = float(inc.get("other_income", 0)),
            deductions_80c   = float(inc.get("deductions_80c", 0)),
            deductions_80d   = float(inc.get("deductions_80d", 0)),
            other_deductions = float(inc.get("other_deductions", 0)),
            tds_deducted     = float(inc.get("tds_deducted", 0)),
            regime           = inc.get("regime", "new"),
        ))

    for p in params.get("payments", []):
        pdate_str = p.get("payment_date")
        pdate = _dt.strptime(pdate_str, "%Y-%m-%d").date() if pdate_str else None
        engine.record_payment(p["quarter"], float(p.get("amount", 0)), pdate)

    result = engine.compute()

    return {
        "financial_year":           result.financial_year,
        "estimated_tax":            result.estimated_tax,
        "tds_credit":               result.tds_credit,
        "net_tax_after_tds":        result.net_tax_after_tds,
        "advance_tax_paid":         result.advance_tax_paid,
        "balance_tax":              result.balance_tax,
        "is_advance_tax_required":  result.is_advance_tax_required,
        "installments":             [asdict(i) for i in result.installments],
        "interest_234b": {
            "applicable":         result.interest_234b.applicable,
            "outstanding_tax":    result.interest_234b.outstanding_tax,
            "months_outstanding": result.interest_234b.months_outstanding,
            "interest_amount":    result.interest_234b.interest_amount,
            "explanation":        result.interest_234b.explanation,
        },
        "interest_234c": {
            "total_interest": result.interest_234c.total_interest,
            "per_quarter":    result.interest_234c.per_quarter,
        },
        "total_interest":           result.total_interest,
        "self_assessment_tax":      result.self_assessment_tax,
        "suggestions":              result.suggestions,
        "reminders":                result.reminders,
    }
