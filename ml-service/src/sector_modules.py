"""
Sector-Specific Tax and GST Modules
Covers:
  1. Gold Shop — hallmarking, making charges GST, 3% jewellery GST
  2. Restaurant — food vs beverage GST split, AC/non-AC rules
  3. Real Estate — stamp duty, TDS u/s 194IA, GST on under-construction
  4. Freelancer — advance tax, foreign remittance TDS (15CA/15CB)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. GOLD SHOP MODULE
# ---------------------------------------------------------------------------

GOLD_GST_RATES = {
    "gold_jewellery":    0.03,   # HSN 7113
    "silver_jewellery":  0.03,   # HSN 7113
    "coins_bars":        0.03,   # HSN 7108
    "making_charges":    0.05,   # SAC 9983
    "hallmarking":       0.00,   # BIS hallmarking fee — exempt
    "diamond_jewellery": 0.0175, # HSN 7102 (rough) / 7113 (studded)
}

BIS_HALLMARKING_FEE = 35   # ₹35 per piece (latest revision)

@dataclass
class GoldSaleResult:
    gold_weight_grams:     float
    purity_karat:          int
    gold_rate_per_gram:    float
    gold_value:            float
    making_charges:        float
    hallmarking_fee:       float
    discount:              float
    subtotal:              float
    gold_gst_3pct:         float
    making_gst_5pct:       float
    total_gst:             float
    invoice_value:         float
    hsn_gold:              str = "711319"
    sac_making:            str = "998314"
    composition_applicable: bool = False
    tcs_on_jewellery:      float = 0.0   # 1% TCS if invoice > ₹2L u/s 206C(1F)
    notes:                 List[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def compute_gold_sale(params: dict) -> dict:
    """
    Compute gold jewellery invoice with GST breakdown.
    params: weight_grams, purity_karat, gold_rate_per_gram, making_per_gram,
            discount, buyer_pan (for >₹2L TCS)
    """
    weight     = float(params.get("weight_grams", 0))
    karat      = int(params.get("purity_karat", 22))
    rate       = float(params.get("gold_rate_per_gram", 6000))
    making_pg  = float(params.get("making_per_gram", 800))
    discount   = float(params.get("discount", 0))
    buyer_pan  = params.get("buyer_pan", "")

    gold_value     = weight * rate
    making_charges = weight * making_pg
    hallmark       = BIS_HALLMARKING_FEE
    subtotal       = gold_value + making_charges + hallmark - discount

    gold_gst     = gold_value * GOLD_GST_RATES["gold_jewellery"]
    making_gst   = making_charges * GOLD_GST_RATES["making_charges"]
    total_gst    = gold_gst + making_gst
    invoice_val  = subtotal + total_gst

    # TCS on purchase > ₹2L (206C(1F))
    tcs = 0.0
    notes = []
    if invoice_val > 2_00_000:
        tcs = invoice_val * 0.01
        notes.append(
            f"TCS of ₹{tcs:,.2f} (1%) applicable u/s 206C(1F) on jewellery purchase > ₹2 lakh. "
            f"Collect buyer's PAN." if not buyer_pan else
            f"TCS ₹{tcs:,.2f} deducted; buyer PAN on record."
        )

    if not buyer_pan and invoice_val > 2_00_000:
        notes.append("Buyer PAN mandatory for transactions above ₹2 lakh — Rule 114B.")

    result = GoldSaleResult(
        gold_weight_grams  = weight,
        purity_karat       = karat,
        gold_rate_per_gram = rate,
        gold_value         = round(gold_value, 2),
        making_charges     = round(making_charges, 2),
        hallmarking_fee    = float(hallmark),
        discount           = discount,
        subtotal           = round(subtotal, 2),
        gold_gst_3pct      = round(gold_gst, 2),
        making_gst_5pct    = round(making_gst, 2),
        total_gst          = round(total_gst, 2),
        invoice_value      = round(invoice_val, 2),
        tcs_on_jewellery   = round(tcs, 2),
        notes              = notes,
    )
    return asdict(result)


# ---------------------------------------------------------------------------
# 2. RESTAURANT GST MODULE
# ---------------------------------------------------------------------------

RESTAURANT_RATES = {
    "non_ac_no_alcohol":     0.05,   # No ITC
    "ac_no_alcohol":         0.05,   # No ITC (equalised post-2019)
    "ac_with_alcohol":       0.18,   # Full ITC
    "outdoor_catering":      0.05,
    "hotel_room_service_7500plus": 0.18,
    "hotel_room_service_below_7500": 0.05,
    "food_delivery_swiggy":  0.05,   # Via ECO (Swiggy/Zomato)
    "beverage_aerated":      0.18,
    "beverage_alcohol_beer": 0.00,   # State VAT applies; no GST
}


def compute_restaurant_bill(params: dict) -> dict:
    """
    Split restaurant bill: food vs beverage GST.
    params: items=[{name, category, amount}], restaurant_type, has_alcohol_license
    """
    items            = params.get("items", [])
    restaurant_type  = params.get("restaurant_type", "non_ac_no_alcohol")
    has_alcohol      = bool(params.get("has_alcohol_license", False))

    food_total = 0.0
    bev_total  = 0.0
    alc_total  = 0.0

    bill_lines = []
    for item in items:
        amt      = float(item.get("amount", 0))
        category = item.get("category", "food")
        if category == "alcohol":
            alc_total += amt
            bill_lines.append({"name": item.get("name",""), "amount": amt,
                               "gst_rate": 0.0, "gst": 0.0, "note": "State VAT/excise; no GST"})
        elif category == "beverage_aerated":
            bev_total += amt
            gst = amt * 0.18
            bill_lines.append({"name": item.get("name",""), "amount": amt,
                               "gst_rate": 0.18, "gst": round(gst, 2)})
        else:
            food_total += amt
            rate = RESTAURANT_RATES.get(restaurant_type, 0.05)
            gst  = amt * rate
            bill_lines.append({"name": item.get("name",""), "amount": amt,
                               "gst_rate": rate, "gst": round(gst, 2)})

    food_gst = sum(l["gst"] for l in bill_lines if l.get("gst_rate", 0) in (0.05, 0.18) and "alcohol" not in l.get("note",""))
    total_taxable = food_total + bev_total + alc_total
    total_gst     = food_gst
    invoice_val   = total_taxable + total_gst

    notes = []
    if has_alcohol and restaurant_type != "ac_with_alcohol":
        notes.append("AC restaurants with alcohol license are taxed at 18% on all items (food + beverages).")
    notes.append(f"Restaurant type: {restaurant_type}. ITC is NOT available for 5% rate restaurants.")
    if alc_total > 0:
        notes.append("Alcohol is subject to state VAT/excise, not GST. Consult state-specific rates.")

    return {
        "restaurant_type":   restaurant_type,
        "food_subtotal":     round(food_total, 2),
        "beverage_subtotal": round(bev_total, 2),
        "alcohol_subtotal":  round(alc_total, 2),
        "total_taxable":     round(total_taxable, 2),
        "total_gst":         round(total_gst, 2),
        "invoice_value":     round(invoice_val, 2),
        "bill_lines":        bill_lines,
        "notes":             notes,
    }


# ---------------------------------------------------------------------------
# 3. REAL ESTATE MODULE
# ---------------------------------------------------------------------------

STAMP_DUTY_RATES: Dict[str, Dict] = {
    "andhra_pradesh": {"male": 0.05, "female": 0.04, "registration": 0.01},
    "telangana":      {"male": 0.05, "female": 0.05, "registration": 0.005},
    "karnataka":      {"male": 0.056,"female": 0.051,"registration": 0.01},
    "maharashtra":    {"male": 0.06, "female": 0.05, "registration": 0.01},
    "delhi":          {"male": 0.06, "female": 0.04, "registration": 0.01},
    "tamil_nadu":     {"male": 0.07, "female": 0.07, "registration": 0.01},
}

GST_REAL_ESTATE = {
    "affordable_under_construction": 0.01,   # After deducting 1/3 land value
    "other_under_construction":      0.05,
    "ready_to_move_oc_received":     0.00,   # Exempt once OC received
    "commercial_under_construction": 0.12,
}


def compute_property_transaction(params: dict) -> dict:
    """
    Compute stamp duty, registration, TDS u/s 194IA, and GST on property.
    params: property_value, property_type, state, gender_buyer, is_under_construction
    """
    value       = float(params.get("property_value", 0))
    state       = params.get("state", "maharashtra").lower().replace(" ","_")
    gender      = params.get("gender_buyer", "male")
    prop_type   = params.get("property_type", "residential")   # residential / commercial
    under_const = bool(params.get("is_under_construction", False))
    affordable  = bool(params.get("is_affordable", False))     # < ₹45L affordable category

    rates       = STAMP_DUTY_RATES.get(state, STAMP_DUTY_RATES["maharashtra"])
    stamp_rate  = rates.get(gender, rates["male"])
    reg_rate    = rates.get("registration", 0.01)

    stamp_duty    = round(value * stamp_rate, 2)
    registration  = round(value * reg_rate, 2)
    total_govt_fee= stamp_duty + registration

    # TDS u/s 194IA (buyer must deduct if property > ₹50L)
    tds_194ia = 0.0
    tds_note  = ""
    if value > 50_00_000:
        tds_194ia = round(value * 0.01, 2)
        tds_note  = (f"TDS of ₹{tds_194ia:,.0f} (1%) must be deducted by buyer u/s 194IA. "
                     f"Deposit via Form 26QB within 30 days and issue Form 16B to seller.")

    # GST on under-construction property
    gst_amount = 0.0
    gst_note   = ""
    if under_const:
        if affordable:
            gst_rate = GST_REAL_ESTATE["affordable_under_construction"]
        elif prop_type == "commercial":
            gst_rate = GST_REAL_ESTATE["commercial_under_construction"]
        else:
            gst_rate = GST_REAL_ESTATE["other_under_construction"]
        # GST on 2/3 of value (1/3 deducted as land value)
        taxable_for_gst = value * (2/3)
        gst_amount      = round(taxable_for_gst * gst_rate, 2)
        gst_note        = (f"GST at {gst_rate*100:.0f}% on 2/3 of value (1/3 land deduction) = ₹{gst_amount:,.0f}. "
                           f"ITC not available to buyer.")
    else:
        gst_note = "No GST on ready-to-move property with Occupancy Certificate (OC)."

    total_cost = value + stamp_duty + registration + gst_amount

    return {
        "property_value":  value,
        "state":           state,
        "stamp_duty":      stamp_duty,
        "registration_fee":registration,
        "total_govt_fee":  total_govt_fee,
        "tds_194ia":       tds_194ia,
        "tds_note":        tds_note,
        "gst_amount":      gst_amount,
        "gst_note":        gst_note,
        "total_acquisition_cost": round(total_cost, 2),
        "notes": [
            f"Stamp duty rate: {stamp_rate*100:.1f}% ({gender} buyer, {state})",
            "Registration: present in sub-registrar's office within 4 months of execution.",
        ],
    }


# ---------------------------------------------------------------------------
# 4. FREELANCER MODULE
# ---------------------------------------------------------------------------

FOREIGN_REMITTANCE_TDS: Dict[str, float] = {
    "software_services":    0.00,   # Exempt if DTAA benefit claimed (Form 15CA/15CB)
    "royalty":              0.15,   # 15% or DTAA rate
    "fees_technical_svcs":  0.10,   # 10% or DTAA rate
    "dividend":             0.20,   # 20% or DTAA rate
    "interest":             0.20,
    "other":                0.30,
}

POPULAR_DTAA_COUNTRIES = {
    "usa": {"software": 0.00, "royalty": 0.10, "fts": 0.10},
    "uk":  {"software": 0.00, "royalty": 0.10, "fts": 0.10},
    "aus": {"software": 0.00, "royalty": 0.10, "fts": 0.10},
    "sgp": {"software": 0.00, "royalty": 0.10, "fts": 0.10},
    "uae": {"software": 0.00, "royalty": 0.10, "fts": 0.10},
    "can": {"software": 0.00, "royalty": 0.15, "fts": 0.10},
}


def compute_freelancer_tax(params: dict) -> dict:
    """
    Compute tax obligations for a freelancer/consultant.
    params: annual_income, expenses, foreign_remittances=[{country, type, amount}],
            regime, sec44ADA (presumptive)
    """
    annual_income = float(params.get("annual_income", 0))
    expenses      = float(params.get("expenses", 0))
    regime        = params.get("regime", "new")
    sec44ada      = bool(params.get("sec44ADA", False))

    # Presumptive: 50% of gross is deemed income
    if sec44ada:
        taxable_business = annual_income * 0.50
        notes = ["Sec 44ADA (Presumptive for professionals): 50% of gross receipts = deemed profit. No books required."]
    else:
        taxable_business = max(0, annual_income - expenses)
        notes = [f"Actual expenses: ₹{expenses:,.0f}. Net profit: ₹{taxable_business:,.0f}."]

    # Basic tax
    slabs = [
        (300_000, 0.00), (700_000, 0.05), (1_000_000, 0.10),
        (1_200_000, 0.15), (1_500_000, 0.20), (float("inf"), 0.30)
    ] if regime == "new" else [
        (250_000, 0.00), (500_000, 0.05), (1_000_000, 0.20), (float("inf"), 0.30)
    ]

    std_ded  = 0 if regime == "new" else 0  # No standard deduction for freelancers
    taxable  = max(0, taxable_business - std_ded)
    prev, tax = 0.0, 0.0
    for thr, rate in slabs:
        if taxable <= prev:
            break
        slab_inc = min(taxable, thr if thr != float("inf") else taxable) - prev
        tax += slab_inc * rate
        prev = thr if thr != float("inf") else taxable

    rebate = min(tax, 25_000) if taxable <= 700_000 and regime == "new" else 0
    tax    = max(0, tax - rebate)
    cess   = tax * 0.04
    total_tax = tax + cess

    # Advance tax quarters
    adv_tax = [
        {"quarter": "Q1", "due": "15 Jun 2024", "amount": round(total_tax * 0.15, 2)},
        {"quarter": "Q2", "due": "15 Sep 2024", "amount": round(total_tax * 0.45, 2)},
        {"quarter": "Q3", "due": "15 Dec 2024", "amount": round(total_tax * 0.75, 2)},
        {"quarter": "Q4", "due": "15 Mar 2025", "amount": round(total_tax, 2)},
    ]

    # Foreign remittances
    remittances = params.get("foreign_remittances", [])
    rem_details = []
    for r in remittances:
        country  = r.get("country", "usa").lower()
        rtype    = r.get("type", "software_services")
        amount   = float(r.get("amount", 0))
        dtaa     = POPULAR_DTAA_COUNTRIES.get(country, {})
        tds_rate = dtaa.get(rtype.split("_")[0], FOREIGN_REMITTANCE_TDS.get(rtype, 0.20))
        tds_amt  = amount * tds_rate
        rem_details.append({
            "country":    country.upper(),
            "type":       rtype,
            "amount":     amount,
            "tds_rate":   tds_rate,
            "tds_amount": round(tds_amt, 2),
            "form_15ca":  True,
            "form_15cb":  tds_amt > 5_00_000,
            "note": (f"Form 15CA mandatory. Form 15CB {'required' if tds_amt > 5_00_000 else 'may not be required'} "
                     f"(CA certificate needed if remittance >₹5L).")
        })

    if remittances:
        notes.append("Foreign remittance: File Form 15CA with bank before remittance. FEMA compliance required.")

    # GST on freelance services
    gst_note = ""
    if annual_income > 20_00_000:
        gst_note = "GST registration mandatory (turnover > ₹20L threshold). Charge 18% GST on invoices."
    elif annual_income > 0:
        gst_note = "If exporting services, GST registration optional (but advantageous for IGST refund on zero-rated exports)."

    return {
        "annual_income":      annual_income,
        "taxable_income":     taxable,
        "income_tax":         round(tax, 2),
        "cess":               round(cess, 2),
        "total_tax":          round(total_tax, 2),
        "effective_rate":     round(total_tax / annual_income * 100, 2) if annual_income else 0,
        "advance_tax":        adv_tax,
        "foreign_remittances":rem_details,
        "gst_note":           gst_note,
        "notes":              notes,
        "itr_form":           "ITR-4 (Sec 44ADA)" if sec44ada else "ITR-3",
    }
