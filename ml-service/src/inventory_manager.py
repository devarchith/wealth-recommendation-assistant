"""
Inventory Management Module
Retail and Gold Shop use cases — India context
Covers:
  • Product / SKU catalog with HSN codes and GST rates
  • Stock-in (purchase), stock-out (sale), stock transfer
  • Reorder level alerts
  • Gold-specific: weight-based inventory (grams), making charges, hallmarking
  • Valuation methods: FIFO / Weighted Average
  • GST implications: purchase ITC, sale GST, composition scheme
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Deque
from collections import deque


class ValuationMethod(str, Enum):
    FIFO    = "fifo"
    WAVG    = "weighted_average"


class TransactionType(str, Enum):
    PURCHASE   = "purchase"
    SALE       = "sale"
    RETURN_IN  = "return_in"
    RETURN_OUT = "return_out"
    ADJUSTMENT = "adjustment"
    TRANSFER   = "transfer"


class Category(str, Enum):
    GENERAL   = "general"
    GOLD      = "gold"
    SILVER    = "silver"
    DIAMOND   = "diamond"
    APPAREL   = "apparel"
    ELECTRONICS = "electronics"
    PHARMA    = "pharma"
    FOOD      = "food"


GOLD_GST_RATE       = 0.03   # 3% on gold
MAKING_CHARGES_GST  = 0.05   # 5% on making charges
SILVER_GST_RATE     = 0.03
DIAMOND_GST_RATE    = 0.0175 # 1.75% (exempt category for rough diamonds: 0%)


@dataclass
class Product:
    sku:              str
    name:             str
    category:         Category
    hsn_code:         str
    gst_rate:         float        # e.g. 0.03 for gold
    unit:             str          # "pcs", "gm", "kg", "ml"
    reorder_level:    float        # Alert when stock drops below this
    reorder_qty:      float        # Suggested order quantity
    description:      Optional[str] = None
    # Gold-specific
    purity_karat:     Optional[int] = None   # 18K, 22K, 24K
    making_charge_per_gram: float = 0.0
    hallmarking_required: bool = False


@dataclass
class StockBatch:
    """A received batch of stock (for FIFO valuation)."""
    batch_id:     str
    purchase_date: date
    quantity:     float
    cost_per_unit: float   # Excluding GST

    @property
    def total_cost(self) -> float:
        return self.quantity * self.cost_per_unit


@dataclass
class InventoryTransaction:
    txn_id:       str
    sku:          str
    txn_type:     TransactionType
    txn_date:     date
    quantity:     float
    unit_price:   float     # For purchases: cost; for sales: selling price
    gst_amount:   float
    party_name:   Optional[str] = None
    invoice_no:   Optional[str] = None
    notes:        Optional[str] = None
    # Gold-specific
    weight_grams: float = 0.0
    making_charges: float = 0.0


@dataclass
class StockLevel:
    sku:              str
    product_name:     str
    category:         str
    current_qty:      float
    unit:             str
    reorder_level:    float
    needs_reorder:    bool
    avg_cost:         float
    total_value:      float
    last_transaction: Optional[date]


@dataclass
class InventorySummary:
    total_skus:          int
    total_stock_value:   float
    low_stock_count:     int
    out_of_stock_count:  int
    stock_levels:        List[StockLevel]
    low_stock_alerts:    List[str]
    valuation_method:    str
    gold_stock_grams:    float
    gold_stock_value:    float


# ---------------------------------------------------------------------------
# Inventory Manager
# ---------------------------------------------------------------------------

class InventoryManager:
    """
    Manages product inventory with FIFO or weighted-average valuation.

    Usage:
        mgr = InventoryManager(valuation=ValuationMethod.FIFO)
        mgr.add_product(Product(...))
        mgr.record_transaction(InventoryTransaction(...))
        summary = mgr.get_summary()
    """

    def __init__(self, valuation: ValuationMethod = ValuationMethod.WAVG):
        self.valuation   = valuation
        self._products:  Dict[str, Product] = {}
        self._stock:     Dict[str, float] = {}           # sku -> qty
        self._fifo:      Dict[str, Deque[StockBatch]] = {}  # sku -> batches
        self._wavg_cost: Dict[str, float] = {}           # sku -> weighted avg cost
        self._txns:      List[InventoryTransaction] = []

    def add_product(self, product: Product) -> None:
        self._products[product.sku] = product
        self._stock[product.sku]    = 0.0
        self._fifo[product.sku]     = deque()
        self._wavg_cost[product.sku]= 0.0

    def record_transaction(self, txn: InventoryTransaction) -> None:
        self._txns.append(txn)
        sku = txn.sku

        if txn.txn_type in (TransactionType.PURCHASE, TransactionType.RETURN_IN):
            self._stock[sku] = self._stock.get(sku, 0) + txn.quantity
            batch = StockBatch(
                batch_id      = txn.txn_id,
                purchase_date = txn.txn_date,
                quantity      = txn.quantity,
                cost_per_unit = txn.unit_price,
            )
            self._fifo.setdefault(sku, deque()).append(batch)
            # Update weighted average
            existing_qty  = self._stock[sku] - txn.quantity
            existing_val  = existing_qty * self._wavg_cost.get(sku, 0)
            new_val       = txn.quantity * txn.unit_price
            total_qty     = self._stock[sku]
            self._wavg_cost[sku] = (existing_val + new_val) / total_qty if total_qty else txn.unit_price

        elif txn.txn_type in (TransactionType.SALE, TransactionType.RETURN_OUT):
            qty = txn.quantity
            self._stock[sku] = max(0.0, self._stock.get(sku, 0) - qty)
            if self.valuation == ValuationMethod.FIFO:
                self._dequeue_fifo(sku, qty)

        elif txn.txn_type == TransactionType.ADJUSTMENT:
            self._stock[sku] = max(0.0, self._stock.get(sku, 0) + txn.quantity)

    def _dequeue_fifo(self, sku: str, qty: float) -> None:
        batches = self._fifo.get(sku, deque())
        remaining = qty
        while remaining > 0 and batches:
            batch = batches[0]
            if batch.quantity <= remaining:
                remaining -= batch.quantity
                batches.popleft()
            else:
                batch.quantity -= remaining
                remaining = 0

    def get_stock_level(self, sku: str) -> Optional[StockLevel]:
        product = self._products.get(sku)
        if not product:
            return None
        qty      = self._stock.get(sku, 0)
        avg_cost = self._get_avg_cost(sku)
        last_txn = max((t.txn_date for t in self._txns if t.sku == sku), default=None)
        return StockLevel(
            sku             = sku,
            product_name    = product.name,
            category        = product.category.value,
            current_qty     = qty,
            unit            = product.unit,
            reorder_level   = product.reorder_level,
            needs_reorder   = qty <= product.reorder_level,
            avg_cost        = avg_cost,
            total_value     = qty * avg_cost,
            last_transaction= last_txn,
        )

    def _get_avg_cost(self, sku: str) -> float:
        if self.valuation == ValuationMethod.WAVG:
            return self._wavg_cost.get(sku, 0)
        # FIFO: use earliest batch cost
        batches = self._fifo.get(sku, deque())
        if batches:
            return batches[0].cost_per_unit
        return 0.0

    def get_summary(self) -> InventorySummary:
        levels = [self.get_stock_level(sku) for sku in self._products]
        levels = [l for l in levels if l is not None]

        total_value    = sum(l.total_value for l in levels)
        low_stock      = [l for l in levels if l.needs_reorder and l.current_qty > 0]
        out_of_stock   = [l for l in levels if l.current_qty == 0]
        low_stock_alerts = [
            f"LOW STOCK: {l.product_name} ({l.sku}) — {l.current_qty:.2f} {l.unit} remaining "
            f"(reorder level: {l.reorder_level} {l.unit})."
            for l in low_stock
        ] + [
            f"OUT OF STOCK: {l.product_name} ({l.sku}) — order {self._products[l.sku].reorder_qty} {l.unit}."
            for l in out_of_stock
        ]

        # Gold-specific aggregation
        gold_levels = [l for l in levels if self._products.get(l.sku, Product("","", Category.GENERAL,"",0,"",0,0)).category == Category.GOLD]
        gold_grams  = sum(l.current_qty for l in gold_levels)
        gold_value  = sum(l.total_value for l in gold_levels)

        return InventorySummary(
            total_skus          = len(levels),
            total_stock_value   = total_value,
            low_stock_count     = len(low_stock),
            out_of_stock_count  = len(out_of_stock),
            stock_levels        = levels,
            low_stock_alerts    = low_stock_alerts,
            valuation_method    = self.valuation.value,
            gold_stock_grams    = gold_grams,
            gold_stock_value    = gold_value,
        )

    def compute_gold_invoice(
        self,
        weight_grams:    float,
        rate_per_gram:   float,
        making_per_gram: float,
        hallmarking_fee: float = 45.0,   # ₹45 per piece (BIS hallmarking)
        purity_karat:    int   = 22,
    ) -> Dict:
        """Compute gold jewellery invoice with GST split (Sec 3% on gold, 5% on making)."""
        gold_value       = weight_grams * rate_per_gram
        making_charges   = weight_grams * making_per_gram
        gold_gst         = gold_value * GOLD_GST_RATE
        making_gst       = making_charges * MAKING_CHARGES_GST
        total_taxable    = gold_value + making_charges + hallmarking_fee
        total_gst        = gold_gst + making_gst
        invoice_value    = total_taxable + total_gst

        return {
            "purity_karat":      purity_karat,
            "weight_grams":      weight_grams,
            "rate_per_gram":     rate_per_gram,
            "gold_value":        round(gold_value, 2),
            "making_charges":    round(making_charges, 2),
            "hallmarking_fee":   hallmarking_fee,
            "total_taxable":     round(total_taxable, 2),
            "gold_gst_3pct":     round(gold_gst, 2),
            "making_gst_5pct":   round(making_gst, 2),
            "total_gst":         round(total_gst, 2),
            "invoice_value":     round(invoice_value, 2),
            "hsn_code_gold":     "7113",
            "hsn_code_making":   "9983",
        }


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def manage_inventory(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> date:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError, AttributeError):
                pass
        return date.today()

    mgr = InventoryManager(
        valuation=ValuationMethod(params.get("valuation", "weighted_average"))
    )

    for p in params.get("products", []):
        mgr.add_product(Product(
            sku           = p.get("sku", ""),
            name          = p.get("name", ""),
            category      = Category(p.get("category", "general")),
            hsn_code      = p.get("hsn_code", ""),
            gst_rate      = float(p.get("gst_rate", 0.18)),
            unit          = p.get("unit", "pcs"),
            reorder_level = float(p.get("reorder_level", 10)),
            reorder_qty   = float(p.get("reorder_qty", 50)),
            purity_karat  = p.get("purity_karat"),
            making_charge_per_gram = float(p.get("making_charge_per_gram", 0)),
            hallmarking_required   = bool(p.get("hallmarking_required", False)),
        ))

    for t in params.get("transactions", []):
        mgr.record_transaction(InventoryTransaction(
            txn_id     = t.get("txn_id", str(id(t))),
            sku        = t.get("sku", ""),
            txn_type   = TransactionType(t.get("txn_type", "purchase")),
            txn_date   = _d(t.get("txn_date", "")),
            quantity   = float(t.get("quantity", 0)),
            unit_price = float(t.get("unit_price", 0)),
            gst_amount = float(t.get("gst_amount", 0)),
            party_name = t.get("party_name"),
            invoice_no = t.get("invoice_no"),
            weight_grams    = float(t.get("weight_grams", 0)),
            making_charges  = float(t.get("making_charges", 0)),
        ))

    summary = mgr.get_summary()

    result = {
        "total_skus":          summary.total_skus,
        "total_stock_value":   summary.total_stock_value,
        "low_stock_count":     summary.low_stock_count,
        "out_of_stock_count":  summary.out_of_stock_count,
        "valuation_method":    summary.valuation_method,
        "gold_stock_grams":    summary.gold_stock_grams,
        "gold_stock_value":    summary.gold_stock_value,
        "low_stock_alerts":    summary.low_stock_alerts,
        "stock_levels":        [asdict(l) for l in summary.stock_levels],
    }

    if params.get("gold_invoice"):
        gi = params["gold_invoice"]
        result["gold_invoice"] = mgr.compute_gold_invoice(
            weight_grams    = float(gi.get("weight_grams", 0)),
            rate_per_gram   = float(gi.get("rate_per_gram", 0)),
            making_per_gram = float(gi.get("making_per_gram", 0)),
            hallmarking_fee = float(gi.get("hallmarking_fee", 45)),
            purity_karat    = int(gi.get("purity_karat", 22)),
        )

    return result
