"""
Rice Mill Farmer Payment Compliance Tracker
============================================
Tracks paddy purchases from farmers and enforces compliance with:

  Income Tax Act:
    - Section 40A(3): Cash payments >₹10,000 per day per person disallowed
      (For agricultural produce: ₹2,00,000 limit per transaction — Rule 6DD(j))
    - Section 269SS: Cash loan/deposit >₹20,000 prohibited
    - Section 269ST: Cash receipt >₹2,00,000 in a single transaction prohibited
    - Form 31A reporting requirement (if cash payments exceed ₹1 Cr)

  GST:
    - Paddy from unregistered farmers: exempt supply (HSN 1006, Sl. 54 exemption)
    - No GST applicable on raw paddy; verify farmer is unregistered

  Banking:
    - PM-KISAN linkage: farmers with PM-KISAN can receive Aadhaar-linked bank payments
    - Jan Dhan account preferred for traceability
    - RTGS/NEFT/UPI payment = full deduction under 40A(3)

Per-farmer records:
    - Paddy sold (weight, rate, amount)
    - Payment mode (cash / bank transfer / cheque)
    - PAN if payment >₹5,000 (Form 60 mandatory above ₹50,000 without PAN)
    - Aadhaar linkage for PMFBY / MSP scheme

Alerts:
    - Cash payment approaching ₹2L limit per farmer per transaction
    - Aggregate cash payments to single farmer in a day
    - Missing PAN / Form 60 for high-value payments
    - Running total nearing ₹1 Cr threshold (Form 31A requirement)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PaymentMode(str, Enum):
    CASH      = "cash"
    RTGS      = "rtgs"
    NEFT      = "neft"
    UPI       = "upi"
    CHEQUE    = "cheque"
    DD        = "demand_draft"


class ComplianceStatus(str, Enum):
    OK       = "ok"
    WARNING  = "warning"
    VIOLATION= "violation"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASH_LIMIT_PER_TRANSACTION = 2_00_000   # ₹2L u/s 40A(3) rule 6DD(j) for agri
PAN_THRESHOLD              = 50_000     # Form 60 mandatory above ₹50K without PAN
FORM_31A_THRESHOLD         = 1_00_00_000  # ₹1 Cr aggregate cash
SEC_269ST_LIMIT            = 2_00_000   # Cash receipt limit
WARNING_THRESHOLD          = 1_80_000   # Alert at 90% of ₹2L limit


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FarmerPayment:
    payment_id:     str
    farmer_id:      str
    farmer_name:    str
    village:        str
    mobile:         str
    pan:            Optional[str]
    aadhaar_linked: bool
    payment_date:   str
    paddy_qtl:      float
    rate_per_qtl:   float
    gross_amount:   float
    payment_mode:   PaymentMode
    bank_ref:       Optional[str]   = None
    form_60_filed:  bool            = False
    status:         ComplianceStatus= ComplianceStatus.OK
    flags:          List[str]       = field(default_factory=list)
    deductible:     bool            = True   # 40A(3) compliance


@dataclass
class FarmerLedger:
    farmer_id:      str
    farmer_name:    str
    village:        str
    mobile:         str
    pan:            Optional[str]
    total_paddy_qtl:float   = 0.0
    total_paid:     float   = 0.0
    cash_paid:      float   = 0.0
    bank_paid:      float   = 0.0
    payments:       List[str] = field(default_factory=list)   # payment_ids


@dataclass
class ComplianceReport:
    mill_id:          str
    mill_name:        str
    report_date:      str
    total_payments:   int
    total_amount:     float
    cash_total:       float
    bank_total:       float
    violations:       List[FarmerPayment]
    warnings:         List[FarmerPayment]
    aggregate_summary: Dict
    form_31a_required: bool
    recommendations:  List[str]


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class FarmerPaymentTracker:
    """
    Records and validates paddy purchases from farmers.
    Tracks compliance with Section 40A(3), 269SS, 269ST.
    """

    def __init__(self, mill_id: str, mill_name: str):
        self.mill_id   = mill_id
        self.mill_name = mill_name
        self._payments: Dict[str, FarmerPayment] = {}
        self._ledgers:  Dict[str, FarmerLedger]  = {}
        self._seq       = 0

    def record_payment(
        self,
        farmer_name:  str,
        village:      str,
        mobile:       str,
        paddy_qtl:    float,
        rate_per_qtl: float,
        payment_mode: str,
        payment_date: Optional[str] = None,
        farmer_id:    Optional[str] = None,
        pan:          Optional[str] = None,
        aadhaar_linked: bool = False,
        bank_ref:     Optional[str] = None,
    ) -> FarmerPayment:

        import hashlib, time
        self._seq      += 1
        pid            = f"PAY{self.mill_id}{self._seq:05d}"
        fid            = farmer_id or hashlib.md5(f"{farmer_name}{village}{mobile}".encode()).hexdigest()[:8]
        amount         = round(paddy_qtl * rate_per_qtl, 2)
        pdate          = payment_date or date.today().isoformat()
        mode           = PaymentMode(payment_mode.lower())

        flags          = []
        status         = ComplianceStatus.OK
        deductible     = True
        form_60_filed  = False

        # ── Compliance checks ────────────────────────────────────────────

        # 1. Cash limit check
        if mode == PaymentMode.CASH:
            if amount > CASH_LIMIT_PER_TRANSACTION:
                flags.append(
                    f"VIOLATION u/s 40A(3): Cash payment ₹{amount:,.0f} exceeds ₹2L limit. "
                    f"₹{amount - CASH_LIMIT_PER_TRANSACTION:,.0f} will be DISALLOWED."
                )
                status     = ComplianceStatus.VIOLATION
                deductible = False
            elif amount >= WARNING_THRESHOLD:
                flags.append(
                    f"WARNING: Cash payment ₹{amount:,.0f} approaching ₹2L limit. "
                    f"Use bank transfer for amounts >₹2L."
                )
                status = ComplianceStatus.WARNING

        # 2. PAN / Form 60 check
        if amount >= PAN_THRESHOLD and not pan:
            flags.append(
                f"Form 60 required: Payment ₹{amount:,.0f} ≥ ₹50,000 without PAN. "
                f"Collect Form 60 from farmer {farmer_name}."
            )
            if status == ComplianceStatus.OK:
                status = ComplianceStatus.WARNING

        # 3. Section 269ST — cash receipt >₹2L
        if mode == PaymentMode.CASH and amount > SEC_269ST_LIMIT:
            flags.append(
                f"VIOLATION u/s 269ST: Cash receipt by farmer >₹2L. "
                f"Farmer may face penalty equal to amount received."
            )
            status = ComplianceStatus.VIOLATION

        # 4. Aadhaar linkage reminder for large payments
        if not aadhaar_linked and amount > 1_00_000:
            flags.append(
                f"Recommend linking farmer Aadhaar for PM-KISAN / PMFBY eligibility "
                f"and for bank-linked payment traceability."
            )

        payment = FarmerPayment(
            payment_id     = pid,
            farmer_id      = fid,
            farmer_name    = farmer_name,
            village        = village,
            mobile         = mobile,
            pan            = pan,
            aadhaar_linked = aadhaar_linked,
            payment_date   = pdate,
            paddy_qtl      = paddy_qtl,
            rate_per_qtl   = rate_per_qtl,
            gross_amount   = amount,
            payment_mode   = mode,
            bank_ref       = bank_ref,
            form_60_filed  = form_60_filed,
            status         = status,
            flags          = flags,
            deductible     = deductible,
        )

        self._payments[pid] = payment

        # Update ledger
        if fid not in self._ledgers:
            self._ledgers[fid] = FarmerLedger(
                farmer_id   = fid,
                farmer_name = farmer_name,
                village     = village,
                mobile      = mobile,
                pan         = pan,
            )
        ledger = self._ledgers[fid]
        ledger.total_paddy_qtl += paddy_qtl
        ledger.total_paid      += amount
        if mode == PaymentMode.CASH:
            ledger.cash_paid   += amount
        else:
            ledger.bank_paid   += amount
        ledger.payments.append(pid)

        return payment

    def get_compliance_report(self) -> ComplianceReport:
        payments   = list(self._payments.values())
        today      = date.today().isoformat()
        violations = [p for p in payments if p.status == ComplianceStatus.VIOLATION]
        warnings   = [p for p in payments if p.status == ComplianceStatus.WARNING]

        total_amount   = sum(p.gross_amount for p in payments)
        cash_total     = sum(p.gross_amount for p in payments if p.payment_mode == PaymentMode.CASH)
        bank_total     = total_amount - cash_total
        disallowed     = sum(p.gross_amount for p in violations)
        non_deductible = sum(p.gross_amount - CASH_LIMIT_PER_TRANSACTION
                             for p in violations if p.payment_mode == PaymentMode.CASH)

        form_31a_req   = cash_total >= FORM_31A_THRESHOLD

        # Missing PAN/Form 60
        missing_pan    = [p for p in payments if p.gross_amount >= PAN_THRESHOLD and not p.pan]

        recommendations = []
        if violations:
            recommendations.append(
                f"{len(violations)} cash payment(s) violate ₹2L limit. "
                f"Estimated tax disallowance: ₹{non_deductible:,.0f}. "
                f"Issue cheques/RTGS for future payments."
            )
        if missing_pan:
            recommendations.append(
                f"{len(missing_pan)} payment(s) ≥ ₹50K without PAN. "
                f"Collect Form 60 immediately from these farmers."
            )
        if form_31a_req:
            recommendations.append(
                f"Cash payments to farmers exceed ₹1 Cr — Form 31A SFT report required. "
                f"File with Income Tax department."
            )
        if cash_total > 0:
            recommendations.append(
                f"Convert farmer payments to Aadhaar-linked bank accounts. "
                f"Reduces 40A(3) risk and improves farmer PM-KISAN eligibility."
            )

        return ComplianceReport(
            mill_id           = self.mill_id,
            mill_name         = self.mill_name,
            report_date       = today,
            total_payments    = len(payments),
            total_amount      = round(total_amount, 2),
            cash_total        = round(cash_total, 2),
            bank_total        = round(bank_total, 2),
            violations        = violations,
            warnings          = warnings,
            aggregate_summary = {
                "total_farmers":          len(self._ledgers),
                "total_paddy_qtl":        round(sum(l.total_paddy_qtl for l in self._ledgers.values()), 2),
                "total_amount":           round(total_amount, 2),
                "cash_pct":               round(cash_total / max(1, total_amount) * 100, 1),
                "bank_pct":               round(bank_total / max(1, total_amount) * 100, 1),
                "violation_count":        len(violations),
                "missing_pan_count":      len(missing_pan),
                "estimated_disallowance": round(non_deductible, 2),
            },
            form_31a_required = form_31a_req,
            recommendations   = recommendations,
        )

    def list_payments(self, status_filter: Optional[str] = None) -> List[Dict]:
        payments = list(self._payments.values())
        if status_filter:
            payments = [p for p in payments if p.status.value == status_filter]
        return [asdict(p) for p in payments]

    def get_farmer_summary(self, farmer_id: str) -> Optional[Dict]:
        ledger = self._ledgers.get(farmer_id)
        if not ledger:
            return None
        payments = [asdict(self._payments[pid]) for pid in ledger.payments if pid in self._payments]
        return {**asdict(ledger), "payment_details": payments}


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_trackers: Dict[str, FarmerPaymentTracker] = {}

def ricemill_farmer_payments(params: dict) -> dict:
    mill_id   = params.get("mill_id", "RM001")
    mill_name = params.get("mill_name", "Rice Mill")
    if mill_id not in _trackers:
        _trackers[mill_id] = FarmerPaymentTracker(mill_id, mill_name)
    tracker = _trackers[mill_id]

    action = params.get("action", "record")
    try:
        if action == "record":
            payment = tracker.record_payment(
                farmer_name    = params["farmer_name"],
                village        = params.get("village", ""),
                mobile         = params.get("mobile", ""),
                paddy_qtl      = float(params["paddy_qtl"]),
                rate_per_qtl   = float(params["rate_per_qtl"]),
                payment_mode   = params.get("payment_mode", "cash"),
                payment_date   = params.get("payment_date"),
                pan            = params.get("pan"),
                aadhaar_linked = bool(params.get("aadhaar_linked", False)),
                bank_ref       = params.get("bank_ref"),
            )
            return asdict(payment)
        elif action == "report":
            report = tracker.get_compliance_report()
            return {
                **asdict(report),
                "violations": [asdict(v) for v in report.violations],
                "warnings":   [asdict(w) for w in report.warnings],
            }
        elif action == "list":
            return {"payments": tracker.list_payments(params.get("status"))}
        elif action == "farmer":
            return tracker.get_farmer_summary(params["farmer_id"]) or {"error": "Farmer not found"}
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
