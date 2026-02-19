"""
Accounts Payable and Receivable Tracker
Small business / SME focused — India context
Tracks invoices, payments, aging buckets, and generates collection/payment alerts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class InvoiceStatus(str, Enum):
    DRAFT     = "draft"
    SENT      = "sent"
    PARTIAL   = "partial"
    PAID      = "paid"
    OVERDUE   = "overdue"
    CANCELLED = "cancelled"
    DISPUTED  = "disputed"


class TransactionType(str, Enum):
    RECEIVABLE = "receivable"
    PAYABLE    = "payable"


@dataclass
class Payment:
    payment_date: date
    amount:       float
    mode:         str   # "cash" | "upi" | "neft" | "cheque"
    reference:    Optional[str] = None


@dataclass
class Invoice:
    invoice_id:      str
    invoice_no:      str
    transaction_type: TransactionType
    party_name:      str
    party_gstin:     Optional[str]
    invoice_date:    date
    due_date:        date
    taxable_amount:  float
    gst_amount:      float
    total_amount:    float
    currency:        str = "INR"
    notes:           Optional[str] = None
    status:          InvoiceStatus = InvoiceStatus.SENT
    payments:        List[Payment] = field(default_factory=list)

    @property
    def total_paid(self) -> float:
        return sum(p.amount for p in self.payments)

    @property
    def balance_due(self) -> float:
        return round(self.total_amount - self.total_paid, 2)

    @property
    def days_outstanding(self) -> int:
        return max(0, (date.today() - self.invoice_date).days)

    @property
    def days_overdue(self) -> int:
        return max(0, (date.today() - self.due_date).days)

    @property
    def aging_bucket(self) -> str:
        d = self.days_overdue if self.balance_due > 0 else 0
        if d == 0:
            return "current"
        if d <= 30:
            return "1-30"
        if d <= 60:
            return "31-60"
        if d <= 90:
            return "61-90"
        return "90+"


@dataclass
class AgingReport:
    current:    float
    days_1_30:  float
    days_31_60: float
    days_61_90: float
    days_90_plus: float
    total:      float


@dataclass
class APARSummary:
    total_receivable:      float
    total_payable:         float
    net_position:          float
    overdue_receivable:    float
    overdue_payable:       float
    receivable_aging:      AgingReport
    payable_aging:         AgingReport
    collection_efficiency: float   # % collected in last 90 days
    dso:                   float   # Days Sales Outstanding
    dpo:                   float   # Days Payable Outstanding
    top_debtors:           List[Dict]
    top_creditors:         List[Dict]
    alerts:                List[str]


class APARTracker:
    """
    Accounts Payable and Receivable tracker.

    Usage:
        tracker = APARTracker()
        tracker.add_invoice(Invoice(...))
        tracker.record_payment("INV-001", Payment(...))
        summary = tracker.summarize()
    """

    def __init__(self):
        self._invoices: Dict[str, Invoice] = {}

    def add_invoice(self, inv: Invoice) -> None:
        self._invoices[inv.invoice_id] = inv
        self._update_status(inv)

    def record_payment(self, invoice_id: str, payment: Payment) -> None:
        inv = self._invoices.get(invoice_id)
        if not inv:
            return
        inv.payments.append(payment)
        self._update_status(inv)

    def _update_status(self, inv: Invoice) -> None:
        if inv.status == InvoiceStatus.CANCELLED:
            return
        if inv.total_paid >= inv.total_amount:
            inv.status = InvoiceStatus.PAID
        elif inv.total_paid > 0:
            inv.status = InvoiceStatus.PARTIAL
        elif date.today() > inv.due_date:
            inv.status = InvoiceStatus.OVERDUE
        else:
            inv.status = InvoiceStatus.SENT

    def summarize(self) -> APARSummary:
        receivables = [i for i in self._invoices.values()
                       if i.transaction_type == TransactionType.RECEIVABLE
                       and i.status not in (InvoiceStatus.CANCELLED, InvoiceStatus.PAID)]
        payables    = [i for i in self._invoices.values()
                       if i.transaction_type == TransactionType.PAYABLE
                       and i.status not in (InvoiceStatus.CANCELLED, InvoiceStatus.PAID)]

        rec_aging = self._aging(receivables)
        pay_aging = self._aging(payables)

        total_rec = sum(i.balance_due for i in receivables)
        total_pay = sum(i.balance_due for i in payables)

        overdue_rec = sum(i.balance_due for i in receivables if i.days_overdue > 0)
        overdue_pay = sum(i.balance_due for i in payables   if i.days_overdue > 0)

        # DSO and DPO (simplified 90-day window)
        ninety_ago   = date.today() - timedelta(days=90)
        recent_sales = [i for i in self._invoices.values()
                        if i.transaction_type == TransactionType.RECEIVABLE
                        and i.invoice_date >= ninety_ago]
        recent_purch = [i for i in self._invoices.values()
                        if i.transaction_type == TransactionType.PAYABLE
                        and i.invoice_date >= ninety_ago]

        total_sales_90   = sum(i.total_amount for i in recent_sales)
        total_purch_90   = sum(i.total_amount for i in recent_purch)
        daily_sales      = total_sales_90 / 90 if total_sales_90 else 1
        daily_purch      = total_purch_90 / 90 if total_purch_90 else 1

        dso = total_rec / daily_sales if daily_sales else 0
        dpo = total_pay / daily_purch if daily_purch else 0

        # Collection efficiency
        collected_90 = sum(p.amount for i in recent_sales for p in i.payments)
        efficiency   = (collected_90 / total_sales_90 * 100) if total_sales_90 else 100.0

        # Top debtors / creditors
        debtor_map: Dict[str, float] = {}
        for i in receivables:
            debtor_map[i.party_name] = debtor_map.get(i.party_name, 0) + i.balance_due
        creditor_map: Dict[str, float] = {}
        for i in payables:
            creditor_map[i.party_name] = creditor_map.get(i.party_name, 0) + i.balance_due

        top_debtors   = [{"name": k, "balance": v} for k, v in
                         sorted(debtor_map.items(), key=lambda x: -x[1])[:5]]
        top_creditors = [{"name": k, "balance": v} for k, v in
                         sorted(creditor_map.items(), key=lambda x: -x[1])[:5]]

        alerts = self._generate_alerts(receivables, payables)

        return APARSummary(
            total_receivable      = total_rec,
            total_payable         = total_pay,
            net_position          = total_rec - total_pay,
            overdue_receivable    = overdue_rec,
            overdue_payable       = overdue_pay,
            receivable_aging      = rec_aging,
            payable_aging         = pay_aging,
            collection_efficiency = round(efficiency, 1),
            dso                   = round(dso, 1),
            dpo                   = round(dpo, 1),
            top_debtors           = top_debtors,
            top_creditors         = top_creditors,
            alerts                = alerts,
        )

    def _aging(self, invoices: List[Invoice]) -> AgingReport:
        buckets = {"current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
        for inv in invoices:
            buckets[inv.aging_bucket] = buckets.get(inv.aging_bucket, 0) + inv.balance_due
        return AgingReport(
            current     = buckets["current"],
            days_1_30   = buckets["1-30"],
            days_31_60  = buckets["31-60"],
            days_61_90  = buckets["61-90"],
            days_90_plus= buckets["90+"],
            total       = sum(buckets.values()),
        )

    def _generate_alerts(
        self,
        receivables: List[Invoice],
        payables:    List[Invoice],
    ) -> List[str]:
        alerts = []

        # High-value overdue receivables
        critical_rec = [i for i in receivables if i.days_overdue > 30 and i.balance_due > 50_000]
        if critical_rec:
            total = sum(i.balance_due for i in critical_rec)
            alerts.append(
                f"{len(critical_rec)} invoice(s) overdue >30 days totalling ₹{total:,.0f} — "
                f"initiate collection calls / legal notice."
            )

        # Payables due soon (within 7 days)
        soon_pay = [i for i in payables if 0 < (i.due_date - date.today()).days <= 7]
        if soon_pay:
            total = sum(i.balance_due for i in soon_pay)
            alerts.append(
                f"{len(soon_pay)} payment(s) due within 7 days totalling ₹{total:,.0f} — "
                f"ensure funds availability."
            )

        # Very old receivables (>90 days)
        old = [i for i in receivables if i.days_overdue > 90]
        if old:
            total = sum(i.balance_due for i in old)
            alerts.append(
                f"₹{total:,.0f} in receivables overdue >90 days — consider provisioning "
                f"as bad debt or initiating MSME Samadhaan / NCLT proceedings."
            )

        return alerts


def analyze_ap_ar(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> date:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError, AttributeError):
                pass
        return date.today()

    tracker = APARTracker()

    for inv_data in params.get("invoices", []):
        inv = Invoice(
            invoice_id       = inv_data.get("invoice_id", str(id(inv_data))),
            invoice_no       = inv_data.get("invoice_no", ""),
            transaction_type = TransactionType(inv_data.get("transaction_type", "receivable")),
            party_name       = inv_data.get("party_name", ""),
            party_gstin      = inv_data.get("party_gstin"),
            invoice_date     = _d(inv_data.get("invoice_date", "")),
            due_date         = _d(inv_data.get("due_date", "")),
            taxable_amount   = float(inv_data.get("taxable_amount", 0)),
            gst_amount       = float(inv_data.get("gst_amount", 0)),
            total_amount     = float(inv_data.get("total_amount", 0)),
            notes            = inv_data.get("notes"),
        )
        for p in inv_data.get("payments", []):
            inv.payments.append(Payment(
                payment_date = _d(p.get("payment_date", "")),
                amount       = float(p.get("amount", 0)),
                mode         = p.get("mode", "neft"),
                reference    = p.get("reference"),
            ))
        tracker.add_invoice(inv)

    summary = tracker.summarize()
    return {
        "total_receivable":      summary.total_receivable,
        "total_payable":         summary.total_payable,
        "net_position":          summary.net_position,
        "overdue_receivable":    summary.overdue_receivable,
        "overdue_payable":       summary.overdue_payable,
        "collection_efficiency": summary.collection_efficiency,
        "dso":                   summary.dso,
        "dpo":                   summary.dpo,
        "receivable_aging":      asdict(summary.receivable_aging),
        "payable_aging":         asdict(summary.payable_aging),
        "top_debtors":           summary.top_debtors,
        "top_creditors":         summary.top_creditors,
        "alerts":                summary.alerts,
    }
