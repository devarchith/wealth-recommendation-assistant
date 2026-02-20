"""
Rice Mill What-If Simulator — Tax Regime & GST Scenarios
=========================================================
Enables rice mill owners and their CAs to model the financial impact of
different strategic and tax decisions without committing to them.

Simulator scenarios:
  1. Tax regime comparison — Old vs New regime for proprietor/partnership
  2. GST: Regular vs Composition scheme break-even analysis
  3. FCI vs private trade mix — optimal revenue split
  4. Branded vs unbranded rice — GST 5% impact on margins
  5. Paddy procurement mix — MSP paddy vs market purchase cost impact
  6. Byproduct pricing sensitivity — bran/husk price change on NP
  7. Bank CC limit optimisation — what CC limit maximises operations
  8. Milling capacity expansion — break-even on new machine investment

Each simulation returns:
  - Scenario A vs Scenario B comparison table
  - Tax/cash impact
  - Recommendation
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Tax slab tables
# ---------------------------------------------------------------------------

_NEW_REGIME_SLABS_FY25 = [
    (0,          3_00_000,  0.00),
    (3_00_000,   7_00_000,  0.05),
    (7_00_000,  10_00_000,  0.10),
    (10_00_000, 12_00_000,  0.15),
    (12_00_000, 15_00_000,  0.20),
    (15_00_000, float('inf'), 0.30),
]

_OLD_REGIME_SLABS = [
    (0,          2_50_000,  0.00),
    (2_50_000,   5_00_000,  0.05),
    (5_00_000,  10_00_000,  0.20),
    (10_00_000, float('inf'), 0.30),
]

_SURCHARGE_SLABS = [
    (50_00_000,  1_00_00_000, 0.10),
    (1_00_00_000, 2_00_00_000, 0.15),
    (2_00_00_000, 5_00_00_000, 0.25),
    (5_00_00_000, float('inf'), 0.37),
]

_HEALTH_ED_CESS = 0.04

def compute_income_tax(taxable_income: float, new_regime: bool = True) -> float:
    slabs = _NEW_REGIME_SLABS_FY25 if new_regime else _OLD_REGIME_SLABS
    tax   = 0.0
    for lo, hi, rate in slabs:
        if taxable_income <= lo:
            break
        bracket = min(taxable_income, hi) - lo
        tax    += bracket * rate
    # Surcharge
    surcharge = 0.0
    for lo, hi, rate in _SURCHARGE_SLABS:
        if taxable_income > lo:
            surcharge = tax * rate
    tax_plus_surcharge = tax + surcharge
    return round(tax_plus_surcharge * (1 + _HEALTH_ED_CESS), 2)


def compute_rebate_87a(taxable_income: float, new_regime: bool, tax: float) -> float:
    """Rebate u/s 87A: up to ₹25,000 for income ≤ ₹7L (new regime) / ₹5L (old)."""
    if new_regime and taxable_income <= 7_00_000:
        return min(tax, 25_000)
    if not new_regime and taxable_income <= 5_00_000:
        return min(tax, 12_500)
    return 0.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    scenario_name: str
    taxable_income: float
    tax_before_rebate: float
    rebate_87a: float
    net_tax: float
    take_home: float
    notes: List[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    simulation_type: str
    scenario_a: Dict
    scenario_b: Dict
    comparison: Dict
    recommendation: str
    net_saving: float         # +ve = A is better, -ve = B is better


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

class RiceMillWhatIfSimulator:

    # ── 1. Tax Regime Comparison ─────────────────────────────────────────

    def regime_comparison(
        self,
        gross_income:        float,
        deductions_80c:      float = 0.0,
        deductions_80d:      float = 0.0,
        hra_exemption:       float = 0.0,
        standard_deduction:  float = 75_000,  # FY 2024-25 new regime
        interest_home_loan:  float = 0.0,     # old regime deduction
        other_deductions:    float = 0.0,
    ) -> SimulationResult:

        # New regime
        new_taxable  = max(0, gross_income - standard_deduction)
        new_tax_raw  = compute_income_tax(new_taxable, new_regime=True)
        new_rebate   = compute_rebate_87a(new_taxable, True, new_tax_raw)
        new_net_tax  = max(0, new_tax_raw - new_rebate)

        # Old regime
        old_deductions = (deductions_80c + deductions_80d + hra_exemption +
                          interest_home_loan + other_deductions + 50_000)  # std deduction old regime
        old_taxable    = max(0, gross_income - old_deductions)
        old_tax_raw    = compute_income_tax(old_taxable, new_regime=False)
        old_rebate     = compute_rebate_87a(old_taxable, False, old_tax_raw)
        old_net_tax    = max(0, old_tax_raw - old_rebate)

        saving         = old_net_tax - new_net_tax
        recommended    = "New Regime" if new_net_tax <= old_net_tax else "Old Regime"

        return SimulationResult(
            simulation_type = "tax_regime_comparison",
            scenario_a = {
                "name":           "New Tax Regime (FY 2024-25)",
                "std_deduction":  standard_deduction,
                "taxable_income": new_taxable,
                "gross_tax":      new_tax_raw,
                "rebate_87a":     new_rebate,
                "net_tax":        new_net_tax,
                "take_home":      gross_income - new_net_tax,
            },
            scenario_b = {
                "name":           "Old Tax Regime",
                "total_deductions": old_deductions,
                "taxable_income": old_taxable,
                "gross_tax":      old_tax_raw,
                "rebate_87a":     old_rebate,
                "net_tax":        old_net_tax,
                "take_home":      gross_income - old_net_tax,
            },
            comparison = {
                "new_regime_tax": new_net_tax,
                "old_regime_tax": old_net_tax,
                "saving_with_new": saving,
                "better_option":  recommended,
            },
            recommendation = (
                f"{'New Regime' if saving >= 0 else 'Old Regime'} saves ₹{abs(saving):,.0f}. "
                + ("Switch to New Regime — simpler, lower rate." if saving >= 0
                   else f"Stay on Old Regime — deductions of ₹{old_deductions:,.0f} outweigh the lower slabs.")
            ),
            net_saving = saving,
        )

    # ── 2. GST Scheme Comparison ─────────────────────────────────────────

    def gst_scheme_comparison(
        self,
        annual_turnover:    float,
        branded_rice_pct:   float = 0.30,    # % of turnover that is branded (5% GST)
        milling_private_pct:float = 0.10,    # % that is private milling service (18% GST)
        input_tax_credit:   float = 0.0,     # Annual ITC available under regular scheme
        purchases:          float = 0.0,
    ) -> SimulationResult:

        # Regular scheme
        branded_gst    = annual_turnover * branded_rice_pct * 0.05
        milling_gst    = annual_turnover * milling_private_pct * 0.18
        regular_output = branded_gst + milling_gst
        regular_net    = max(0, regular_output - input_tax_credit)
        regular_compliance = 36_000   # annual filing cost (GSTR-1/3B monthly + GSTR-9)

        # Composition scheme (1% for traders, ½% for manufacturers)
        if annual_turnover > 1_50_00_000:
            comp_applicable = False
            comp_tax        = 0.0
            comp_note       = "Composition NOT applicable — turnover exceeds ₹1.5 Cr limit"
        else:
            comp_applicable = True
            comp_tax        = annual_turnover * 0.01   # 1% composition
            comp_note       = "Composition @ 1% of turnover (no ITC, no output GST collected from buyers)"
        comp_compliance = 12_000   # quarterly CMP-08 + GSTR-9A

        if comp_applicable:
            saving = (regular_net + regular_compliance) - (comp_tax + comp_compliance)
            recommended = "Composition" if saving > 0 else "Regular"
        else:
            saving = 0.0
            recommended = "Regular (mandatory)"

        return SimulationResult(
            simulation_type = "gst_scheme_comparison",
            scenario_a = {
                "name":              "Regular GST Scheme",
                "output_gst":        round(regular_output, 2),
                "itc_available":     input_tax_credit,
                "net_gst_payable":   round(regular_net, 2),
                "compliance_cost":   regular_compliance,
                "total_gst_outflow": round(regular_net + regular_compliance, 2),
            },
            scenario_b = {
                "name":              "Composition Scheme",
                "composition_tax":   round(comp_tax, 2),
                "itc_not_available": True,
                "compliance_cost":   comp_compliance,
                "total_gst_outflow": round(comp_tax + comp_compliance, 2) if comp_applicable else None,
                "applicable":        comp_applicable,
                "note":              comp_note,
            },
            comparison = {
                "saving_with_composition": round(saving, 2),
                "better_option":           recommended,
                "turnover_limit_crores":   1.5,
            },
            recommendation = (
                f"{'Composition' if saving > 0 else 'Regular'} scheme is better. "
                + (f"Annual saving: ₹{abs(saving):,.0f}. " if saving != 0 else "")
                + comp_note
            ),
            net_saving = saving,
        )

    # ── 3. FCI vs Private Trade Mix ───────────────────────────────────────

    def fci_vs_private_mix(
        self,
        total_rice_tonnes: float,
        fci_milling_rate_qtl: float = 27.50,   # ₹ per quintal
        private_sale_price_qtl: float = 2200.0,
        paddy_cost_qtl: float = 2183.0,         # MSP 2024-25 common
        milling_recovery_pct: float = 0.67,     # 67% rice from paddy
        byproduct_revenue_qtl: float = 80.0,    # bran + husk per qtl paddy
        operating_cost_per_tonne: float = 800.0,
        fci_pct_of_capacity: float = 0.60,      # current FCI share
    ) -> SimulationResult:

        for fci_share in [fci_pct_of_capacity, 1.0 - fci_pct_of_capacity]:
            pass   # just to illustrate — compute both

        def compute_margin(fci_share: float) -> Dict:
            fci_tonnes   = total_rice_tonnes * fci_share
            pvt_tonnes   = total_rice_tonnes * (1 - fci_share)

            # FCI milling income (per quintal of rice delivered)
            fci_income   = fci_tonnes * 10 * fci_milling_rate_qtl

            # Private: paddy cost, milling, sale
            paddy_needed_qtl = (pvt_tonnes * 10) / milling_recovery_pct
            paddy_cost   = paddy_needed_qtl * paddy_cost_qtl
            pvt_revenue  = pvt_tonnes * 10 * private_sale_price_qtl
            byproduct_rev= paddy_needed_qtl * byproduct_revenue_qtl
            op_cost      = total_rice_tonnes * operating_cost_per_tonne
            net_profit   = fci_income + pvt_revenue + byproduct_rev - paddy_cost - op_cost

            return {
                "fci_share_pct":      round(fci_share * 100, 1),
                "fci_income":         round(fci_income, 2),
                "private_revenue":    round(pvt_revenue, 2),
                "byproduct_revenue":  round(byproduct_rev, 2),
                "paddy_cost":         round(paddy_cost, 2),
                "operating_cost":     round(op_cost, 2),
                "net_profit":         round(net_profit, 2),
                "margin_pct":         round(net_profit / max(1, fci_income + pvt_revenue + byproduct_rev) * 100, 2),
            }

        scenario_a = compute_margin(fci_pct_of_capacity)
        scenario_a["name"] = f"Current Mix: {fci_pct_of_capacity*100:.0f}% FCI"

        # Compare with 100% private
        scenario_b = compute_margin(0.0)
        scenario_b["name"] = "Full Private Trade"

        # Also 100% FCI
        scenario_c = compute_margin(1.0)

        saving = scenario_b["net_profit"] - scenario_a["net_profit"]
        recommended = "Private trade" if saving > 0 else "Current FCI mix"

        return SimulationResult(
            simulation_type = "fci_vs_private_mix",
            scenario_a      = scenario_a,
            scenario_b      = scenario_b,
            comparison = {
                "current_profit":       scenario_a["net_profit"],
                "private_only_profit":  scenario_b["net_profit"],
                "fci_only_profit":      scenario_c["net_profit"],
                "best_option":          recommended,
                "switching_to_private_impact": round(saving, 2),
            },
            recommendation = (
                f"{'Private trade' if saving > 0 else 'FCI mix'} maximises profit. "
                f"Private trade NP: ₹{scenario_b['net_profit']:,.0f} vs current ₹{scenario_a['net_profit']:,.0f}. "
                f"Note: FCI provides guaranteed off-take and working capital against milling dues. "
                f"Consider hybrid: FCI for 40–50%, private for rest."
            ),
            net_saving = saving,
        )

    # ── 4. Byproduct Pricing Sensitivity ─────────────────────────────────

    def byproduct_sensitivity(
        self,
        annual_paddy_tonnes: float,
        bran_yield_pct: float = 0.08,       # 8% bran of paddy
        husk_yield_pct: float = 0.20,       # 20% husk of paddy
        base_bran_price_qtl: float = 350.0,
        base_husk_price_qtl: float = 60.0,
        price_scenarios: Optional[List[float]] = None,
    ) -> SimulationResult:
        if price_scenarios is None:
            price_scenarios = [-20, -10, 0, 10, 20]

        paddy_qtl  = annual_paddy_tonnes * 10
        bran_qtl   = paddy_qtl * bran_yield_pct
        husk_qtl   = paddy_qtl * husk_yield_pct

        base_bran_rev  = bran_qtl * base_bran_price_qtl
        base_husk_rev  = husk_qtl * base_husk_price_qtl
        base_total     = base_bran_rev + base_husk_rev

        scenarios = []
        for pct_change in price_scenarios:
            bran_p = base_bran_price_qtl * (1 + pct_change / 100)
            husk_p = base_husk_price_qtl * (1 + pct_change / 100)
            rev    = bran_qtl * bran_p + husk_qtl * husk_p
            scenarios.append({
                "price_change_pct": pct_change,
                "bran_price":       round(bran_p, 2),
                "husk_price":       round(husk_p, 2),
                "byproduct_revenue":round(rev, 2),
                "vs_base":          round(rev - base_total, 2),
            })

        return SimulationResult(
            simulation_type = "byproduct_sensitivity",
            scenario_a = {"name": "Base Case", "bran_price": base_bran_price_qtl,
                          "husk_price": base_husk_price_qtl, "revenue": round(base_total, 2)},
            scenario_b = {"price_scenarios": scenarios},
            comparison = {
                "bran_tonnes_annual":  round(bran_qtl / 10, 1),
                "husk_tonnes_annual":  round(husk_qtl / 10, 1),
                "base_byproduct_rev":  round(base_total, 2),
                "impact_per_10pct_change": round(base_total * 0.10, 2),
            },
            recommendation = (
                f"Byproduct revenue ₹{base_total:,.0f}/yr. Each 10% price move = ₹{base_total*0.10:,.0f} impact. "
                f"Negotiate advance contracts with bran solvent extractors for price stability."
            ),
            net_saving = 0.0,
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_simulator = RiceMillWhatIfSimulator()

def ricemill_whatif(params: dict) -> dict:
    scenario = params.get("scenario", "regime")
    try:
        if scenario == "regime":
            result = _simulator.regime_comparison(
                gross_income       = float(params.get("gross_income", 0)),
                deductions_80c     = float(params.get("deductions_80c", 0)),
                deductions_80d     = float(params.get("deductions_80d", 0)),
                hra_exemption      = float(params.get("hra_exemption", 0)),
                interest_home_loan = float(params.get("interest_home_loan", 0)),
                other_deductions   = float(params.get("other_deductions", 0)),
            )
        elif scenario == "gst_scheme":
            result = _simulator.gst_scheme_comparison(
                annual_turnover      = float(params.get("annual_turnover", 0)),
                branded_rice_pct     = float(params.get("branded_rice_pct", 0.30)),
                milling_private_pct  = float(params.get("milling_private_pct", 0.10)),
                input_tax_credit     = float(params.get("input_tax_credit", 0)),
            )
        elif scenario == "fci_vs_private":
            result = _simulator.fci_vs_private_mix(
                total_rice_tonnes         = float(params.get("total_rice_tonnes", 0)),
                fci_milling_rate_qtl      = float(params.get("fci_milling_rate_qtl", 27.50)),
                private_sale_price_qtl    = float(params.get("private_sale_price_qtl", 2200)),
                paddy_cost_qtl            = float(params.get("paddy_cost_qtl", 2183)),
                fci_pct_of_capacity       = float(params.get("fci_pct_of_capacity", 0.60)),
            )
        elif scenario == "byproduct":
            result = _simulator.byproduct_sensitivity(
                annual_paddy_tonnes  = float(params.get("annual_paddy_tonnes", 0)),
                base_bran_price_qtl  = float(params.get("base_bran_price_qtl", 350)),
                base_husk_price_qtl  = float(params.get("base_husk_price_qtl", 60)),
            )
        else:
            return {"error": f"Unknown scenario: {scenario}"}
        return asdict(result)
    except Exception as e:
        return {"error": str(e)}
