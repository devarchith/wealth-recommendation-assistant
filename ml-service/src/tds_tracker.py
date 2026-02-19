"""
TDS Tracker and Form 26AS Reconciliation Module
FY 2024-25 — Indian Income Tax
Handles TDS deduction tracking, Form 26AS data ingestion,
and mismatch detection between self-declared and TRACES data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TDSSection(str, Enum):
    """Common TDS sections under the Income Tax Act."""
    S192  = "192"   # Salary
    S192A = "192A"  # PF withdrawal (>₹50K, before 5yr)
    S193  = "193"   # Interest on securities
    S194  = "194"   # Dividend on equity shares
    S194A = "194A"  # Interest on deposits (banks/PO)
    S194B = "194B"  # Lottery / crossword winnings
    S194C = "194C"  # Contractor payments
    S194D = "194D"  # Insurance commission
    S194G = "194G"  # Commission on lottery tickets
    S194H = "194H"  # Commission / brokerage
    S194I = "194I"  # Rent
    S194IA = "194IA" # TDS on property purchase (>₹50L)
    S194J = "194J"  # Professional / technical fees
    S194K = "194K"  # Income from MF units
    S194N = "194N"  # Cash withdrawal above threshold
    S194Q = "194Q"  # Purchase of goods (>₹50L)
    S195  = "195"   # Payments to non-residents
    S206AA = "206AA" # Higher TDS for no PAN
    OTHER = "OTHER"


TDS_RATES: Dict[str, float] = {
    "192":   0.0,    # Varies by slab — handled separately
    "192A":  0.10,
    "193":   0.10,
    "194":   0.10,
    "194A":  0.10,
    "194B":  0.30,
    "194C":  0.01,   # 1% individual; 2% company
    "194D":  0.05,
    "194G":  0.05,
    "194H":  0.05,
    "194I":  0.10,
    "194IA": 0.01,
    "194J":  0.10,
    "194K":  0.10,
    "194N":  0.02,
    "194Q":  0.001,
    "195":   0.20,
    "206AA": 0.20,
    "OTHER": 0.10,
}

SECTION_DESCRIPTIONS: Dict[str, str] = {
    "192":   "TDS on Salary",
    "192A":  "TDS on PF Withdrawal",
    "193":   "TDS on Interest on Securities",
    "194":   "TDS on Dividend",
    "194A":  "TDS on Interest (Banks/PO)",
    "194B":  "TDS on Lottery Winnings",
    "194C":  "TDS on Contractor Payments",
    "194D":  "TDS on Insurance Commission",
    "194G":  "TDS on Lottery Commission",
    "194H":  "TDS on Commission/Brokerage",
    "194I":  "TDS on Rent",
    "194IA": "TDS on Property Purchase",
    "194J":  "TDS on Professional Fees",
    "194K":  "TDS on MF Income",
    "194N":  "TDS on Cash Withdrawal",
    "194Q":  "TDS on Goods Purchase",
    "195":   "TDS on Non-Resident Payments",
    "206AA": "Higher TDS (No PAN)",
    "OTHER": "Other TDS",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TDSEntry:
    """Single TDS deduction record."""
    entry_id:        str
    deductor_name:   str
    deductor_tan:    str                  # 10-character TAN
    deductee_pan:    str                  # 10-character PAN
    section:         str                  # TDSSection value or raw string
    deduction_date:  date
    payment_date:    Optional[date]       # Date TDS paid to government
    gross_amount:    float                # Amount on which TDS deducted
    tds_deducted:    float                # Actual TDS deducted (₹)
    tds_deposited:   float = 0.0          # Amount deposited to TRACES
    certificate_no:  Optional[str] = None
    remarks:         Optional[str] = None
    quarter:         str = ""             # Q1/Q2/Q3/Q4 FY

    def __post_init__(self):
        if not self.quarter:
            self.quarter = _date_to_quarter(self.deduction_date)

    @property
    def effective_rate(self) -> float:
        """Actual TDS rate applied."""
        if self.gross_amount <= 0:
            return 0.0
        return round(self.tds_deducted / self.gross_amount * 100, 4)

    @property
    def deposit_shortfall(self) -> float:
        """TDS deducted but not yet deposited."""
        return max(0.0, self.tds_deducted - self.tds_deposited)


@dataclass
class Form26ASEntry:
    """Single entry as appearing in Form 26AS / AIS from TRACES."""
    deductor_tan:    str
    deductor_name:   str
    section:         str
    quarter:         str
    gross_amount:    float
    tds_amount:      float
    tds_deposited:   float
    booking_date:    Optional[date] = None
    certificate_no:  Optional[str] = None


@dataclass
class ReconciliationMismatch:
    """Discrepancy between self-declared TDS and Form 26AS."""
    entry_id:         str
    mismatch_type:    str           # "amount_diff" | "missing_in_26as" | "extra_in_26as"
    self_gross:       float
    traced_gross:     float
    self_tds:         float
    traced_tds:       float
    amount_diff:      float         # self_tds - traced_tds
    section:          str
    deductor_tan:     str
    description:      str
    impact:           str           # "high" | "medium" | "low"


@dataclass
class TDSSummary:
    """Aggregate TDS summary for a financial year."""
    financial_year:       str
    total_gross_income:   float
    total_tds_deducted:   float
    total_tds_deposited:  float
    total_tds_refundable: float       # If excess over tax liability
    total_tds_payable:    float       # If short
    section_breakdown:    List[Dict]
    quarter_breakdown:    List[Dict]
    mismatches:           List[ReconciliationMismatch]
    mismatch_count:       int
    mismatch_amount:      float


@dataclass
class TDSTrackerResult:
    """Full output from TDSTracker.analyze()."""
    summary:        TDSSummary
    entries:        List[TDSEntry]
    form_26as:      List[Form26ASEntry]
    suggestions:    List[str]
    warnings:       List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_to_quarter(d: date) -> str:
    """Return FY quarter label (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)."""
    m = d.month
    if m in (4, 5, 6):
        return "Q1"
    if m in (7, 8, 9):
        return "Q2"
    if m in (10, 11, 12):
        return "Q3"
    return "Q4"


def _validate_pan(pan: str) -> bool:
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan.upper()))


def _validate_tan(tan: str) -> bool:
    return bool(re.match(r'^[A-Z]{4}[0-9]{5}[A-Z]$', tan.upper()))


# ---------------------------------------------------------------------------
# TDS Tracker
# ---------------------------------------------------------------------------

class TDSTracker:
    """
    Tracks TDS deductions across sources and reconciles with Form 26AS data.

    Usage:
        tracker = TDSTracker(financial_year="2024-25", pan="ABCDE1234F")
        tracker.add_entry(TDSEntry(...))
        tracker.load_form_26as([Form26ASEntry(...), ...])
        result = tracker.analyze(tax_liability=95_000)
    """

    def __init__(self, financial_year: str = "2024-25", pan: str = ""):
        self.financial_year = financial_year
        self.pan = pan.upper()
        self._entries: List[TDSEntry] = []
        self._form_26as: List[Form26ASEntry] = []

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_entry(self, entry: TDSEntry) -> None:
        """Add a self-declared TDS entry."""
        self._entries.append(entry)

    def add_entries(self, entries: List[TDSEntry]) -> None:
        for e in entries:
            self.add_entry(e)

    def load_form_26as(self, records: List[Form26ASEntry]) -> None:
        """Load Form 26AS / AIS data downloaded from TRACES."""
        self._form_26as = records

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def analyze(self, tax_liability: float = 0.0) -> TDSTrackerResult:
        """
        Reconcile self-declared TDS with Form 26AS and compute summary.

        Args:
            tax_liability: Estimated income tax liability for the year (₹).

        Returns:
            TDSTrackerResult with full breakdown, mismatches, suggestions.
        """
        entries     = self._entries
        form_26as   = self._form_26as
        mismatches  = self._reconcile(entries, form_26as)

        # Aggregate totals
        total_gross     = sum(e.gross_amount for e in entries)
        total_deducted  = sum(e.tds_deducted for e in entries)
        total_deposited = sum(e.tds_deposited for e in entries)

        # Net TDS after reconciliation
        net_tds = total_deducted  # credit available (govt has the money)
        tds_refundable = max(0.0, net_tds - tax_liability)
        tds_payable    = max(0.0, tax_liability - net_tds)

        # Section breakdown
        section_map: Dict[str, Dict] = {}
        for e in entries:
            s = e.section
            if s not in section_map:
                section_map[s] = {
                    "section": s,
                    "description": SECTION_DESCRIPTIONS.get(s, "TDS"),
                    "gross_amount": 0.0,
                    "tds_deducted": 0.0,
                    "count": 0,
                }
            section_map[s]["gross_amount"] += e.gross_amount
            section_map[s]["tds_deducted"] += e.tds_deducted
            section_map[s]["count"] += 1

        # Quarter breakdown
        quarter_map: Dict[str, Dict] = {}
        for q in ("Q1", "Q2", "Q3", "Q4"):
            quarter_map[q] = {"quarter": q, "gross_amount": 0.0, "tds_deducted": 0.0}
        for e in entries:
            q = e.quarter
            quarter_map.setdefault(q, {"quarter": q, "gross_amount": 0.0, "tds_deducted": 0.0})
            quarter_map[q]["gross_amount"] += e.gross_amount
            quarter_map[q]["tds_deducted"] += e.tds_deducted

        mismatch_amount = sum(abs(m.amount_diff) for m in mismatches)

        summary = TDSSummary(
            financial_year       = self.financial_year,
            total_gross_income   = total_gross,
            total_tds_deducted   = total_deducted,
            total_tds_deposited  = total_deposited,
            total_tds_refundable = tds_refundable,
            total_tds_payable    = tds_payable,
            section_breakdown    = list(section_map.values()),
            quarter_breakdown    = list(quarter_map.values()),
            mismatches           = mismatches,
            mismatch_count       = len(mismatches),
            mismatch_amount      = mismatch_amount,
        )

        suggestions = self._generate_suggestions(summary, entries, form_26as)
        warnings    = self._generate_warnings(mismatches, entries)

        return TDSTrackerResult(
            summary     = summary,
            entries     = entries,
            form_26as   = form_26as,
            suggestions = suggestions,
            warnings    = warnings,
        )

    # ------------------------------------------------------------------
    # Reconciliation logic
    # ------------------------------------------------------------------

    def _reconcile(
        self,
        entries: List[TDSEntry],
        form_26as: List[Form26ASEntry],
    ) -> List[ReconciliationMismatch]:
        """Match self-declared entries to Form 26AS records by TAN + section + quarter."""
        mismatches: List[ReconciliationMismatch] = []

        # Build a lookup keyed by (tan, section, quarter)
        as26_map: Dict[Tuple, List[Form26ASEntry]] = {}
        for rec in form_26as:
            key = (rec.deductor_tan.upper(), rec.section, rec.quarter)
            as26_map.setdefault(key, []).append(rec)

        matched_keys = set()

        for entry in entries:
            key = (entry.deductor_tan.upper(), entry.section, entry.quarter)
            if key not in as26_map:
                mismatches.append(ReconciliationMismatch(
                    entry_id     = entry.entry_id,
                    mismatch_type = "missing_in_26as",
                    self_gross   = entry.gross_amount,
                    traced_gross = 0.0,
                    self_tds     = entry.tds_deducted,
                    traced_tds   = 0.0,
                    amount_diff  = entry.tds_deducted,
                    section      = entry.section,
                    deductor_tan = entry.deductor_tan,
                    description  = (
                        f"{SECTION_DESCRIPTIONS.get(entry.section, 'TDS')} from "
                        f"{entry.deductor_name} ({entry.quarter}) not found in Form 26AS."
                    ),
                    impact = "high" if entry.tds_deducted > 10_000 else "medium",
                ))
            else:
                as26_rec = as26_map[key][0]
                diff = round(entry.tds_deducted - as26_rec.tds_amount, 2)
                if abs(diff) > 1.0:   # ₹1 tolerance for rounding
                    mismatches.append(ReconciliationMismatch(
                        entry_id     = entry.entry_id,
                        mismatch_type = "amount_diff",
                        self_gross   = entry.gross_amount,
                        traced_gross = as26_rec.gross_amount,
                        self_tds     = entry.tds_deducted,
                        traced_tds   = as26_rec.tds_amount,
                        amount_diff  = diff,
                        section      = entry.section,
                        deductor_tan = entry.deductor_tan,
                        description  = (
                            f"TDS mismatch for {entry.deductor_name} under "
                            f"Section {entry.section} ({entry.quarter}): "
                            f"Self-declared ₹{entry.tds_deducted:,.0f} vs "
                            f"Form 26AS ₹{as26_rec.tds_amount:,.0f} (diff ₹{diff:+,.0f})."
                        ),
                        impact = "high" if abs(diff) > 5_000 else "medium",
                    ))
                matched_keys.add(key)

        # Form 26AS entries with no self-declared match
        for key, recs in as26_map.items():
            if key not in matched_keys:
                for rec in recs:
                    mismatches.append(ReconciliationMismatch(
                        entry_id     = f"26AS_{rec.deductor_tan}_{rec.section}_{rec.quarter}",
                        mismatch_type = "extra_in_26as",
                        self_gross   = 0.0,
                        traced_gross = rec.gross_amount,
                        self_tds     = 0.0,
                        traced_tds   = rec.tds_amount,
                        amount_diff  = -rec.tds_amount,
                        section      = rec.section,
                        deductor_tan = rec.deductor_tan,
                        description  = (
                            f"TDS of ₹{rec.tds_amount:,.0f} in Form 26AS under "
                            f"Section {rec.section} from {rec.deductor_name} ({rec.quarter}) "
                            f"has no matching self-declared entry — possible unreported income."
                        ),
                        impact = "high",
                    ))

        return mismatches

    # ------------------------------------------------------------------
    # Suggestions and warnings
    # ------------------------------------------------------------------

    def _generate_suggestions(
        self,
        summary: TDSSummary,
        entries: List[TDSEntry],
        form_26as: List[Form26ASEntry],
    ) -> List[str]:
        suggestions = []

        if summary.total_tds_refundable > 0:
            suggestions.append(
                f"You have ₹{summary.total_tds_refundable:,.0f} excess TDS — "
                f"file your ITR promptly (by July 31) to claim your refund."
            )

        if summary.total_tds_payable > 0:
            suggestions.append(
                f"Your tax liability exceeds TDS credit by ₹{summary.total_tds_payable:,.0f}. "
                f"Pay advance tax or self-assessment tax to avoid interest under Sec 234B/C."
            )

        deposits_pending = sum(e.deposit_shortfall for e in entries)
        if deposits_pending > 0:
            suggestions.append(
                f"₹{deposits_pending:,.0f} in TDS deducted but not yet deposited. "
                f"Late deposit attracts 1.5% p.m. interest under Sec 201(1A) — "
                f"advise deductor to deposit immediately."
            )

        if summary.mismatch_count:
            suggestions.append(
                f"{summary.mismatch_count} mismatch(es) found totalling "
                f"₹{summary.mismatch_amount:,.0f}. Contact your deductors to "
                f"file revised TDS returns (Form 24Q/26Q) and update TRACES."
            )

        # Salary TDS check
        salary_entries = [e for e in entries if e.section in ("192", TDSSection.S192.value)]
        if salary_entries:
            total_salary_tds = sum(e.tds_deducted for e in salary_entries)
            suggestions.append(
                f"Salary TDS (Sec 192) credited: ₹{total_salary_tds:,.0f}. "
                f"Verify Form 16 Part A from employer matches this amount."
            )

        # Interest TDS
        interest_entries = [e for e in entries if e.section in ("194A", TDSSection.S194A.value)]
        if interest_entries:
            suggestions.append(
                "If total bank interest is below ₹40,000 (₹50,000 for seniors), "
                "submit Form 15G/15H to avoid TDS deduction next year."
            )

        if not suggestions:
            suggestions.append(
                "TDS reconciliation looks clean. Verify Form 16 / Form 16A "
                "from all deductors before filing ITR."
            )

        return suggestions

    def _generate_warnings(
        self,
        mismatches: List[ReconciliationMismatch],
        entries: List[TDSEntry],
    ) -> List[str]:
        warnings = []
        high_mismatches = [m for m in mismatches if m.impact == "high"]
        if high_mismatches:
            warnings.append(
                f"{len(high_mismatches)} high-impact mismatch(es) — may trigger scrutiny notice."
            )
        missing = [m for m in mismatches if m.mismatch_type == "missing_in_26as"]
        if missing:
            warnings.append(
                f"{len(missing)} deduction(s) not visible in Form 26AS. "
                f"The deductor may not have filed TDS returns — raise grievance on TRACES."
            )
        extra = [m for m in mismatches if m.mismatch_type == "extra_in_26as"]
        if extra:
            warnings.append(
                f"{len(extra)} entry(ies) in Form 26AS with no matching self-declared income — "
                f"verify for unreported income that must be declared in ITR."
            )
        return warnings


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def analyze_tds(params: dict) -> dict:
    """
    JSON-serializable wrapper for Flask endpoint.

    params keys:
        financial_year (str):   e.g. "2024-25"
        pan (str):              Assessee PAN
        tax_liability (float):  Estimated income tax for the year
        entries (list[dict]):   TDSEntry fields
        form_26as (list[dict]): Form26ASEntry fields
    """
    fy = params.get("financial_year", "2024-25")
    pan = params.get("pan", "")
    tax_liability = float(params.get("tax_liability", 0))

    tracker = TDSTracker(financial_year=fy, pan=pan)

    for e in params.get("entries", []):
        tracker.add_entry(TDSEntry(
            entry_id       = e.get("entry_id", f"E{id(e)}"),
            deductor_name  = e.get("deductor_name", ""),
            deductor_tan   = e.get("deductor_tan", ""),
            deductee_pan   = e.get("deductee_pan", pan),
            section        = e.get("section", "OTHER"),
            deduction_date = _parse_date(e.get("deduction_date", "")),
            payment_date   = _parse_date(e.get("payment_date")) if e.get("payment_date") else None,
            gross_amount   = float(e.get("gross_amount", 0)),
            tds_deducted   = float(e.get("tds_deducted", 0)),
            tds_deposited  = float(e.get("tds_deposited", 0)),
            certificate_no = e.get("certificate_no"),
            remarks        = e.get("remarks"),
        ))

    for rec in params.get("form_26as", []):
        tracker.load_form_26as([Form26ASEntry(
            deductor_tan  = rec.get("deductor_tan", ""),
            deductor_name = rec.get("deductor_name", ""),
            section       = rec.get("section", "OTHER"),
            quarter       = rec.get("quarter", "Q1"),
            gross_amount  = float(rec.get("gross_amount", 0)),
            tds_amount    = float(rec.get("tds_amount", 0)),
            tds_deposited = float(rec.get("tds_deposited", 0)),
            booking_date  = _parse_date(rec.get("booking_date")) if rec.get("booking_date") else None,
        )])

    result = tracker.analyze(tax_liability=tax_liability)

    return {
        "financial_year":       result.summary.financial_year,
        "total_gross_income":   result.summary.total_gross_income,
        "total_tds_deducted":   result.summary.total_tds_deducted,
        "total_tds_deposited":  result.summary.total_tds_deposited,
        "total_tds_refundable": result.summary.total_tds_refundable,
        "total_tds_payable":    result.summary.total_tds_payable,
        "mismatch_count":       result.summary.mismatch_count,
        "mismatch_amount":      result.summary.mismatch_amount,
        "section_breakdown":    result.summary.section_breakdown,
        "quarter_breakdown":    result.summary.quarter_breakdown,
        "mismatches":           [asdict(m) for m in result.summary.mismatches],
        "suggestions":          result.suggestions,
        "warnings":             result.warnings,
    }


def _parse_date(val) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return date.today()
