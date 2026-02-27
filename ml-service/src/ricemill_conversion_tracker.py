"""
Rice Mill Paddy-to-Rice Conversion Tracker
===========================================
Tracks the complete conversion cycle from paddy procurement to finished
product (milled rice) and all by-products, for:

  Stock accounting:
    - Paddy inward (lot-wise, variety-wise)
    - Milling output: head rice, broken rice (5%, 25%, D-grade)
    - By-products: rice bran, husk, rice bran oil cake (if solvent plant)
    - Paddy moisture loss (weight reduction)
    - Milling loss (machine waste)

  Revenue accounting:
    - Rice sale (by grade/variety/market)
    - Bran sale (to solvent extractor / cattle feed)
    - Husk sale (to boiler / brick kiln)
    - Broken rice sale (poultry feed / starch industry)

  Efficiency KPIs:
    - Outturn % (actual vs standard 67%)
    - Head rice % (whole grain vs broken)
    - Bran recovery % (standard 8%)
    - Husk recovery % (standard 20%)
    - Milling loss % (should be <2%)
    - Energy consumption per tonne

  Inventory reconciliation:
    - Opening + Inward − Processed = Closing paddy
    - Total rice + bran + husk + broken + loss = Paddy processed
    - Any variance flags for investigation

  Lot traceability:
    - Variety tracking (Sona Masoori, BPT, MTU-1010, Swarna, IR-64)
    - Grade-wise output (FCI CMR, premium raw, export grade)
    - Date-wise milling schedule
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Constants — Industry standards for AP rice mills
# ---------------------------------------------------------------------------

STANDARD_OUTTURN         = 0.670   # 67% milled rice
STANDARD_HEAD_RICE_PCT   = 0.850   # 85% head rice of total milled rice
STANDARD_BRAN_PCT        = 0.080   # 8% bran of paddy
STANDARD_HUSK_PCT        = 0.200   # 20% husk of paddy
STANDARD_BROKEN_PCT      = 0.015   # 1.5% broken rice of paddy
STANDARD_MILLING_LOSS    = 0.030   # 3% unaccounted loss (dust, moisture)

# Moisture loss during drying/storage (%)
MOISTURE_LOSS_PER_PCT    = 0.01    # 1% weight reduction per 1% moisture above 14%

# Variety-specific outturn adjustments
VARIETY_OUTTURN = {
    "sona_masoori":  0.68,
    "bpt_5204":      0.68,
    "mtu_1010":      0.67,
    "swarna":        0.67,
    "ir_64":         0.66,
    "hmt":           0.69,
    "lalat":         0.65,
    "rni_15":        0.67,
    "common":        0.67,
}

# Market prices (₹/quintal, AP/TS wholesale, Feb 2025 reference)
MARKET_PRICES = {
    "sona_masoori_raw":   3200,
    "sona_masoori_boiled":3000,
    "bpt_raw":            2800,
    "mtu_1010_raw":       2400,
    "swarna_raw":         2200,
    "ir_64_raw":          2100,
    "broken_5pct":        1800,
    "broken_25pct":       1400,
    "broken_d_grade":     1000,
    "rice_bran":           380,
    "husk":                 65,
    "bran_oil_cake":       220,
    "common_raw":          2200,
}

# Enums
class PaddyVariety(str, Enum):
    SONA_MASOORI = "sona_masoori"
    BPT_5204     = "bpt_5204"
    MTU_1010     = "mtu_1010"
    SWARNA       = "swarna"
    IR_64        = "ir_64"
    HMT          = "hmt"
    COMMON       = "common"

class MillingType(str, Enum):
    RAW          = "raw"
    PARBOILED    = "parboiled"   # soaked, steamed, dried before milling
    BOILED       = "boiled"

class LotStatus(str, Enum):
    PENDING      = "pending"
    MILLING      = "milling"
    COMPLETED    = "completed"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PaddyLot:
    lot_id:           str
    receipt_date:     str
    variety:          str
    milling_type:     MillingType
    paddy_qtl:        float        # quintals received
    moisture_pct:     float
    # After moisture adjustment
    effective_paddy_qtl: float     = 0.0
    status:           LotStatus    = LotStatus.PENDING
    milled_date:      Optional[str]= None


@dataclass
class MillingOutput:
    lot_id:           str
    paddy_qtl_processed: float

    # Rice output
    head_rice_qtl:    float        # whole grain
    broken_5pct_qtl:  float
    broken_25pct_qtl: float
    broken_d_qtl:     float
    total_rice_qtl:   float

    # By-products
    bran_qtl:         float
    husk_qtl:         float
    milling_loss_qtl: float

    # KPIs
    actual_outturn_pct:  float
    head_rice_pct:       float
    bran_recovery_pct:   float
    husk_recovery_pct:   float
    milling_loss_pct:    float
    outturn_variance:    float    # actual vs standard (+ = better)

    # Revenue potential
    head_rice_value:     float
    broken_value:        float
    bran_value:          float
    husk_value:          float
    total_revenue_potential: float


@dataclass
class ConversionReport:
    mill_id:          str
    report_period:    str
    # Aggregate volumes
    total_paddy_qtl:  float
    total_rice_qtl:   float
    total_bran_qtl:   float
    total_husk_qtl:   float
    total_broken_qtl: float
    total_loss_qtl:   float
    # KPI averages
    avg_outturn_pct:  float
    avg_head_rice_pct:float
    # Revenue
    total_revenue_potential: float
    # Reconciliation
    reconciliation:   Dict
    efficiency_alerts:List[str]
    lots:             List[Dict]


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class ConversionTracker:
    """
    Tracks paddy-to-rice conversion for a rice mill.
    """

    def __init__(self, mill_id: str):
        self.mill_id   = mill_id
        self._lots:    Dict[str, PaddyLot]     = {}
        self._outputs: Dict[str, MillingOutput] = {}

    def receive_paddy(
        self,
        lot_id:       str,
        paddy_qtl:    float,
        variety:      str      = "common",
        milling_type: str      = "raw",
        moisture_pct: float    = 13.5,
        receipt_date: Optional[str] = None,
    ) -> PaddyLot:
        # Moisture adjustment
        if moisture_pct > 14.0:
            moisture_loss = paddy_qtl * (moisture_pct - 14.0) * MOISTURE_LOSS_PER_PCT
            effective_qtl = round(paddy_qtl - moisture_loss, 2)
        else:
            effective_qtl = paddy_qtl

        lot = PaddyLot(
            lot_id           = lot_id,
            receipt_date     = receipt_date or date.today().isoformat(),
            variety          = variety.lower(),
            milling_type     = MillingType(milling_type),
            paddy_qtl        = paddy_qtl,
            moisture_pct     = moisture_pct,
            effective_paddy_qtl = effective_qtl,
        )
        self._lots[lot_id] = lot
        return lot

    def record_milling(
        self,
        lot_id:           str,
        head_rice_qtl:    Optional[float] = None,
        broken_5pct_qtl:  float = 0.0,
        broken_25pct_qtl: float = 0.0,
        broken_d_qtl:     float = 0.0,
        bran_qtl:         Optional[float] = None,
        husk_qtl:         Optional[float] = None,
        variety:          Optional[str]   = None,
        milled_date:      Optional[str]   = None,
        rice_market:      str             = "common_raw",
    ) -> MillingOutput:

        lot = self._lots.get(lot_id)
        if not lot:
            raise KeyError(f"Lot {lot_id} not found")

        paddy = lot.effective_paddy_qtl
        var   = variety or lot.variety
        std_outturn = VARIETY_OUTTURN.get(var, STANDARD_OUTTURN)

        # If actuals not provided, compute from standard
        total_rice  = head_rice_qtl or round(paddy * std_outturn, 2)
        if head_rice_qtl is None:
            head_rice_qtl = round(total_rice * STANDARD_HEAD_RICE_PCT, 2)
            broken_5pct_qtl  = round(total_rice * 0.05, 2)
            broken_25pct_qtl = round(total_rice * 0.08, 2)
            broken_d_qtl     = round(total_rice * 0.02, 2)
            total_rice       = head_rice_qtl + broken_5pct_qtl + broken_25pct_qtl + broken_d_qtl
        else:
            total_rice = head_rice_qtl + broken_5pct_qtl + broken_25pct_qtl + broken_d_qtl

        bran_qtl_v = bran_qtl if bran_qtl is not None else round(paddy * STANDARD_BRAN_PCT, 2)
        husk_qtl_v = husk_qtl if husk_qtl is not None else round(paddy * STANDARD_HUSK_PCT, 2)

        accounted  = total_rice + bran_qtl_v + husk_qtl_v
        loss_qtl   = max(0.0, round(paddy - accounted, 2))

        # KPIs
        actual_outturn   = round(total_rice / max(0.01, paddy) * 100, 2)
        std_outturn_pct  = std_outturn * 100
        outturn_var      = round(actual_outturn - std_outturn_pct, 2)
        head_rice_pct    = round(head_rice_qtl / max(0.01, total_rice) * 100, 2)
        bran_pct         = round(bran_qtl_v / max(0.01, paddy) * 100, 2)
        husk_pct         = round(husk_qtl_v / max(0.01, paddy) * 100, 2)
        loss_pct         = round(loss_qtl / max(0.01, paddy) * 100, 2)

        # Revenue potential
        rice_price       = MARKET_PRICES.get(rice_market, MARKET_PRICES["common_raw"])
        head_rice_val    = round(head_rice_qtl * rice_price, 2)
        broken_val       = (
            round(broken_5pct_qtl  * MARKET_PRICES["broken_5pct"], 2) +
            round(broken_25pct_qtl * MARKET_PRICES["broken_25pct"], 2) +
            round(broken_d_qtl     * MARKET_PRICES["broken_d_grade"], 2)
        )
        bran_val         = round(bran_qtl_v * MARKET_PRICES["rice_bran"], 2)
        husk_val         = round(husk_qtl_v * MARKET_PRICES["husk"], 2)
        total_rev        = head_rice_val + broken_val + bran_val + husk_val

        output = MillingOutput(
            lot_id               = lot_id,
            paddy_qtl_processed  = paddy,
            head_rice_qtl        = head_rice_qtl,
            broken_5pct_qtl      = broken_5pct_qtl,
            broken_25pct_qtl     = broken_25pct_qtl,
            broken_d_qtl         = broken_d_qtl,
            total_rice_qtl       = round(total_rice, 2),
            bran_qtl             = bran_qtl_v,
            husk_qtl             = husk_qtl_v,
            milling_loss_qtl     = loss_qtl,
            actual_outturn_pct   = actual_outturn,
            head_rice_pct        = head_rice_pct,
            bran_recovery_pct    = bran_pct,
            husk_recovery_pct    = husk_pct,
            milling_loss_pct     = loss_pct,
            outturn_variance     = outturn_var,
            head_rice_value      = head_rice_val,
            broken_value         = broken_val,
            bran_value           = bran_val,
            husk_value           = husk_val,
            total_revenue_potential = total_rev,
        )
        self._outputs[lot_id] = output
        lot.status     = LotStatus.COMPLETED
        lot.milled_date= milled_date or date.today().isoformat()
        return output

    def generate_report(self, period: str = "") -> ConversionReport:
        outputs = list(self._outputs.values())
        lots    = list(self._lots.values())

        if not outputs:
            return ConversionReport(
                mill_id=self.mill_id, report_period=period or date.today().isoformat(),
                total_paddy_qtl=0, total_rice_qtl=0, total_bran_qtl=0, total_husk_qtl=0,
                total_broken_qtl=0, total_loss_qtl=0, avg_outturn_pct=0, avg_head_rice_pct=0,
                total_revenue_potential=0, reconciliation={}, efficiency_alerts=[],
                lots=[asdict(l) for l in lots],
            )

        total_paddy    = sum(o.paddy_qtl_processed for o in outputs)
        total_rice     = sum(o.total_rice_qtl for o in outputs)
        total_bran     = sum(o.bran_qtl for o in outputs)
        total_husk     = sum(o.husk_qtl for o in outputs)
        total_broken   = sum(o.broken_5pct_qtl + o.broken_25pct_qtl + o.broken_d_qtl for o in outputs)
        total_loss     = sum(o.milling_loss_qtl for o in outputs)
        avg_outturn    = round(sum(o.actual_outturn_pct for o in outputs) / len(outputs), 2)
        avg_head_rice  = round(sum(o.head_rice_pct for o in outputs) / len(outputs), 2)
        total_rev      = sum(o.total_revenue_potential for o in outputs)

        # Reconciliation
        total_output   = total_rice + total_bran + total_husk + total_loss
        recon_diff     = round(total_paddy - total_output, 2)

        recon = {
            "paddy_in":          round(total_paddy, 2),
            "rice_out":          round(total_rice, 2),
            "bran_out":          round(total_bran, 2),
            "husk_out":          round(total_husk, 2),
            "loss":              round(total_loss, 2),
            "total_accounted":   round(total_output, 2),
            "unaccounted_diff":  recon_diff,
            "balanced":          abs(recon_diff) < 1.0,
        }

        # Efficiency alerts
        alerts = []
        if avg_outturn < 65.0:
            alerts.append(f"Low outturn {avg_outturn}% (standard 67%) — check machine settings, paddy quality")
        if avg_head_rice < 80.0:
            alerts.append(f"Head rice {avg_head_rice}% below 85% norm — broken rice cost rising")
        if total_loss / max(1, total_paddy) * 100 > 4.0:
            alerts.append(f"Milling loss {total_loss/total_paddy*100:.1f}% above 3% norm — check dust extraction")
        if abs(recon_diff) > 5.0:
            alerts.append(f"Stock reconciliation gap: {recon_diff} qtl unaccounted — physical stock count required")

        return ConversionReport(
            mill_id               = self.mill_id,
            report_period         = period or date.today().isoformat(),
            total_paddy_qtl       = round(total_paddy, 2),
            total_rice_qtl        = round(total_rice, 2),
            total_bran_qtl        = round(total_bran, 2),
            total_husk_qtl        = round(total_husk, 2),
            total_broken_qtl      = round(total_broken, 2),
            total_loss_qtl        = round(total_loss, 2),
            avg_outturn_pct       = avg_outturn,
            avg_head_rice_pct     = avg_head_rice,
            total_revenue_potential = round(total_rev, 2),
            reconciliation        = recon,
            efficiency_alerts     = alerts,
            lots                  = [asdict(l) for l in lots],
        )


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_trackers: Dict[str, ConversionTracker] = {}

def ricemill_conversion(params: dict) -> dict:
    mill_id = params.get("mill_id", "RM001")
    if mill_id not in _trackers:
        _trackers[mill_id] = ConversionTracker(mill_id)
    tracker = _trackers[mill_id]

    action = params.get("action", "report")
    try:
        if action == "receive":
            lot = tracker.receive_paddy(
                lot_id       = params["lot_id"],
                paddy_qtl    = float(params["paddy_qtl"]),
                variety      = params.get("variety", "common"),
                milling_type = params.get("milling_type", "raw"),
                moisture_pct = float(params.get("moisture_pct", 13.5)),
                receipt_date = params.get("receipt_date"),
            )
            return asdict(lot)
        elif action == "mill":
            output = tracker.record_milling(
                lot_id           = params["lot_id"],
                head_rice_qtl    = float(params["head_rice_qtl"]) if "head_rice_qtl" in params else None,
                broken_5pct_qtl  = float(params.get("broken_5pct_qtl", 0)),
                broken_25pct_qtl = float(params.get("broken_25pct_qtl", 0)),
                broken_d_qtl     = float(params.get("broken_d_qtl", 0)),
                bran_qtl         = float(params["bran_qtl"]) if "bran_qtl" in params else None,
                husk_qtl         = float(params["husk_qtl"]) if "husk_qtl" in params else None,
                rice_market      = params.get("rice_market", "common_raw"),
            )
            return asdict(output)
        elif action == "report":
            return asdict(tracker.generate_report(params.get("period", "")))
        elif action == "prices":
            return {"market_prices_per_qtl": MARKET_PRICES, "variety_outturns": VARIETY_OUTTURN}
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
