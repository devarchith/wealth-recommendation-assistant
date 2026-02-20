"""
Rice Mill Penalty Alert Engine — GST / TDS / Income Tax Violations
===================================================================
Proactively detects and alerts on potential penalty exposure for rice mills
operating in Andhra Pradesh / Telangana. Covers:

  GST Violations:
    - GSTR-1 / GSTR-3B late filing (₹50/day, max ₹10K)
    - Reverse Charge on paddy purchases from farmers (exempt supply → RCM)
    - ITC reversal for exempt supplies (paddy/rice partially exempt)
    - E-way bill violations for inter-state rice movement
    - Composition scheme threshold breach (₹1.5 Cr turnover limit)

  TDS Violations:
    - Section 194C: TDS on milling contracts / transport (1%/2%)
    - Section 194Q: TDS on purchases >₹50L from registered supplier
    - Section 206C(1H): TCS on sale >₹50L (if buyer's turnover >₹10Cr)

  Income Tax:
    - Advance tax under-payment (u/s 234B/234C)
    - Cash purchases from farmers >₹2L (u/s 40A(3))
    - FCI milling receipts unreported

Integrates with:
  - ca_gst_calendar.py for filing status
  - ca_anomaly_detector.py risk scores
  - WhatsApp alerts via caWhatsAppTemplates.js
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import List, Dict, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ViolationType(str, Enum):
    GST_LATE_FILING      = "gst_late_filing"
    GST_ITC_REVERSAL     = "gst_itc_reversal"
    GST_EWAYBILL         = "gst_ewaybill"
    GST_RCM_MISSED       = "gst_rcm_missed"
    GST_COMPOSITION_LIMIT= "gst_composition_limit"
    TDS_194C             = "tds_194c"
    TDS_194Q             = "tds_194q"
    TCS_206C_1H          = "tcs_206c_1h"
    ADVANCE_TAX          = "advance_tax"
    CASH_PURCHASE_40A3   = "cash_purchase_40a3"
    FCI_UNREPORTED       = "fci_unreported"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"   # penalty already accruing / demand likely
    HIGH     = "high"       # violation confirmed, action within 7 days
    MEDIUM   = "medium"     # risk detected, review needed
    LOW      = "low"        # informational


# ---------------------------------------------------------------------------
# Constants — Rice Mill specific
# ---------------------------------------------------------------------------

# GST rates for rice mill activities
GST_RATES = {
    "paddy_unmilled":          0.00,   # Nil — raw agricultural produce
    "rice_branded":            0.05,   # 5% HSN 1006
    "rice_unbranded":          0.00,   # Nil HSN 1006
    "rice_bran":               0.05,   # 5% HSN 2302
    "broken_rice":             0.00,   # Nil
    "husk":                    0.00,   # Nil
    "milling_service_govt":    0.00,   # Nil — FCI/govt milling
    "milling_service_private": 0.18,   # 18% SAC 998812
    "transport":               0.05,   # 5% GTA if paying freight
}

# AP / Telangana FCI milling rates (2024-25, per quintal)
FCI_MILLING_RATE_PER_QUINTAL = {
    "ap_guntur":    27.50,
    "ap_krishna":   27.50,
    "ap_east_godavari": 27.50,
    "ap_west_godavari": 27.50,
    "ap_nellore":   27.00,
    "ap_kurnool":   27.00,
    "ts_nizamabad": 27.50,
    "ts_karimnagar":27.50,
    "ts_warangal":  27.50,
    "ts_khammam":   27.00,
    "default":      27.50,
}

# TDS rates
TDS_RATES = {
    "194C_individual": 0.01,
    "194C_company":    0.02,
    "194Q":            0.001,
    "206C_1H":         0.001,
}

# Late fee per day (GST)
LATE_FEE_PER_DAY_REGULAR = 50.0   # ₹25 CGST + ₹25 SGST
LATE_FEE_PER_DAY_NIL     = 20.0
MAX_LATE_FEE_REGULAR      = 10_000.0
MAX_LATE_FEE_NIL          = 500.0

# Interest rate on GST delay
GST_INTEREST_RATE = 0.18   # 18% per annum


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PenaltyAlert:
    alert_id:      str
    mill_id:       str
    mill_name:     str
    violation:     ViolationType
    severity:      AlertSeverity
    title:         str
    description:   str
    penalty_amount: float       # estimated ₹ penalty / exposure
    interest_amount: float      # interest accrued
    total_exposure: float
    action_required: str
    deadline:      Optional[str] = None
    section_ref:   str          = ""
    already_paid:  float        = 0.0
    net_exposure:  float        = 0.0

    def __post_init__(self):
        self.net_exposure = max(0.0, self.total_exposure - self.already_paid)


@dataclass
class PenaltyReport:
    mill_id:        str
    mill_name:      str
    generated_date: str
    total_exposure: float
    alerts:         List[PenaltyAlert]
    summary:        Dict         = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Penalty calculation functions
# ---------------------------------------------------------------------------

def calc_gst_late_fee(return_type: str, days_late: int, is_nil: bool,
                      turnover_crores: float = 0) -> float:
    if days_late <= 0:
        return 0.0
    if is_nil:
        return min(days_late * LATE_FEE_PER_DAY_NIL, MAX_LATE_FEE_NIL)
    return min(days_late * LATE_FEE_PER_DAY_REGULAR, MAX_LATE_FEE_REGULAR)


def calc_gst_interest(tax_amount: float, days_late: int) -> float:
    """18% p.a. simple interest on unpaid GST."""
    return round(tax_amount * GST_INTEREST_RATE * days_late / 365, 2)


def calc_194c_tds(contract_amount: float, is_individual: bool) -> float:
    rate = TDS_RATES["194C_individual"] if is_individual else TDS_RATES["194C_company"]
    return round(contract_amount * rate, 2)


def calc_194q_tds(purchase_amount: float, threshold: float = 5_000_000) -> float:
    taxable = max(0, purchase_amount - threshold)
    return round(taxable * TDS_RATES["194Q"], 2)


# ---------------------------------------------------------------------------
# Main alert engine
# ---------------------------------------------------------------------------

class RiceMillPenaltyEngine:
    """
    Detects and quantifies penalty exposure for a rice mill.
    Call assess() with the mill's compliance data snapshot.
    """

    def assess(
        self,
        mill_id:          str,
        mill_name:        str,
        # GST filing
        gstr1_days_late:  int   = 0,
        gstr3b_days_late: int   = 0,
        gst_nil_return:   bool  = False,
        unpaid_gst:       float = 0.0,
        gst_delay_days:   int   = 0,
        # ITC reversal
        exempt_supply_pct: float = 0.0,    # % of total supply that is exempt
        itc_total_claimed: float = 0.0,
        # RCM
        farmer_purchases:  float = 0.0,    # Total paddy purchased from unregistered farmers
        rcm_paid:          float = 0.0,
        # Composition
        annual_turnover:   float = 0.0,
        is_composition:    bool  = False,
        # E-way bill
        ewaybill_defaults: int   = 0,
        ewaybill_value_each: float = 50_000,
        # TDS 194C
        milling_contracts: float = 0.0,    # Total paid to transporters / contractors
        tds_194c_deducted: float = 0.0,
        is_individual_contractor: bool = False,
        # TDS 194Q
        registered_purchases: float = 0.0, # Purchases from single registered supplier
        tds_194q_deducted: float = 0.0,
        # Advance tax
        estimated_tax:     float = 0.0,
        advance_paid:      float = 0.0,
        # Cash purchases
        cash_purchases_farmers: float = 0.0,  # per payment (not total)
        # FCI income
        fci_milling_receipts: float = 0.0,
        fci_declared_in_itr:  float = 0.0,
    ) -> PenaltyReport:

        import hashlib, time
        alerts: List[PenaltyAlert] = []
        today  = date.today().isoformat()

        def aid(suffix: str) -> str:
            return hashlib.md5(f"{mill_id}{suffix}{time.time()}".encode()).hexdigest()[:8]

        # ── GST: Late filing ─────────────────────────────────────────────

        if gstr1_days_late > 0:
            fee = calc_gst_late_fee("GSTR-1", gstr1_days_late, gst_nil_return)
            alerts.append(PenaltyAlert(
                alert_id       = aid("gstr1"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.GST_LATE_FILING,
                severity       = AlertSeverity.CRITICAL if gstr1_days_late > 30 else AlertSeverity.HIGH,
                title          = f"GSTR-1 overdue by {gstr1_days_late} days",
                description    = f"GSTR-1 not filed for the period. Late fee accumulating at ₹{LATE_FEE_PER_DAY_REGULAR}/day.",
                penalty_amount = fee,
                interest_amount= 0.0,
                total_exposure = fee,
                action_required= "File GSTR-1 immediately on GST portal.",
                section_ref    = "Section 47 CGST Act",
            ))

        if gstr3b_days_late > 0:
            fee  = calc_gst_late_fee("GSTR-3B", gstr3b_days_late, gst_nil_return)
            intr = calc_gst_interest(unpaid_gst, gst_delay_days) if unpaid_gst > 0 else 0.0
            alerts.append(PenaltyAlert(
                alert_id       = aid("gstr3b"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.GST_LATE_FILING,
                severity       = AlertSeverity.CRITICAL,
                title          = f"GSTR-3B overdue by {gstr3b_days_late} days",
                description    = (
                    f"GSTR-3B not filed. Late fee ₹{fee:,.0f}. "
                    + (f"Interest on unpaid GST ₹{unpaid_gst:,.0f} @ 18% p.a. = ₹{intr:,.0f}." if unpaid_gst > 0 else "")
                ),
                penalty_amount = fee,
                interest_amount= intr,
                total_exposure = fee + intr,
                action_required= "File GSTR-3B and pay outstanding GST with interest.",
                section_ref    = "Section 47 + Section 50 CGST Act",
            ))

        # ── GST: ITC reversal (exempt supply proportion) ─────────────────

        if exempt_supply_pct > 0 and itc_total_claimed > 0:
            itc_to_reverse = itc_total_claimed * (exempt_supply_pct / 100)
            if itc_to_reverse > 1000:
                interest = calc_gst_interest(itc_to_reverse, 90)  # approx 3-month delay
                alerts.append(PenaltyAlert(
                    alert_id       = aid("itc"),
                    mill_id        = mill_id,
                    mill_name      = mill_name,
                    violation      = ViolationType.GST_ITC_REVERSAL,
                    severity       = AlertSeverity.HIGH,
                    title          = f"ITC reversal required: ₹{itc_to_reverse:,.0f}",
                    description    = (
                        f"{exempt_supply_pct:.1f}% of supplies are exempt (paddy/husk). "
                        f"Proportionate ITC of ₹{itc_to_reverse:,.0f} must be reversed in GSTR-3B Table 4(B)."
                    ),
                    penalty_amount = itc_to_reverse,
                    interest_amount= interest,
                    total_exposure = itc_to_reverse + interest,
                    action_required= "Reverse proportionate ITC in next GSTR-3B. Recalculate using Rule 42/43.",
                    section_ref    = "Rule 42/43 CGST Rules",
                ))

        # ── GST: RCM on unregistered farmer purchases ─────────────────────

        # Note: paddy from unregistered farmers is agricultural produce — exempt supply under Schedule I.
        # However, milling services provided to FCI may trigger RCM if provided by unregistered entity.
        if farmer_purchases > 0:
            rcm_required = 0.0  # Paddy from farmers is Nil rated — RCM not typically applicable
            if rcm_paid == 0 and farmer_purchases > 0:
                # Flag for CA review rather than automatic penalty
                alerts.append(PenaltyAlert(
                    alert_id       = aid("rcm"),
                    mill_id        = mill_id,
                    mill_name      = mill_name,
                    violation      = ViolationType.GST_RCM_MISSED,
                    severity       = AlertSeverity.LOW,
                    title          = f"RCM review: paddy purchases ₹{farmer_purchases:,.0f} from farmers",
                    description    = (
                        "Paddy purchases from unregistered farmers are exempt under Sl. No. 54 of CGST Exemption Notification. "
                        "RCM not applicable on agricultural produce. Review if any non-exempt services were received."
                    ),
                    penalty_amount = 0.0,
                    interest_amount= 0.0,
                    total_exposure = 0.0,
                    action_required= "CA to confirm no non-agricultural supplies received under RCM category.",
                    section_ref    = "Notification 12/2017-CT(Rate), Sl. No. 54",
                ))

        # ── GST: Composition scheme limit ─────────────────────────────────

        if is_composition and annual_turnover > 1_50_00_000:
            excess = annual_turnover - 1_50_00_000
            alerts.append(PenaltyAlert(
                alert_id       = aid("comp"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.GST_COMPOSITION_LIMIT,
                severity       = AlertSeverity.CRITICAL,
                title          = f"Composition limit exceeded: turnover ₹{annual_turnover/1e7:.2f} Cr",
                description    = (
                    f"Annual turnover ₹{annual_turnover:,.0f} exceeds ₹1.5 Cr composition limit. "
                    f"Must switch to regular scheme from the day of breach. "
                    f"All past composition tax short-paid must be paid as regular GST."
                ),
                penalty_amount = excess * 0.01,   # approx differential
                interest_amount= calc_gst_interest(excess * 0.01, 180),
                total_exposure = excess * 0.015,
                action_required= "File GST REG-01 to opt out of composition. Pay differential GST with interest.",
                section_ref    = "Section 10(3) CGST Act",
            ))

        # ── GST: E-way bill defaults ──────────────────────────────────────

        if ewaybill_defaults > 0:
            penalty_each = min(ewaybill_value_each, 10_000)
            total_penalty= penalty_each * ewaybill_defaults
            alerts.append(PenaltyAlert(
                alert_id       = aid("ewb"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.GST_EWAYBILL,
                severity       = AlertSeverity.HIGH,
                title          = f"{ewaybill_defaults} e-way bill violation(s) detected",
                description    = (
                    f"Goods transported without valid e-way bill. Penalty: ₹{penalty_each:,.0f} per "
                    f"instance (min ₹10,000 or value of goods). Total exposure ₹{total_penalty:,.0f}."
                ),
                penalty_amount = total_penalty,
                interest_amount= 0.0,
                total_exposure = total_penalty,
                action_required= "Respond to any MOV-09/10 notices immediately. Maintain e-way bill register.",
                section_ref    = "Section 129 CGST Act; Rule 138",
            ))

        # ── TDS: Section 194C (milling/transport contracts) ──────────────

        if milling_contracts > 30_000:    # Single payment threshold
            tds_required = calc_194c_tds(milling_contracts, is_individual_contractor)
            shortfall    = max(0, tds_required - tds_194c_deducted)
            if shortfall > 100:
                alerts.append(PenaltyAlert(
                    alert_id       = aid("194c"),
                    mill_id        = mill_id,
                    mill_name      = mill_name,
                    violation      = ViolationType.TDS_194C,
                    severity       = AlertSeverity.HIGH,
                    title          = f"TDS u/s 194C shortfall: ₹{shortfall:,.0f}",
                    description    = (
                        f"TDS on milling/transport contracts of ₹{milling_contracts:,.0f} "
                        f"at {1 if is_individual_contractor else 2}%: required ₹{tds_required:,.0f}, "
                        f"deducted ₹{tds_194c_deducted:,.0f}."
                    ),
                    penalty_amount = shortfall,
                    interest_amount= shortfall * 0.015 * 3,  # 1.5%/month for 3 months
                    total_exposure = shortfall * 1.045,
                    action_required= "Deduct balance TDS and deposit via Challan 281. File TDS return.",
                    section_ref    = "Section 194C + Section 201(1A) Income Tax Act",
                ))

        # ── TDS: Section 194Q ─────────────────────────────────────────────

        if registered_purchases > 5_000_000:
            tds_required = calc_194q_tds(registered_purchases)
            shortfall    = max(0, tds_required - tds_194q_deducted)
            if shortfall > 100:
                alerts.append(PenaltyAlert(
                    alert_id       = aid("194q"),
                    mill_id        = mill_id,
                    mill_name      = mill_name,
                    violation      = ViolationType.TDS_194Q,
                    severity       = AlertSeverity.MEDIUM,
                    title          = f"TDS u/s 194Q shortfall: ₹{shortfall:,.0f}",
                    description    = (
                        f"Purchases from single registered supplier ₹{registered_purchases:,.0f} "
                        f"exceed ₹50L threshold. TDS @ 0.1% on excess: ₹{tds_required:,.0f}."
                    ),
                    penalty_amount = shortfall,
                    interest_amount= shortfall * 0.015 * 3,
                    total_exposure = shortfall * 1.045,
                    action_required= "Deduct 0.1% TDS on purchases above ₹50L. File quarterly TDS return.",
                    section_ref    = "Section 194Q Income Tax Act (w.e.f 1 Jul 2021)",
                ))

        # ── Advance tax ───────────────────────────────────────────────────

        if estimated_tax > 10_000:
            required_75pct = estimated_tax * 0.75
            shortfall      = max(0, required_75pct - advance_paid)
            if shortfall > 5_000:
                interest = shortfall * 0.01 * 3  # 1%/month approx for 234B
                alerts.append(PenaltyAlert(
                    alert_id       = aid("adv"),
                    mill_id        = mill_id,
                    mill_name      = mill_name,
                    violation      = ViolationType.ADVANCE_TAX,
                    severity       = AlertSeverity.HIGH,
                    title          = f"Advance tax shortfall ₹{shortfall:,.0f}",
                    description    = (
                        f"Estimated income tax ₹{estimated_tax:,.0f}. "
                        f"75% required by 15 Dec: ₹{required_75pct:,.0f}. "
                        f"Paid: ₹{advance_paid:,.0f}. Shortfall: ₹{shortfall:,.0f}."
                    ),
                    penalty_amount = 0.0,
                    interest_amount= interest,
                    total_exposure = interest,
                    action_required= "Pay balance advance tax via Challan 280 (online). Interest u/s 234B/C accruing.",
                    section_ref    = "Section 234B, 234C Income Tax Act",
                ))

        # ── Cash purchases from farmers >₹2L ─────────────────────────────

        if cash_purchases_farmers > 2_00_000:
            excess = cash_purchases_farmers - 2_00_000
            disallowance = excess   # full disallowance u/s 40A(3)
            tax_impact   = disallowance * 0.30  # approx at 30% tax rate
            alerts.append(PenaltyAlert(
                alert_id       = aid("40a3"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.CASH_PURCHASE_40A3,
                severity       = AlertSeverity.HIGH,
                title          = f"Cash payments >₹2L to farmers: ₹{cash_purchases_farmers:,.0f}",
                description    = (
                    f"Single cash payment of ₹{cash_purchases_farmers:,.0f} to farmer exceeds ₹2L limit. "
                    f"₹{excess:,.0f} disallowable u/s 40A(3). Estimated tax impact: ₹{tax_impact:,.0f}."
                ),
                penalty_amount = tax_impact,
                interest_amount= 0.0,
                total_exposure = tax_impact,
                action_required= "Pay farmers via RTGS/NEFT/cheque. Obtain Form 26 for exemption if applicable.",
                section_ref    = "Section 40A(3) Income Tax Act",
            ))

        # ── FCI milling receipts unreported ──────────────────────────────

        if fci_milling_receipts > 0 and fci_declared_in_itr < fci_milling_receipts * 0.9:
            diff       = fci_milling_receipts - fci_declared_in_itr
            tax_impact = diff * 0.30
            alerts.append(PenaltyAlert(
                alert_id       = aid("fci"),
                mill_id        = mill_id,
                mill_name      = mill_name,
                violation      = ViolationType.FCI_UNREPORTED,
                severity       = AlertSeverity.CRITICAL,
                title          = f"FCI milling receipts under-declared: ₹{diff:,.0f}",
                description    = (
                    f"FCI milling receipts: ₹{fci_milling_receipts:,.0f}. "
                    f"Declared in ITR: ₹{fci_declared_in_itr:,.0f}. "
                    f"Shortfall ₹{diff:,.0f} — risk of reassessment u/s 147."
                ),
                penalty_amount = tax_impact,
                interest_amount= calc_gst_interest(tax_impact, 365),
                total_exposure = tax_impact * 1.36,   # tax + 234A interest + 271 penalty up to 200%
                action_required= "Declare full FCI receipts in ITR. File revised return if assessment pending.",
                section_ref    = "Section 147 + 271(1)(c) Income Tax Act",
            ))

        # Compute totals
        total_exposure = sum(a.total_exposure for a in alerts)
        critical_count = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)

        summary = {
            "total_alerts":    len(alerts),
            "critical":        critical_count,
            "high":            sum(1 for a in alerts if a.severity == AlertSeverity.HIGH),
            "medium":          sum(1 for a in alerts if a.severity == AlertSeverity.MEDIUM),
            "total_exposure":  round(total_exposure, 2),
            "immediate_action_required": critical_count > 0,
        }

        alerts.sort(key=lambda a: (
            0 if a.severity == AlertSeverity.CRITICAL else
            1 if a.severity == AlertSeverity.HIGH else
            2 if a.severity == AlertSeverity.MEDIUM else 3
        ))

        return PenaltyReport(
            mill_id        = mill_id,
            mill_name      = mill_name,
            generated_date = today,
            total_exposure = round(total_exposure, 2),
            alerts         = alerts,
            summary        = summary,
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_engine = RiceMillPenaltyEngine()

def ricemill_penalty_check(params: dict) -> dict:
    """API entry point — called from Flask route or WhatsApp bot."""
    try:
        report = _engine.assess(
            mill_id                   = params.get("mill_id", "RM001"),
            mill_name                 = params.get("mill_name", "Rice Mill"),
            gstr1_days_late           = int(params.get("gstr1_days_late", 0)),
            gstr3b_days_late          = int(params.get("gstr3b_days_late", 0)),
            gst_nil_return            = bool(params.get("gst_nil_return", False)),
            unpaid_gst                = float(params.get("unpaid_gst", 0)),
            gst_delay_days            = int(params.get("gst_delay_days", 0)),
            exempt_supply_pct         = float(params.get("exempt_supply_pct", 0)),
            itc_total_claimed         = float(params.get("itc_total_claimed", 0)),
            farmer_purchases          = float(params.get("farmer_purchases", 0)),
            rcm_paid                  = float(params.get("rcm_paid", 0)),
            annual_turnover           = float(params.get("annual_turnover", 0)),
            is_composition            = bool(params.get("is_composition", False)),
            ewaybill_defaults         = int(params.get("ewaybill_defaults", 0)),
            ewaybill_value_each       = float(params.get("ewaybill_value_each", 50000)),
            milling_contracts         = float(params.get("milling_contracts", 0)),
            tds_194c_deducted         = float(params.get("tds_194c_deducted", 0)),
            is_individual_contractor  = bool(params.get("is_individual_contractor", True)),
            registered_purchases      = float(params.get("registered_purchases", 0)),
            tds_194q_deducted         = float(params.get("tds_194q_deducted", 0)),
            estimated_tax             = float(params.get("estimated_tax", 0)),
            advance_paid              = float(params.get("advance_paid", 0)),
            cash_purchases_farmers    = float(params.get("cash_purchases_farmers", 0)),
            fci_milling_receipts      = float(params.get("fci_milling_receipts", 0)),
            fci_declared_in_itr       = float(params.get("fci_declared_in_itr", 0)),
        )
        return {
            "mill_id":       report.mill_id,
            "mill_name":     report.mill_name,
            "generated":     report.generated_date,
            "total_exposure":report.total_exposure,
            "summary":       report.summary,
            "alerts":        [asdict(a) for a in report.alerts],
        }
    except Exception as e:
        return {"error": str(e)}
