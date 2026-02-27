"""
CA Client Onboarding Flow — GST, PAN, ITR History Intake
=========================================================
Extends ca_client_manager.py with a structured onboarding pipeline.

Onboarding steps:
  Step 1 — Basic KYC: name, DOB/incorporation date, PAN, Aadhaar / CIN
  Step 2 — GST Registration: GSTINs, registration type, turnover
  Step 3 — Tax History: last 3-year ITR filings, outstanding demands
  Step 4 — Business Profile: nature of business, turnover, employees
  Step 5 — Document Checklist: auto-generated list with completeness score
  Step 6 — Risk Assessment: flags high-risk indicators for CA review
  Step 7 — Engagement Letter: generates fee proposal and service scope

Integrates with:
  - ca_client_manager.py (Client, ClientType)
  - ca_billing.py (ServiceType, DEFAULT_FEE_SCHEDULE)
  - audit_trail.py (get_audit_logger)
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from enum import Enum
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RegistrationType(str, Enum):
    REGULAR        = "regular"
    COMPOSITION    = "composition"
    CASUAL         = "casual"
    NON_RESIDENT   = "non_resident"
    INPUT_SERVICE  = "input_service_distributor"
    EXEMPT         = "exempt_voluntary"

class FilingStatus(str, Enum):
    FILED_ON_TIME  = "filed_on_time"
    FILED_BELATED  = "filed_belated"
    NOT_FILED      = "not_filed"
    EXEMPT         = "exempt"

class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    CRITICAL = "critical"

class OnboardingStep(str, Enum):
    KYC         = "kyc"
    GST         = "gst"
    TAX_HISTORY = "tax_history"
    BUSINESS    = "business"
    DOCUMENTS   = "documents"
    RISK        = "risk"
    ENGAGEMENT  = "engagement"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GSTRegistration:
    gstin:               str
    state_code:          str
    registration_type:   RegistrationType
    effective_date:      str       # YYYY-MM-DD
    annual_turnover:     float     # ₹
    gstr1_frequency:     str       # monthly | quarterly
    gstr3b_frequency:    str       # monthly | quarterly
    pending_returns:     int       = 0
    cancelled:           bool      = False
    cancellation_date:   Optional[str] = None

    def __post_init__(self):
        # Validate GSTIN format: 15-char, state code 2 digits + PAN 10 + entity + Z + checksum
        if not re.match(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$', self.gstin.upper()):
            raise ValueError(f"Invalid GSTIN format: {self.gstin}")

@dataclass
class ITRHistoryRecord:
    assessment_year:  str       # e.g., "2024-25"
    itr_form:         str       # ITR-1, ITR-2, ITR-3, ITR-4, ITR-5, ITR-6
    gross_income:     float     # ₹
    tax_paid:         float     # ₹
    refund_claimed:   float     # ₹ (0 if nil)
    filing_status:    FilingStatus
    filing_date:      Optional[str] = None   # YYYY-MM-DD
    acknowledgement:  Optional[str] = None   # 15-digit ITR-V
    outstanding_demand: float       = 0.0   # ₹ pending as per CPC
    notice_pending:   bool          = False
    notice_section:   Optional[str] = None   # e.g., "143(2)", "148"

@dataclass
class DocumentItem:
    name:        str
    description: str
    mandatory:   bool
    received:    bool = False
    file_ref:    Optional[str] = None   # document vault reference

@dataclass
class RiskFlag:
    code:        str
    description: str
    severity:    RiskLevel
    action:      str   # recommended action for CA

@dataclass
class OnboardingProfile:
    # Identification
    onboarding_id:     str
    client_id:         Optional[str]   # set after formal Client creation
    created_at:        str
    completed_steps:   List[str]       = field(default_factory=list)

    # KYC
    entity_name:       str             = ""
    pan:               str             = ""
    aadhaar_or_cin:    str             = ""
    date_of_birth:     Optional[str]   = None   # individuals
    incorporation_date: Optional[str]  = None   # companies
    constitution:      str             = ""     # Proprietor/Partnership/Pvt Ltd/LLP

    # GST
    gst_registrations: List[GSTRegistration] = field(default_factory=list)
    aggregate_turnover: float          = 0.0

    # Tax history
    itr_history:       List[ITRHistoryRecord] = field(default_factory=list)
    outstanding_demand_total: float    = 0.0
    pending_notices:   List[str]       = field(default_factory=list)

    # Business profile
    nature_of_business: str           = ""
    industry_code:      str           = ""   # NIC code
    employee_count:     int            = 0
    annual_turnover:    float          = 0.0
    bank_accounts:      List[str]      = field(default_factory=list)

    # Checklist
    document_checklist: List[DocumentItem] = field(default_factory=list)
    completeness_score: float          = 0.0   # 0–100

    # Risk
    risk_flags:        List[RiskFlag]  = field(default_factory=list)
    overall_risk:      RiskLevel       = RiskLevel.LOW

    # Engagement
    proposed_fee_annual: float         = 0.0
    proposed_services:   List[str]     = field(default_factory=list)
    engagement_date:     Optional[str] = None

# ---------------------------------------------------------------------------
# Document checklists by constitution
# ---------------------------------------------------------------------------

_INDIVIDUAL_DOCS = [
    DocumentItem("PAN Card", "Permanent Account Number card copy", mandatory=True),
    DocumentItem("Aadhaar Card", "UIDAI Aadhaar card / e-Aadhaar", mandatory=True),
    DocumentItem("Bank Statements", "All bank accounts — last 12 months", mandatory=True),
    DocumentItem("Form 16", "TDS certificate from employer (if salaried)", mandatory=False),
    DocumentItem("Form 26AS / AIS", "Annual Information Statement from IT portal", mandatory=True),
    DocumentItem("Investment Proofs", "80C investments, insurance, PPF, NSC, ELSS", mandatory=False),
    DocumentItem("Rent Receipts", "If claiming HRA exemption", mandatory=False),
    DocumentItem("Home Loan Statement", "Principal + interest split from bank", mandatory=False),
    DocumentItem("Capital Gains Statement", "Stock broker P&L statement / CAS from CAMS", mandatory=False),
    DocumentItem("Previous ITR Copy", "Last 3 years acknowledged ITRs", mandatory=True),
]

_COMPANY_DOCS = [
    DocumentItem("PAN Card", "Company PAN", mandatory=True),
    DocumentItem("Certificate of Incorporation", "MCA CoI with CIN", mandatory=True),
    DocumentItem("MOA & AOA", "Memorandum and Articles of Association", mandatory=True),
    DocumentItem("GST Registration Certificate", "GSTIN(s) for all states", mandatory=True),
    DocumentItem("Bank Statements", "All bank accounts — last 12 months", mandatory=True),
    DocumentItem("Audited Financial Statements", "Last 3 years P&L and Balance Sheet", mandatory=True),
    DocumentItem("Previous ITR", "Last 3 years ITR-6 with receipts", mandatory=True),
    DocumentItem("Form 26AS / AIS", "Tax credit statement from IT portal", mandatory=True),
    DocumentItem("TDS Certificates", "Form 16A from customers/deductors", mandatory=True),
    DocumentItem("GST Returns", "Last 12 months GSTR-1 and GSTR-3B", mandatory=True),
    DocumentItem("Director/Partner Details", "PAN, Aadhaar, DIN/DPIN of all directors", mandatory=True),
    DocumentItem("Shareholding Pattern", "Latest equity structure", mandatory=False),
]

_GST_ONLY_DOCS = [
    DocumentItem("GSTIN Certificate", "Current GST registration", mandatory=True),
    DocumentItem("GST Returns", "Last 24 months GSTR-1, GSTR-3B", mandatory=True),
    DocumentItem("E-way Bills", "Sample e-way bills if applicable", mandatory=False),
    DocumentItem("ITC Ledger", "Electronic credit ledger from GST portal", mandatory=True),
    DocumentItem("Liability Ledger", "Electronic liability ledger", mandatory=True),
]

# ---------------------------------------------------------------------------
# Risk assessment rules
# ---------------------------------------------------------------------------

def _assess_risk(profile: OnboardingProfile) -> Tuple[List[RiskFlag], RiskLevel]:
    flags = []

    # 1. Outstanding tax demands
    if profile.outstanding_demand_total > 1_000_000:  # > ₹10 lakh
        flags.append(RiskFlag(
            code="DEMAND_HIGH",
            description=f"Outstanding tax demand ₹{profile.outstanding_demand_total:,.0f} — CA to review before acceptance",
            severity=RiskLevel.HIGH,
            action="Obtain demand notices; check if appeals filed; compute liability exposure",
        ))
    elif profile.outstanding_demand_total > 0:
        flags.append(RiskFlag(
            code="DEMAND_PRESENT",
            description=f"Outstanding demand ₹{profile.outstanding_demand_total:,.0f}",
            severity=RiskLevel.MEDIUM,
            action="Verify demand details; check rectification/appeal status",
        ))

    # 2. Pending notices
    if profile.pending_notices:
        flags.append(RiskFlag(
            code="NOTICES_PENDING",
            description=f"{len(profile.pending_notices)} pending IT notices: {', '.join(profile.pending_notices)}",
            severity=RiskLevel.HIGH,
            action="Obtain copies of all notices; check response deadlines",
        ))

    # 3. Non-filing history
    not_filed = [r for r in profile.itr_history if r.filing_status == FilingStatus.NOT_FILED]
    if len(not_filed) >= 2:
        flags.append(RiskFlag(
            code="NON_FILER",
            description=f"ITR not filed for {len(not_filed)} years: {[r.assessment_year for r in not_filed]}",
            severity=RiskLevel.CRITICAL,
            action="File pending returns immediately; assess penalty u/s 234F and prosecution risk u/s 276CC",
        ))
    elif len(not_filed) == 1:
        flags.append(RiskFlag(
            code="MISSING_ITR",
            description=f"ITR not filed for AY {not_filed[0].assessment_year}",
            severity=RiskLevel.MEDIUM,
            action="File belated/updated return (ITR-U) if within window",
        ))

    # 4. GST pending returns
    for gst in profile.gst_registrations:
        if gst.pending_returns > 3:
            flags.append(RiskFlag(
                code="GST_DEFAULTS",
                description=f"GSTIN {gst.gstin}: {gst.pending_returns} pending GST returns",
                severity=RiskLevel.HIGH,
                action="File pending returns; compute late fees and interest; avoid further accrual",
            ))
        elif gst.pending_returns > 0:
            flags.append(RiskFlag(
                code="GST_PARTIAL",
                description=f"GSTIN {gst.gstin}: {gst.pending_returns} pending returns",
                severity=RiskLevel.MEDIUM,
                action="Clear pending returns; set up monthly compliance calendar",
            ))

    # 5. High turnover + no GST (mandatory if > ₹20L services / ₹40L goods)
    if profile.annual_turnover > 2_000_000 and not profile.gst_registrations:
        flags.append(RiskFlag(
            code="GST_NOT_REGISTERED",
            description=f"Annual turnover ₹{profile.annual_turnover:,.0f} but no GST registration found",
            severity=RiskLevel.CRITICAL,
            action="Apply for GST registration immediately; assess retrospective tax liability",
        ))

    # Derive overall risk
    if any(f.severity == RiskLevel.CRITICAL for f in flags):
        overall = RiskLevel.CRITICAL
    elif any(f.severity == RiskLevel.HIGH for f in flags):
        overall = RiskLevel.HIGH
    elif any(f.severity == RiskLevel.MEDIUM for f in flags):
        overall = RiskLevel.MEDIUM
    else:
        overall = RiskLevel.LOW

    return flags, overall

# ---------------------------------------------------------------------------
# Fee proposal engine
# ---------------------------------------------------------------------------

_FEE_MATRIX = {
    # (constitution, annual_turnover_bracket) → annual_fee
    ("individual", 0):       15_000,
    ("individual", 500_000): 20_000,
    ("individual", 2_000_000):30_000,
    ("proprietor", 0):       25_000,
    ("proprietor", 1_000_000):35_000,
    ("proprietor", 5_000_000):50_000,
    ("partnership", 0):      40_000,
    ("partnership", 5_000_000):60_000,
    ("pvt_ltd", 0):          75_000,
    ("pvt_ltd", 10_000_000): 100_000,
    ("pvt_ltd", 50_000_000): 150_000,
    ("llp", 0):              55_000,
    ("llp", 10_000_000):     80_000,
}

def _propose_fee(constitution: str, annual_turnover: float, has_gst: bool, pending_notices: int) -> float:
    key_type = constitution.lower().replace(" ", "_")
    # Find closest bracket
    matching = [(k, v) for k, v in _FEE_MATRIX.items()
                if k[0] == key_type and k[1] <= annual_turnover]
    base_fee = matching[-1][1] if matching else 25_000

    # Adjustments
    if has_gst:
        base_fee += 18_000   # Monthly GST filings (₹1,500/month)
    if pending_notices > 0:
        base_fee += pending_notices * 7_500   # Per-notice handling fee
    return base_fee

# ---------------------------------------------------------------------------
# Main onboarding class
# ---------------------------------------------------------------------------

import uuid

class ClientOnboardingFlow:
    """
    Manages the multi-step client onboarding process.
    Each step is idempotent — can be re-called to update data.
    """

    def __init__(self):
        self._profiles: Dict[str, OnboardingProfile] = {}

    # ── Step 1: KYC ─────────────────────────────────────────────────────────

    def start(
        self,
        entity_name:     str,
        pan:             str,
        constitution:    str,
        aadhaar_or_cin:  str = "",
        date_of_birth:   Optional[str] = None,
        incorporation_date: Optional[str] = None,
    ) -> OnboardingProfile:
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan.upper()):
            raise ValueError(f"Invalid PAN format: {pan}")
        oid = str(uuid.uuid4())[:16].replace("-", "")
        profile = OnboardingProfile(
            onboarding_id      = oid,
            client_id          = None,
            created_at         = datetime.utcnow().isoformat(),
            entity_name        = entity_name,
            pan                = pan.upper(),
            aadhaar_or_cin     = aadhaar_or_cin,
            constitution       = constitution,
            date_of_birth      = date_of_birth,
            incorporation_date = incorporation_date,
        )
        # Generate doc checklist based on constitution
        if constitution.lower() in ("pvt_ltd", "llp", "partnership", "company"):
            profile.document_checklist = list(_COMPANY_DOCS)
        else:
            profile.document_checklist = list(_INDIVIDUAL_DOCS)
        profile.completed_steps.append(OnboardingStep.KYC)
        self._profiles[oid] = profile
        return profile

    # ── Step 2: GST ─────────────────────────────────────────────────────────

    def add_gst(self, onboarding_id: str, registrations: List[Dict]) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        for reg in registrations:
            profile.gst_registrations.append(GSTRegistration(
                gstin             = reg["gstin"],
                state_code        = reg.get("state_code", reg["gstin"][:2]),
                registration_type = RegistrationType(reg.get("registration_type", "regular")),
                effective_date    = reg.get("effective_date", ""),
                annual_turnover   = float(reg.get("annual_turnover", 0)),
                gstr1_frequency   = reg.get("gstr1_frequency", "monthly"),
                gstr3b_frequency  = reg.get("gstr3b_frequency", "monthly"),
                pending_returns   = int(reg.get("pending_returns", 0)),
            ))
        profile.aggregate_turnover = sum(r.annual_turnover for r in profile.gst_registrations)
        profile.document_checklist.extend([d for d in _GST_ONLY_DOCS if d.name not in
                                           [x.name for x in profile.document_checklist]])
        if OnboardingStep.GST not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.GST)
        return profile

    # ── Step 3: Tax History ─────────────────────────────────────────────────

    def add_itr_history(self, onboarding_id: str, history: List[Dict]) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        for h in history:
            record = ITRHistoryRecord(
                assessment_year  = h["assessment_year"],
                itr_form         = h.get("itr_form", "ITR-1"),
                gross_income     = float(h.get("gross_income", 0)),
                tax_paid         = float(h.get("tax_paid", 0)),
                refund_claimed   = float(h.get("refund_claimed", 0)),
                filing_status    = FilingStatus(h.get("filing_status", "filed_on_time")),
                filing_date      = h.get("filing_date"),
                acknowledgement  = h.get("acknowledgement"),
                outstanding_demand = float(h.get("outstanding_demand", 0)),
                notice_pending   = bool(h.get("notice_pending", False)),
                notice_section   = h.get("notice_section"),
            )
            profile.itr_history.append(record)
            profile.outstanding_demand_total += record.outstanding_demand
            if record.notice_pending and record.notice_section:
                profile.pending_notices.append(f"{record.assessment_year}: {record.notice_section}")
        if OnboardingStep.TAX_HISTORY not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.TAX_HISTORY)
        return profile

    # ── Step 4: Business profile ─────────────────────────────────────────────

    def add_business_profile(
        self, onboarding_id: str,
        nature_of_business: str,
        annual_turnover: float,
        employee_count: int = 0,
        industry_code: str = "",
        bank_accounts: Optional[List[str]] = None,
    ) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        profile.nature_of_business = nature_of_business
        profile.annual_turnover    = annual_turnover
        profile.employee_count     = employee_count
        profile.industry_code      = industry_code
        profile.bank_accounts      = bank_accounts or []
        if OnboardingStep.BUSINESS not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.BUSINESS)
        return profile

    # ── Step 5: Document checklist status ────────────────────────────────────

    def mark_documents(self, onboarding_id: str, received_docs: List[str]) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        for doc in profile.document_checklist:
            if doc.name in received_docs:
                doc.received = True
        mandatory_total   = sum(1 for d in profile.document_checklist if d.mandatory)
        mandatory_received= sum(1 for d in profile.document_checklist if d.mandatory and d.received)
        optional_total    = sum(1 for d in profile.document_checklist if not d.mandatory)
        optional_received = sum(1 for d in profile.document_checklist if not d.mandatory and d.received)
        if mandatory_total + optional_total > 0:
            profile.completeness_score = round(
                ((mandatory_received * 1.5 + optional_received) /
                 (mandatory_total * 1.5 + optional_total)) * 100, 1
            )
        if OnboardingStep.DOCUMENTS not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.DOCUMENTS)
        return profile

    # ── Step 6: Risk assessment ──────────────────────────────────────────────

    def assess_risk(self, onboarding_id: str) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        profile.risk_flags, profile.overall_risk = _assess_risk(profile)
        if OnboardingStep.RISK not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.RISK)
        return profile

    # ── Step 7: Engagement letter / fee proposal ──────────────────────────────

    def propose_engagement(self, onboarding_id: str) -> OnboardingProfile:
        profile = self._get(onboarding_id)
        has_gst = len(profile.gst_registrations) > 0
        profile.proposed_fee_annual = _propose_fee(
            profile.constitution,
            profile.annual_turnover,
            has_gst,
            len(profile.pending_notices),
        )
        profile.proposed_services = self._suggest_services(profile)
        profile.engagement_date   = datetime.utcnow().strftime("%Y-%m-%d")
        if OnboardingStep.ENGAGEMENT not in profile.completed_steps:
            profile.completed_steps.append(OnboardingStep.ENGAGEMENT)
        return profile

    def _suggest_services(self, profile: OnboardingProfile) -> List[str]:
        svc = ["Income Tax Return Filing (Annual)"]
        if profile.gst_registrations:
            svc.append("GST Monthly Filings (GSTR-1 + GSTR-3B)")
        if profile.outstanding_demand_total > 0:
            svc.append("Tax Demand Resolution")
        if profile.pending_notices:
            svc.append("Tax Notice Response")
        if profile.employee_count > 0:
            svc.append("Payroll & TDS Compliance")
        if profile.annual_turnover > 10_000_000:
            svc.append("Statutory Audit (Mandatory)")
        if profile.constitution.lower() in ("pvt_ltd", "company"):
            svc.append("ROC Annual Filings (AOC-4, MGT-7)")
        return svc

    # ── Getters ──────────────────────────────────────────────────────────────

    def get_profile(self, onboarding_id: str) -> OnboardingProfile:
        return self._get(onboarding_id)

    def get_missing_documents(self, onboarding_id: str) -> List[str]:
        profile = self._get(onboarding_id)
        return [d.name for d in profile.document_checklist if not d.received and d.mandatory]

    def _get(self, oid: str) -> OnboardingProfile:
        if oid not in self._profiles:
            raise KeyError(f"Onboarding ID not found: {oid}")
        return self._profiles[oid]


# ---------------------------------------------------------------------------
# Flask / API wrapper
# ---------------------------------------------------------------------------

_flow = ClientOnboardingFlow()

def client_onboarding(params: dict) -> dict:
    """
    Unified API wrapper for Flask route.
    action: start | add_gst | add_itr | add_business | mark_docs | assess_risk | propose | get
    """
    action = params.get("action", "get")
    oid    = params.get("onboarding_id", "")

    try:
        if action == "start":
            profile = _flow.start(
                entity_name        = params["entity_name"],
                pan                = params["pan"],
                constitution       = params["constitution"],
                aadhaar_or_cin     = params.get("aadhaar_or_cin", ""),
                date_of_birth      = params.get("date_of_birth"),
                incorporation_date = params.get("incorporation_date"),
            )
        elif action == "add_gst":
            profile = _flow.add_gst(oid, params.get("registrations", []))
        elif action == "add_itr":
            profile = _flow.add_itr_history(oid, params.get("history", []))
        elif action == "add_business":
            profile = _flow.add_business_profile(
                oid,
                nature_of_business = params.get("nature_of_business", ""),
                annual_turnover    = float(params.get("annual_turnover", 0)),
                employee_count     = int(params.get("employee_count", 0)),
                industry_code      = params.get("industry_code", ""),
                bank_accounts      = params.get("bank_accounts", []),
            )
        elif action == "mark_docs":
            profile = _flow.mark_documents(oid, params.get("received_docs", []))
        elif action == "assess_risk":
            profile = _flow.assess_risk(oid)
        elif action == "propose":
            profile = _flow.propose_engagement(oid)
        elif action == "get":
            profile = _flow.get_profile(oid)
        else:
            return {"error": f"Unknown action: {action}"}

        return asdict(profile)

    except (KeyError, ValueError) as e:
        return {"error": str(e)}
