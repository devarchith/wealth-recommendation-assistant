"""
GST Calculator — India
Computes GST for goods and services with HSN/SAC code lookup.
Covers:
  • HSN code to GST rate mapping (Chapter-level gazetteer)
  • SAC code to GST rate mapping (services)
  • IGST / CGST+SGST split based on supply type (inter/intra-state)
  • Composition scheme rates
  • Reverse charge applicability
  • Invoice value breakdown (taxable + tax + cess)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# HSN code rate table (Chapter-level, abbreviated)
# ---------------------------------------------------------------------------

HSN_RATES: Dict[str, Dict] = {
    # Chapter 1-5: Live animals, meat, fish, dairy
    "01": {"rate": 0.00, "description": "Live animals"},
    "02": {"rate": 0.00, "description": "Meat and edible offal"},
    "03": {"rate": 0.05, "description": "Fish and crustaceans"},
    "04": {"rate": 0.00, "description": "Dairy produce, eggs, honey"},
    "05": {"rate": 0.05, "description": "Other animal products"},
    # Chapter 6-14: Vegetables, fruits, cereals
    "06": {"rate": 0.05, "description": "Live trees and plants"},
    "07": {"rate": 0.00, "description": "Edible vegetables"},
    "08": {"rate": 0.00, "description": "Edible fruits and nuts"},
    "09": {"rate": 0.05, "description": "Coffee, tea, spices"},
    "10": {"rate": 0.00, "description": "Cereals"},
    "11": {"rate": 0.00, "description": "Products of milling industry"},
    "12": {"rate": 0.05, "description": "Oil seeds and oleaginous fruits"},
    "17": {"rate": 0.05, "description": "Sugars and confectionery"},
    "18": {"rate": 0.18, "description": "Cocoa and preparations"},
    "19": {"rate": 0.18, "description": "Preparations of cereals, flour"},
    "20": {"rate": 0.12, "description": "Preparations of vegetables/fruits"},
    "21": {"rate": 0.18, "description": "Miscellaneous edible preparations"},
    "22": {"rate": 0.18, "description": "Beverages, spirits"},
    "24": {"rate": 0.28, "description": "Tobacco and manufactured substitutes"},
    # Chapter 25-27: Mineral products
    "25": {"rate": 0.05, "description": "Salt, sulphur, limestone"},
    "27": {"rate": 0.05, "description": "Mineral fuels, oils"},
    # Chapter 28-38: Chemical industry
    "28": {"rate": 0.18, "description": "Inorganic chemicals"},
    "29": {"rate": 0.18, "description": "Organic chemicals"},
    "30": {"rate": 0.12, "description": "Pharmaceutical products"},
    "31": {"rate": 0.05, "description": "Fertilisers"},
    "33": {"rate": 0.18, "description": "Essential oils, cosmetics"},
    "34": {"rate": 0.18, "description": "Soap, lubricants"},
    "38": {"rate": 0.18, "description": "Miscellaneous chemical products"},
    # Chapter 39-40: Plastics, rubber
    "39": {"rate": 0.18, "description": "Plastics and articles"},
    "40": {"rate": 0.12, "description": "Rubber and articles"},
    # Chapter 41-43: Leather
    "41": {"rate": 0.05, "description": "Raw hides and skins"},
    "42": {"rate": 0.18, "description": "Leather articles, handbags"},
    # Chapter 44-49: Wood, paper
    "44": {"rate": 0.12, "description": "Wood and articles"},
    "47": {"rate": 0.12, "description": "Pulp of wood"},
    "48": {"rate": 0.12, "description": "Paper and paperboard"},
    "49": {"rate": 0.12, "description": "Printed books, newspapers"},
    # Chapter 50-63: Textiles
    "50": {"rate": 0.05, "description": "Silk"},
    "51": {"rate": 0.05, "description": "Wool"},
    "52": {"rate": 0.05, "description": "Cotton"},
    "61": {"rate": 0.05, "description": "Knitted or crocheted clothing"},
    "62": {"rate": 0.05, "description": "Woven clothing"},
    "63": {"rate": 0.05, "description": "Other made textile articles"},
    # Chapter 64-67: Footwear, headgear
    "64": {"rate": 0.12, "description": "Footwear, gaiters"},
    # Chapter 71: Precious metals, jewellery
    "71": {"rate": 0.03, "description": "Precious metals, jewellery, coins"},
    # Chapter 72-83: Metals
    "72": {"rate": 0.18, "description": "Iron and steel"},
    "73": {"rate": 0.18, "description": "Articles of iron or steel"},
    "74": {"rate": 0.18, "description": "Copper and articles"},
    "76": {"rate": 0.18, "description": "Aluminium and articles"},
    "84": {"rate": 0.18, "description": "Nuclear reactors, boilers, machinery"},
    "85": {"rate": 0.18, "description": "Electrical machinery, equipment"},
    "86": {"rate": 0.12, "description": "Railway locomotives"},
    "87": {"rate": 0.28, "description": "Vehicles other than railway"},
    "88": {"rate": 0.18, "description": "Aircraft, spacecraft"},
    "89": {"rate": 0.05, "description": "Ships, boats"},
    "90": {"rate": 0.18, "description": "Optical, photographic instruments"},
    "94": {"rate": 0.18, "description": "Furniture, bedding, lamps"},
    "95": {"rate": 0.12, "description": "Toys, games, sports equipment"},
    "96": {"rate": 0.18, "description": "Miscellaneous manufactured articles"},
}

# 6-digit HSN overrides (specific items with different rates)
HSN_6DIGIT_RATES: Dict[str, Dict] = {
    "300490": {"rate": 0.12, "description": "Medicines (branded)"},
    "300410": {"rate": 0.05, "description": "Penicillin medicines"},
    "870321": {"rate": 0.28, "description": "Petrol cars <1000cc"},
    "870322": {"rate": 0.28, "description": "Petrol cars 1000-1500cc"},
    "870323": {"rate": 0.28, "description": "Petrol cars >1500cc"},
    "870331": {"rate": 0.28, "description": "Diesel cars <1500cc"},
    "870332": {"rate": 0.28, "description": "Diesel cars >1500cc"},
    "711319": {"rate": 0.03, "description": "Gold jewellery (other than 711311)"},
    "711311": {"rate": 0.03, "description": "Silver jewellery"},
    "110100": {"rate": 0.00, "description": "Wheat flour"},
    "100610": {"rate": 0.00, "description": "Paddy/Rice (non-branded)"},
    "220110": {"rate": 0.00, "description": "Mineral water (plain)"},
    "220210": {"rate": 0.12, "description": "Aerated water"},
    "240110": {"rate": 0.05, "description": "Unmanufactured tobacco"},
    "240220": {"rate": 0.28, "description": "Cigarettes"},
}

# ---------------------------------------------------------------------------
# SAC codes (Services)
# ---------------------------------------------------------------------------

SAC_RATES: Dict[str, Dict] = {
    # Construction
    "9954": {"rate": 0.12, "description": "Construction of residential complex"},
    "995411": {"rate": 0.05, "description": "Affordable housing construction"},
    "995421": {"rate": 0.18, "description": "Commercial construction"},
    # Professional services
    "9982": {"rate": 0.18, "description": "Legal, accounting, consulting"},
    "998211": {"rate": 0.18, "description": "Legal services"},
    "998221": {"rate": 0.18, "description": "Accounting, auditing, bookkeeping"},
    "998231": {"rate": 0.18, "description": "Tax consulting"},
    # IT services
    "9983": {"rate": 0.18, "description": "IT software and services"},
    "998313": {"rate": 0.18, "description": "Software development"},
    "998314": {"rate": 0.18, "description": "IT consulting"},
    # Hospitality
    "9963": {"rate": 0.18, "description": "Hotel accommodation (>₹7500/day)"},
    "996311": {"rate": 0.12, "description": "Hotel accommodation (₹1000-7500/day)"},
    "996312": {"rate": 0.00, "description": "Hotel accommodation (<₹1000/day)"},
    "996331": {"rate": 0.05, "description": "Restaurant services (non-AC)"},
    "996332": {"rate": 0.05, "description": "Restaurant services (AC without alcohol)"},
    "996333": {"rate": 0.18, "description": "Restaurant with bar/alcohol"},
    # Transport
    "9965": {"rate": 0.05, "description": "Goods transport by road (GTA)"},
    "9966": {"rate": 0.05, "description": "Passenger transport by road"},
    "996411": {"rate": 0.05, "description": "Air transport (economy)"},
    "996412": {"rate": 0.12, "description": "Air transport (business/first class)"},
    # Financial services
    "9971": {"rate": 0.18, "description": "Financial and related services"},
    "997111": {"rate": 0.18, "description": "Banking and deposit services"},
    "997120": {"rate": 0.18, "description": "Insurance services"},
    # Education
    "9992": {"rate": 0.00, "description": "Educational services (recognised)"},
    "999210": {"rate": 0.00, "description": "Pre-primary / primary education"},
    "999291": {"rate": 0.18, "description": "Commercial training and coaching"},
    # Healthcare
    "9993": {"rate": 0.00, "description": "Health and social care services"},
    "999311": {"rate": 0.00, "description": "Hospital services"},
    "999312": {"rate": 0.00, "description": "Medical / dental services"},
    # Telecom
    "9984": {"rate": 0.18, "description": "Telecommunication services"},
    "998411": {"rate": 0.18, "description": "Internet access services"},
    # Entertainment / Gambling
    "9996": {"rate": 0.28, "description": "Sports, amusement, gambling"},
    "999641": {"rate": 0.28, "description": "Online gaming (with actionable claim)"},
    # Renting
    "9972": {"rate": 0.18, "description": "Renting of immovable property"},
    "997212": {"rate": 0.18, "description": "Renting of commercial property"},
    "997213": {"rate": 0.00, "description": "Renting of residential dwelling (individual)"},
}

# Composition scheme rates
COMPOSITION_RATES: Dict[str, float] = {
    "manufacturer":   0.01,   # 1% turnover
    "trader":         0.01,   # 1% turnover
    "restaurant":     0.05,   # 5% turnover
    "service":        0.06,   # 6% turnover (Notification 2/2019-CT)
}

# Reverse charge categories
REVERSE_CHARGE_SERVICES = {
    "9965",   # GTA transport
    "9982",   # Legal services (advocate)
    "9997",   # Import of services
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HSNLookupResult:
    hsn_code:      str
    description:   str
    gst_rate:      float
    cess_rate:     float
    is_exempt:     bool
    is_zero_rated: bool
    reverse_charge: bool
    note:          Optional[str] = None


@dataclass
class GSTBreakdown:
    item_description:  str
    hsn_sac_code:      str
    quantity:          float
    unit_price:        float
    taxable_value:     float
    discount:          float
    gst_rate:          float
    igst:              float
    cgst:              float
    sgst:              float
    cess:              float
    total_gst:         float
    invoice_value:     float
    supply_type:       str   # "inter_state" | "intra_state"
    reverse_charge:    bool


@dataclass
class InvoiceGSTSummary:
    invoice_no:        str
    seller_gstin:      str
    buyer_gstin:       Optional[str]
    place_of_supply:   str
    seller_state_code: str
    items:             List[GSTBreakdown]
    total_taxable:     float
    total_igst:        float
    total_cgst:        float
    total_sgst:        float
    total_cess:        float
    total_gst:         float
    invoice_value:     float
    is_b2b:            bool
    composition_rate:  Optional[float]


# ---------------------------------------------------------------------------
# GST Calculator
# ---------------------------------------------------------------------------

class GSTCalculator:
    """
    Compute GST for goods/services with HSN/SAC code lookup.

    Usage:
        calc = GSTCalculator(seller_gstin="27AABCU9603R1ZX", seller_state_code="27")
        calc.add_item("Laptop", "8471", qty=2, unit_price=50000)
        result = calc.compute_invoice("INV-001", buyer_gstin="29AABCU9603R1ZX", place_of_supply="29")
    """

    def __init__(
        self,
        seller_gstin:       str,
        seller_state_code:  str,
        composition_type:   Optional[str] = None,
    ):
        self.seller_gstin      = seller_gstin
        self.seller_state_code = seller_state_code
        self.composition_type  = composition_type
        self._items: List[Dict] = []

    def add_item(
        self,
        description:  str,
        hsn_sac_code: str,
        qty:          float,
        unit_price:   float,
        discount:     float = 0.0,
        cess_rate:    float = 0.0,
        override_rate: Optional[float] = None,
    ) -> None:
        self._items.append({
            "description":  description,
            "hsn_sac_code": hsn_sac_code,
            "qty":          qty,
            "unit_price":   unit_price,
            "discount":     discount,
            "cess_rate":    cess_rate,
            "override_rate": override_rate,
        })

    def lookup_hsn_sac(self, code: str) -> HSNLookupResult:
        """Look up GST rate by HSN or SAC code."""
        code = code.strip().upper()

        # Check SAC first
        if code in SAC_RATES:
            info = SAC_RATES[code]
            return HSNLookupResult(
                hsn_code      = code,
                description   = info["description"],
                gst_rate      = info["rate"],
                cess_rate     = 0.0,
                is_exempt     = info["rate"] == 0.0,
                is_zero_rated = False,
                reverse_charge= code in REVERSE_CHARGE_SERVICES,
            )

        # 6-digit HSN
        if code in HSN_6DIGIT_RATES:
            info = HSN_6DIGIT_RATES[code]
            return HSNLookupResult(
                hsn_code      = code,
                description   = info["description"],
                gst_rate      = info["rate"],
                cess_rate     = 0.28 if info["rate"] == 0.28 else 0.0,
                is_exempt     = info["rate"] == 0.0,
                is_zero_rated = False,
                reverse_charge= False,
            )

        # Chapter-level (first 2 digits)
        chapter = code[:2] if len(code) >= 2 else code
        if chapter in HSN_RATES:
            info = HSN_RATES[chapter]
            return HSNLookupResult(
                hsn_code      = code,
                description   = info["description"],
                gst_rate      = info["rate"],
                cess_rate     = 0.0,
                is_exempt     = info["rate"] == 0.0,
                is_zero_rated = False,
                reverse_charge= False,
                note          = "Chapter-level rate — verify 6-digit HSN for specific rate",
            )

        return HSNLookupResult(
            hsn_code      = code,
            description   = "Unknown HSN/SAC",
            gst_rate      = 0.18,
            cess_rate     = 0.0,
            is_exempt     = False,
            is_zero_rated = False,
            reverse_charge= False,
            note          = "HSN not found — defaulting to 18%. Verify on GST portal.",
        )

    def compute_invoice(
        self,
        invoice_no:        str,
        buyer_gstin:       Optional[str],
        place_of_supply:   str,
    ) -> InvoiceGSTSummary:
        # Determine supply type
        is_inter_state = (place_of_supply != self.seller_state_code)

        items: List[GSTBreakdown] = []

        for item in self._items:
            code      = item["hsn_sac_code"]
            lookup    = self.lookup_hsn_sac(code)
            rate      = item["override_rate"] if item["override_rate"] is not None else lookup.gst_rate
            cess_rate = item["cess_rate"]

            taxable = item["qty"] * item["unit_price"] - item["discount"]
            gst_amt = taxable * rate
            cess    = taxable * cess_rate

            if self.composition_type:
                comp_rate = COMPOSITION_RATES.get(self.composition_type, 0.01)
                igst = 0.0
                cgst = taxable * comp_rate / 2
                sgst = taxable * comp_rate / 2
                rate = comp_rate
            elif is_inter_state:
                igst = gst_amt
                cgst = 0.0
                sgst = 0.0
            else:
                igst = 0.0
                cgst = gst_amt / 2
                sgst = gst_amt / 2

            items.append(GSTBreakdown(
                item_description = item["description"],
                hsn_sac_code     = code,
                quantity         = item["qty"],
                unit_price       = item["unit_price"],
                taxable_value    = taxable,
                discount         = item["discount"],
                gst_rate         = rate,
                igst             = round(igst, 2),
                cgst             = round(cgst, 2),
                sgst             = round(sgst, 2),
                cess             = round(cess, 2),
                total_gst        = round(igst + cgst + sgst + cess, 2),
                invoice_value    = round(taxable + igst + cgst + sgst + cess, 2),
                supply_type      = "inter_state" if is_inter_state else "intra_state",
                reverse_charge   = lookup.reverse_charge,
            ))

        total_taxable = sum(i.taxable_value for i in items)
        total_igst    = sum(i.igst for i in items)
        total_cgst    = sum(i.cgst for i in items)
        total_sgst    = sum(i.sgst for i in items)
        total_cess    = sum(i.cess for i in items)
        total_gst     = sum(i.total_gst for i in items)
        inv_value     = total_taxable + total_gst

        return InvoiceGSTSummary(
            invoice_no        = invoice_no,
            seller_gstin      = self.seller_gstin,
            buyer_gstin       = buyer_gstin,
            place_of_supply   = place_of_supply,
            seller_state_code = self.seller_state_code,
            items             = items,
            total_taxable     = round(total_taxable, 2),
            total_igst        = round(total_igst, 2),
            total_cgst        = round(total_cgst, 2),
            total_sgst        = round(total_sgst, 2),
            total_cess        = round(total_cess, 2),
            total_gst         = round(total_gst, 2),
            invoice_value     = round(inv_value, 2),
            is_b2b            = bool(buyer_gstin),
            composition_rate  = COMPOSITION_RATES.get(self.composition_type, None) if self.composition_type else None,
        )


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def lookup_gst_rate(hsn_sac_code: str) -> dict:
    """Standalone HSN/SAC lookup."""
    calc = GSTCalculator("", "27")
    result = calc.lookup_hsn_sac(hsn_sac_code)
    return asdict(result)


def compute_gst_invoice(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    calc = GSTCalculator(
        seller_gstin      = params.get("seller_gstin", ""),
        seller_state_code = params.get("seller_state_code", "27"),
        composition_type  = params.get("composition_type"),
    )

    for item in params.get("items", []):
        calc.add_item(
            description   = item.get("description", ""),
            hsn_sac_code  = item.get("hsn_sac_code", ""),
            qty           = float(item.get("qty", 1)),
            unit_price    = float(item.get("unit_price", 0)),
            discount      = float(item.get("discount", 0)),
            cess_rate     = float(item.get("cess_rate", 0)),
            override_rate = item.get("override_rate"),
        )

    result = calc.compute_invoice(
        invoice_no      = params.get("invoice_no", "INV-001"),
        buyer_gstin     = params.get("buyer_gstin"),
        place_of_supply = params.get("place_of_supply", "27"),
    )

    return {
        "invoice_no":      result.invoice_no,
        "seller_gstin":    result.seller_gstin,
        "buyer_gstin":     result.buyer_gstin,
        "place_of_supply": result.place_of_supply,
        "supply_type":     "inter_state" if result.total_igst > 0 else "intra_state",
        "total_taxable":   result.total_taxable,
        "total_igst":      result.total_igst,
        "total_cgst":      result.total_cgst,
        "total_sgst":      result.total_sgst,
        "total_cess":      result.total_cess,
        "total_gst":       result.total_gst,
        "invoice_value":   result.invoice_value,
        "is_b2b":          result.is_b2b,
        "composition_rate": result.composition_rate,
        "items":           [asdict(i) for i in result.items],
    }
