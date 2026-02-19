"""
Payroll Module — India FY 2024-25
Computes:
  • Gross salary breakdown (basic, HRA, allowances)
  • EPF (Employee Provident Fund) — Sec 80C eligible
  • ESIC (Employee State Insurance)
  • Professional Tax (state-wise)
  • TDS on salary under Sec 192
  • Net take-home salary
  • Employer cost (CTC) breakdown
  • Payslip generation for individual employees
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants — FY 2024-25
# ---------------------------------------------------------------------------

# EPF rates
EPF_EMPLOYEE_RATE  = 0.12   # 12% of basic+DA
EPF_EMPLOYER_RATE  = 0.12   # 12% of basic+DA (3.67% EPF + 8.33% EPS capped at ₹15K basic)
EPF_WAGE_CAP       = 15_000 # EPF computed on ₹15,000 max (if basic > 15K, 12% on 15K for EPS)
EPF_ADMIN_CHARGE   = 0.005  # 0.5% employer admin charge

# ESIC
ESIC_EMPLOYEE_RATE    = 0.0075  # 0.75% of gross wages
ESIC_EMPLOYER_RATE    = 0.0325  # 3.25% of gross wages
ESIC_WAGE_LIMIT       = 21_000  # ESIC applicable if gross ≤ ₹21,000/month

# Professional tax — monthly (state-specific; Maharashtra rates as default)
PROFESSIONAL_TAX_MH = [
    (7_500,  0),
    (10_000, 175),
    (float("inf"), 200),
]  # ₹200/month (₹2,500/year) for Maharashtra

# New regime TDS slabs (FY 2024-25 — annual)
NEW_REGIME_ANNUAL_SLABS = [
    (300_000,   0.00),
    (700_000,   0.05),
    (1_000_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]

OLD_REGIME_ANNUAL_SLABS = [
    (250_000,   0.00),
    (500_000,   0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

STANDARD_DEDUCTION_NEW = 75_000
STANDARD_DEDUCTION_OLD = 50_000


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SalaryStructure:
    """Input salary structure for an employee."""
    employee_id:       str
    employee_name:     str
    designation:       str
    pan:               str
    basic_monthly:     float
    hra_monthly:       float          # HRA component from employer
    special_allowance: float = 0.0
    lta_monthly:       float  = 0.0   # Leave Travel Allowance
    medical_allowance: float  = 0.0
    other_allowances:  float  = 0.0
    # Deductions (employer-declared)
    voluntary_pf:      float  = 0.0   # VPF contribution by employee
    professional_tax_monthly: float = 200.0
    regime:            str    = "new"
    # Old regime deductions (employee-declared)
    sec80c:            float  = 0.0
    sec80d:            float  = 0.0
    hra_exemption:     float  = 0.0   # HRA exemption computed separately
    other_deductions:  float  = 0.0

    @property
    def gross_monthly(self) -> float:
        return (self.basic_monthly + self.hra_monthly + self.special_allowance
                + self.lta_monthly + self.medical_allowance + self.other_allowances)

    @property
    def gross_annual(self) -> float:
        return self.gross_monthly * 12


@dataclass
class EPFBreakdown:
    employee_contribution: float
    employer_epf:          float   # 3.67% to EPF
    employer_eps:          float   # 8.33% to EPS (capped at ₹1,250/month)
    employer_total:        float
    admin_charge:          float
    total_epf_outflow:     float   # Employer cost (employer PF + admin)


@dataclass
class ESICBreakdown:
    applicable:            bool
    employee_contribution: float
    employer_contribution: float
    total:                 float


@dataclass
class TDSBreakdown:
    annual_gross:          float
    standard_deduction:    float
    chapter_vi_deductions: float
    taxable_income:        float
    basic_tax:             float
    rebate_87a:            float
    cess:                  float
    annual_tds:            float
    monthly_tds:           float
    effective_tds_rate:    float


@dataclass
class Payslip:
    """Monthly payslip for an employee."""
    employee_id:       str
    employee_name:     str
    designation:       str
    pan:               str
    month:             str
    # Earnings
    basic:             float
    hra:               float
    special_allowance: float
    lta:               float
    medical_allowance: float
    other_allowances:  float
    gross_earnings:    float
    # Deductions
    epf_employee:      float
    esic_employee:     float
    professional_tax:  float
    tds:               float
    voluntary_pf:      float
    total_deductions:  float
    net_take_home:     float
    # Employer cost
    epf_employer:      float
    esic_employer:     float
    epf_admin:         float
    total_ctc_monthly: float
    # Statutory info
    epf:               EPFBreakdown
    esic:              ESICBreakdown
    tds_detail:        TDSBreakdown


@dataclass
class PayrollRunResult:
    month:            str
    payslips:         List[Payslip]
    total_gross:      float
    total_tds:        float
    total_epf_ee:     float
    total_epf_er:     float
    total_esic_ee:    float
    total_esic_er:    float
    total_pt:         float
    total_net:        float
    total_ctc:        float
    tds_challan_280:  float   # TDS to deposit by 7th of next month
    epf_challan:      float   # EPF to deposit by 15th of next month
    esic_challan:     float   # ESIC to deposit by 15th of next month
    alerts:           List[str]


# ---------------------------------------------------------------------------
# Payroll Engine
# ---------------------------------------------------------------------------

class PayrollEngine:
    """
    Processes payroll for a list of employees.

    Usage:
        engine = PayrollEngine(month="Mar-2025")
        engine.add_employee(SalaryStructure(...))
        result = engine.run()
    """

    def __init__(self, month: str = "Mar-2025"):
        self.month = month
        self._employees: List[SalaryStructure] = []

    def add_employee(self, emp: SalaryStructure) -> None:
        self._employees.append(emp)

    def run(self) -> PayrollRunResult:
        payslips = [self._process_employee(emp) for emp in self._employees]

        total_gross  = sum(p.gross_earnings for p in payslips)
        total_tds    = sum(p.tds for p in payslips)
        total_epf_ee = sum(p.epf_employee for p in payslips)
        total_epf_er = sum(p.epf_employer for p in payslips)
        total_esic_ee= sum(p.esic_employee for p in payslips)
        total_esic_er= sum(p.esic_employer for p in payslips)
        total_pt     = sum(p.professional_tax for p in payslips)
        total_net    = sum(p.net_take_home for p in payslips)
        total_ctc    = sum(p.total_ctc_monthly for p in payslips)

        alerts = []
        if total_tds > 0:
            alerts.append(
                f"TDS of ₹{total_tds:,.0f} to be deposited by 7th {self.month.split('-')[0]} "
                f"via Challan 281 (Code 0021 for TDS on salary)."
            )
        if total_epf_ee + total_epf_er > 0:
            alerts.append(
                f"EPF contribution of ₹{total_epf_ee + total_epf_er:,.0f} to be deposited "
                f"by 15th {self.month.split('-')[0]} on EPFO Unified Portal."
            )
        if total_esic_ee + total_esic_er > 0:
            alerts.append(
                f"ESIC contribution of ₹{total_esic_ee + total_esic_er:,.0f} to be deposited "
                f"by 15th {self.month.split('-')[0]} on ESIC portal."
            )

        return PayrollRunResult(
            month           = self.month,
            payslips        = payslips,
            total_gross     = total_gross,
            total_tds       = total_tds,
            total_epf_ee    = total_epf_ee,
            total_epf_er    = total_epf_er,
            total_esic_ee   = total_esic_ee,
            total_esic_er   = total_esic_er,
            total_pt        = total_pt,
            total_net       = total_net,
            total_ctc       = total_ctc,
            tds_challan_280 = total_tds,
            epf_challan     = total_epf_ee + total_epf_er,
            esic_challan    = total_esic_ee + total_esic_er,
            alerts          = alerts,
        )

    def _process_employee(self, emp: SalaryStructure) -> Payslip:
        # EPF
        epf_basic = min(emp.basic_monthly, EPF_WAGE_CAP)
        epf_ee    = round(emp.basic_monthly * EPF_EMPLOYEE_RATE + emp.voluntary_pf, 2)
        eps_er    = min(round(epf_basic * 0.0833, 2), 1_250)   # EPS capped ₹1,250
        epf_er_to_epf = round(epf_basic * 0.0367, 2)
        epf_er_total  = round(eps_er + epf_er_to_epf, 2)
        admin     = round(emp.basic_monthly * EPF_ADMIN_CHARGE, 2)

        epf = EPFBreakdown(
            employee_contribution = epf_ee,
            employer_epf          = epf_er_to_epf,
            employer_eps          = eps_er,
            employer_total        = epf_er_total,
            admin_charge          = admin,
            total_epf_outflow     = epf_er_total + admin,
        )

        # ESIC
        gross_m = emp.gross_monthly
        esic_applicable = gross_m <= ESIC_WAGE_LIMIT
        esic = ESICBreakdown(
            applicable            = esic_applicable,
            employee_contribution = round(gross_m * ESIC_EMPLOYEE_RATE, 2) if esic_applicable else 0.0,
            employer_contribution = round(gross_m * ESIC_EMPLOYER_RATE, 2) if esic_applicable else 0.0,
            total                 = round(gross_m * (ESIC_EMPLOYEE_RATE + ESIC_EMPLOYER_RATE), 2) if esic_applicable else 0.0,
        )

        # TDS
        tds_detail = self._compute_tds(emp, epf_ee)

        # Deductions from gross
        total_ded = round(epf_ee + esic.employee_contribution
                          + emp.professional_tax_monthly + tds_detail.monthly_tds, 2)
        net       = round(gross_m - total_ded, 2)

        # CTC
        employer_extras = epf.total_epf_outflow + esic.employer_contribution
        ctc_monthly     = round(gross_m + employer_extras, 2)

        return Payslip(
            employee_id       = emp.employee_id,
            employee_name     = emp.employee_name,
            designation       = emp.designation,
            pan               = emp.pan,
            month             = self.month,
            basic             = emp.basic_monthly,
            hra               = emp.hra_monthly,
            special_allowance = emp.special_allowance,
            lta               = emp.lta_monthly,
            medical_allowance = emp.medical_allowance,
            other_allowances  = emp.other_allowances,
            gross_earnings    = gross_m,
            epf_employee      = epf_ee,
            esic_employee     = esic.employee_contribution,
            professional_tax  = emp.professional_tax_monthly,
            tds               = tds_detail.monthly_tds,
            voluntary_pf      = emp.voluntary_pf,
            total_deductions  = total_ded,
            net_take_home     = net,
            epf_employer      = epf_er_total,
            esic_employer     = esic.employer_contribution,
            epf_admin         = admin,
            total_ctc_monthly = ctc_monthly,
            epf               = epf,
            esic              = esic,
            tds_detail        = tds_detail,
        )

    def _compute_tds(self, emp: SalaryStructure, epf_ee_monthly: float) -> TDSBreakdown:
        annual_gross = emp.gross_annual
        slabs        = NEW_REGIME_ANNUAL_SLABS if emp.regime == "new" else OLD_REGIME_ANNUAL_SLABS
        std_ded      = STANDARD_DEDUCTION_NEW  if emp.regime == "new" else STANDARD_DEDUCTION_OLD

        chapter_vi = 0.0
        if emp.regime == "old":
            chapter_vi = (min(emp.sec80c + epf_ee_monthly * 12, 150_000)
                          + min(emp.sec80d, 25_000)
                          + emp.hra_exemption
                          + emp.other_deductions)

        taxable = max(0.0, annual_gross - std_ded - chapter_vi)

        prev = 0.0
        basic_tax = 0.0
        for threshold, rate in slabs:
            if taxable <= prev:
                break
            slab_income = min(taxable, threshold if threshold != float("inf") else taxable) - prev
            basic_tax  += slab_income * rate
            prev        = threshold if threshold != float("inf") else taxable

        # Rebate 87A
        rebate_limit = 700_000 if emp.regime == "new" else 500_000
        rebate_cap   = 25_000  if emp.regime == "new" else 12_500
        rebate       = min(basic_tax, rebate_cap) if taxable <= rebate_limit else 0.0
        basic_tax   -= rebate

        cess       = max(0.0, basic_tax) * 0.04
        annual_tds = max(0.0, basic_tax) + cess
        monthly_tds= round(annual_tds / 12, 2)
        eff_rate   = (annual_tds / annual_gross * 100) if annual_gross else 0.0

        return TDSBreakdown(
            annual_gross          = annual_gross,
            standard_deduction    = std_ded,
            chapter_vi_deductions = chapter_vi,
            taxable_income        = taxable,
            basic_tax             = round(max(0.0, basic_tax), 2),
            rebate_87a            = round(rebate, 2),
            cess                  = round(cess, 2),
            annual_tds            = round(annual_tds, 2),
            monthly_tds           = monthly_tds,
            effective_tds_rate    = round(eff_rate, 2),
        )


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def run_payroll(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    engine = PayrollEngine(month=params.get("month", "Mar-2025"))

    for emp_data in params.get("employees", []):
        engine.add_employee(SalaryStructure(
            employee_id       = emp_data.get("employee_id", ""),
            employee_name     = emp_data.get("employee_name", ""),
            designation       = emp_data.get("designation", ""),
            pan               = emp_data.get("pan", ""),
            basic_monthly     = float(emp_data.get("basic_monthly", 0)),
            hra_monthly       = float(emp_data.get("hra_monthly", 0)),
            special_allowance = float(emp_data.get("special_allowance", 0)),
            lta_monthly       = float(emp_data.get("lta_monthly", 0)),
            medical_allowance = float(emp_data.get("medical_allowance", 0)),
            other_allowances  = float(emp_data.get("other_allowances", 0)),
            voluntary_pf      = float(emp_data.get("voluntary_pf", 0)),
            professional_tax_monthly = float(emp_data.get("professional_tax_monthly", 200)),
            regime            = emp_data.get("regime", "new"),
            sec80c            = float(emp_data.get("sec80c", 0)),
            sec80d            = float(emp_data.get("sec80d", 0)),
            hra_exemption     = float(emp_data.get("hra_exemption", 0)),
            other_deductions  = float(emp_data.get("other_deductions", 0)),
        ))

    result = engine.run()
    return {
        "month":            result.month,
        "total_gross":      result.total_gross,
        "total_tds":        result.total_tds,
        "total_epf_ee":     result.total_epf_ee,
        "total_epf_er":     result.total_epf_er,
        "total_esic_ee":    result.total_esic_ee,
        "total_esic_er":    result.total_esic_er,
        "total_pt":         result.total_pt,
        "total_net":        result.total_net,
        "total_ctc":        result.total_ctc,
        "tds_challan_280":  result.tds_challan_280,
        "epf_challan":      result.epf_challan,
        "esic_challan":     result.esic_challan,
        "alerts":           result.alerts,
        "payslips":         [asdict(p) for p in result.payslips],
    }
