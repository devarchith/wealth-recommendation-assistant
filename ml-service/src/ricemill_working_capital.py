"""
Rice Mill Working Capital Stress Predictor
==========================================
Predicts working capital stress for rice mills based on:

  Stock positions:
    - Paddy inventory (value at MSP / purchase price)
    - Milled rice inventory (by grade: raw/boiled/parboiled)
    - By-products (rice bran, husk, broken rice)
    - In-transit / custom milling stock

  Cash flow:
    - Daily cash burn (operations, wages, power)
    - Pending receivables (FCI dues, private buyers)
    - Payables to farmers (pending paddy payments)
    - Bank overdraft utilisation vs CC limit

  Seasonal signals:
    - Kharif season: Oct–Jan (peak procurement)
    - Rabi season: Mar–May (second crop)
    - Lean season: Jun–Sep (stock drawdown)
    - FCI payment cycle: typically 30–45 days post-delivery

  Stress indicators:
    - Cash runway (days of operations funded)
    - Current ratio (< 1.2 = stressed)
    - Debtor days (FCI dues >45 days = stressed)
    - Stock holding period vs industry norm (25–35 days)
    - CC utilisation >80% = credit stress
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StressLevel(str, Enum):
    CRITICAL = "critical"   # < 7 days cash runway
    HIGH     = "high"       # 7–15 days
    MODERATE = "moderate"   # 15–30 days
    LOW      = "low"        # 30–60 days
    HEALTHY  = "healthy"    # > 60 days


class Season(str, Enum):
    KHARIF  = "kharif"    # Oct–Jan
    RABI    = "rabi"      # Mar–May
    LEAN    = "lean"      # Jun–Sep


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Industry benchmarks for rice mills (AP/TS)
BENCHMARK = {
    "current_ratio_min":     1.20,
    "current_ratio_healthy": 1.75,
    "debtor_days_max":       45,
    "stock_days_normal":     30,
    "cc_utilisation_max":    0.80,
    "cash_runway_critical":  7,
    "cash_runway_healthy":   30,
}

# Average daily cost benchmarks (₹ per tonne milling capacity)
COST_PER_TONNE_DAY = {
    "power":     120,      # electricity (3-phase mill)
    "labour":     80,      # skilled + unskilled
    "fuel":       40,      # diesel for boiler (parboiled mills)
    "admin":      20,      # office / misc
}


def get_season() -> Season:
    m = date.today().month
    if m in (10, 11, 12, 1):
        return Season.KHARIF
    elif m in (3, 4, 5):
        return Season.RABI
    else:
        return Season.LEAN


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StockPosition:
    paddy_tonnes:          float = 0.0
    paddy_value:           float = 0.0
    rice_raw_tonnes:       float = 0.0
    rice_boiled_tonnes:    float = 0.0
    rice_parboiled_tonnes: float = 0.0
    rice_avg_price_qtl:    float = 2200.0   # ₹/quintal market price
    bran_tonnes:           float = 0.0
    bran_price_qtl:        float = 350.0    # ₹/quintal rice bran
    husk_tonnes:           float = 0.0
    husk_price_qtl:        float = 60.0     # ₹/quintal husk
    broken_rice_tonnes:    float = 0.0
    broken_price_qtl:      float = 1200.0   # ₹/quintal broken

    @property
    def total_rice_tonnes(self) -> float:
        return self.rice_raw_tonnes + self.rice_boiled_tonnes + self.rice_parboiled_tonnes

    @property
    def rice_value(self) -> float:
        return self.total_rice_tonnes * 10 * self.rice_avg_price_qtl  # tonnes→qtl ×10

    @property
    def bran_value(self) -> float:
        return self.bran_tonnes * 10 * self.bran_price_qtl

    @property
    def husk_value(self) -> float:
        return self.husk_tonnes * 10 * self.husk_price_qtl

    @property
    def broken_value(self) -> float:
        return self.broken_rice_tonnes * 10 * self.broken_price_qtl

    @property
    def total_inventory_value(self) -> float:
        return self.paddy_value + self.rice_value + self.bran_value + self.husk_value + self.broken_value


@dataclass
class CashFlowSnapshot:
    cash_in_hand:          float = 0.0
    bank_balance:          float = 0.0
    # Receivables
    fci_dues:              float = 0.0
    fci_due_days:          int   = 0     # how old is the FCI invoice
    private_buyer_dues:    float = 0.0
    # Payables
    farmer_payables:       float = 0.0   # paddy payments pending
    transport_payables:    float = 0.0
    misc_creditors:        float = 0.0
    # Credit facility
    cc_limit:              float = 0.0
    cc_utilised:           float = 0.0
    # Daily burn
    daily_operations_cost: float = 0.0
    milling_capacity_tpd:  float = 0.0  # tonnes per day


@dataclass
class WorkingCapitalReport:
    mill_id:           str
    mill_name:         str
    report_date:       str
    season:            Season
    stress_level:      StressLevel
    # Key ratios
    current_ratio:     float
    cash_runway_days:  int
    debtor_days_fci:   int
    cc_utilisation_pct:float
    stock_days:        int
    # Values
    total_current_assets:  float
    total_current_liabilities: float
    net_working_capital:   float
    # Recommendations
    alerts:            List[str]
    recommendations:   List[str]
    # Detailed breakdown
    inventory:         Dict
    cashflow:          Dict


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class WorkingCapitalPredictor:
    """
    Computes working capital stress for a rice mill.
    """

    def assess(
        self,
        mill_id:    str,
        mill_name:  str,
        stock:      StockPosition,
        cash:       CashFlowSnapshot,
        monthly_revenue: float = 0.0,
    ) -> WorkingCapitalReport:

        today  = date.today()
        season = get_season()

        # ── Current assets ───────────────────────────────────────────────
        liquid_cash      = cash.cash_in_hand + cash.bank_balance + (cash.cc_limit - cash.cc_utilised)
        receivables      = cash.fci_dues + cash.private_buyer_dues
        total_ca         = liquid_cash + receivables + stock.total_inventory_value

        # ── Current liabilities ──────────────────────────────────────────
        total_cl         = (cash.farmer_payables + cash.transport_payables +
                            cash.misc_creditors + cash.cc_utilised)

        # ── Ratios ───────────────────────────────────────────────────────
        current_ratio    = total_ca / max(1, total_cl)
        net_wc           = total_ca - total_cl

        # Daily burn
        daily_cost = cash.daily_operations_cost
        if daily_cost == 0 and cash.milling_capacity_tpd > 0:
            daily_cost = cash.milling_capacity_tpd * sum(COST_PER_TONNE_DAY.values())

        available_cash   = cash.cash_in_hand + cash.bank_balance + (cash.cc_limit - cash.cc_utilised)
        cash_runway      = int(available_cash / max(1, daily_cost))

        debtor_days_fci  = cash.fci_due_days if cash.fci_dues > 0 else 0
        cc_util_pct      = (cash.cc_utilised / max(1, cash.cc_limit)) * 100 if cash.cc_limit > 0 else 0.0

        # Stock days (inventory turnover)
        daily_revenue    = monthly_revenue / 30 if monthly_revenue > 0 else max(1, daily_cost * 1.05)
        stock_days       = int(stock.total_inventory_value / max(1, daily_revenue))

        # ── Stress level ─────────────────────────────────────────────────
        if cash_runway <= BENCHMARK["cash_runway_critical"]:
            stress = StressLevel.CRITICAL
        elif cash_runway <= 15:
            stress = StressLevel.HIGH
        elif cash_runway <= BENCHMARK["cash_runway_healthy"]:
            stress = StressLevel.MODERATE
        elif cash_runway <= 60:
            stress = StressLevel.LOW
        else:
            stress = StressLevel.HEALTHY

        # Additional stress escalation
        if current_ratio < 1.0 and stress.value not in ("critical",):
            stress = StressLevel.HIGH
        if cc_util_pct > 90:
            stress = StressLevel.CRITICAL if cash_runway < 15 else StressLevel.HIGH

        # ── Alerts ───────────────────────────────────────────────────────
        alerts = []
        recommendations = []

        if cash_runway <= 7:
            alerts.append(f"CRITICAL: Only {cash_runway} days of cash runway remaining")
            recommendations.append("Urgently collect FCI dues. Reduce farmer payments to minimum. Draw CC limit.")

        if current_ratio < BENCHMARK["current_ratio_min"]:
            alerts.append(f"Current ratio {current_ratio:.2f} is below healthy threshold of {BENCHMARK['current_ratio_min']}")
            recommendations.append("Reduce creditor payments. Accelerate rice sale to improve liquidity.")

        if debtor_days_fci > BENCHMARK["debtor_days_max"]:
            alerts.append(f"FCI dues ₹{cash.fci_dues:,.0f} outstanding for {debtor_days_fci} days (>45 day norm)")
            recommendations.append("Submit FCI Payment Follow-up (FPF) form to district FCI office. Escalate if needed.")

        if cc_util_pct > BENCHMARK["cc_utilisation_max"] * 100:
            alerts.append(f"CC utilisation {cc_util_pct:.0f}% exceeds 80% limit — credit stress")
            recommendations.append("Liquidate bran/husk stock immediately for cash. Negotiate CC limit enhancement.")

        if stock_days > 45:
            alerts.append(f"Inventory holding {stock_days} days — excess stock build-up")
            recommendations.append("Accelerate rice dispatches. Avoid paddy procurement until stock reduces.")

        if season == Season.KHARIF:
            recommendations.append("Kharif season: stagger paddy procurement to avoid cash crunch. Pre-negotiate FCI delivery schedule.")
        elif season == Season.LEAN:
            recommendations.append("Lean season: focus on bran/husk sales for cash generation. Reduce mill running hours if unprofitable.")

        if cash.farmer_payables > available_cash * 0.5:
            alerts.append(f"Farmer payables ₹{cash.farmer_payables:,.0f} exceed 50% of available cash")
            recommendations.append("Prioritise farmer payments to maintain paddy supply chain. Arrange short-term bridge loan if needed.")

        return WorkingCapitalReport(
            mill_id                   = mill_id,
            mill_name                 = mill_name,
            report_date               = today.isoformat(),
            season                    = season,
            stress_level              = stress,
            current_ratio             = round(current_ratio, 2),
            cash_runway_days          = cash_runway,
            debtor_days_fci           = debtor_days_fci,
            cc_utilisation_pct        = round(cc_util_pct, 1),
            stock_days                = stock_days,
            total_current_assets      = round(total_ca, 2),
            total_current_liabilities = round(total_cl, 2),
            net_working_capital       = round(net_wc, 2),
            alerts                    = alerts,
            recommendations           = recommendations,
            inventory                 = {
                "paddy_value":          round(stock.paddy_value, 2),
                "rice_value":           round(stock.rice_value, 2),
                "bran_value":           round(stock.bran_value, 2),
                "husk_value":           round(stock.husk_value, 2),
                "broken_value":         round(stock.broken_value, 2),
                "total_inventory":      round(stock.total_inventory_value, 2),
                "paddy_tonnes":         stock.paddy_tonnes,
                "rice_tonnes":          stock.total_rice_tonnes,
            },
            cashflow                  = {
                "cash_and_bank":        round(cash.cash_in_hand + cash.bank_balance, 2),
                "fci_receivable":       round(cash.fci_dues, 2),
                "private_receivable":   round(cash.private_buyer_dues, 2),
                "farmer_payable":       round(cash.farmer_payables, 2),
                "cc_limit":             round(cash.cc_limit, 2),
                "cc_utilised":          round(cash.cc_utilised, 2),
                "cc_available":         round(cash.cc_limit - cash.cc_utilised, 2),
                "daily_burn":           round(daily_cost, 2),
            },
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_predictor = WorkingCapitalPredictor()

def ricemill_working_capital(params: dict) -> dict:
    try:
        stock = StockPosition(
            paddy_tonnes           = float(params.get("paddy_tonnes", 0)),
            paddy_value            = float(params.get("paddy_value", 0)),
            rice_raw_tonnes        = float(params.get("rice_raw_tonnes", 0)),
            rice_boiled_tonnes     = float(params.get("rice_boiled_tonnes", 0)),
            rice_parboiled_tonnes  = float(params.get("rice_parboiled_tonnes", 0)),
            rice_avg_price_qtl     = float(params.get("rice_avg_price_qtl", 2200)),
            bran_tonnes            = float(params.get("bran_tonnes", 0)),
            bran_price_qtl         = float(params.get("bran_price_qtl", 350)),
            husk_tonnes            = float(params.get("husk_tonnes", 0)),
            husk_price_qtl         = float(params.get("husk_price_qtl", 60)),
            broken_rice_tonnes     = float(params.get("broken_rice_tonnes", 0)),
            broken_price_qtl       = float(params.get("broken_price_qtl", 1200)),
        )
        cash = CashFlowSnapshot(
            cash_in_hand           = float(params.get("cash_in_hand", 0)),
            bank_balance           = float(params.get("bank_balance", 0)),
            fci_dues               = float(params.get("fci_dues", 0)),
            fci_due_days           = int(params.get("fci_due_days", 0)),
            private_buyer_dues     = float(params.get("private_buyer_dues", 0)),
            farmer_payables        = float(params.get("farmer_payables", 0)),
            transport_payables     = float(params.get("transport_payables", 0)),
            misc_creditors         = float(params.get("misc_creditors", 0)),
            cc_limit               = float(params.get("cc_limit", 0)),
            cc_utilised            = float(params.get("cc_utilised", 0)),
            daily_operations_cost  = float(params.get("daily_operations_cost", 0)),
            milling_capacity_tpd   = float(params.get("milling_capacity_tpd", 0)),
        )
        report = _predictor.assess(
            mill_id         = params.get("mill_id", "RM001"),
            mill_name       = params.get("mill_name", "Rice Mill"),
            stock           = stock,
            cash            = cash,
            monthly_revenue = float(params.get("monthly_revenue", 0)),
        )
        return asdict(report)
    except Exception as e:
        return {"error": str(e)}
