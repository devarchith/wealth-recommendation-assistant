"""
Capital Gains Calculator — India FY 2024-25
Post-Budget 2024 rates (Finance Act 2024):
  • STCG on listed equity/equity MF (Sec 111A): 20% (raised from 15%)
  • LTCG on listed equity/equity MF (Sec 112A): 12.5% (raised from 10%), ₹1.25L exempt
  • LTCG on other assets (Sec 112): 12.5% WITHOUT indexation (indexation removed w.e.f. 23-Jul-2024)
  • STCG on other assets: Added to total income, taxed at slab rate
  • Debt MF purchased on/after 1-Apr-2023: STCG regardless of holding — taxed at slab
  • Gold / Unlisted Shares: LTCG if held >24 months
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------

class AssetType(str, Enum):
    LISTED_EQUITY      = "listed_equity"       # Shares on NSE/BSE
    EQUITY_MUTUAL_FUND = "equity_mutual_fund"  # Equity-oriented MF (>65% equity)
    DEBT_MUTUAL_FUND   = "debt_mutual_fund"    # Debt MF (always STCG post Apr-2023)
    GOLD               = "gold"                # Physical/digital/SGBs (non-SGB)
    REAL_ESTATE        = "real_estate"         # Immovable property
    UNLISTED_SHARES    = "unlisted_shares"     # Private company shares
    OTHER              = "other"               # Art, jewellery, other capital assets


# Holding period thresholds (months) for LTCG classification
LTCG_HOLDING_THRESHOLD: Dict[AssetType, int] = {
    AssetType.LISTED_EQUITY:      12,
    AssetType.EQUITY_MUTUAL_FUND: 12,
    AssetType.DEBT_MUTUAL_FUND:   0,   # Always STCG (post Apr-2023 purchases)
    AssetType.GOLD:               24,
    AssetType.REAL_ESTATE:        24,
    AssetType.UNLISTED_SHARES:    24,
    AssetType.OTHER:              36,
}

# Tax rates post-Budget 2024
STCG_RATE_111A   = 0.20    # Listed equity / equity MF STCG (Sec 111A)
LTCG_RATE_112A   = 0.125   # Listed equity / equity MF LTCG (Sec 112A)
LTCG_EXEMPT_112A = 125_000 # ₹1.25L annual exemption (Sec 112A)
LTCG_RATE_OTHER  = 0.125   # Other LTCG (Sec 112) — no indexation post Jul-2024
SURCHARGE_CAP_LTCG = 0.15  # Surcharge on LTCG capped at 15%

# CII for indexation (pre-Jul-2024 purchases of real estate / gold may use old rates)
COST_INFLATION_INDEX: Dict[int, int] = {
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117, 2006: 122,
    2007: 129, 2008: 137, 2009: 148, 2010: 167, 2011: 184, 2012: 200,
    2013: 220, 2014: 240, 2015: 254, 2016: 264, 2017: 272, 2018: 280,
    2019: 289, 2020: 301, 2021: 317, 2022: 331, 2023: 348, 2024: 363,
    2025: 380,   # Provisional — update when notified
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AssetTransaction:
    """A single buy-sell transaction for capital gains computation."""
    transaction_id:   str
    asset_type:       AssetType
    asset_name:       str                    # e.g. "RELIANCE", "Nifty 50 Index Fund"
    buy_date:         date
    sell_date:        date
    buy_price:        float                  # Per unit cost (₹)
    sell_price:       float                  # Per unit sale price (₹)
    units:            float                  # Number of units / shares
    buy_expenses:     float = 0.0            # Brokerage, STT, stamp duty on buy
    sell_expenses:    float = 0.0            # Brokerage, STT on sell
    purchase_after_apr2023: bool = True      # For debt MF classification
    apply_indexation: bool = False           # Override: use indexed cost (pre-Jul-2024)
    isin:             Optional[str] = None

    @property
    def holding_months(self) -> int:
        delta = self.sell_date - self.buy_date
        return int(delta.days / 30.44)   # Approximate

    @property
    def holding_days(self) -> int:
        return (self.sell_date - self.buy_date).days

    @property
    def is_ltcg(self) -> bool:
        threshold = LTCG_HOLDING_THRESHOLD.get(self.asset_type, 36)
        if self.asset_type == AssetType.DEBT_MUTUAL_FUND and self.purchase_after_apr2023:
            return False   # Always STCG regardless of holding
        return self.holding_months >= threshold

    @property
    def gross_proceeds(self) -> float:
        return self.sell_price * self.units

    @property
    def cost_of_acquisition(self) -> float:
        return self.buy_price * self.units + self.buy_expenses

    @property
    def net_proceeds(self) -> float:
        return self.gross_proceeds - self.sell_expenses


@dataclass
class GainRecord:
    """Computed gain/loss for a single transaction."""
    transaction_id:    str
    asset_type:        str
    asset_name:        str
    holding_days:      int
    gain_type:         str           # "STCG" | "LTCG"
    applicable_section: str          # "111A" | "112A" | "112" | "slab"
    cost_of_acquisition: float
    indexed_cost:      Optional[float]
    net_proceeds:      float
    gain_amount:       float         # Positive = gain, negative = loss
    tax_rate:          float
    tax_amount:        float         # Before 87A / surcharge / cess
    is_exempt:         bool          # E.g. within ₹1.25L LTCG 112A limit


@dataclass
class SetOffSummary:
    """
    Loss set-off rules (Sec 70–74):
      STCL can offset STCG and LTCG.
      LTCL can only offset LTCG (not STCG).
      Unabsorbed losses carry forward 8 years.
    """
    stcg_before_setoff:    float
    ltcg_before_setoff:    float
    stcl_current_year:     float      # Total short-term losses (positive number)
    ltcl_current_year:     float      # Total long-term losses (positive number)
    stcl_setoff_against_stcg: float
    stcl_setoff_against_ltcg: float
    ltcl_setoff_against_ltcg: float
    stcg_after_setoff:     float
    ltcg_after_setoff:     float
    stcl_carry_forward:    float
    ltcl_carry_forward:    float


@dataclass
class CapitalGainsResult:
    """Full capital gains computation output."""
    financial_year:        str
    records:               List[GainRecord]
    stcg_111a:             float     # Taxable STCG under Sec 111A
    stcg_slab:             float     # STCG taxed at slab (other assets)
    ltcg_112a_gross:       float     # LTCG under Sec 112A (before exemption)
    ltcg_112a_exempt:      float     # Exempt portion (up to ₹1.25L)
    ltcg_112a_taxable:     float     # After deducting exemption
    ltcg_other:            float     # LTCG under Sec 112 (other assets)
    set_off:               SetOffSummary
    tax_on_stcg_111a:      float
    tax_on_ltcg_112a:      float
    tax_on_ltcg_other:     float
    total_capital_gains_tax: float
    total_carry_forward_loss: float
    suggestions:           List[str]


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class CapitalGainsCalculator:
    """
    Computes capital gains tax for a financial year.

    Usage:
        calc = CapitalGainsCalculator(financial_year="2024-25")
        calc.add_transaction(AssetTransaction(...))
        result = calc.compute()
    """

    def __init__(self, financial_year: str = "2024-25"):
        self.financial_year = financial_year
        self._transactions: List[AssetTransaction] = []

    def add_transaction(self, txn: AssetTransaction) -> None:
        self._transactions.append(txn)

    def add_transactions(self, txns: List[AssetTransaction]) -> None:
        for t in txns:
            self.add_transaction(t)

    def compute(self) -> CapitalGainsResult:
        records: List[GainRecord] = []

        for txn in self._transactions:
            rec = self._compute_single(txn)
            records.append(rec)

        # Aggregate by category
        stcg_111a = sum(r.gain_amount for r in records
                        if r.gain_type == "STCG" and r.applicable_section == "111A"
                        and r.gain_amount > 0)
        stcl_111a = abs(sum(r.gain_amount for r in records
                            if r.gain_type == "STCG" and r.applicable_section == "111A"
                            and r.gain_amount < 0))

        stcg_slab = sum(r.gain_amount for r in records
                        if r.gain_type == "STCG" and r.applicable_section == "slab"
                        and r.gain_amount > 0)
        stcl_slab = abs(sum(r.gain_amount for r in records
                            if r.gain_type == "STCG" and r.applicable_section == "slab"
                            and r.gain_amount < 0))

        stcg_total_gain = stcg_111a + stcg_slab
        stcl_total      = stcl_111a + stcl_slab

        ltcg_112a_gross = sum(r.gain_amount for r in records
                              if r.gain_type == "LTCG" and r.applicable_section == "112A"
                              and r.gain_amount > 0)
        ltcl_112a       = abs(sum(r.gain_amount for r in records
                                  if r.gain_type == "LTCG" and r.applicable_section == "112A"
                                  and r.gain_amount < 0))

        ltcg_other_gain = sum(r.gain_amount for r in records
                              if r.gain_type == "LTCG" and r.applicable_section in ("112", "other")
                              and r.gain_amount > 0)
        ltcl_other      = abs(sum(r.gain_amount for r in records
                                  if r.gain_type == "LTCG" and r.applicable_section in ("112", "other")
                                  and r.gain_amount < 0))

        ltcg_total = ltcg_112a_gross + ltcg_other_gain
        ltcl_total = ltcl_112a + ltcl_other

        # Set-off
        set_off = self._apply_setoff(
            stcg_total_gain, ltcg_total, stcl_total, ltcl_total
        )

        # After set-off distribute proportionally between 111A and slab STCG
        stcg_net   = set_off.stcg_after_setoff
        ltcg_net   = set_off.ltcg_after_setoff

        # Allocate net STCG: 111A first, then slab
        stcg_111a_net = min(stcg_111a, stcg_net)
        stcg_slab_net = max(0.0, stcg_net - stcg_111a_net)

        # LTCG 112A exemption (₹1.25L)
        ltcg_112a_net   = min(ltcg_112a_gross, ltcg_net)
        ltcg_other_net  = max(0.0, ltcg_net - ltcg_112a_net)

        ltcg_112a_exempt  = min(LTCG_EXEMPT_112A, ltcg_112a_net)
        ltcg_112a_taxable = max(0.0, ltcg_112a_net - ltcg_112a_exempt)

        # Tax computation
        tax_stcg_111a  = stcg_111a_net * STCG_RATE_111A
        tax_ltcg_112a  = ltcg_112a_taxable * LTCG_RATE_112A
        tax_ltcg_other = ltcg_other_net * LTCG_RATE_OTHER

        total_cg_tax = tax_stcg_111a + tax_ltcg_112a + tax_ltcg_other
        total_cfl    = set_off.stcl_carry_forward + set_off.ltcl_carry_forward

        suggestions = self._generate_suggestions(
            stcg_111a_net, ltcg_112a_net, ltcg_112a_exempt,
            ltcg_112a_taxable, ltcg_other_net, set_off
        )

        return CapitalGainsResult(
            financial_year          = self.financial_year,
            records                 = records,
            stcg_111a               = stcg_111a_net,
            stcg_slab               = stcg_slab_net,
            ltcg_112a_gross         = ltcg_112a_gross,
            ltcg_112a_exempt        = ltcg_112a_exempt,
            ltcg_112a_taxable       = ltcg_112a_taxable,
            ltcg_other              = ltcg_other_net,
            set_off                 = set_off,
            tax_on_stcg_111a        = tax_stcg_111a,
            tax_on_ltcg_112a        = tax_ltcg_112a,
            tax_on_ltcg_other       = tax_ltcg_other,
            total_capital_gains_tax = total_cg_tax,
            total_carry_forward_loss= total_cfl,
            suggestions             = suggestions,
        )

    # ------------------------------------------------------------------
    # Single transaction computation
    # ------------------------------------------------------------------

    def _compute_single(self, txn: AssetTransaction) -> GainRecord:
        is_ltcg   = txn.is_ltcg
        gain_type = "LTCG" if is_ltcg else "STCG"

        # Determine section and rate
        if txn.asset_type in (AssetType.LISTED_EQUITY, AssetType.EQUITY_MUTUAL_FUND):
            if is_ltcg:
                section = "112A"
                rate    = LTCG_RATE_112A
            else:
                section = "111A"
                rate    = STCG_RATE_111A
        elif txn.asset_type == AssetType.DEBT_MUTUAL_FUND:
            section = "slab"   # Always at slab rate
            rate    = 0.0      # Will be added to normal income
        else:
            if is_ltcg:
                section = "112"
                rate    = LTCG_RATE_OTHER
            else:
                section = "slab"
                rate    = 0.0

        # Indexed cost (only relevant for pre-Jul-2024 real estate / gold if elected)
        indexed_cost = None
        effective_cost = txn.cost_of_acquisition
        if txn.apply_indexation and is_ltcg:
            buy_year  = txn.buy_date.year if txn.buy_date.month >= 4 else txn.buy_date.year - 1
            sell_year = txn.sell_date.year if txn.sell_date.month >= 4 else txn.sell_date.year - 1
            cii_buy   = COST_INFLATION_INDEX.get(buy_year, 100)
            cii_sell  = COST_INFLATION_INDEX.get(sell_year, 363)
            indexed_cost = txn.cost_of_acquisition * (cii_sell / cii_buy)
            effective_cost = indexed_cost

        gain = txn.net_proceeds - effective_cost
        tax  = max(0.0, gain) * rate

        return GainRecord(
            transaction_id     = txn.transaction_id,
            asset_type         = txn.asset_type.value,
            asset_name         = txn.asset_name,
            holding_days       = txn.holding_days,
            gain_type          = gain_type,
            applicable_section = section,
            cost_of_acquisition= txn.cost_of_acquisition,
            indexed_cost       = indexed_cost,
            net_proceeds       = txn.net_proceeds,
            gain_amount        = round(gain, 2),
            tax_rate           = rate,
            tax_amount         = round(tax, 2),
            is_exempt          = False,   # Updated later for 112A
        )

    # ------------------------------------------------------------------
    # Loss set-off
    # ------------------------------------------------------------------

    def _apply_setoff(
        self,
        stcg: float,
        ltcg: float,
        stcl: float,
        ltcl: float,
    ) -> SetOffSummary:
        # STCL offsets STCG first, then LTCG
        stcl_vs_stcg = min(stcl, stcg)
        remaining_stcl = stcl - stcl_vs_stcg
        stcg_after = stcg - stcl_vs_stcg

        stcl_vs_ltcg = min(remaining_stcl, ltcg)
        remaining_stcl_after = remaining_stcl - stcl_vs_ltcg
        ltcg_after_stcl = ltcg - stcl_vs_ltcg

        # LTCL only offsets remaining LTCG
        ltcl_vs_ltcg = min(ltcl, ltcg_after_stcl)
        remaining_ltcl = ltcl - ltcl_vs_ltcg
        ltcg_after = ltcg_after_stcl - ltcl_vs_ltcg

        return SetOffSummary(
            stcg_before_setoff         = stcg,
            ltcg_before_setoff         = ltcg,
            stcl_current_year          = stcl,
            ltcl_current_year          = ltcl,
            stcl_setoff_against_stcg   = stcl_vs_stcg,
            stcl_setoff_against_ltcg   = stcl_vs_ltcg,
            ltcl_setoff_against_ltcg   = ltcl_vs_ltcg,
            stcg_after_setoff          = max(0.0, stcg_after),
            ltcg_after_setoff          = max(0.0, ltcg_after),
            stcl_carry_forward         = remaining_stcl_after,
            ltcl_carry_forward         = remaining_ltcl,
        )

    # ------------------------------------------------------------------
    # Suggestions
    # ------------------------------------------------------------------

    def _generate_suggestions(
        self,
        stcg_111a: float,
        ltcg_112a: float,
        ltcg_112a_exempt: float,
        ltcg_112a_taxable: float,
        ltcg_other: float,
        set_off: SetOffSummary,
    ) -> List[str]:
        suggestions = []

        if ltcg_112a_taxable > 0:
            suggestions.append(
                f"You have ₹{ltcg_112a_taxable:,.0f} taxable LTCG on equity (Sec 112A) "
                f"at 12.5% — ₹{ltcg_112a_exempt:,.0f} was exempted under the ₹1.25L limit."
            )

        if set_off.stcl_carry_forward > 0:
            suggestions.append(
                f"₹{set_off.stcl_carry_forward:,.0f} short-term capital loss can be "
                f"carried forward for 8 years and set-off against future capital gains."
            )
        if set_off.ltcl_carry_forward > 0:
            suggestions.append(
                f"₹{set_off.ltcl_carry_forward:,.0f} long-term capital loss (LTCL) can be "
                f"carried forward for 8 years — set-off only against future LTCG."
            )

        # Tax-loss harvesting opportunity
        if stcg_111a > 0 and ltcg_112a < LTCG_EXEMPT_112A:
            headroom = LTCG_EXEMPT_112A - ltcg_112a
            suggestions.append(
                f"You have ₹{headroom:,.0f} of unused LTCG exemption (Sec 112A). "
                f"Consider booking profits on long-term equity holdings up to this amount "
                f"(tax-loss harvesting) before March 31."
            )

        if stcg_111a > 0:
            suggestions.append(
                f"STCG of ₹{stcg_111a:,.0f} on equity/equity MF taxed at 20% (Sec 111A) — "
                f"consider holding for 12+ months to qualify for the lower 12.5% LTCG rate."
            )

        if ltcg_other > 0:
            suggestions.append(
                f"LTCG of ₹{ltcg_other:,.0f} on other assets (gold/property/unlisted) "
                f"taxed at 12.5% without indexation under Sec 112 (post-Budget 2024 rules)."
            )

        # Debt MF note
        debt_txns = [t for t in self._transactions
                     if t.asset_type == AssetType.DEBT_MUTUAL_FUND
                     and t.purchase_after_apr2023]
        if debt_txns:
            suggestions.append(
                "Debt mutual fund gains (purchased after Apr 1, 2023) are taxed at "
                "your income slab rate — consider alternatives like PPF or tax-free bonds "
                "for lower post-tax returns."
            )

        if not suggestions:
            suggestions.append(
                "No taxable capital gains this year. Keep records of all transactions "
                "for ITR filing and carry-forward loss claims."
            )

        return suggestions


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def compute_capital_gains(params: dict) -> dict:
    """
    JSON-serializable wrapper for Flask endpoint.

    params keys:
        financial_year (str)
        transactions (list[dict]) — AssetTransaction fields with string dates
    """
    from datetime import datetime as _dt

    def _parse(val) -> date:
        if isinstance(val, date):
            return val
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return _dt.strptime(val, fmt).date()
            except (ValueError, TypeError):
                continue
        return date.today()

    calc = CapitalGainsCalculator(financial_year=params.get("financial_year", "2024-25"))

    for t in params.get("transactions", []):
        asset_type = AssetType(t.get("asset_type", "listed_equity"))
        calc.add_transaction(AssetTransaction(
            transaction_id        = t.get("transaction_id", str(id(t))),
            asset_type            = asset_type,
            asset_name            = t.get("asset_name", ""),
            buy_date              = _parse(t.get("buy_date", "")),
            sell_date             = _parse(t.get("sell_date", "")),
            buy_price             = float(t.get("buy_price", 0)),
            sell_price            = float(t.get("sell_price", 0)),
            units                 = float(t.get("units", 0)),
            buy_expenses          = float(t.get("buy_expenses", 0)),
            sell_expenses         = float(t.get("sell_expenses", 0)),
            purchase_after_apr2023= bool(t.get("purchase_after_apr2023", True)),
            apply_indexation      = bool(t.get("apply_indexation", False)),
            isin                  = t.get("isin"),
        ))

    result = calc.compute()

    return {
        "financial_year":           result.financial_year,
        "stcg_111a":                result.stcg_111a,
        "stcg_slab":                result.stcg_slab,
        "ltcg_112a_gross":          result.ltcg_112a_gross,
        "ltcg_112a_exempt":         result.ltcg_112a_exempt,
        "ltcg_112a_taxable":        result.ltcg_112a_taxable,
        "ltcg_other":               result.ltcg_other,
        "tax_on_stcg_111a":         result.tax_on_stcg_111a,
        "tax_on_ltcg_112a":         result.tax_on_ltcg_112a,
        "tax_on_ltcg_other":        result.tax_on_ltcg_other,
        "total_capital_gains_tax":  result.total_capital_gains_tax,
        "total_carry_forward_loss": result.total_carry_forward_loss,
        "set_off": {
            "stcg_before_setoff":  result.set_off.stcg_before_setoff,
            "ltcg_before_setoff":  result.set_off.ltcg_before_setoff,
            "stcl_current_year":   result.set_off.stcl_current_year,
            "ltcl_current_year":   result.set_off.ltcl_current_year,
            "stcg_after_setoff":   result.set_off.stcg_after_setoff,
            "ltcg_after_setoff":   result.set_off.ltcg_after_setoff,
            "stcl_carry_forward":  result.set_off.stcl_carry_forward,
            "ltcl_carry_forward":  result.set_off.ltcl_carry_forward,
        },
        "records": [asdict(r) for r in result.records],
        "suggestions": result.suggestions,
    }
