"""
Bulk ITR Filing Status Dashboard — All Clients
===============================================
Aggregates ITR filing progress for all clients managed by a CA firm
for AY 2025-26 (FY 2024-25).

Tracks:
  - Document collection status (Form 16, AIS, bank statements, P&L)
  - Computation progress (drafted / reviewed / approved)
  - Filing status (not_started / in_progress / ready / filed / verified)
  - Missing information checklist per client
  - Deadline countdown (31 July 2025 for non-audit; 31 October 2025 for audit)
  - Form selection: ITR-1 to ITR-7 based on client profile

Integrates with ca_client_manager.py — uses Client and ClientType.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import date, timedelta
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FilingProgress(str, Enum):
    NOT_STARTED   = "not_started"
    DOCS_PENDING  = "docs_pending"
    COMPUTATION   = "computation"
    CA_REVIEW     = "ca_review"
    CLIENT_REVIEW = "client_review"
    APPROVED      = "approved"
    FILED         = "filed"
    VERIFIED      = "itr_v_verified"   # ITR-V e-verified / sent to CPC

class ComputationStatus(str, Enum):
    NOT_STARTED = "not_started"
    DRAFTED     = "drafted"
    REVIEWED    = "reviewed"
    FINAL       = "final"

class ITRForm(str, Enum):
    ITR1  = "ITR-1"   # Salaried, one house, income < ₹50L
    ITR2  = "ITR-2"   # Capital gains, foreign income, > ₹50L
    ITR3  = "ITR-3"   # Business/profession (non-presumptive)
    ITR4  = "ITR-4"   # Presumptive business (44AD/44ADA/44AE)
    ITR5  = "ITR-5"   # Partnership firms, LLPs
    ITR6  = "ITR-6"   # Companies
    ITR7  = "ITR-7"   # Trusts, political parties, institutions

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AY                  = "AY 2025-26"
FY                  = "FY 2024-25"
DEADLINE_NON_AUDIT  = date(2025, 7, 31)
DEADLINE_AUDIT      = date(2025, 10, 31)
DEADLINE_COMPANY    = date(2025, 10, 31)
BELATED_DEADLINE    = date(2025, 12, 31)

_REQUIRED_DOCS_BASE = [
    "PAN Card",
    "Form 26AS / AIS / TIS",
    "Bank statements (Apr 2024 – Mar 2025)",
]
_SALARY_DOCS        = ["Form 16 from employer"]
_INVESTMENT_DOCS    = ["80C investment proofs", "LIC premium receipts"]
_CAPITAL_GAINS_DOCS = ["Broker P&L statement (STCG/LTCG)", "CAMS/Kfintech CAS statement"]
_PROPERTY_DOCS      = ["Rent receipts (HRA claim)", "Home loan interest certificate"]
_BUSINESS_DOCS      = ["P&L statement (provisional)", "Balance sheet", "GST returns summary"]
_AUDIT_DOCS         = ["Audited financial statements signed by auditor", "Tax Audit Report (3CD)"]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DocumentChecklist:
    document:  str
    received:  bool  = False
    source:    str   = ""   # "client" | "fetched" | "portal"

@dataclass
class ITRRecord:
    client_id:    str
    client_name:  str
    client_type:  str          # matches ClientType enum value
    pan:          str
    itr_form:     ITRForm
    requires_audit: bool

    # Progress
    progress:     FilingProgress  = FilingProgress.NOT_STARTED
    computation:  ComputationStatus = ComputationStatus.NOT_STARTED

    # Documents
    docs_checklist: List[DocumentChecklist] = field(default_factory=list)
    docs_score:   float = 0.0   # 0–100

    # Financials (from computation)
    gross_income: float = 0.0
    taxable_income: float = 0.0
    tax_payable:  float = 0.0
    refund_due:   float = 0.0
    tds_credit:   float = 0.0
    advance_tax:  float = 0.0

    # Filing
    filing_date:       Optional[str] = None
    acknowledgement:   Optional[str] = None
    itrv_verified:     bool          = False
    itrv_verify_date:  Optional[str] = None

    # Timeline
    deadline:          str = DEADLINE_NON_AUDIT.isoformat()
    days_to_deadline:  int = 0
    is_overdue:        bool = False

    # Flags
    missing_items:     List[str] = field(default_factory=list)
    notes:             str       = ""
    staff_assigned:    str       = ""


# ---------------------------------------------------------------------------
# ITR form selector
# ---------------------------------------------------------------------------

_FORM_MAP = {
    "individual":      ITRForm.ITR1,   # may be upgraded to ITR2/3
    "huf":             ITRForm.ITR2,
    "proprietary":     ITRForm.ITR4,
    "partnership":     ITRForm.ITR5,
    "private_limited": ITRForm.ITR6,
    "llp":             ITRForm.ITR5,
    "trust":           ITRForm.ITR7,
}

def suggest_itr_form(client_type: str, has_capital_gains: bool = False,
                     is_presumptive: bool = False, income_above_50l: bool = False) -> ITRForm:
    base = _FORM_MAP.get(client_type.lower(), ITRForm.ITR3)
    if base == ITRForm.ITR1:
        if has_capital_gains or income_above_50l:
            return ITRForm.ITR2
        if is_presumptive:
            return ITRForm.ITR4
    return base

# ---------------------------------------------------------------------------
# Main dashboard class
# ---------------------------------------------------------------------------

class BulkITRDashboard:
    """
    Tracks ITR filing progress for all clients in a CA portfolio.
    """

    def __init__(self, ca_name: str, assessment_year: str = AY):
        self.ca_name    = ca_name
        self.ay         = assessment_year
        self._records:  Dict[str, ITRRecord] = {}   # client_id → ITRRecord

    # ── Registration ────────────────────────────────────────────────────────

    def add_client(
        self,
        client_id:     str,
        client_name:   str,
        client_type:   str,
        pan:           str,
        has_salary:    bool = True,
        has_capital_gains: bool = False,
        has_business:  bool = False,
        is_presumptive:bool = False,
        income_above_50l: bool = False,
        requires_audit:bool = False,
        staff_assigned: str = "",
    ) -> ITRRecord:
        itr_form = suggest_itr_form(client_type, has_capital_gains, is_presumptive, income_above_50l)
        if has_business and not is_presumptive:
            itr_form = ITRForm.ITR3

        # Build doc checklist
        docs = [DocumentChecklist(d) for d in _REQUIRED_DOCS_BASE]
        if has_salary:
            docs.extend([DocumentChecklist(d) for d in _SALARY_DOCS])
        docs.extend([DocumentChecklist(d) for d in _INVESTMENT_DOCS])
        if has_capital_gains:
            docs.extend([DocumentChecklist(d) for d in _CAPITAL_GAINS_DOCS])
        if has_salary:
            docs.extend([DocumentChecklist(d) for d in _PROPERTY_DOCS])
        if has_business:
            docs.extend([DocumentChecklist(d) for d in _BUSINESS_DOCS])
        if requires_audit:
            docs.extend([DocumentChecklist(d) for d in _AUDIT_DOCS])

        deadline_date = DEADLINE_AUDIT if requires_audit or client_type.lower() in ("private_limited",) else DEADLINE_NON_AUDIT
        today         = date.today()
        days_to_due   = (deadline_date - today).days

        record = ITRRecord(
            client_id      = client_id,
            client_name    = client_name,
            client_type    = client_type,
            pan            = pan,
            itr_form       = itr_form,
            requires_audit = requires_audit,
            docs_checklist = docs,
            deadline       = deadline_date.isoformat(),
            days_to_deadline = days_to_due,
            is_overdue     = days_to_due < 0,
            staff_assigned = staff_assigned,
        )
        self._records[client_id] = record
        self._refresh_missing(record)
        return record

    # ── Progress updates ────────────────────────────────────────────────────

    def mark_doc_received(self, client_id: str, doc_name: str, source: str = "client"):
        rec = self._get(client_id)
        for d in rec.docs_checklist:
            if d.document == doc_name:
                d.received = True
                d.source   = source
        self._recompute_docs_score(rec)
        self._refresh_progress(rec)
        self._refresh_missing(rec)

    def update_computation(self, client_id: str, status: str,
                           gross_income: float = 0, taxable_income: float = 0,
                           tax_payable: float = 0, refund_due: float = 0,
                           tds_credit: float = 0, advance_tax: float = 0):
        rec = self._get(client_id)
        rec.computation     = ComputationStatus(status)
        rec.gross_income    = gross_income
        rec.taxable_income  = taxable_income
        rec.tax_payable     = tax_payable
        rec.refund_due      = refund_due
        rec.tds_credit      = tds_credit
        rec.advance_tax     = advance_tax
        self._refresh_progress(rec)

    def mark_filed(self, client_id: str, filing_date: str, acknowledgement: str):
        rec = self._get(client_id)
        rec.filing_date    = filing_date
        rec.acknowledgement= acknowledgement
        rec.progress       = FilingProgress.FILED

    def mark_verified(self, client_id: str, verify_date: str):
        rec = self._get(client_id)
        rec.itrv_verified    = True
        rec.itrv_verify_date = verify_date
        rec.progress         = FilingProgress.VERIFIED

    def assign_staff(self, client_id: str, staff_name: str):
        self._get(client_id).staff_assigned = staff_name

    def add_note(self, client_id: str, note: str):
        self._get(client_id).notes = note

    # ── Dashboard views ─────────────────────────────────────────────────────

    def portfolio_summary(self) -> Dict:
        records = list(self._records.values())
        today   = date.today()

        by_status = {}
        for r in records:
            by_status[r.progress.value] = by_status.get(r.progress.value, 0) + 1

        total_refund  = sum(r.refund_due  for r in records)
        total_payable = sum(r.tax_payable for r in records)

        critical = [r for r in records
                    if r.progress not in (FilingProgress.FILED, FilingProgress.VERIFIED)
                    and r.days_to_deadline <= 7]

        return {
            "assessment_year":   self.ay,
            "total_clients":     len(records),
            "by_status":         by_status,
            "filed":             by_status.get("filed", 0) + by_status.get("itr_v_verified", 0),
            "pending":           len(records) - by_status.get("filed", 0) - by_status.get("itr_v_verified", 0),
            "critical_deadline": len(critical),
            "non_audit_deadline":DEADLINE_NON_AUDIT.isoformat(),
            "audit_deadline":    DEADLINE_AUDIT.isoformat(),
            "total_refund_portfolio":  round(total_refund, 2),
            "total_payable_portfolio": round(total_payable, 2),
            "critical_clients":  [{"client_id": r.client_id, "name": r.client_name,
                                   "days_to_deadline": r.days_to_deadline,
                                   "progress": r.progress.value} for r in critical],
        }

    def get_client_status(self, client_id: str) -> Dict:
        return asdict(self._get(client_id))

    def list_pending(self, staff: Optional[str] = None) -> List[Dict]:
        records = [r for r in self._records.values()
                   if r.progress not in (FilingProgress.FILED, FilingProgress.VERIFIED)]
        if staff:
            records = [r for r in records if r.staff_assigned == staff]
        records.sort(key=lambda r: r.days_to_deadline)
        return [{"client_id": r.client_id, "name": r.client_name, "pan": r.pan,
                 "form": r.itr_form.value, "progress": r.progress.value,
                 "docs_score": r.docs_score, "days_to_deadline": r.days_to_deadline,
                 "missing": r.missing_items[:3], "staff": r.staff_assigned} for r in records]

    # ── Internals ────────────────────────────────────────────────────────────

    def _get(self, client_id: str) -> ITRRecord:
        if client_id not in self._records:
            raise KeyError(f"Client not found: {client_id}")
        return self._records[client_id]

    def _recompute_docs_score(self, rec: ITRRecord):
        total    = len(rec.docs_checklist)
        received = sum(1 for d in rec.docs_checklist if d.received)
        rec.docs_score = round((received / total) * 100, 1) if total else 0.0

    def _refresh_progress(self, rec: ITRRecord):
        if rec.filing_date:
            return  # already filed
        if rec.docs_score < 60:
            rec.progress = FilingProgress.DOCS_PENDING
        elif rec.computation == ComputationStatus.NOT_STARTED:
            rec.progress = FilingProgress.COMPUTATION
        elif rec.computation == ComputationStatus.DRAFTED:
            rec.progress = FilingProgress.CA_REVIEW
        elif rec.computation == ComputationStatus.REVIEWED:
            rec.progress = FilingProgress.CLIENT_REVIEW
        elif rec.computation == ComputationStatus.FINAL:
            rec.progress = FilingProgress.APPROVED
        else:
            rec.progress = FilingProgress.NOT_STARTED

    def _refresh_missing(self, rec: ITRRecord):
        rec.missing_items = [d.document for d in rec.docs_checklist if not d.received]


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_dashboards: Dict[str, BulkITRDashboard] = {}

def bulk_itr_dashboard(params: dict) -> dict:
    ca_name = params.get("ca_name", "default_ca")
    if ca_name not in _dashboards:
        _dashboards[ca_name] = BulkITRDashboard(ca_name)
    dashboard = _dashboards[ca_name]

    action = params.get("action", "summary")
    try:
        if action == "add_client":
            rec = dashboard.add_client(**{k: v for k, v in params.items() if k not in ("action", "ca_name")})
            return asdict(rec)
        elif action == "mark_doc":
            dashboard.mark_doc_received(params["client_id"], params["doc_name"], params.get("source", "client"))
            return {"success": True, "client": asdict(dashboard._get(params["client_id"]))}
        elif action == "update_computation":
            dashboard.update_computation(params["client_id"], params["status"],
                                         float(params.get("gross_income", 0)),
                                         float(params.get("taxable_income", 0)),
                                         float(params.get("tax_payable", 0)),
                                         float(params.get("refund_due", 0)),
                                         float(params.get("tds_credit", 0)),
                                         float(params.get("advance_tax", 0)))
            return {"success": True}
        elif action == "mark_filed":
            dashboard.mark_filed(params["client_id"], params["filing_date"], params["acknowledgement"])
            return {"success": True}
        elif action == "summary":
            return dashboard.portfolio_summary()
        elif action == "pending":
            return {"pending": dashboard.list_pending(params.get("staff"))}
        elif action == "client":
            return dashboard.get_client_status(params["client_id"])
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
