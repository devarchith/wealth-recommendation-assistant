"""
Rice Mill MSP Calculator — 2024-25 Kharif and Rabi Rates
==========================================================
Computes MSP-based paddy procurement costs, FCI purchase economics,
and profitability analysis for rice mills using official MSP rates.

MSP 2024-25:
  Kharif crops (Cabinet approved June 2024):
    - Common paddy:  ₹2,300/quintal (up from ₹2,183 in 2023-24)
    - Grade A paddy: ₹2,320/quintal (premium for long-grain)

  Rabi crops (for reference):
    - Wheat:         ₹2,275/quintal

  Additional levies on MSP procurement:
    - Market fee (APMC): 1.5–2% (state-specific)
    - Rural Infrastructure Development Fund (RIDF): 1% (waived in some states)
    - Commission agent fee: 1% (if via APMC)
    - Handling / loading: ₹15–₹25/qtl

  Procurement economics:
    - Effective cost = MSP + all levies
    - FCI reimbursement = MSP + EC (Economic Cost)
    - Miller's margin = FCI rate − Effective procurement cost

  Break-even analysis:
    - At what rice price does the mill break even?
    - Sensitivity to paddy price, milling cost, byproduct revenue

Integrates with:
  - ricemill_fci_billing.py for FCI milling income
  - ricemill_whatif_simulator.py for scenario analysis
  - ricemill_conversion_tracker.py for outturn efficiency
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import date
from enum import Enum


# ---------------------------------------------------------------------------
# MSP Rates — Official CACP recommendations, approved by Cabinet
# ---------------------------------------------------------------------------

MSP_KHARIF_2024_25: Dict[str, float] = {
    "paddy_common":       2300.0,   # ₹/quintal
    "paddy_grade_a":      2320.0,
    "jowar_hybrid":       3371.0,
    "bajra":              2625.0,
    "maize":              2225.0,
    "ragi":               4290.0,
    "tur_arhar":          7550.0,
    "moong":              8682.0,
    "urad":               7400.0,
    "groundnut":          6783.0,
    "sunflower":          7280.0,
    "soybean":            4892.0,
    "sesamum":            9267.0,
    "nigerseed":          8717.0,
    "cotton_medium":      7121.0,
    "cotton_long":        7521.0,
}

MSP_RABI_2024_25: Dict[str, float] = {
    "wheat":             2275.0,
    "barley":            1735.0,
    "gram":              5440.0,
    "lentil_masur":      6425.0,
    "rapeseed_mustard":  5650.0,
    "safflower":         5800.0,
}

# Year-over-year increase for paddy
MSP_PADDY_HISTORY: Dict[str, Dict[str, float]] = {
    "2020-21": {"common": 1868, "grade_a": 1888},
    "2021-22": {"common": 1940, "grade_a": 1960},
    "2022-23": {"common": 2015, "grade_a": 2035},
    "2023-24": {"common": 2183, "grade_a": 2203},
    "2024-25": {"common": 2300, "grade_a": 2320},
}

# AP / TS state-specific levies on paddy procurement (% of MSP)
AP_LEVIES = {
    "apmc_market_fee":     0.015,   # 1.5%
    "ridf":                0.010,   # 1%
    "commission_agent":    0.010,   # 1%
    "pollution_cess":      0.002,   # 0.2%
}

TS_LEVIES = {
    "apmc_market_fee":     0.020,   # 2%
    "ridf":                0.010,   # 1%
    "commission_agent":    0.010,   # 1%
}

HANDLING_COST_PER_QTL = 20.0   # ₹/qtl loading/unloading

# FCI Economic Cost components (approximate, 2024-25)
FCI_ECONOMIC_COST_COMPONENTS = {
    "msp":            2300.0,
    "procurement_incidentals": 120.0,   # state levies + handling
    "milling_charges":  27.5,
    "distribution_cost":150.0,          # freight + storage
    "total_economic_cost": 2597.5,      # approximate CIP basis
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProcurementChannel(str, Enum):
    FCI_DIRECT   = "fci_direct"
    APMC         = "apmc"
    DIRECT_FARMER= "direct_farmer"


class State(str, Enum):
    ANDHRA_PRADESH = "ap"
    TELANGANA      = "ts"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProcurementCost:
    channel:          ProcurementChannel
    state:            State
    paddy_grade:      str      # "common" or "grade_a"
    qtl:              float    # quintals

    msp_per_qtl:      float
    levy_total_pct:   float
    levy_amount_qtl:  float
    handling_qtl:     float
    effective_cost_qtl: float
    total_cost:       float

    notes:            List[str] = field(default_factory=list)


@dataclass
class BreakEvenResult:
    paddy_qtl:           float
    paddy_cost_qtl:      float
    milling_cost_qtl:    float
    byproduct_revenue_qtl: float
    total_cost_qtl:      float
    break_even_rice_price_qtl: float
    current_rice_price_qtl: float
    margin_per_qtl:      float
    margin_pct:          float
    is_profitable:       bool
    fci_milling_income_qtl: float   # if milling for FCI
    fci_net_per_qtl_paddy:  float


@dataclass
class MSPAnalysisReport:
    report_date:      str
    season:           str        # "kharif_2024_25" or "rabi_2024_25"
    paddy_grade:      str
    msp_per_qtl:      float
    yoy_increase:     float
    yoy_increase_pct: float
    procurement_cost: ProcurementCost
    break_even:       BreakEvenResult
    historical_msp:   Dict[str, float]
    recommendations:  List[str]


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class MSPCalculator:

    def compute_procurement_cost(
        self,
        qtl:          float,
        paddy_grade:  str   = "common",
        state:        str   = "ap",
        channel:      str   = "direct_farmer",
        custom_msp:   Optional[float] = None,
    ) -> ProcurementCost:

        msp = custom_msp or MSP_KHARIF_2024_25.get(f"paddy_{paddy_grade}", 2300.0)
        st  = State(state)
        ch  = ProcurementChannel(channel)

        levies_map = AP_LEVIES if st == State.ANDHRA_PRADESH else TS_LEVIES
        levy_pct   = sum(levies_map.values()) if ch != ProcurementChannel.DIRECT_FARMER else 0.0
        levy_qtl   = round(msp * levy_pct, 2)
        handling   = HANDLING_COST_PER_QTL
        eff_cost   = round(msp + levy_qtl + handling, 2)
        total      = round(eff_cost * qtl, 2)

        notes = []
        if ch == ProcurementChannel.DIRECT_FARMER:
            notes.append("Direct farmer purchase: no APMC levy. Ensure digital payment for 40A(3) compliance.")
        if ch == ProcurementChannel.FCI_DIRECT:
            notes.append("FCI procurement: levies covered under state agreement. Mill acts as commission agent.")

        return ProcurementCost(
            channel          = ch,
            state            = st,
            paddy_grade      = paddy_grade,
            qtl              = qtl,
            msp_per_qtl      = msp,
            levy_total_pct   = round(levy_pct * 100, 2),
            levy_amount_qtl  = levy_qtl,
            handling_qtl     = handling,
            effective_cost_qtl = eff_cost,
            total_cost       = total,
            notes            = notes,
        )

    def compute_break_even(
        self,
        paddy_cost_qtl:    float,   # effective paddy cost per quintal
        milling_cost_qtl:  float = 150.0,  # ₹/qtl milled rice (power, labour, overhead)
        outturn:           float = 0.67,
        bran_yield:        float = 0.08,
        husk_yield:        float = 0.20,
        bran_price_qtl:    float = 380.0,
        husk_price_qtl:    float = 65.0,
        current_rice_price:float = 2200.0,
        fci_milling_rate:  float = 27.50,  # ₹/qtl paddy (if milling for FCI)
    ) -> BreakEvenResult:

        # Per quintal of paddy processed
        rice_qtl_per_paddy   = outturn
        bran_qtl_per_paddy   = bran_yield
        husk_qtl_per_paddy   = husk_yield

        byproduct_rev        = round(bran_qtl_per_paddy * bran_price_qtl + husk_qtl_per_paddy * husk_price_qtl, 2)
        milling_cost_paddy   = round(milling_cost_qtl * outturn, 2)  # scale to paddy basis
        total_cost_paddy     = round(paddy_cost_qtl + milling_cost_paddy - byproduct_rev, 2)

        # Break-even rice price per quintal
        breakeven_rice_qtl   = round(total_cost_paddy / max(0.01, rice_qtl_per_paddy), 2)
        margin_qtl           = round(current_rice_price - breakeven_rice_qtl, 2)
        margin_pct           = round(margin_qtl / max(1, current_rice_price) * 100, 2)

        # FCI milling income (if not selling rice but milling for FCI)
        fci_income_per_paddy = fci_milling_rate   # ₹/qtl paddy
        fci_net              = round(fci_income_per_paddy + byproduct_rev - milling_cost_paddy, 2)

        return BreakEvenResult(
            paddy_qtl              = 100.0,   # per 100 qtl basis
            paddy_cost_qtl         = paddy_cost_qtl,
            milling_cost_qtl       = milling_cost_qtl,
            byproduct_revenue_qtl  = byproduct_rev,
            total_cost_qtl         = total_cost_paddy,
            break_even_rice_price_qtl = breakeven_rice_qtl,
            current_rice_price_qtl = current_rice_price,
            margin_per_qtl         = margin_qtl,
            margin_pct             = margin_pct,
            is_profitable          = margin_qtl > 0,
            fci_milling_income_qtl = fci_income_per_paddy,
            fci_net_per_qtl_paddy  = fci_net,
        )

    def full_analysis(
        self,
        qtl:              float,
        paddy_grade:      str   = "common",
        state:            str   = "ap",
        channel:          str   = "direct_farmer",
        milling_cost_qtl: float = 150.0,
        current_rice_price: float = 2200.0,
        fci_milling_rate: float = 27.50,
    ) -> MSPAnalysisReport:

        pc   = self.compute_procurement_cost(qtl, paddy_grade, state, channel)
        be   = self.compute_break_even(
            paddy_cost_qtl    = pc.effective_cost_qtl,
            milling_cost_qtl  = milling_cost_qtl,
            current_rice_price= current_rice_price,
            fci_milling_rate  = fci_milling_rate,
        )

        msp_now  = pc.msp_per_qtl
        msp_prev = MSP_PADDY_HISTORY["2023-24"].get(paddy_grade, 2183)
        yoy_inc  = round(msp_now - msp_prev, 2)
        yoy_pct  = round(yoy_inc / msp_prev * 100, 2)

        recs = []
        if not be.is_profitable:
            recs.append(
                f"Current rice price ₹{current_rice_price}/qtl is below break-even "
                f"₹{be.break_even_rice_price_qtl}/qtl. Consider FCI milling (net ₹{be.fci_net_per_qtl_paddy}/qtl paddy)."
            )
        if be.fci_net_per_qtl_paddy > be.margin_per_qtl:
            recs.append(
                f"FCI milling (₹{be.fci_net_per_qtl_paddy}/qtl paddy) is more profitable than "
                f"private trade (₹{be.margin_per_qtl}/qtl paddy) at current prices."
            )
        recs.append(f"MSP 2024-25: ₹{msp_now}/qtl, up {yoy_pct:.1f}% (₹{yoy_inc}) from 2023-24.")
        recs.append("Pay farmers at MSP or above. Sub-MSP procurement attracts state penalty in AP/TS.")

        return MSPAnalysisReport(
            report_date     = date.today().isoformat(),
            season          = "kharif_2024_25",
            paddy_grade     = paddy_grade,
            msp_per_qtl     = msp_now,
            yoy_increase    = yoy_inc,
            yoy_increase_pct= yoy_pct,
            procurement_cost= pc,
            break_even      = be,
            historical_msp  = {yr: v[paddy_grade] for yr, v in MSP_PADDY_HISTORY.items()},
            recommendations = recs,
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_calc = MSPCalculator()

def ricemill_msp(params: dict) -> dict:
    action = params.get("action", "analysis")
    try:
        if action == "analysis":
            report = _calc.full_analysis(
                qtl              = float(params.get("qtl", 1000)),
                paddy_grade      = params.get("paddy_grade", "common"),
                state            = params.get("state", "ap"),
                channel          = params.get("channel", "direct_farmer"),
                milling_cost_qtl = float(params.get("milling_cost_qtl", 150)),
                current_rice_price = float(params.get("current_rice_price", 2200)),
                fci_milling_rate = float(params.get("fci_milling_rate", 27.50)),
            )
            return asdict(report)
        elif action == "rates":
            return {
                "msp_kharif_2024_25":  MSP_KHARIF_2024_25,
                "msp_rabi_2024_25":    MSP_RABI_2024_25,
                "paddy_history":       MSP_PADDY_HISTORY,
                "fci_economic_cost":   FCI_ECONOMIC_COST_COMPONENTS,
            }
        elif action == "break_even":
            be = _calc.compute_break_even(
                paddy_cost_qtl     = float(params.get("paddy_cost_qtl", 2300)),
                milling_cost_qtl   = float(params.get("milling_cost_qtl", 150)),
                current_rice_price = float(params.get("current_rice_price", 2200)),
                fci_milling_rate   = float(params.get("fci_milling_rate", 27.50)),
            )
            return asdict(be)
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
