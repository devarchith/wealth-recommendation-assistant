"""
Tax Notice Response Templates — India Income Tax
Covers common IT Department notices with:
  • Notice type classification
  • Response template generation
  • Required documents checklist
  • Deadline calculation
  • Response letter drafting guidelines
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional


class NoticeType(str, Enum):
    SEC_139_5   = "139(5)"   # Revised return
    SEC_142_1   = "142(1)"   # Inquiry before assessment
    SEC_143_1   = "143(1)"   # Intimation / Prima facie adjustments
    SEC_143_2   = "143(2)"   # Scrutiny notice
    SEC_144     = "144"      # Best judgment assessment
    SEC_148     = "148"      # Reassessment (income escaped)
    SEC_148A    = "148A"     # Show cause before 148 (mandatory post-Finance Act 2021)
    SEC_156     = "156"      # Demand notice
    SEC_245     = "245"      # Refund set-off against demand
    SEC_271_1C  = "271(1)(c)" # Penalty for concealment
    SEC_263     = "263"      # Revision by CIT
    SEC_264     = "264"      # Revision on taxpayer's application
    FORM_26AS_MISMATCH = "26as_mismatch"   # AIS / 26AS mismatch
    HIGH_VALUE  = "high_value_transaction" # Non-filer monitoring system
    CUSTOM      = "custom"


NOTICE_DESCRIPTIONS: Dict[str, str] = {
    "139(5)":                 "Revised Return Filing",
    "142(1)":                 "Pre-Assessment Inquiry",
    "143(1)":                 "Intimation / Adjustment",
    "143(2)":                 "Scrutiny Assessment",
    "144":                    "Best Judgment Assessment",
    "148":                    "Income Escaped Assessment (Reassessment)",
    "148A":                   "Show Cause Before Reassessment",
    "156":                    "Tax Demand Notice",
    "245":                    "Refund Adjusted Against Demand",
    "271(1)(c)":              "Penalty for Concealment / Inaccurate Particulars",
    "263":                    "Revision by Commissioner (CIT)",
    "264":                    "Revision on Taxpayer Application",
    "26as_mismatch":          "AIS / Form 26AS Mismatch",
    "high_value_transaction": "High Value Transaction — Non-Filer Monitoring",
    "custom":                 "Custom / Other Notice",
}

RESPONSE_DEADLINES: Dict[str, int] = {
    "139(5)":                 30,
    "142(1)":                 15,
    "143(1)":                 30,  # 30 days to dispute
    "143(2)":                 30,
    "144":                    15,
    "148":                    30,
    "148A":                   7,   # Reduced after 2021 amendment
    "156":                    30,
    "245":                    30,
    "271(1)(c)":              30,
    "263":                    30,
    "264":                    60,
    "26as_mismatch":          15,
    "high_value_transaction": 30,
    "custom":                 30,
}


@dataclass
class NoticeDetails:
    notice_type:   NoticeType
    notice_date:   date
    assessment_year: str        # e.g. "AY 2024-25"
    notice_no:     str
    demand_amount: float = 0.0
    subject:       Optional[str] = None


@dataclass
class NoticeResponse:
    notice_type:       str
    notice_description: str
    notice_date:       str
    response_deadline: str
    days_remaining:    int
    is_urgent:         bool
    demand_amount:     float
    documents_required: List[str]
    response_template:  str
    action_steps:       List[str]
    escalation_options: List[str]


class TaxNoticeHandler:
    """
    Generates response templates and action plans for IT Department notices.

    Usage:
        handler = TaxNoticeHandler()
        response = handler.generate_response(NoticeDetails(...), taxpayer_name="Ramesh Kumar")
    """

    def generate_response(
        self,
        notice:        NoticeDetails,
        taxpayer_name: str = "the taxpayer",
        pan:           str = "",
        ca_name:       str = "",
    ) -> NoticeResponse:
        ntype        = notice.notice_type.value
        description  = NOTICE_DESCRIPTIONS.get(ntype, "Tax Notice")
        days_limit   = RESPONSE_DEADLINES.get(ntype, 30)
        deadline     = notice.notice_date + timedelta(days=days_limit)
        days_rem     = (deadline - date.today()).days

        docs     = self._get_required_documents(notice)
        template = self._get_response_template(notice, taxpayer_name, pan, ca_name)
        steps    = self._get_action_steps(notice)
        escalate = self._get_escalation_options(notice)

        return NoticeResponse(
            notice_type        = ntype,
            notice_description = description,
            notice_date        = notice.notice_date.isoformat(),
            response_deadline  = deadline.isoformat(),
            days_remaining     = days_rem,
            is_urgent          = days_rem <= 7,
            demand_amount      = notice.demand_amount,
            documents_required = docs,
            response_template  = template,
            action_steps       = steps,
            escalation_options = escalate,
        )

    def _get_required_documents(self, notice: NoticeDetails) -> List[str]:
        common = [
            "Copy of the notice",
            f"ITR acknowledgment for {notice.assessment_year}",
            "PAN card copy",
            "Form 26AS / AIS for the relevant year",
        ]
        specific: Dict[str, List[str]] = {
            "143(1)": common + [
                "Details of income, TDS, and deductions declared",
                "Bank statements for salary/interest income",
                "TDS certificates (Form 16, Form 16A)",
            ],
            "143(2)": common + [
                "Books of accounts (P&L, Balance Sheet)",
                "Bank statements (all accounts) — full year",
                "Proofs for all deductions claimed (80C, 80D etc.)",
                "Capital gains computation with purchase/sale proofs",
                "Rental income — rental agreements, TDS from tenant",
                "Foreign income / FEMA declarations if applicable",
            ],
            "142(1)": common + [
                "Information specified in the notice questionnaire",
                "Books of accounts as applicable",
            ],
            "148": common + [
                "All financial records for the reassessment year",
                "Source of high-value transactions",
                "Investment proofs",
            ],
            "156": common + [
                "Computation of income and tax",
                "Proof of taxes paid (challan copies)",
                "Details of any excess demand",
            ],
            "26as_mismatch": common + [
                "Explanation for each mismatched item",
                "Source documentation for unreported income",
                "Corrected ITR draft (if revision needed)",
            ],
        }
        return specific.get(notice.notice_type.value, common)

    def _get_response_template(
        self,
        notice:        NoticeDetails,
        taxpayer_name: str,
        pan:           str,
        ca_name:       str,
    ) -> str:
        ntype = notice.notice_type.value

        templates: Dict[str, str] = {
            "143(1)": f"""To,
The Assessing Officer,
Income Tax Department.

Sub: Response to Intimation u/s 143(1) for {notice.assessment_year}
Notice No: {notice.notice_no} dated {notice.notice_date}

Respected Sir/Madam,

I, {taxpayer_name} (PAN: {pan}), have received the above intimation for Assessment Year {notice.assessment_year}.

After reviewing the intimation, I wish to submit the following:

[EXPLAIN EACH ADJUSTMENT POINT-BY-POINT]
1. The adjustment made on account of [Item] — my submission is: [Your explanation]
2. The TDS credit as per Form 26AS/AIS is ₹[Amount]. The intimation has considered ₹[Amount].

I enclose the following documents:
• Form 26AS for {notice.assessment_year}
• TDS Certificates (Form 16/16A)
• [Other relevant documents]

I request you to kindly rectify the intimation and issue a revised computation.

Yours faithfully,
{taxpayer_name}
PAN: {pan}
Date: {date.today().strftime('%d %B %Y')}
{'CA Representative: ' + ca_name if ca_name else ''}
""",
            "143(2)": f"""To,
The Assessing Officer (Scrutiny),
Income Tax Department.

Sub: Response to Scrutiny Notice u/s 143(2) for {notice.assessment_year}
Notice No: {notice.notice_no} dated {notice.notice_date}

Respected Sir/Madam,

In response to the above notice for Assessment Year {notice.assessment_year}, I submit:

BACKGROUND:
I, {taxpayer_name} (PAN: {pan}), filed my ITR for AY {notice.assessment_year} declaring total income of ₹[Amount].

POINT-WISE RESPONSE:
[For each query raised in the notice:]
Query: [Copy query from notice]
Response: [Your detailed explanation]
Supporting Documents: [List documents enclosed]

I request a hearing date convenient to the department and am willing to provide additional information if required.

Enclosures:
1. [Document list]

Yours faithfully,
{taxpayer_name} / {ca_name}
Date: {date.today().strftime('%d %B %Y')}
""",
            "148": f"""To,
The Assessing Officer,
Income Tax Department.

Sub: Response to Notice u/s 148 for Assessment Year {notice.assessment_year}
Notice No: {notice.notice_no} dated {notice.notice_date}

Respected Sir/Madam,

1. Objection to Jurisdiction: I hereby object to the issuance of this notice on the following grounds:
   [State reasons: income fully disclosed, no new information, limitation period, etc.]

2. Without prejudice to the above objection, I submit the following:
   [If providing details voluntarily]

Please dispose of my objection before proceeding with the assessment as mandated by the Hon'ble Supreme Court in GKN Driveshafts (India) Ltd. v. ITO [2003] 259 ITR 19 (SC).

Yours faithfully,
{taxpayer_name}
PAN: {pan}
Date: {date.today().strftime('%d %B %Y')}
""",
            "26as_mismatch": f"""To,
The Assessing Officer,
Income Tax Department.

Sub: Explanation for AIS/Form 26AS Mismatch — AY {notice.assessment_year}

I, {taxpayer_name} (PAN: {pan}), submit the following explanation for the discrepancy:

[For each mismatch item:]
Item: [Description]
AIS/26AS Amount: ₹[Amount]
ITR Amount: ₹[Amount]
Explanation: [Reason — e.g., amount is not taxable, duplicate entry, TDS by multiple deductors, etc.]

[If revision needed:]
I am filing a revised ITR u/s 139(5) to address [specific items].

Yours faithfully,
{taxpayer_name}
""",
        }

        return templates.get(ntype, f"""To,
The Assessing Officer,
Income Tax Department.

Sub: Response to Notice u/s {ntype} for {notice.assessment_year}
Notice No: {notice.notice_no}

Respected Sir/Madam,

I, {taxpayer_name} (PAN: {pan}), am in receipt of the above notice dated {notice.notice_date.strftime('%d %B %Y')}.

[PROVIDE POINT-WISE RESPONSE TO EACH QUERY/DEMAND]

I am enclosing relevant documents and request you to consider the same.

Yours faithfully,
{taxpayer_name}
Date: {date.today().strftime('%d %B %Y')}
""")

    def _get_action_steps(self, notice: NoticeDetails) -> List[str]:
        ntype = notice.notice_type.value
        steps: Dict[str, List[str]] = {
            "143(1)": [
                "Review the intimation for each adjustment made",
                "Verify against ITR computation and Form 26AS",
                "If correct, pay demand within 30 days (Challan 280, Code 400)",
                "If incorrect, file rectification u/s 154 within 4 years",
                "Do NOT file revised return for 143(1) corrections — use rectification",
            ],
            "143(2)": [
                "Engage a CA immediately — scrutiny requires professional assistance",
                "Compile all financial records for the assessment year",
                "Attend hearing on scheduled date with all documents",
                "Respond to each query specifically — avoid vague answers",
                "Keep proof of all submissions (acknowledgment slip)",
            ],
            "148": [
                "Do NOT automatically comply — first raise jurisdictional objection",
                "Check limitation period: 3 years (regular), 10 years (>₹50L escaped)",
                "After objection, wait for AO's disposal before filing return",
                "Engage a CA/Advocate with assessment experience",
                "Compile all records for the escapment year",
            ],
            "156": [
                f"Pay demand of ₹{notice.demand_amount:,.0f} within 30 days to avoid interest u/s 220(2)",
                "If demand is disputed, file stay of demand application u/s 220(6)",
                "File appeal to CIT(A) within 30 days if disputing the addition",
                "Pay at least 20% of demand before stay is granted (CBDT circular)",
            ],
        }
        return steps.get(ntype, [
            "Read the notice carefully and note the response deadline",
            "Engage a qualified CA/Tax Consultant",
            "Compile all relevant financial documents",
            "Respond within the stipulated time limit",
            "Retain acknowledgment of all submissions",
        ])

    def _get_escalation_options(self, notice: NoticeDetails) -> List[str]:
        ntype = notice.notice_type.value
        escalations = [
            "Appeal to CIT(A) within 30 days of order under Sec 246A",
            "File appeal to Income Tax Appellate Tribunal (ITAT) against CIT(A) order",
            "Approach Dispute Resolution Panel (DRP) for international transactions",
            "File writ petition before High Court if notice lacks jurisdiction",
            "Approach Faceless Assessment/Appeal unit through e-proceedings portal",
        ]
        if ntype in ("271(1)(c)", "263"):
            escalations.insert(0, "File appeal before CIT(A) against penalty order within 30 days")
        if notice.demand_amount > 10_00_000:
            escalations.insert(0, "Approach Advance Ruling Authority for jurisdictional issues")
        return escalations


def handle_tax_notice(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> date:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError, AttributeError):
                pass
        return date.today()

    notice = NoticeDetails(
        notice_type      = NoticeType(params.get("notice_type", "143(1)")),
        notice_date      = _d(params.get("notice_date", "")),
        assessment_year  = params.get("assessment_year", "AY 2024-25"),
        notice_no        = params.get("notice_no", ""),
        demand_amount    = float(params.get("demand_amount", 0)),
        subject          = params.get("subject"),
    )

    handler  = TaxNoticeHandler()
    response = handler.generate_response(
        notice         = notice,
        taxpayer_name  = params.get("taxpayer_name", "the taxpayer"),
        pan            = params.get("pan", ""),
        ca_name        = params.get("ca_name", ""),
    )

    return asdict(response)
