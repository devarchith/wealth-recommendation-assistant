"""
FCI Custom Milling Billing Calculator — AP / Telangana District Rates
======================================================================
Computes FCI custom milling bills for rice mills, incorporating:

  - Milling charges: per-quintal rates by district (AP/TS, 2024-25)
  - Paddy outturn (67% rice recovery standard; 68% for double-polished)
  - Transportation charges (inward paddy + outward rice delivery)
  - Storage / gunny bag charges
  - Moisture content deductions (>14% triggers dockage)
  - CMR (Custom Milled Rice) grade specifications
  - GST: milling service for government = Nil rated (FCI is government)
  - 2% TDS deduction by FCI on milling charges
  - Gunny bag security deposit adjustment

AP District FCI Depots and Milling Rates (per quintal of paddy milled):
  Districts with higher rates: flood-affected / remote procurement zones
  Source: FCI Zonal Office, Hyderabad — Rates applicable Oct 2024

Output:
  - Gross milling bill
  - Deductions (TDS, moisture, bag damage)
  - Net payable by FCI
  - CMR tonnage to be delivered to FCI depot

Integration:
  - ricemill_penalty_engine.py → FCI income reporting checks
  - ricemill_working_capital.py → FCI receivable tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import date
from enum import Enum


# ---------------------------------------------------------------------------
# FCI milling rates by AP / TS district (₹ per quintal paddy, 2024-25)
# ---------------------------------------------------------------------------

FCI_MILLING_RATES: Dict[str, float] = {
    # Andhra Pradesh
    "ap_guntur":           28.00,
    "ap_krishna":          28.00,
    "ap_east_godavari":    28.50,
    "ap_west_godavari":    28.50,
    "ap_nellore":          27.50,
    "ap_prakasam":         27.50,
    "ap_kurnool":          27.00,
    "ap_kadapa":           27.00,
    "ap_srikakulam":       29.00,
    "ap_vizianagaram":     29.00,
    "ap_visakhapatnam":    28.50,
    "ap_eluru":            28.00,
    "ap_bapatla":          28.00,
    "ap_palnadu":          27.50,
    # Telangana
    "ts_nizamabad":        28.00,
    "ts_karimnagar":       28.00,
    "ts_warangal":         28.50,
    "ts_khammam":          27.50,
    "ts_nalgonda":         27.50,
    "ts_rangareddy":       27.00,
    "ts_medak":            27.00,
    "ts_adilabad":         29.00,
    # Default
    "default":             27.50,
}

# Transportation rates (₹/quintal, FCI levy — included in CMR rate for some zones)
FCI_TRANSPORT_INWARD: Dict[str, float] = {
    "ap_srikakulam": 12.0,
    "ap_vizianagaram": 12.0,
    "ts_adilabad": 15.0,
    "default": 8.0,
}
FCI_TRANSPORT_OUTWARD: Dict[str, float] = {
    "ap_srikakulam": 15.0,
    "ap_vizianagaram": 15.0,
    "ts_adilabad": 18.0,
    "default": 10.0,
}

# CMR specifications
CMR_OUTTURN_RATIO      = 0.67    # 67 kg rice per 100 kg paddy (standard)
CMR_OUTTURN_PREMIUM    = 0.68    # 68% for grade A paddy
MOISTURE_TOLERANCE     = 14.0    # % maximum allowed
MOISTURE_DOCKAGE_PER_PCT = 0.5   # ₹ per quintal per excess % point
GUNNY_BAG_COST         = 28.0    # ₹ per bag (50 kg capacity)
GUNNY_BAGS_PER_100_QTL = 200     # 200 bags for 100 qtl rice

TDS_RATE_FCI           = 0.02    # 2% TDS deducted by FCI
GST_ON_MILLING_FCI     = 0.00    # Nil — milling for government entity


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CMRGrade(str, Enum):
    GRADE_A      = "grade_a"     # Long grain, head rice > 50%
    GRADE_B      = "grade_b"     # Medium grain, acceptable broken
    PARBOILED    = "parboiled"   # Boiled/parboiled rice
    RAW          = "raw"         # Raw milled rice


class MoistureAction(str, Enum):
    ACCEPTED     = "accepted"
    DOCKAGE      = "dockage"
    REJECTED     = "rejected"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FCIMillingBill:
    bill_no:            str
    mill_id:            str
    mill_name:          str
    district:           str
    lot_no:             str
    bill_date:          str

    # Paddy received
    paddy_qtl:          float        # quintals
    paddy_variety:      str
    moisture_pct:       float
    moisture_action:    MoistureAction
    moisture_dockage:   float        # ₹

    # CMR to be delivered
    cmr_grade:          CMRGrade
    outturn_ratio:      float
    cmr_qtl:            float        # quintals rice to deliver
    cmr_bags:           int

    # Milling charges
    milling_rate_qtl:   float
    gross_milling_charge: float
    inward_transport:   float
    outward_transport:  float
    storage_charge:     float
    gunny_bag_charge:   float

    # Deductions
    tds_2pct:           float
    bag_damage_deduction: float
    other_deductions:   float

    # Totals
    gross_bill:         float
    total_deductions:   float
    net_payable:        float

    # GST
    gst_amount:         float        # Nil for FCI milling
    gst_note:           str

    notes:              List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class FCIMillingCalculator:
    """
    Computes FCI custom milling bill for a given paddy lot.
    """

    def compute_bill(
        self,
        mill_id:       str,
        mill_name:     str,
        district:      str,
        lot_no:        str,
        paddy_qtl:     float,
        paddy_variety: str   = "Common",
        moisture_pct:  float = 13.5,
        cmr_grade:     CMRGrade = CMRGrade.RAW,
        is_grade_a_paddy: bool = False,
        include_inward_transport: bool = True,
        include_outward_transport:bool = True,
        storage_days:  int   = 0,       # days paddy stored at mill
        bag_damage_bags: int = 0,       # number of damaged bags
        other_deductions: float = 0.0,
        bill_no:       str   = "",
    ) -> FCIMillingBill:

        today    = date.today().isoformat()
        district = district.lower().strip()
        rate     = FCI_MILLING_RATES.get(district, FCI_MILLING_RATES["default"])

        # Outturn
        outturn  = CMR_OUTTURN_PREMIUM if is_grade_a_paddy else CMR_OUTTURN_RATIO
        cmr_qtl  = round(paddy_qtl * outturn, 2)
        cmr_bags = int(cmr_qtl * 2)   # 50 kg bag = 0.5 qtl; bags = cmr_qtl / 0.5

        # Moisture
        if moisture_pct <= MOISTURE_TOLERANCE:
            moisture_action  = MoistureAction.ACCEPTED
            moisture_dockage = 0.0
        elif moisture_pct <= 17.0:
            excess           = moisture_pct - MOISTURE_TOLERANCE
            moisture_dockage = round(paddy_qtl * MOISTURE_DOCKAGE_PER_PCT * excess, 2)
            moisture_action  = MoistureAction.DOCKAGE
        else:
            moisture_dockage = 0.0
            moisture_action  = MoistureAction.REJECTED

        # Milling charges
        gross_milling = round(paddy_qtl * rate, 2)
        inward_trans  = round(paddy_qtl * FCI_TRANSPORT_INWARD.get(district, FCI_TRANSPORT_INWARD["default"]), 2) if include_inward_transport else 0.0
        outward_trans = round(cmr_qtl * FCI_TRANSPORT_OUTWARD.get(district, FCI_TRANSPORT_OUTWARD["default"]), 2) if include_outward_transport else 0.0
        storage_charge= round(paddy_qtl * 0.50 * storage_days, 2)  # ₹0.50/qtl/day
        bag_charge    = round(cmr_bags * GUNNY_BAG_COST, 2)

        gross_bill    = gross_milling + inward_trans + outward_trans + storage_charge + bag_charge

        # Deductions
        tds           = round(gross_milling * TDS_RATE_FCI, 2)
        bag_damage    = round(bag_damage_bags * GUNNY_BAG_COST, 2)
        total_ded     = tds + moisture_dockage + bag_damage + other_deductions
        net_payable   = round(gross_bill - total_ded, 2)

        notes = []
        if moisture_action == MoistureAction.DOCKAGE:
            notes.append(f"Moisture {moisture_pct}% exceeds 14% — dockage ₹{moisture_dockage:,.0f} applied")
        if moisture_action == MoistureAction.REJECTED:
            notes.append(f"REJECTED: Moisture {moisture_pct}% exceeds 17% — lot cannot be milled")
        if storage_days > 7:
            notes.append(f"Storage charge for {storage_days} days: ₹{storage_charge:,.0f}")
        notes.append(f"CMR to deliver to FCI depot: {cmr_qtl} qtl ({cmr_bags} bags × 50 kg)")
        notes.append("GST: Nil — milling service to government entity (FCI) under Notification 12/2017-CT(Rate)")
        notes.append(f"TDS u/s 194C @ 2% deducted by FCI: ₹{tds:,.0f} (Form 16A will be issued)")

        auto_bill_no = bill_no or f"FCI/{mill_id}/{today[:7].replace('-', '')}/{lot_no}"

        return FCIMillingBill(
            bill_no               = auto_bill_no,
            mill_id               = mill_id,
            mill_name             = mill_name,
            district              = district,
            lot_no                = lot_no,
            bill_date             = today,
            paddy_qtl             = paddy_qtl,
            paddy_variety         = paddy_variety,
            moisture_pct          = moisture_pct,
            moisture_action       = moisture_action,
            moisture_dockage      = moisture_dockage,
            cmr_grade             = cmr_grade,
            outturn_ratio         = outturn,
            cmr_qtl               = cmr_qtl,
            cmr_bags              = cmr_bags,
            milling_rate_qtl      = rate,
            gross_milling_charge  = gross_milling,
            inward_transport      = inward_trans,
            outward_transport     = outward_trans,
            storage_charge        = storage_charge,
            gunny_bag_charge      = bag_charge,
            tds_2pct              = tds,
            bag_damage_deduction  = bag_damage,
            other_deductions      = other_deductions,
            gross_bill            = gross_bill,
            total_deductions      = round(total_ded, 2),
            net_payable           = net_payable,
            gst_amount            = 0.0,
            gst_note              = "Nil — FCI milling service to government",
            notes                 = notes,
        )

    def compute_seasonal_total(
        self,
        mill_id:   str,
        mill_name: str,
        district:  str,
        lots:      List[Dict],
    ) -> Dict:
        """Compute total FCI billing for multiple lots in a season."""
        bills  = []
        for lot in lots:
            b = self.compute_bill(mill_id=mill_id, mill_name=mill_name, district=district, **lot)
            bills.append(b)

        return {
            "mill_id":           mill_id,
            "season_summary": {
                "total_lots":         len(bills),
                "total_paddy_qtl":    round(sum(b.paddy_qtl for b in bills), 2),
                "total_cmr_qtl":      round(sum(b.cmr_qtl for b in bills), 2),
                "gross_milling_total":round(sum(b.gross_milling_charge for b in bills), 2),
                "total_tds":          round(sum(b.tds_2pct for b in bills), 2),
                "total_net_payable":  round(sum(b.net_payable for b in bills), 2),
                "rejected_lots":      sum(1 for b in bills if b.moisture_action == MoistureAction.REJECTED),
            },
            "bills": [asdict(b) for b in bills],
        }


# ---------------------------------------------------------------------------
# Singleton + API wrapper
# ---------------------------------------------------------------------------

_calc = FCIMillingCalculator()

def ricemill_fci_billing(params: dict) -> dict:
    action = params.get("action", "compute_bill")
    try:
        if action == "compute_bill":
            bill = _calc.compute_bill(
                mill_id      = params.get("mill_id", "RM001"),
                mill_name    = params.get("mill_name", "Rice Mill"),
                district     = params.get("district", "default"),
                lot_no       = params.get("lot_no", "LOT001"),
                paddy_qtl    = float(params.get("paddy_qtl", 0)),
                paddy_variety= params.get("paddy_variety", "Common"),
                moisture_pct = float(params.get("moisture_pct", 13.5)),
                cmr_grade    = CMRGrade(params.get("cmr_grade", "raw")),
                is_grade_a_paddy = bool(params.get("is_grade_a_paddy", False)),
                include_inward_transport  = bool(params.get("include_inward_transport", True)),
                include_outward_transport = bool(params.get("include_outward_transport", True)),
                storage_days  = int(params.get("storage_days", 0)),
                bag_damage_bags = int(params.get("bag_damage_bags", 0)),
                other_deductions = float(params.get("other_deductions", 0)),
            )
            return asdict(bill)
        elif action == "rates":
            return {"fci_milling_rates_per_qtl": FCI_MILLING_RATES,
                    "note": "Rates per quintal of paddy milled, 2024-25, AP/TS"}
        elif action == "seasonal_total":
            return _calc.compute_seasonal_total(
                mill_id   = params.get("mill_id", "RM001"),
                mill_name = params.get("mill_name", "Rice Mill"),
                district  = params.get("district", "default"),
                lots      = params.get("lots", []),
            )
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": str(e)}
