"""
CA Notice AI — AI-Generated Tax Notice Response Drafts
=======================================================
Generates ready-to-file draft responses for common Income Tax Department
notices served on CA clients. Integrates with tax_notice_handler.py for
notice classification and adds:

  - Full letter drafts (Assessing Officer address, subject, body, salutation)
  - Client-specific facts merged into templates
  - Jurisdiction lookup (AO code → address)
  - Grounds of response library (per notice type)
  - Document annexure checklist
  - Tracking of notice → response workflow status

Supports notice types:
  143(1), 143(2), 142(1), 148/148A, 156, 245, 271(1)(c), 263,
  26AS mismatch, High Value Transaction

Usage:
  from ca_notice_ai import NoticeAI, DraftRequest
  ai = NoticeAI()
  draft = ai.generate_draft(DraftRequest(
      client_name="Ramesh Exports Pvt Ltd",
      pan="AAACR1234C",
      notice_type="143(2)",
      notice_date="2025-02-01",
      ay="AY 2024-25",
      ao_name="ITO Ward 3(1)",
      ao_city="Guntur",
      ...
  ))
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

class ResponseStatus(str, Enum):
    DRAFT    = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FILED    = "filed"


class NoticeUrgency(str, Enum):
    CRITICAL = "critical"   # < 7 days to deadline
    HIGH     = "high"       # 7–14 days
    MEDIUM   = "medium"     # 15–30 days
    LOW      = "low"        # > 30 days


# ---------------------------------------------------------------------------
# AO address library (major IT circles across India)
# ---------------------------------------------------------------------------

_AO_ADDRESSES: Dict[str, str] = {
    "hyderabad": (
        "The Income Tax Officer / Assessing Officer,\n"
        "Income Tax Department,\n"
        "Aayakar Bhavan, Basheer Bagh,\n"
        "Hyderabad — 500 004\n"
        "Telangana"
    ),
    "guntur": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Old Court Complex, Guntur — 522 001\n"
        "Andhra Pradesh"
    ),
    "vijayawada": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Gandhi Nagar, Vijayawada — 520 003\n"
        "Andhra Pradesh"
    ),
    "vizag": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Dwaraka Nagar, Visakhapatnam — 530 016\n"
        "Andhra Pradesh"
    ),
    "chennai": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Aayakar Bhavan, 121 Nungambakkam High Road,\n"
        "Chennai — 600 034\n"
        "Tamil Nadu"
    ),
    "bengaluru": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Aayakar Bhavan, MG Road,\n"
        "Bengaluru — 560 001\n"
        "Karnataka"
    ),
    "mumbai": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Aayakar Bhavan, Maharishi Karve Road,\n"
        "Mumbai — 400 020\n"
        "Maharashtra"
    ),
    "delhi": (
        "The Income Tax Officer,\n"
        "Income Tax Department,\n"
        "Central Revenue Building, IP Estate,\n"
        "New Delhi — 110 002"
    ),
}

def get_ao_address(ao_city: str, ao_name: str = "") -> str:
    base = _AO_ADDRESSES.get(ao_city.lower().strip())
    if base and ao_name:
        # Insert AO designation on first line
        lines = base.split("\n")
        lines[0] = f"{ao_name},"
        lines.insert(1, "Income Tax Officer,")
        return "\n".join(lines)
    return base or f"The Assessing Officer,\nIncome Tax Department,\n{ao_city}"


# ---------------------------------------------------------------------------
# Grounds library — standard legal grounds per notice type
# ---------------------------------------------------------------------------

_GROUNDS: Dict[str, List[str]] = {
    "143(1)": [
        "The adjustment proposed under section 143(1) is without jurisdiction as the returned income "
        "correctly reflects all income and deductions as per law.",
        "The TDS credits as per Form 26AS and AIS have been correctly claimed. Any mismatch is due to "
        "delay in uploading by the deductor and not attributable to the assessee.",
        "The disallowance of deduction under section {deduction_section} is contrary to law as all "
        "conditions precedent have been duly fulfilled.",
        "The assessee reserves the right to raise additional grounds at the time of personal hearing.",
    ],
    "143(2)": [
        "The assessee submits that all income chargeable to tax has been duly disclosed in the return "
        "of income filed for {ay}.",
        "The books of accounts and supporting documents are maintained in proper order and reflect the "
        "true and correct state of affairs.",
        "All deductions and exemptions claimed are in accordance with the provisions of the Income Tax "
        "Act, 1961 as amended up to Finance Act 2024.",
        "The assessee prays that the assessment be completed on the basis of the return of income filed "
        "and no adverse inference be drawn.",
        "The assessee reserves the right to submit additional documents and raise additional grounds "
        "at the time of personal hearing.",
    ],
    "142(1)": [
        "The assessee has furnished all information and documents as called for under the notice.",
        "The information furnished is true and complete to the best of the assessee's knowledge and belief.",
        "The books of accounts have been maintained as per the requirements of section 44AA of the Act.",
    ],
    "148": [
        "The notice under section 148 is bad in law as the conditions precedent under section 147 "
        "are not satisfied — there is no reason to believe that income chargeable to tax has escaped assessment.",
        "The reopening beyond 4 years is barred by limitation as there was no failure to disclose "
        "material facts truly and fully at the time of original assessment.",
        "The 'reasons to believe' furnished do not constitute tangible material and are based solely "
        "on change of opinion, which is not permissible under law.",
        "The assessee specifically requests supply of the 'reasons recorded' before complying with "
        "the notice, as held by the Hon'ble Supreme Court in GKN Driveshafts (India) Ltd.",
        "Without prejudice to the above, all income has been correctly disclosed in the original "
        "return of income.",
    ],
    "148A": [
        "The show cause notice under section 148A is misconceived as the information cited does not "
        "constitute 'information' as defined under Explanation 1 to section 148 inserted by Finance Act 2021.",
        "The alleged escaped income is fully explained and was disclosed in the original return / "
        "AIS / Form 26AS of the relevant assessment year.",
        "The assessee prays that no notice under section 148 be issued and the proceedings be dropped.",
    ],
    "156": [
        "The demand raised vide the above notice is incorrect and the assessee respectfully submits "
        "that the same be stayed pending rectification / appeal.",
        "TDS credit of ₹{tds_amount} as per Form 26AS has not been given credit for, which if allowed "
        "will reduce/extinguish the demand.",
        "Advance tax of ₹{advance_tax} paid as per challan details furnished herewith has not been "
        "properly adjusted against the demand.",
        "The assessee intends to file a rectification petition under section 154 of the Act.",
    ],
    "245": [
        "The refund adjustment proposed under section 245 is objected to as the underlying demand "
        "for {demand_ay} is disputed and an appeal is pending before CIT(A) / ITAT.",
        "The assessee prays that the refund due for {refund_ay} be released forthwith without "
        "adjustment against the disputed demand.",
        "Without prejudice, if any adjustment is to be made, it may be restricted to the undisputed "
        "portion of the demand only.",
    ],
    "271(1)(c)": [
        "The penalty proceedings under section 271(1)(c) are not maintainable as the assessee has "
        "neither concealed income nor furnished inaccurate particulars of income.",
        "The addition made in the assessment order was based on a difference of opinion on a debatable "
        "legal issue and not on account of any concealment.",
        "The assessee relies on the decision of the Hon'ble Supreme Court in CIT v. Reliance Petro "
        "Products Ltd (2010) that mere making of a claim which is not sustainable does not constitute "
        "furnishing of inaccurate particulars.",
        "The penalty, if any, cannot exceed the tax sought to be evaded under the amended provisions "
        "of section 271(1)(c) after Finance Act 2016.",
    ],
    "263": [
        "The revision proceedings under section 263 are without jurisdiction as the order sought to be "
        "revised is neither erroneous nor prejudicial to the interests of Revenue.",
        "The Assessing Officer had examined the issue in question during the original assessment "
        "proceedings and the order is based on a permissible view.",
        "The assessee relies on the principle that revision under section 263 cannot be used as a "
        "tool of review of the AO's order where two views are possible.",
    ],
    "26as_mismatch": [
        "The mismatch between AIS / Form 26AS and the return of income is explained as follows:\n"
        "  (a) Certain entries in AIS relate to non-taxable receipts / receipts already included in "
        "taxable income under a different head.\n"
        "  (b) Some deductors have incorrectly uploaded TDS data which is being rectified.",
        "The assessee has filed a feedback / correction on the AIS portal for the disputed entries.",
        "The actual income chargeable to tax is as disclosed in the return and the AIS entries do "
        "not represent additional income.",
    ],
    "high_value_transaction": [
        "The high value transaction flagged in the notice is fully explained:\n"
        "  (a) The amount represents {transaction_description}, which is not income but a capital/loan receipt.\n"
        "  (b) The transaction is duly recorded in books of accounts and bank statements.",
        "The assessee is a regular filer and has been disclosing all income accurately in returns "
        "filed for the past {filing_years} years.",
        "The assessee prays that the proceedings be dropped and no adverse action be taken.",
    ],
}

# Documents required per notice type
_DOCS_REQUIRED: Dict[str, List[str]] = {
    "143(1)": [
        "Copy of ITR filed for the relevant AY with acknowledgement",
        "Form 26AS / AIS for the relevant AY",
        "TDS certificates (Form 16 / 16A)",
        "Bank statements for the relevant FY",
        "Investment proof supporting deductions claimed",
    ],
    "143(2)": [
        "Copy of ITR filed with acknowledgement",
        "Books of accounts (ledgers, cash book, bank book)",
        "Form 26AS / AIS / TIS",
        "Supporting for all income reported (salary slips, P&L, rent receipts)",
        "Supporting for deductions / exemptions (investment proofs, home loan certificate)",
        "Bank statements for the relevant FY",
        "Details of all bank accounts held during the year",
        "Audited financial statements (if applicable)",
    ],
    "142(1)": [
        "Documents as specifically called for in the notice",
        "Books of accounts and bank statements",
        "ITR and computation of income",
    ],
    "148": [
        "Original return filed for the year under reassessment",
        "Computation of income",
        "Books of accounts for the relevant year",
        "Form 26AS for the relevant year",
        "Any correspondence with the department for the original assessment",
    ],
    "148A": [
        "Explanation letter addressing the specific information cited",
        "Supporting documents for the amount/transaction cited",
        "Original ITR for the year in question",
    ],
    "156": [
        "Copy of assessment order raising the demand",
        "Advance tax payment challans (Form 280)",
        "TDS certificates and Form 26AS",
        "Bank statements showing advance tax / self-assessment tax payments",
    ],
    "245": [
        "Copy of refund order for the AY where refund is due",
        "Copy of demand order for the AY where demand exists",
        "Appeal filing acknowledgement (if demand is under appeal)",
        "Bank account details for refund credit",
    ],
    "271(1)(c)": [
        "Copy of assessment order and penalty notice",
        "Written submissions explaining the addition made",
        "Case law supporting the assessee's position",
        "Computation of income original vs assessed",
    ],
    "263": [
        "Copy of original assessment order",
        "All documents furnished during original assessment",
        "Written submissions on each issue cited in 263 notice",
    ],
    "26as_mismatch": [
        "AIS / Form 26AS for the year",
        "Bank statements explaining each highlighted transaction",
        "Feedback / correction filed on AIS portal (screenshot)",
        "Correspondence with deductors to correct TDS data",
    ],
    "high_value_transaction": [
        "Bank statements showing the flagged transaction",
        "Source of funds (loan agreement / sale deed / inheritance documents)",
        "ITR filed for the relevant AY",
        "PAN of counter-parties where applicable",
    ],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DraftRequest:
    client_name:   str
    pan:           str
    notice_type:   str          # e.g. "143(2)"
    notice_date:   str          # ISO date
    ay:            str          # e.g. "AY 2024-25"
    ao_name:       str          # e.g. "ITO Ward 3(1), Guntur"
    ao_city:       str          # e.g. "guntur"
    client_address: str         = ""
    ca_name:       str          = ""
    ca_membership: str          = ""   # ICAI membership number
    ca_firm:       str          = ""
    ca_city:       str          = ""

    # Optional context merged into grounds
    extra_facts:   Dict[str, str] = field(default_factory=dict)
    # e.g. {"tds_amount": "₹45,000", "deduction_section": "80D", "ay": "AY 2024-25"}

    # Override deadline days (default from notice type)
    deadline_override_days: Optional[int] = None


@dataclass
class NoticeDraft:
    draft_id:       str
    client_name:    str
    pan:            str
    notice_type:    str
    ay:             str
    notice_date:    str
    response_deadline: str
    urgency:        NoticeUrgency
    status:         ResponseStatus
    letter_text:    str
    grounds:        List[str]
    docs_required:  List[str]
    annexures:      List[str]   # "Annexure A — Form 26AS" etc.
    notes:          str         = ""


# ---------------------------------------------------------------------------
# Response deadline map (days from notice date)
# ---------------------------------------------------------------------------

_DEADLINE_DAYS: Dict[str, int] = {
    "143(1)":                 30,
    "143(2)":                 30,
    "142(1)":                 15,
    "148":                    30,
    "148A":                   7,
    "156":                    30,
    "245":                    30,
    "271(1)(c)":              30,
    "263":                    30,
    "264":                    30,
    "26as_mismatch":          15,
    "high_value_transaction": 15,
    "custom":                 30,
}


# ---------------------------------------------------------------------------
# Draft generator
# ---------------------------------------------------------------------------

class NoticeAI:
    """
    Generates AI-drafted response letters for IT notices.
    Merges client-specific facts into ground templates.
    """

    def generate_draft(self, req: DraftRequest) -> NoticeDraft:
        import hashlib, time
        draft_id = hashlib.md5(f"{req.pan}{req.notice_type}{req.notice_date}".encode()).hexdigest()[:12]

        # Compute deadline
        notice_dt = date.fromisoformat(req.notice_date)
        days      = req.deadline_override_days or _DEADLINE_DAYS.get(req.notice_type, 30)
        deadline  = notice_dt + timedelta(days=days)
        today     = date.today()
        days_left = (deadline - today).days

        if days_left < 7:
            urgency = NoticeUrgency.CRITICAL
        elif days_left < 14:
            urgency = NoticeUrgency.HIGH
        elif days_left < 30:
            urgency = NoticeUrgency.MEDIUM
        else:
            urgency = NoticeUrgency.LOW

        # Build grounds with fact substitution
        raw_grounds = _GROUNDS.get(req.notice_type, _GROUNDS.get("143(2)", []))
        grounds = []
        for g in raw_grounds:
            try:
                merged = g.format(ay=req.ay, **req.extra_facts)
            except KeyError:
                merged = g
            grounds.append(merged)

        docs = _DOCS_REQUIRED.get(req.notice_type, [
            "Copy of ITR with acknowledgement",
            "Form 26AS / AIS",
            "Bank statements for the relevant FY",
        ])

        annexures = [f"Annexure {chr(65 + i)} — {d}" for i, d in enumerate(docs)]

        letter = self._compose_letter(req, grounds, annexures, deadline)

        return NoticeDraft(
            draft_id         = draft_id,
            client_name      = req.client_name,
            pan              = req.pan,
            notice_type      = req.notice_type,
            ay               = req.ay,
            notice_date      = req.notice_date,
            response_deadline= deadline.isoformat(),
            urgency          = urgency,
            status           = ResponseStatus.DRAFT,
            letter_text      = letter,
            grounds          = grounds,
            docs_required    = docs,
            annexures        = annexures,
        )

    def _compose_letter(self, req: DraftRequest, grounds: List[str],
                        annexures: List[str], deadline: date) -> str:
        today_str = date.today().strftime("%d %B %Y")
        ao_addr   = get_ao_address(req.ao_city, req.ao_name)

        grounds_text = "\n\n".join(
            f"  {i + 1}. {g}" for i, g in enumerate(grounds)
        )
        annexure_list = "\n".join(f"  {a}" for a in annexures)

        ca_block = ""
        if req.ca_name:
            ca_block = (
                f"\nFor {req.ca_firm or 'Chartered Accountants'}\n\n\n"
                f"{req.ca_name}\n"
                f"Chartered Accountant\n"
                f"Membership No. {req.ca_membership or 'XXXXXXXXX'}\n"
                f"Place: {req.ca_city or req.ao_city}\n"
                f"Date: {today_str}"
            )
        else:
            ca_block = (
                f"\nYours faithfully,\n\n\n"
                f"(Authorised Signatory)\n"
                f"For {req.client_name}\n"
                f"PAN: {req.pan}\n"
                f"Date: {today_str}"
            )

        return f"""
{today_str}

To,
{ao_addr}

Sub: Response to Notice under Section {req.notice_type} of the Income Tax Act, 1961
     Assessment Year: {req.ay}
     PAN: {req.pan}
     Assessee: {req.client_name}

Ref: Notice dated {req.notice_date} issued under section {req.notice_type}

Respected Sir/Madam,

We write with reference to the above-mentioned notice issued by your
good office. The assessee {req.client_name} (PAN: {req.pan}) respectfully
submits its response as under:

GROUNDS OF RESPONSE
-------------------
{grounds_text}

DOCUMENTS ENCLOSED
------------------
The following documents are enclosed in support of the above submissions:

{annexure_list}

PRAYER
------
In view of the foregoing submissions and documents, it is most respectfully
prayed that the proceedings initiated vide the above notice be dropped /
decided favourably in the assessee's interest.

The assessee shall make itself available for a personal hearing if deemed
necessary by the Honourable Assessing Officer. We request that adequate
notice be given for the same.

Thanking you,

{ca_block}

Encl: As above ({len(annexures)} annexures)
""".strip()


# ---------------------------------------------------------------------------
# Notice tracking
# ---------------------------------------------------------------------------

@dataclass
class NoticeRecord:
    notice_id:    str
    client_id:    str
    client_name:  str
    pan:          str
    notice_type:  str
    notice_date:  str
    ay:           str
    response_due: str
    status:       ResponseStatus = ResponseStatus.DRAFT
    draft_id:     Optional[str]  = None
    filed_date:   Optional[str]  = None
    notes:        str            = ""


class NoticeTracker:
    """Tracks all pending notices across the CA's client portfolio."""

    def __init__(self):
        self._notices: Dict[str, NoticeRecord] = {}  # notice_id → record
        self._ai      = NoticeAI()

    def add_notice(
        self,
        client_id:   str,
        client_name: str,
        pan:         str,
        notice_type: str,
        notice_date: str,
        ay:          str,
        ao_name:     str = "",
        ao_city:     str = "hyderabad",
        ca_name:     str = "",
        ca_firm:     str = "",
        ca_membership: str = "",
        extra_facts: Optional[Dict] = None,
    ) -> NoticeDraft:
        import hashlib
        nid = hashlib.md5(f"{pan}{notice_type}{notice_date}".encode()).hexdigest()[:10]

        req = DraftRequest(
            client_name   = client_name,
            pan           = pan,
            notice_type   = notice_type,
            notice_date   = notice_date,
            ay            = ay,
            ao_name       = ao_name,
            ao_city       = ao_city,
            ca_name       = ca_name,
            ca_firm       = ca_firm,
            ca_membership = ca_membership,
            extra_facts   = extra_facts or {},
        )
        draft = self._ai.generate_draft(req)

        days      = _DEADLINE_DAYS.get(notice_type, 30)
        response_due = (date.fromisoformat(notice_date) + timedelta(days=days)).isoformat()

        self._notices[nid] = NoticeRecord(
            notice_id    = nid,
            client_id    = client_id,
            client_name  = client_name,
            pan          = pan,
            notice_type  = notice_type,
            notice_date  = notice_date,
            ay           = ay,
            response_due = response_due,
            draft_id     = draft.draft_id,
        )
        return draft

    def mark_filed(self, notice_id: str, filed_date: str):
        if notice_id in self._notices:
            self._notices[notice_id].status      = ResponseStatus.FILED
            self._notices[notice_id].filed_date  = filed_date

    def get_pending(self) -> List[NoticeRecord]:
        today = date.today()
        pending = [n for n in self._notices.values()
                   if n.status != ResponseStatus.FILED]
        pending.sort(key=lambda n: n.response_due)
        return pending

    def portfolio_notice_summary(self) -> Dict:
        all_n   = list(self._notices.values())
        pending = [n for n in all_n if n.status != ResponseStatus.FILED]
        today   = date.today()
        critical= [n for n in pending
                   if (date.fromisoformat(n.response_due) - today).days < 7]
        return {
            "total_notices":  len(all_n),
            "pending":        len(pending),
            "filed":          len(all_n) - len(pending),
            "critical_7days": len(critical),
            "critical":       [asdict(n) for n in critical],
        }


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_tracker = NoticeTracker()

def ca_notice_ai(params: dict) -> dict:
    action = params.get("action", "draft")
    try:
        if action == "draft":
            req = DraftRequest(
                client_name    = params["client_name"],
                pan            = params["pan"],
                notice_type    = params["notice_type"],
                notice_date    = params["notice_date"],
                ay             = params.get("ay", "AY 2024-25"),
                ao_name        = params.get("ao_name", ""),
                ao_city        = params.get("ao_city", "hyderabad"),
                ca_name        = params.get("ca_name", ""),
                ca_firm        = params.get("ca_firm", ""),
                ca_membership  = params.get("ca_membership", ""),
                extra_facts    = params.get("extra_facts", {}),
            )
            draft = NoticeAI().generate_draft(req)
            return asdict(draft)

        elif action == "add_notice":
            draft = _tracker.add_notice(
                client_id    = params["client_id"],
                client_name  = params["client_name"],
                pan          = params["pan"],
                notice_type  = params["notice_type"],
                notice_date  = params["notice_date"],
                ay           = params.get("ay", "AY 2024-25"),
                ao_name      = params.get("ao_name", ""),
                ao_city      = params.get("ao_city", "hyderabad"),
                ca_name      = params.get("ca_name", ""),
                ca_firm      = params.get("ca_firm", ""),
                ca_membership= params.get("ca_membership", ""),
                extra_facts  = params.get("extra_facts", {}),
            )
            return asdict(draft)

        elif action == "mark_filed":
            _tracker.mark_filed(params["notice_id"], params["filed_date"])
            return {"success": True}

        elif action == "pending":
            return {"pending": [asdict(n) for n in _tracker.get_pending()]}

        elif action == "summary":
            return _tracker.portfolio_notice_summary()

        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
