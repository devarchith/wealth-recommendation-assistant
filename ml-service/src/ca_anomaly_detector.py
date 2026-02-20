"""
CA Anomaly Detector — Flags Inconsistencies in Client Financials
================================================================
Detects red-flag patterns in client financial data to help CAs
identify errors, omissions, and potential compliance risks before
filing returns or preparing audit reports.

Anomaly categories:
  1. Income anomalies — unexplained income jumps, missing salary months
  2. GST anomalies    — GSTR-1 vs GSTR-3B mismatch, ITC ratio spikes
  3. TDS anomalies    — 26AS vs books mismatch, missing TDS credits
  4. Expense anomalies — cash expenses >₹10K (section 40A(3)), related-party transactions
  5. Bank anomalies   — large credits with no income source, round-trip transactions
  6. Ratio anomalies  — GP/NP ratio deviation from industry benchmarks
  7. Advance tax      — under-payment detection (interest u/s 234B/C)

Each anomaly has:
  - severity: CRITICAL | HIGH | MEDIUM | LOW
  - rule_id: stable identifier for the detection rule
  - description: human-readable explanation
  - flagged_value: the specific figure that triggered the flag
  - expected_range / benchmark: what normal looks like
  - recommendation: action the CA should take
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class AnomalyCategory(str, Enum):
    INCOME       = "income"
    GST          = "gst"
    TDS          = "tds"
    EXPENSE      = "expense"
    BANK         = "bank"
    RATIO        = "ratio"
    ADVANCE_TAX  = "advance_tax"
    RELATED_PARTY= "related_party"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    rule_id:       str
    category:      AnomalyCategory
    severity:      Severity
    description:   str
    flagged_value: float
    expected:      str        # human-readable range or benchmark
    recommendation: str
    client_id:     str        = ""
    ay:            str        = ""

@dataclass
class AnomalyReport:
    client_id:    str
    client_name:  str
    ay:           str
    anomalies:    List[Anomaly]
    health_score: int         # 0–100 (100 = no anomalies)
    summary:      Dict        = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Industry GP ratio benchmarks (sector → (min%, max%))
# Used for ratio anomaly detection
# ---------------------------------------------------------------------------

_GP_BENCHMARKS: Dict[str, Tuple[float, float]] = {
    "rice_mill":       (3.0,   8.0),
    "trader":          (10.0,  25.0),
    "manufacturer":    (15.0,  35.0),
    "software":        (40.0,  75.0),
    "contractor":      (8.0,   20.0),
    "restaurant":      (25.0,  45.0),
    "pharmacy":        (15.0,  25.0),
    "real_estate":     (20.0,  40.0),
    "professional":    (50.0,  85.0),    # CA, doctor, lawyer
    "default":         (10.0,  40.0),
}

_NP_BENCHMARKS: Dict[str, Tuple[float, float]] = {
    "rice_mill":       (1.0,   4.0),
    "trader":          (3.0,   12.0),
    "manufacturer":    (5.0,   20.0),
    "software":        (15.0,  40.0),
    "contractor":      (3.0,   12.0),
    "restaurant":      (8.0,   20.0),
    "pharmacy":        (5.0,   15.0),
    "real_estate":     (10.0,  25.0),
    "professional":    (30.0,  60.0),
    "default":         (3.0,   20.0),
}


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Detects financial anomalies in client data.
    Call detect_all() with a financial snapshot to get a report.
    """

    def detect_all(
        self,
        client_id:      str,
        client_name:    str,
        ay:             str,
        sector:         str = "default",
        # Income
        gross_income:   float = 0.0,
        prev_yr_income: float = 0.0,
        salary_months:  int   = 12,
        # GST
        gstr1_turnover: float = 0.0,
        gstr3b_turnover:float = 0.0,
        itc_claimed:    float = 0.0,
        purchases:      float = 0.0,
        gst_liability:  float = 0.0,
        # TDS
        tds_26as:       float = 0.0,
        tds_books:      float = 0.0,
        # Expenses
        cash_expenses:  float = 0.0,
        related_party_transactions: float = 0.0,
        total_expenses: float = 0.0,
        # Bank
        total_bank_credits: float = 0.0,
        unexplained_credits:float = 0.0,
        # P&L
        gross_profit:   float = 0.0,
        net_profit:     float = 0.0,
        turnover:       float = 0.0,
        # Advance tax
        advance_tax_paid:   float = 0.0,
        estimated_tax_due:  float = 0.0,
        # Flags
        has_related_party:  bool = False,
        declared_loans_received: float = 0.0,
    ) -> AnomalyReport:

        anomalies: List[Anomaly] = []

        # --- Income anomalies ---
        if prev_yr_income > 0 and gross_income > 0:
            pct_change = (gross_income - prev_yr_income) / prev_yr_income * 100
            if pct_change > 50:
                anomalies.append(Anomaly(
                    rule_id        = "INC001",
                    category       = AnomalyCategory.INCOME,
                    severity       = Severity.HIGH,
                    description    = f"Income increased by {pct_change:.1f}% vs prior year — verify source",
                    flagged_value  = gross_income,
                    expected       = f"Within 20–30% of prior year income (₹{prev_yr_income:,.0f})",
                    recommendation = "Obtain explanation letter from client. Verify new income sources.",
                    client_id      = client_id,
                    ay             = ay,
                ))
            elif pct_change < -30:
                anomalies.append(Anomaly(
                    rule_id        = "INC002",
                    category       = AnomalyCategory.INCOME,
                    severity       = Severity.MEDIUM,
                    description    = f"Income dropped by {abs(pct_change):.1f}% vs prior year",
                    flagged_value  = gross_income,
                    expected       = f"Within 20% drop from prior year (₹{prev_yr_income:,.0f})",
                    recommendation = "Check if income is under-reported. Verify with AIS/26AS.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        if salary_months < 12 and salary_months > 0:
            anomalies.append(Anomaly(
                rule_id        = "INC003",
                category       = AnomalyCategory.INCOME,
                severity       = Severity.MEDIUM,
                description    = f"Only {salary_months} month(s) of salary found — {12 - salary_months} months missing",
                flagged_value  = float(salary_months),
                expected       = "12 months of Form 16 / salary credited",
                recommendation = "Verify job change, gap period, or omitted Form 16. Check AIS.",
                client_id      = client_id,
                ay             = ay,
            ))

        # --- GST anomalies ---
        if gstr1_turnover > 0 and gstr3b_turnover > 0:
            diff = abs(gstr1_turnover - gstr3b_turnover)
            diff_pct = diff / max(gstr1_turnover, gstr3b_turnover) * 100
            if diff_pct > 5:
                anomalies.append(Anomaly(
                    rule_id        = "GST001",
                    category       = AnomalyCategory.GST,
                    severity       = Severity.CRITICAL,
                    description    = f"GSTR-1 vs GSTR-3B turnover mismatch: ₹{diff:,.0f} ({diff_pct:.1f}%)",
                    flagged_value  = diff,
                    expected       = "GSTR-1 and GSTR-3B should match within 5%",
                    recommendation = "Reconcile GSTR-1 and GSTR-3B immediately. File GSTR-3B amendment if required.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        if purchases > 0 and itc_claimed > 0:
            itc_ratio = itc_claimed / purchases * 100
            if itc_ratio > 28:   # GST standard rates; >28% is suspicious
                anomalies.append(Anomaly(
                    rule_id        = "GST002",
                    category       = AnomalyCategory.GST,
                    severity       = Severity.HIGH,
                    description    = f"ITC claimed ({itc_ratio:.1f}% of purchases) exceeds expected rate",
                    flagged_value  = itc_ratio,
                    expected       = "ITC ratio ≤ applicable GST rate on purchases (max 28%)",
                    recommendation = "Verify GSTR-2B vs purchase register. Check for fake invoices.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        if gst_liability > 0 and gstr3b_turnover > 0:
            eff_rate = gst_liability / gstr3b_turnover * 100
            if eff_rate < 1.0:   # Suspiciously low effective rate
                anomalies.append(Anomaly(
                    rule_id        = "GST003",
                    category       = AnomalyCategory.GST,
                    severity       = Severity.MEDIUM,
                    description    = f"Effective GST rate on turnover is only {eff_rate:.2f}% — seems low",
                    flagged_value  = eff_rate,
                    expected       = "Effective rate ≥ applicable GST rate after ITC",
                    recommendation = "Check if all output tax has been correctly reported in GSTR-3B.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        # --- TDS anomalies ---
        if tds_26as > 0 and tds_books > 0:
            tds_diff = abs(tds_26as - tds_books)
            if tds_diff > 1000:
                anomalies.append(Anomaly(
                    rule_id        = "TDS001",
                    category       = AnomalyCategory.TDS,
                    severity       = Severity.HIGH,
                    description    = f"26AS TDS (₹{tds_26as:,.0f}) ≠ books TDS (₹{tds_books:,.0f}) — diff ₹{tds_diff:,.0f}",
                    flagged_value  = tds_diff,
                    expected       = "26AS and books should match within ₹1,000",
                    recommendation = "Reconcile 26AS vs books. Follow up with deductors for TDS correction.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        # --- Expense anomalies ---
        if cash_expenses > 10_000:
            anomalies.append(Anomaly(
                rule_id        = "EXP001",
                category       = AnomalyCategory.EXPENSE,
                severity       = Severity.HIGH,
                description    = f"Cash expenses ₹{cash_expenses:,.0f} may attract disallowance u/s 40A(3)",
                flagged_value  = cash_expenses,
                expected       = "Single cash payment ≤ ₹10,000 (₹35,000 for transporters)",
                recommendation = "Review each cash expense. Disallow excess u/s 40A(3). Advise digital payments.",
                client_id      = client_id,
                ay             = ay,
            ))

        if total_expenses > 0 and gross_income > 0:
            exp_ratio = total_expenses / gross_income * 100
            if exp_ratio > 90:
                anomalies.append(Anomaly(
                    rule_id        = "EXP002",
                    category       = AnomalyCategory.EXPENSE,
                    severity       = Severity.MEDIUM,
                    description    = f"Expenses are {exp_ratio:.1f}% of income — very high",
                    flagged_value  = exp_ratio,
                    expected       = "Expenses typically 60–80% of turnover for most sectors",
                    recommendation = "Review inflated expense claims. Verify genuineness and business purpose.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        if has_related_party and related_party_transactions > 0:
            anomalies.append(Anomaly(
                rule_id        = "EXP003",
                category       = AnomalyCategory.RELATED_PARTY,
                severity       = Severity.MEDIUM,
                description    = f"Related party transactions ₹{related_party_transactions:,.0f} detected",
                flagged_value  = related_party_transactions,
                expected       = "Related party transactions at arm's length; disclosure required",
                recommendation = "Disclose in notes to accounts. Verify arm's length pricing. Comply with section 40A(2).",
                client_id      = client_id,
                ay             = ay,
            ))

        # --- Bank anomalies ---
        if unexplained_credits > 0:
            anomalies.append(Anomaly(
                rule_id        = "BNK001",
                category       = AnomalyCategory.BANK,
                severity       = Severity.CRITICAL,
                description    = f"Unexplained bank credits ₹{unexplained_credits:,.0f} — may be treated as income",
                flagged_value  = unexplained_credits,
                expected       = "All bank credits should be reconciled to income / loan source",
                recommendation = "Obtain source explanation for each credit. Cash deposits may attract section 69A addition.",
                client_id      = client_id,
                ay             = ay,
            ))

        if declared_loans_received > 0 and total_bank_credits > 0:
            loan_ratio = declared_loans_received / total_bank_credits * 100
            if loan_ratio > 40:
                anomalies.append(Anomaly(
                    rule_id        = "BNK002",
                    category       = AnomalyCategory.BANK,
                    severity       = Severity.MEDIUM,
                    description    = f"Loans constitute {loan_ratio:.1f}% of total bank credits — high",
                    flagged_value  = declared_loans_received,
                    expected       = "Loan receipts < 40% of bank credits; verify genuine lending",
                    recommendation = "Ensure loans are from identifiable lenders with repayment terms. Check section 68 conditions.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        # --- Ratio anomalies ---
        if turnover > 0 and gross_profit >= 0:
            gp_pct = gross_profit / turnover * 100
            lo, hi  = _GP_BENCHMARKS.get(sector, _GP_BENCHMARKS["default"])
            if gp_pct < lo:
                anomalies.append(Anomaly(
                    rule_id        = "RAT001",
                    category       = AnomalyCategory.RATIO,
                    severity       = Severity.HIGH,
                    description    = f"GP ratio {gp_pct:.1f}% is below industry benchmark ({lo}%–{hi}%)",
                    flagged_value  = gp_pct,
                    expected       = f"{lo}%–{hi}% for {sector}",
                    recommendation = "Check if purchases/COGS are inflated. Review stock valuation.",
                    client_id      = client_id,
                    ay             = ay,
                ))
            elif gp_pct > hi:
                anomalies.append(Anomaly(
                    rule_id        = "RAT002",
                    category       = AnomalyCategory.RATIO,
                    severity       = Severity.MEDIUM,
                    description    = f"GP ratio {gp_pct:.1f}% is above industry benchmark ({lo}%–{hi}%)",
                    flagged_value  = gp_pct,
                    expected       = f"{lo}%–{hi}% for {sector}",
                    recommendation = "Verify no income is omitted from purchases. May attract scrutiny.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        if turnover > 0 and net_profit >= 0:
            np_pct = net_profit / turnover * 100
            lo, hi  = _NP_BENCHMARKS.get(sector, _NP_BENCHMARKS["default"])
            if np_pct < lo:
                anomalies.append(Anomaly(
                    rule_id        = "RAT003",
                    category       = AnomalyCategory.RATIO,
                    severity       = Severity.HIGH,
                    description    = f"NP ratio {np_pct:.1f}% is below industry benchmark ({lo}%–{hi}%)",
                    flagged_value  = np_pct,
                    expected       = f"{lo}%–{hi}% for {sector}",
                    recommendation = "Review operating expenses for inflated/inadmissible claims.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        # --- Advance tax anomalies ---
        if estimated_tax_due > 10_000 and advance_tax_paid >= 0:
            required = estimated_tax_due * 0.75    # 75% by 15 Dec (simplified)
            shortfall = required - advance_tax_paid
            if shortfall > 5_000:
                anomalies.append(Anomaly(
                    rule_id        = "ADV001",
                    category       = AnomalyCategory.ADVANCE_TAX,
                    severity       = Severity.HIGH,
                    description    = f"Advance tax shortfall ₹{shortfall:,.0f} — interest u/s 234B/C applicable",
                    flagged_value  = shortfall,
                    expected       = f"75% of estimated tax (₹{required:,.0f}) by 15 December",
                    recommendation = "Pay balance advance tax immediately. Compute interest u/s 234B and 234C.",
                    client_id      = client_id,
                    ay             = ay,
                ))

        # Compute health score
        severity_weights = {
            Severity.CRITICAL: 25,
            Severity.HIGH:     10,
            Severity.MEDIUM:   5,
            Severity.LOW:      2,
        }
        score_deduction = sum(severity_weights[a.severity] for a in anomalies)
        health_score    = max(0, 100 - score_deduction)

        # Summary
        by_severity = {}
        by_category = {}
        for a in anomalies:
            by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1
            by_category[a.category.value] = by_category.get(a.category.value, 0) + 1

        summary = {
            "total_anomalies":   len(anomalies),
            "by_severity":       by_severity,
            "by_category":       by_category,
            "critical_count":    by_severity.get("critical", 0),
            "health_score":      health_score,
            "sector_benchmarked": sector,
        }

        return AnomalyReport(
            client_id    = client_id,
            client_name  = client_name,
            ay           = ay,
            anomalies    = anomalies,
            health_score = health_score,
            summary      = summary,
        )


# ---------------------------------------------------------------------------
# Portfolio scanner
# ---------------------------------------------------------------------------

class PortfolioAnomalyScanner:
    """Runs anomaly detection across all clients in a portfolio."""

    def __init__(self):
        self._detector = AnomalyDetector()
        self._reports:  Dict[str, AnomalyReport] = {}

    def scan_client(self, client_id: str, client_name: str, **kwargs) -> AnomalyReport:
        report = self._detector.detect_all(client_id=client_id, client_name=client_name, **kwargs)
        self._reports[client_id] = report
        return report

    def portfolio_summary(self) -> Dict:
        reports = list(self._reports.values())
        if not reports:
            return {"total_clients": 0}

        critical_clients = [r for r in reports if r.summary.get("critical_count", 0) > 0]
        low_health       = [r for r in reports if r.health_score < 60]

        return {
            "total_clients":     len(reports),
            "avg_health_score":  round(sum(r.health_score for r in reports) / len(reports), 1),
            "critical_clients":  len(critical_clients),
            "low_health_clients":len(low_health),
            "clients_needing_attention": [
                {"client_id": r.client_id, "client_name": r.client_name,
                 "health_score": r.health_score, "anomalies": r.summary["total_anomalies"],
                 "critical": r.summary.get("critical_count", 0)}
                for r in sorted(reports, key=lambda r: r.health_score)[:10]
            ],
        }

    def get_report(self, client_id: str) -> Optional[AnomalyReport]:
        return self._reports.get(client_id)


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_scanner = PortfolioAnomalyScanner()

def ca_anomaly_detector(params: dict) -> dict:
    action = params.get("action", "scan")
    try:
        if action == "scan":
            report = _scanner.scan_client(
                client_id   = params["client_id"],
                client_name = params.get("client_name", params["client_id"]),
                ay          = params.get("ay", "AY 2024-25"),
                sector      = params.get("sector", "default"),
                gross_income        = float(params.get("gross_income", 0)),
                prev_yr_income      = float(params.get("prev_yr_income", 0)),
                salary_months       = int(params.get("salary_months", 12)),
                gstr1_turnover      = float(params.get("gstr1_turnover", 0)),
                gstr3b_turnover     = float(params.get("gstr3b_turnover", 0)),
                itc_claimed         = float(params.get("itc_claimed", 0)),
                purchases           = float(params.get("purchases", 0)),
                gst_liability       = float(params.get("gst_liability", 0)),
                tds_26as            = float(params.get("tds_26as", 0)),
                tds_books           = float(params.get("tds_books", 0)),
                cash_expenses       = float(params.get("cash_expenses", 0)),
                related_party_transactions = float(params.get("related_party_transactions", 0)),
                total_expenses      = float(params.get("total_expenses", 0)),
                total_bank_credits  = float(params.get("total_bank_credits", 0)),
                unexplained_credits = float(params.get("unexplained_credits", 0)),
                gross_profit        = float(params.get("gross_profit", 0)),
                net_profit          = float(params.get("net_profit", 0)),
                turnover            = float(params.get("turnover", 0)),
                advance_tax_paid    = float(params.get("advance_tax_paid", 0)),
                estimated_tax_due   = float(params.get("estimated_tax_due", 0)),
                has_related_party   = bool(params.get("has_related_party", False)),
                declared_loans_received = float(params.get("declared_loans_received", 0)),
            )
            return {
                "client_id":    report.client_id,
                "client_name":  report.client_name,
                "ay":           report.ay,
                "health_score": report.health_score,
                "summary":      report.summary,
                "anomalies":    [asdict(a) for a in report.anomalies],
            }
        elif action == "portfolio":
            return _scanner.portfolio_summary()
        elif action == "report":
            r = _scanner.get_report(params["client_id"])
            if not r:
                return {"error": "No report found for client"}
            return {
                "client_id":    r.client_id,
                "health_score": r.health_score,
                "summary":      r.summary,
                "anomalies":    [asdict(a) for a in r.anomalies],
            }
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
