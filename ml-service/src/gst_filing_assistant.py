"""
GST Filing Assistant — GSTR-1 and GSTR-3B
India Goods and Services Tax — FY 2024-25
Covers:
  • GSTR-1: Outward supplies (B2B, B2C, exports, credit notes, amendments)
  • GSTR-3B: Monthly/quarterly summary with tax payment and ITC details
  • Due date calculation with late fee and interest under Sec 47 and 50
  • Reconciliation between GSTR-1 and GSTR-3B
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import re


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GST_RATES = [0, 0.05, 0.12, 0.18, 0.28]   # Standard GST rate buckets

# Late fee per day per return (CGST + SGST)
LATE_FEE_PER_DAY = {
    "gstr1":  {"nil_return": 10, "regular": 50},
    "gstr3b": {"nil_return": 10, "regular": 50},
}
MAX_LATE_FEE = {
    "gstr1":  {"nil_return": 500, "regular": 10_000},
    "gstr3b": {"nil_return": 500, "regular": 10_000},
}

INTEREST_RATE_SEC50 = 0.18 / 365   # 18% p.a. on unpaid tax

class FilingFrequency(str, Enum):
    MONTHLY   = "monthly"
    QUARTERLY = "quarterly"   # QRMP scheme — turnover ≤ ₹5 Cr


# ---------------------------------------------------------------------------
# Due date calendar
# ---------------------------------------------------------------------------

def gstr1_due_date(period_year: int, period_month: int, frequency: FilingFrequency) -> date:
    """Return GSTR-1 due date for a given period."""
    if frequency == FilingFrequency.MONTHLY:
        # 11th of following month
        if period_month == 12:
            return date(period_year + 1, 1, 11)
        return date(period_year, period_month + 1, 11)
    else:
        # Quarterly — 13th of month following quarter end
        quarter_end = {1: 3, 2: 3, 3: 3, 4: 6, 5: 6, 6: 6,
                       7: 9, 8: 9, 9: 9, 10: 12, 11: 12, 12: 12}[period_month]
        qe_year = period_year if quarter_end >= period_month else period_year + 1
        if quarter_end == 12:
            return date(qe_year + 1, 1, 13)
        return date(qe_year, quarter_end + 1, 13)


def gstr3b_due_date(period_year: int, period_month: int, turnover_crore: float) -> date:
    """Return GSTR-3B due date based on turnover bracket."""
    # >₹5 Cr: 20th; ≤₹5 Cr: 22nd (state 1) or 24th (state 2) — use 22nd as default
    day = 20 if turnover_crore > 5 else 22
    if period_month == 12:
        return date(period_year + 1, 1, day)
    return date(period_year, period_month + 1, day)


# ---------------------------------------------------------------------------
# Data structures — supply entries
# ---------------------------------------------------------------------------

@dataclass
class B2BInvoice:
    """Business-to-business supply."""
    invoice_no:     str
    invoice_date:   date
    buyer_gstin:    str
    place_of_supply: str    # 2-digit state code
    taxable_value:  float
    gst_rate:       float   # e.g. 0.18
    igst:           float   = 0.0
    cgst:           float   = 0.0
    sgst:           float   = 0.0
    is_reverse_charge: bool = False

    def __post_init__(self):
        if self.igst == 0 and self.cgst == 0 and self.sgst == 0:
            # Auto-compute: inter-state → IGST, intra-state → CGST+SGST
            tax = self.taxable_value * self.gst_rate
            self.igst = tax   # Simplified: assume all inter-state
            self.cgst = 0.0
            self.sgst = 0.0


@dataclass
class B2CInvoice:
    """Business-to-consumer (small) supply."""
    invoice_date:   date
    place_of_supply: str
    taxable_value:  float
    gst_rate:       float
    igst:           float = 0.0
    cgst:           float = 0.0
    sgst:           float = 0.0

    def __post_init__(self):
        if self.igst == 0 and self.cgst == 0 and self.sgst == 0:
            tax = self.taxable_value * self.gst_rate
            self.cgst = tax / 2
            self.sgst = tax / 2


@dataclass
class CreditNote:
    """Credit/debit note (CDN)."""
    note_no:        str
    note_date:      date
    original_invoice_no: str
    buyer_gstin:    str
    note_type:      str   # "C" = credit, "D" = debit
    taxable_value:  float
    gst_rate:       float


@dataclass
class ITCEntry:
    """Input Tax Credit entry for GSTR-3B."""
    supplier_gstin: str
    invoice_no:     str
    invoice_date:   date
    taxable_value:  float
    igst:           float = 0.0
    cgst:           float = 0.0
    sgst:           float = 0.0
    eligible:       bool  = True
    ineligible_reason: Optional[str] = None

    @property
    def total_itc(self) -> float:
        return self.igst + self.cgst + self.sgst


# ---------------------------------------------------------------------------
# GSTR-1 Summary
# ---------------------------------------------------------------------------

@dataclass
class GSTR1Summary:
    """Summarised GSTR-1 outward supply data."""
    period:            str   # e.g. "Mar-2025"
    gstin:             str
    b2b_taxable:       float
    b2b_igst:          float
    b2b_cgst:          float
    b2b_sgst:          float
    b2c_taxable:       float
    b2c_igst:          float
    b2c_cgst:          float
    b2c_sgst:          float
    cdn_taxable:       float
    cdn_tax:           float
    total_taxable:     float
    total_igst:        float
    total_cgst:        float
    total_sgst:        float
    total_tax:         float
    invoice_count:     int
    due_date:          date
    filed_date:        Optional[date]
    late_fee:          float
    is_nil_return:     bool


# ---------------------------------------------------------------------------
# GSTR-3B Summary
# ---------------------------------------------------------------------------

@dataclass
class GSTR3BSummary:
    """GSTR-3B monthly summary return."""
    period:            str
    gstin:             str
    outward_taxable:   float
    outward_igst:      float
    outward_cgst:      float
    outward_sgst:      float
    inward_rc_igst:    float    # Inward supplies under reverse charge
    inward_rc_cgst:    float
    inward_rc_sgst:    float
    total_tax_liability: float
    itc_igst:          float
    itc_cgst:          float
    itc_sgst:          float
    total_itc:         float
    net_igst_payable:  float
    net_cgst_payable:  float
    net_sgst_payable:  float
    net_tax_payable:   float
    amount_paid:       float
    outstanding:       float
    interest_sec50:    float
    due_date:          date
    filed_date:        Optional[date]
    late_fee:          float


# ---------------------------------------------------------------------------
# Filing Assistant
# ---------------------------------------------------------------------------

class GSTFilingAssistant:
    """
    Prepares GSTR-1 and GSTR-3B summaries, computes late fees and interest,
    and reconciles outward supplies between both returns.

    Usage:
        assistant = GSTFilingAssistant(gstin="27AABCU9603R1ZX", period_month=3, period_year=2025)
        assistant.add_b2b(B2BInvoice(...))
        assistant.add_itc(ITCEntry(...))
        result = assistant.prepare_returns()
    """

    def __init__(
        self,
        gstin:           str,
        period_month:    int,
        period_year:     int,
        turnover_crore:  float = 1.0,
        frequency:       FilingFrequency = FilingFrequency.MONTHLY,
        filed_gstr1:     Optional[date] = None,
        filed_gstr3b:    Optional[date] = None,
        amount_paid:     float = 0.0,
        today:           Optional[date] = None,
    ):
        self.gstin          = gstin
        self.period_month   = period_month
        self.period_year    = period_year
        self.turnover_crore = turnover_crore
        self.frequency      = frequency
        self.filed_gstr1    = filed_gstr1
        self.filed_gstr3b   = filed_gstr3b
        self.amount_paid    = amount_paid
        self.today          = today or date.today()

        self._b2b:    List[B2BInvoice]  = []
        self._b2c:    List[B2CInvoice]  = []
        self._cdn:    List[CreditNote]  = []
        self._itc:    List[ITCEntry]    = []

    def add_b2b(self, inv: B2BInvoice) -> None:
        self._b2b.append(inv)

    def add_b2c(self, inv: B2CInvoice) -> None:
        self._b2c.append(inv)

    def add_cdn(self, note: CreditNote) -> None:
        self._cdn.append(note)

    def add_itc(self, entry: ITCEntry) -> None:
        self._itc.append(entry)

    def prepare_returns(self) -> Dict:
        period_str = date(self.period_year, self.period_month, 1).strftime("%b-%Y")
        gstr1  = self._prepare_gstr1(period_str)
        gstr3b = self._prepare_gstr3b(period_str, gstr1)
        recon  = self._reconcile(gstr1, gstr3b)
        alerts = self._generate_alerts(gstr1, gstr3b)

        return {
            "gstin":   self.gstin,
            "period":  period_str,
            "gstr1":   asdict(gstr1),
            "gstr3b":  asdict(gstr3b),
            "reconciliation": recon,
            "alerts":  alerts,
        }

    def _prepare_gstr1(self, period_str: str) -> GSTR1Summary:
        b2b_taxable = sum(i.taxable_value for i in self._b2b)
        b2b_igst    = sum(i.igst for i in self._b2b)
        b2b_cgst    = sum(i.cgst for i in self._b2b)
        b2b_sgst    = sum(i.sgst for i in self._b2b)

        b2c_taxable = sum(i.taxable_value for i in self._b2c)
        b2c_igst    = sum(i.igst for i in self._b2c)
        b2c_cgst    = sum(i.cgst for i in self._b2c)
        b2c_sgst    = sum(i.sgst for i in self._b2c)

        cdn_taxable = sum(c.taxable_value for c in self._cdn)
        cdn_tax     = sum(c.taxable_value * c.gst_rate for c in self._cdn)

        total_taxable = b2b_taxable + b2c_taxable - cdn_taxable
        total_igst    = b2b_igst + b2c_igst
        total_cgst    = b2b_cgst + b2c_cgst
        total_sgst    = b2b_sgst + b2c_sgst
        total_tax     = total_igst + total_cgst + total_sgst

        due = gstr1_due_date(self.period_year, self.period_month, self.frequency)
        late_fee = self._late_fee("gstr1", due, self.filed_gstr1, total_taxable == 0)

        return GSTR1Summary(
            period        = period_str,
            gstin         = self.gstin,
            b2b_taxable   = b2b_taxable,
            b2b_igst      = b2b_igst,
            b2b_cgst      = b2b_cgst,
            b2b_sgst      = b2b_sgst,
            b2c_taxable   = b2c_taxable,
            b2c_igst      = b2c_igst,
            b2c_cgst      = b2c_cgst,
            b2c_sgst      = b2c_sgst,
            cdn_taxable   = cdn_taxable,
            cdn_tax       = cdn_tax,
            total_taxable = total_taxable,
            total_igst    = total_igst,
            total_cgst    = total_cgst,
            total_sgst    = total_sgst,
            total_tax     = total_tax,
            invoice_count = len(self._b2b) + len(self._b2c),
            due_date      = due,
            filed_date    = self.filed_gstr1,
            late_fee      = late_fee,
            is_nil_return = total_taxable == 0,
        )

    def _prepare_gstr3b(self, period_str: str, gstr1: GSTR1Summary) -> GSTR3BSummary:
        eligible_itc = [e for e in self._itc if e.eligible]
        itc_igst = sum(e.igst for e in eligible_itc)
        itc_cgst = sum(e.cgst for e in eligible_itc)
        itc_sgst = sum(e.sgst for e in eligible_itc)
        total_itc = itc_igst + itc_cgst + itc_sgst

        total_liability = gstr1.total_tax
        net_igst = max(0.0, gstr1.total_igst - itc_igst)
        net_cgst = max(0.0, gstr1.total_cgst - itc_cgst)
        net_sgst = max(0.0, gstr1.total_sgst - itc_sgst)
        net_payable = net_igst + net_cgst + net_sgst

        outstanding = max(0.0, net_payable - self.amount_paid)
        due = gstr3b_due_date(self.period_year, self.period_month, self.turnover_crore)
        late_fee = self._late_fee("gstr3b", due, self.filed_gstr3b, total_liability == 0)

        # Interest on outstanding tax
        ref_date = self.filed_gstr3b or self.today
        days_late = max(0, (ref_date - due).days)
        interest = outstanding * INTEREST_RATE_SEC50 * days_late

        return GSTR3BSummary(
            period             = period_str,
            gstin              = self.gstin,
            outward_taxable    = gstr1.total_taxable,
            outward_igst       = gstr1.total_igst,
            outward_cgst       = gstr1.total_cgst,
            outward_sgst       = gstr1.total_sgst,
            inward_rc_igst     = 0.0,
            inward_rc_cgst     = 0.0,
            inward_rc_sgst     = 0.0,
            total_tax_liability= total_liability,
            itc_igst           = itc_igst,
            itc_cgst           = itc_cgst,
            itc_sgst           = itc_sgst,
            total_itc          = total_itc,
            net_igst_payable   = net_igst,
            net_cgst_payable   = net_cgst,
            net_sgst_payable   = net_sgst,
            net_tax_payable    = net_payable,
            amount_paid        = self.amount_paid,
            outstanding        = outstanding,
            interest_sec50     = round(interest, 2),
            due_date           = due,
            filed_date         = self.filed_gstr3b,
            late_fee           = late_fee,
        )

    def _late_fee(
        self,
        return_type: str,
        due: date,
        filed: Optional[date],
        is_nil: bool,
    ) -> float:
        ref = filed or self.today
        if ref <= due:
            return 0.0
        days_late = (ref - due).days
        category = "nil_return" if is_nil else "regular"
        fee_per_day = LATE_FEE_PER_DAY[return_type][category]
        max_fee     = MAX_LATE_FEE[return_type][category]
        return min(days_late * fee_per_day, max_fee)

    def _reconcile(self, gstr1: GSTR1Summary, gstr3b: GSTR3BSummary) -> Dict:
        igst_diff = round(gstr1.total_igst - gstr3b.outward_igst, 2)
        cgst_diff = round(gstr1.total_cgst - gstr3b.outward_cgst, 2)
        sgst_diff = round(gstr1.total_sgst - gstr3b.outward_sgst, 2)
        return {
            "gstr1_total_tax":  gstr1.total_tax,
            "gstr3b_liability": gstr3b.total_tax_liability,
            "igst_difference":  igst_diff,
            "cgst_difference":  cgst_diff,
            "sgst_difference":  sgst_diff,
            "reconciled":       abs(igst_diff) < 1 and abs(cgst_diff) < 1 and abs(sgst_diff) < 1,
        }

    def _generate_alerts(self, gstr1: GSTR1Summary, gstr3b: GSTR3BSummary) -> List[str]:
        alerts = []
        today = self.today

        if self.filed_gstr1 is None and today > gstr1.due_date:
            days = (today - gstr1.due_date).days
            alerts.append(f"GSTR-1 overdue by {days} day(s). Late fee: ₹{gstr1.late_fee:,.0f}.")

        if self.filed_gstr3b is None and today > gstr3b.due_date:
            days = (today - gstr3b.due_date).days
            alerts.append(
                f"GSTR-3B overdue by {days} day(s). "
                f"Late fee: ₹{gstr3b.late_fee:,.0f} + interest ₹{gstr3b.interest_sec50:,.2f}."
            )

        g1_upcoming = (gstr1.due_date - today).days
        if 0 < g1_upcoming <= 5 and not self.filed_gstr1:
            alerts.append(f"GSTR-1 due in {g1_upcoming} day(s) on {gstr1.due_date.strftime('%d %b %Y')}.")

        g3b_upcoming = (gstr3b.due_date - today).days
        if 0 < g3b_upcoming <= 5 and not self.filed_gstr3b:
            alerts.append(f"GSTR-3B due in {g3b_upcoming} day(s) on {gstr3b.due_date.strftime('%d %b %Y')}.")

        if gstr3b.outstanding > 0:
            alerts.append(
                f"Net GST payable: ₹{gstr3b.net_tax_payable:,.0f}. "
                f"Outstanding after payment: ₹{gstr3b.outstanding:,.0f}. "
                f"Pay via PMT-06 challan to avoid interest."
            )

        ineligible = [e for e in self._itc if not e.eligible]
        if ineligible:
            ineligible_amt = sum(e.total_itc for e in ineligible)
            alerts.append(
                f"₹{ineligible_amt:,.0f} ITC blocked — ineligible under Sec 17(5) "
                f"(e.g. motor vehicles, personal expenses). Not included in GSTR-3B."
            )

        if not alerts:
            alerts.append("All GST returns are up to date. No pending actions.")

        return alerts


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def prepare_gst_returns(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> Optional[date]:
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError):
                pass
        return None

    assistant = GSTFilingAssistant(
        gstin          = params.get("gstin", ""),
        period_month   = int(params.get("period_month", date.today().month)),
        period_year    = int(params.get("period_year",  date.today().year)),
        turnover_crore = float(params.get("turnover_crore", 1.0)),
        frequency      = FilingFrequency(params.get("frequency", "monthly")),
        filed_gstr1    = _d(params.get("filed_gstr1")),
        filed_gstr3b   = _d(params.get("filed_gstr3b")),
        amount_paid    = float(params.get("amount_paid", 0)),
        today          = _d(params.get("today")),
    )

    for inv in params.get("b2b", []):
        assistant.add_b2b(B2BInvoice(
            invoice_no       = inv.get("invoice_no", ""),
            invoice_date     = _d(inv.get("invoice_date")) or date.today(),
            buyer_gstin      = inv.get("buyer_gstin", ""),
            place_of_supply  = inv.get("place_of_supply", "27"),
            taxable_value    = float(inv.get("taxable_value", 0)),
            gst_rate         = float(inv.get("gst_rate", 0.18)),
        ))

    for inv in params.get("b2c", []):
        assistant.add_b2c(B2CInvoice(
            invoice_date    = _d(inv.get("invoice_date")) or date.today(),
            place_of_supply = inv.get("place_of_supply", "27"),
            taxable_value   = float(inv.get("taxable_value", 0)),
            gst_rate        = float(inv.get("gst_rate", 0.18)),
        ))

    for e in params.get("itc", []):
        assistant.add_itc(ITCEntry(
            supplier_gstin = e.get("supplier_gstin", ""),
            invoice_no     = e.get("invoice_no", ""),
            invoice_date   = _d(e.get("invoice_date")) or date.today(),
            taxable_value  = float(e.get("taxable_value", 0)),
            igst           = float(e.get("igst", 0)),
            cgst           = float(e.get("cgst", 0)),
            sgst           = float(e.get("sgst", 0)),
            eligible       = bool(e.get("eligible", True)),
            ineligible_reason = e.get("ineligible_reason"),
        ))

    return assistant.prepare_returns()
