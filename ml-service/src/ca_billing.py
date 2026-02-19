"""
CA Client Billing and Invoice Generation Module
Features:
  • Service catalog with standard CA fee schedules
  • Invoice generation with GST (18% on professional services, SAC 998221)
  • Payment tracking and aging
  • Recurring annual retainer management
  • Professional fee receipt format compliant with ICAI guidelines
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional


SAC_CODE_CA       = "998221"   # Accounting, auditing, bookkeeping
SAC_CODE_TAX      = "998231"   # Tax consulting
SAC_CODE_ADVISORY = "998219"   # Other professional services
GST_RATE_CA       = 0.18       # 18% GST on CA services


class ServiceType(str, Enum):
    ITR_FILING_INDIVIDUAL = "itr_individual"
    ITR_FILING_BUSINESS   = "itr_business"
    GST_MONTHLY           = "gst_monthly"
    GST_ANNUAL            = "gst_annual"
    AUDIT_STATUTORY       = "audit_statutory"
    AUDIT_TAX             = "audit_tax"
    BOOKKEEPING_MONTHLY   = "bookkeeping_monthly"
    NOTICE_RESPONSE       = "notice_response"
    RETAINER_ANNUAL       = "retainer_annual"
    INCORPORATION         = "incorporation"
    PAYROLL_MONTHLY       = "payroll_monthly"
    CUSTOM                = "custom"


# Default fee schedule (INR) — can be overridden per client
DEFAULT_FEE_SCHEDULE: Dict[ServiceType, float] = {
    ServiceType.ITR_FILING_INDIVIDUAL: 2_000,
    ServiceType.ITR_FILING_BUSINESS:   5_000,
    ServiceType.GST_MONTHLY:           2_500,
    ServiceType.GST_ANNUAL:            8_000,
    ServiceType.AUDIT_STATUTORY:       50_000,
    ServiceType.AUDIT_TAX:             25_000,
    ServiceType.BOOKKEEPING_MONTHLY:   5_000,
    ServiceType.NOTICE_RESPONSE:       10_000,
    ServiceType.RETAINER_ANNUAL:       24_000,
    ServiceType.INCORPORATION:         15_000,
    ServiceType.PAYROLL_MONTHLY:       1_500,
    ServiceType.CUSTOM:                0,
}

SERVICE_DESCRIPTIONS: Dict[ServiceType, str] = {
    ServiceType.ITR_FILING_INDIVIDUAL: "Income Tax Return Filing (Individual)",
    ServiceType.ITR_FILING_BUSINESS:   "Income Tax Return Filing (Business)",
    ServiceType.GST_MONTHLY:           "GST Monthly Return Filing (GSTR-1 + GSTR-3B)",
    ServiceType.GST_ANNUAL:            "GST Annual Return Filing (GSTR-9)",
    ServiceType.AUDIT_STATUTORY:       "Statutory Audit under Companies Act",
    ServiceType.AUDIT_TAX:             "Tax Audit under Section 44AB",
    ServiceType.BOOKKEEPING_MONTHLY:   "Monthly Bookkeeping and Accounts Maintenance",
    ServiceType.NOTICE_RESPONSE:       "Income Tax Notice Response and Representation",
    ServiceType.RETAINER_ANNUAL:       "Annual Retainer — All-Inclusive CA Services",
    ServiceType.INCORPORATION:         "Company / LLP Incorporation Services",
    ServiceType.PAYROLL_MONTHLY:       "Monthly Payroll Processing",
    ServiceType.CUSTOM:                "Professional Services",
}


@dataclass
class InvoiceLineItem:
    service_type:  ServiceType
    description:   str
    sac_code:      str
    quantity:      float
    unit_price:    float
    discount:      float = 0.0

    @property
    def taxable_value(self) -> float:
        return max(0.0, self.quantity * self.unit_price - self.discount)

    @property
    def gst_amount(self) -> float:
        return round(self.taxable_value * GST_RATE_CA, 2)

    @property
    def cgst(self) -> float:
        return round(self.gst_amount / 2, 2)

    @property
    def sgst(self) -> float:
        return round(self.gst_amount / 2, 2)

    @property
    def line_total(self) -> float:
        return round(self.taxable_value + self.gst_amount, 2)


@dataclass
class CAInvoice:
    invoice_no:     str
    invoice_date:   date
    due_date:       date
    ca_name:        str
    ca_gstin:       str
    ca_pan:         str
    ca_address:     str
    client_id:      str
    client_name:    str
    client_pan:     Optional[str]
    client_gstin:   Optional[str]
    client_address: str
    line_items:     List[InvoiceLineItem]
    notes:          Optional[str] = None
    paid_amount:    float = 0.0
    payment_date:   Optional[date] = None
    payment_mode:   Optional[str] = None

    @property
    def total_taxable(self) -> float:
        return round(sum(i.taxable_value for i in self.line_items), 2)

    @property
    def total_cgst(self) -> float:
        return round(sum(i.cgst for i in self.line_items), 2)

    @property
    def total_sgst(self) -> float:
        return round(sum(i.sgst for i in self.line_items), 2)

    @property
    def total_gst(self) -> float:
        return round(self.total_cgst + self.total_sgst, 2)

    @property
    def invoice_value(self) -> float:
        return round(self.total_taxable + self.total_gst, 2)

    @property
    def balance_due(self) -> float:
        return round(self.invoice_value - self.paid_amount, 2)

    @property
    def days_overdue(self) -> int:
        return max(0, (date.today() - self.due_date).days)

    @property
    def is_overdue(self) -> bool:
        return self.balance_due > 0 and date.today() > self.due_date


@dataclass
class BillingReport:
    period:           str
    total_billed:     float
    total_collected:  float
    total_outstanding: float
    overdue_amount:   float
    by_service:       List[Dict]
    top_revenue_clients: List[Dict]
    unpaid_invoices:  List[Dict]
    collection_rate:  float


class CABillingEngine:
    """
    Billing and invoice management for CA firms.

    Usage:
        engine = CABillingEngine(ca_name="CA Ramesh Kumar", ca_gstin="...")
        inv = engine.create_invoice(client_id="C001", ...)
        report = engine.billing_report()
    """

    def __init__(
        self,
        ca_name:    str = "",
        ca_gstin:   str = "",
        ca_pan:     str = "",
        ca_address: str = "",
    ):
        self.ca_name    = ca_name
        self.ca_gstin   = ca_gstin
        self.ca_pan     = ca_pan
        self.ca_address = ca_address
        self._invoices: Dict[str, CAInvoice] = {}
        self._invoice_counter = 1

    def create_invoice(
        self,
        client_id:      str,
        client_name:    str,
        client_address: str,
        services:       List[Dict],   # [{service_type, qty, override_price?, discount?}]
        client_pan:     Optional[str] = None,
        client_gstin:   Optional[str] = None,
        notes:          Optional[str] = None,
        due_days:       int = 30,
        invoice_date:   Optional[date] = None,
    ) -> CAInvoice:
        inv_date  = invoice_date or date.today()
        due_date  = inv_date + timedelta(days=due_days)
        inv_no    = f"CA{inv_date.year}{self._invoice_counter:04d}"
        self._invoice_counter += 1

        line_items = []
        for svc in services:
            stype      = ServiceType(svc.get("service_type", "custom"))
            price      = svc.get("override_price", DEFAULT_FEE_SCHEDULE.get(stype, 0))
            desc       = svc.get("description", SERVICE_DESCRIPTIONS.get(stype, "Professional Services"))
            sac        = svc.get("sac_code", SAC_CODE_TAX)
            line_items.append(InvoiceLineItem(
                service_type = stype,
                description  = desc,
                sac_code     = sac,
                quantity     = float(svc.get("qty", 1)),
                unit_price   = float(price),
                discount     = float(svc.get("discount", 0)),
            ))

        invoice = CAInvoice(
            invoice_no     = inv_no,
            invoice_date   = inv_date,
            due_date       = due_date,
            ca_name        = self.ca_name,
            ca_gstin       = self.ca_gstin,
            ca_pan         = self.ca_pan,
            ca_address     = self.ca_address,
            client_id      = client_id,
            client_name    = client_name,
            client_pan     = client_pan,
            client_gstin   = client_gstin,
            client_address = client_address,
            line_items     = line_items,
            notes          = notes,
        )
        self._invoices[inv_no] = invoice
        return invoice

    def record_payment(
        self,
        invoice_no:   str,
        amount:       float,
        payment_date: Optional[date] = None,
        payment_mode: str = "neft",
    ) -> bool:
        inv = self._invoices.get(invoice_no)
        if not inv:
            return False
        inv.paid_amount   += amount
        inv.payment_date   = payment_date or date.today()
        inv.payment_mode   = payment_mode
        return True

    def billing_report(self, period: str = "FY 2024-25") -> BillingReport:
        invoices = list(self._invoices.values())

        total_billed      = sum(i.invoice_value for i in invoices)
        total_collected   = sum(i.paid_amount    for i in invoices)
        total_outstanding = sum(i.balance_due    for i in invoices)
        overdue           = sum(i.balance_due    for i in invoices if i.is_overdue)
        collection_rate   = (total_collected / total_billed * 100) if total_billed else 100.0

        # By service
        svc_map: Dict[str, float] = {}
        for inv in invoices:
            for item in inv.line_items:
                svc_map[item.service_type.value] = svc_map.get(item.service_type.value, 0) + item.taxable_value
        by_service = [{"service": k, "revenue": v} for k, v in
                      sorted(svc_map.items(), key=lambda x: -x[1])]

        # Top clients
        client_rev: Dict[str, float] = {}
        for inv in invoices:
            client_rev[inv.client_name] = client_rev.get(inv.client_name, 0) + inv.paid_amount
        top_clients = [{"client": k, "revenue": v} for k, v in
                       sorted(client_rev.items(), key=lambda x: -x[1])[:5]]

        unpaid = [{"invoice_no": i.invoice_no, "client": i.client_name,
                   "amount": i.balance_due, "days_overdue": i.days_overdue}
                  for i in invoices if i.balance_due > 0]

        return BillingReport(
            period            = period,
            total_billed      = total_billed,
            total_collected   = total_collected,
            total_outstanding = total_outstanding,
            overdue_amount    = overdue,
            by_service        = by_service,
            top_revenue_clients = top_clients,
            unpaid_invoices   = unpaid,
            collection_rate   = round(collection_rate, 1),
        )


def ca_billing(params: dict) -> dict:
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

    engine = CABillingEngine(
        ca_name    = params.get("ca_name", ""),
        ca_gstin   = params.get("ca_gstin", ""),
        ca_pan     = params.get("ca_pan", ""),
        ca_address = params.get("ca_address", ""),
    )

    for inv_data in params.get("invoices", []):
        inv = engine.create_invoice(
            client_id      = inv_data.get("client_id", ""),
            client_name    = inv_data.get("client_name", ""),
            client_address = inv_data.get("client_address", ""),
            services       = inv_data.get("services", []),
            client_pan     = inv_data.get("client_pan"),
            client_gstin   = inv_data.get("client_gstin"),
            notes          = inv_data.get("notes"),
            due_days       = int(inv_data.get("due_days", 30)),
            invoice_date   = _d(inv_data.get("invoice_date")),
        )
        for pay in inv_data.get("payments", []):
            engine.record_payment(
                invoice_no   = inv.invoice_no,
                amount       = float(pay.get("amount", 0)),
                payment_date = _d(pay.get("payment_date")),
                payment_mode = pay.get("payment_mode", "neft"),
            )

    action = params.get("action", "report")

    if action == "report":
        report = engine.billing_report(params.get("period", "FY 2024-25"))
        return asdict(report)

    # Return latest invoice
    if engine._invoices:
        last_inv = list(engine._invoices.values())[-1]
        return {
            "invoice_no":    last_inv.invoice_no,
            "invoice_date":  last_inv.invoice_date.isoformat(),
            "due_date":      last_inv.due_date.isoformat(),
            "client_name":   last_inv.client_name,
            "total_taxable": last_inv.total_taxable,
            "total_cgst":    last_inv.total_cgst,
            "total_sgst":    last_inv.total_sgst,
            "invoice_value": last_inv.invoice_value,
            "balance_due":   last_inv.balance_due,
            "line_items":    [asdict(i) for i in last_inv.line_items],
        }

    return {"status": "no_invoices"}
