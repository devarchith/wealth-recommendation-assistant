"""
P&L Statement and Balance Sheet Generator
India SME / Sole Proprietorship context (Ind AS simplified)
Generates:
  • Profit & Loss Statement (vertical format)
  • Balance Sheet (vertical format)
  • Key financial ratios
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional


@dataclass
class LineItem:
    name:     str
    amount:   float
    note:     Optional[str] = None


@dataclass
class PLStatement:
    """Profit & Loss — vertical format."""
    period:                str
    revenue_from_ops:      float
    other_income:          float
    total_revenue:         float
    cost_of_goods_sold:    float
    gross_profit:          float
    gross_margin_pct:      float
    employee_costs:        float
    rent_expense:          float
    depreciation:          float
    other_opex:            float
    total_opex:            float
    ebitda:                float
    ebitda_margin_pct:     float
    ebit:                  float
    interest_expense:      float
    pbt:                   float     # Profit Before Tax
    income_tax:            float
    pat:                   float     # Profit After Tax
    pat_margin_pct:        float
    line_items:            List[LineItem] = field(default_factory=list)


@dataclass
class BalanceSheet:
    """Balance Sheet — vertical format (Assets = Liabilities + Equity)."""
    as_of_date:           str
    # Assets
    cash_and_bank:        float
    accounts_receivable:  float
    inventory:            float
    prepaid_expenses:     float
    other_current_assets: float
    total_current_assets: float
    fixed_assets_gross:   float
    accumulated_dep:      float
    net_fixed_assets:     float
    intangibles:          float
    other_noncurrent:     float
    total_assets:         float
    # Liabilities
    accounts_payable:     float
    short_term_loans:     float
    gst_payable:          float
    tds_payable:          float
    other_current_liab:   float
    total_current_liab:   float
    long_term_loans:      float
    other_noncurrent_liab: float
    total_liabilities:    float
    # Equity
    owner_capital:        float
    retained_earnings:    float
    current_year_profit:  float
    total_equity:         float
    total_liab_equity:    float
    is_balanced:          bool


@dataclass
class FinancialRatios:
    current_ratio:        float
    quick_ratio:          float
    debt_to_equity:       float
    interest_coverage:    float
    inventory_turnover:   float
    receivables_turnover: float
    asset_turnover:       float
    roe:                  float   # Return on Equity
    roa:                  float   # Return on Assets
    gross_margin:         float
    net_margin:           float


@dataclass
class FinancialStatementsResult:
    pl:              PLStatement
    bs:              BalanceSheet
    ratios:          FinancialRatios
    observations:    List[str]


class FinancialStatementsGenerator:
    """
    Generates P&L and Balance Sheet from raw income/expense inputs.

    Usage:
        gen = FinancialStatementsGenerator(period="FY 2024-25")
        gen.set_revenue(revenue=12_00_000, other_income=50_000)
        gen.set_expenses(cogs=6_00_000, employee=2_00_000, rent=1_20_000, depreciation=50_000)
        gen.set_balance_sheet_inputs(cash=2_00_000, receivables=1_50_000, ...)
        result = gen.generate()
    """

    def __init__(self, period: str = "FY 2024-25", as_of_date: Optional[str] = None):
        self.period     = period
        self.as_of_date = as_of_date or date.today().strftime("%d %b %Y")
        # P&L inputs
        self._revenue            = 0.0
        self._other_income       = 0.0
        self._cogs               = 0.0
        self._employee_costs     = 0.0
        self._rent               = 0.0
        self._depreciation       = 0.0
        self._other_opex         = 0.0
        self._interest_expense   = 0.0
        self._income_tax         = 0.0
        self._pl_line_items:  List[LineItem] = []
        # Balance sheet inputs
        self._cash               = 0.0
        self._receivables        = 0.0
        self._inventory          = 0.0
        self._prepaid            = 0.0
        self._other_current_a    = 0.0
        self._fixed_assets_gross = 0.0
        self._accumulated_dep    = 0.0
        self._intangibles        = 0.0
        self._other_noncurrent_a = 0.0
        self._accounts_payable   = 0.0
        self._short_term_loans   = 0.0
        self._gst_payable        = 0.0
        self._tds_payable        = 0.0
        self._other_current_l    = 0.0
        self._long_term_loans    = 0.0
        self._other_noncurrent_l = 0.0
        self._owner_capital      = 0.0
        self._retained_earnings  = 0.0

    def set_revenue(self, revenue: float, other_income: float = 0.0) -> None:
        self._revenue      = revenue
        self._other_income = other_income

    def set_expenses(
        self,
        cogs:           float = 0.0,
        employee:       float = 0.0,
        rent:           float = 0.0,
        depreciation:   float = 0.0,
        other_opex:     float = 0.0,
        interest:       float = 0.0,
        income_tax:     float = 0.0,
    ) -> None:
        self._cogs             = cogs
        self._employee_costs   = employee
        self._rent             = rent
        self._depreciation     = depreciation
        self._other_opex       = other_opex
        self._interest_expense = interest
        self._income_tax       = income_tax

    def add_pl_line_item(self, name: str, amount: float, note: Optional[str] = None) -> None:
        self._pl_line_items.append(LineItem(name, amount, note))
        self._other_opex += amount

    def set_balance_sheet_inputs(
        self,
        cash:               float = 0.0,
        receivables:        float = 0.0,
        inventory:          float = 0.0,
        prepaid:            float = 0.0,
        other_current_a:    float = 0.0,
        fixed_assets_gross: float = 0.0,
        accumulated_dep:    float = 0.0,
        intangibles:        float = 0.0,
        other_noncurrent_a: float = 0.0,
        accounts_payable:   float = 0.0,
        short_term_loans:   float = 0.0,
        gst_payable:        float = 0.0,
        tds_payable:        float = 0.0,
        other_current_l:    float = 0.0,
        long_term_loans:    float = 0.0,
        other_noncurrent_l: float = 0.0,
        owner_capital:      float = 0.0,
        retained_earnings:  float = 0.0,
    ) -> None:
        self._cash               = cash
        self._receivables        = receivables
        self._inventory          = inventory
        self._prepaid            = prepaid
        self._other_current_a    = other_current_a
        self._fixed_assets_gross = fixed_assets_gross
        self._accumulated_dep    = accumulated_dep
        self._intangibles        = intangibles
        self._other_noncurrent_a = other_noncurrent_a
        self._accounts_payable   = accounts_payable
        self._short_term_loans   = short_term_loans
        self._gst_payable        = gst_payable
        self._tds_payable        = tds_payable
        self._other_current_l    = other_current_l
        self._long_term_loans    = long_term_loans
        self._other_noncurrent_l = other_noncurrent_l
        self._owner_capital      = owner_capital
        self._retained_earnings  = retained_earnings

    def generate(self) -> FinancialStatementsResult:
        pl     = self._build_pl()
        bs     = self._build_bs(pl.pat)
        ratios = self._compute_ratios(pl, bs)
        obs    = self._observations(pl, bs, ratios)
        return FinancialStatementsResult(pl=pl, bs=bs, ratios=ratios, observations=obs)

    def _build_pl(self) -> PLStatement:
        total_revenue = self._revenue + self._other_income
        gross_profit  = self._revenue - self._cogs
        gm_pct        = (gross_profit / self._revenue * 100) if self._revenue else 0

        total_opex    = self._employee_costs + self._rent + self._other_opex
        ebitda        = gross_profit - total_opex
        ebitda_pct    = (ebitda / total_revenue * 100) if total_revenue else 0
        ebit          = ebitda - self._depreciation
        pbt           = ebit - self._interest_expense
        pat           = pbt - self._income_tax
        pat_pct       = (pat / total_revenue * 100) if total_revenue else 0

        return PLStatement(
            period             = self.period,
            revenue_from_ops   = self._revenue,
            other_income       = self._other_income,
            total_revenue      = total_revenue,
            cost_of_goods_sold = self._cogs,
            gross_profit       = gross_profit,
            gross_margin_pct   = round(gm_pct, 2),
            employee_costs     = self._employee_costs,
            rent_expense       = self._rent,
            depreciation       = self._depreciation,
            other_opex         = self._other_opex,
            total_opex         = total_opex + self._depreciation,
            ebitda             = ebitda,
            ebitda_margin_pct  = round(ebitda_pct, 2),
            ebit               = ebit,
            interest_expense   = self._interest_expense,
            pbt                = pbt,
            income_tax         = self._income_tax,
            pat                = pat,
            pat_margin_pct     = round(pat_pct, 2),
            line_items         = self._pl_line_items,
        )

    def _build_bs(self, current_year_profit: float) -> BalanceSheet:
        tca = (self._cash + self._receivables + self._inventory
               + self._prepaid + self._other_current_a)
        net_fa  = self._fixed_assets_gross - self._accumulated_dep
        ta      = tca + net_fa + self._intangibles + self._other_noncurrent_a

        tcl = (self._accounts_payable + self._short_term_loans
               + self._gst_payable + self._tds_payable + self._other_current_l)
        tl  = tcl + self._long_term_loans + self._other_noncurrent_l
        te  = self._owner_capital + self._retained_earnings + current_year_profit
        tle = tl + te

        return BalanceSheet(
            as_of_date            = self.as_of_date,
            cash_and_bank         = self._cash,
            accounts_receivable   = self._receivables,
            inventory             = self._inventory,
            prepaid_expenses      = self._prepaid,
            other_current_assets  = self._other_current_a,
            total_current_assets  = tca,
            fixed_assets_gross    = self._fixed_assets_gross,
            accumulated_dep       = self._accumulated_dep,
            net_fixed_assets      = net_fa,
            intangibles           = self._intangibles,
            other_noncurrent      = self._other_noncurrent_a,
            total_assets          = ta,
            accounts_payable      = self._accounts_payable,
            short_term_loans      = self._short_term_loans,
            gst_payable           = self._gst_payable,
            tds_payable           = self._tds_payable,
            other_current_liab    = self._other_current_l,
            total_current_liab    = tcl,
            long_term_loans       = self._long_term_loans,
            other_noncurrent_liab = self._other_noncurrent_l,
            total_liabilities     = tl,
            owner_capital         = self._owner_capital,
            retained_earnings     = self._retained_earnings,
            current_year_profit   = current_year_profit,
            total_equity          = te,
            total_liab_equity     = tle,
            is_balanced           = abs(ta - tle) < 1.0,
        )

    def _compute_ratios(self, pl: PLStatement, bs: BalanceSheet) -> FinancialRatios:
        cl  = bs.total_current_liab or 1
        te  = bs.total_equity or 1
        ta  = bs.total_assets or 1
        rev = pl.total_revenue or 1

        return FinancialRatios(
            current_ratio        = round(bs.total_current_assets / cl, 2),
            quick_ratio          = round((bs.total_current_assets - bs.inventory) / cl, 2),
            debt_to_equity       = round((bs.short_term_loans + bs.long_term_loans) / te, 2),
            interest_coverage    = round(pl.ebit / pl.interest_expense, 2) if pl.interest_expense else 99.0,
            inventory_turnover   = round(pl.cost_of_goods_sold / (bs.inventory or 1), 2),
            receivables_turnover = round(rev / (bs.accounts_receivable or 1), 2),
            asset_turnover       = round(rev / ta, 2),
            roe                  = round(pl.pat / te * 100, 2),
            roa                  = round(pl.pat / ta * 100, 2),
            gross_margin         = pl.gross_margin_pct,
            net_margin           = pl.pat_margin_pct,
        )

    def _observations(
        self,
        pl: PLStatement,
        bs: BalanceSheet,
        r:  FinancialRatios,
    ) -> List[str]:
        obs = []
        if pl.pat < 0:
            obs.append(f"Business reported a net loss of ₹{abs(pl.pat):,.0f} — review COGS and overheads.")
        if r.current_ratio < 1.0:
            obs.append("Current ratio < 1 — risk of short-term liquidity issues. Consider a working capital line.")
        if r.debt_to_equity > 2.0:
            obs.append("High leverage (D/E > 2) — excessive debt; consider equity infusion or debt reduction.")
        if r.gross_margin < 20:
            obs.append("Low gross margin (<20%) — negotiate better supplier rates or revise pricing.")
        if r.interest_coverage < 1.5 and pl.interest_expense > 0:
            obs.append("Interest coverage < 1.5 — EBIT barely covers interest; refinancing risk is high.")
        if not bs.is_balanced:
            obs.append("Balance sheet does not balance — verify all entries for completeness.")
        if pl.ebitda_margin_pct > 20:
            obs.append(f"Strong EBITDA margin ({pl.ebitda_margin_pct:.1f}%) — business is generating healthy operating cash flows.")
        if not obs:
            obs.append("Financial position looks healthy — maintain current cost controls and collection efficiency.")
        return obs


def generate_financial_statements(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    gen = FinancialStatementsGenerator(
        period     = params.get("period", "FY 2024-25"),
        as_of_date = params.get("as_of_date"),
    )
    gen.set_revenue(
        revenue      = float(params.get("revenue", 0)),
        other_income = float(params.get("other_income", 0)),
    )
    exp = params.get("expenses", {})
    gen.set_expenses(
        cogs        = float(exp.get("cogs", 0)),
        employee    = float(exp.get("employee", 0)),
        rent        = float(exp.get("rent", 0)),
        depreciation= float(exp.get("depreciation", 0)),
        other_opex  = float(exp.get("other_opex", 0)),
        interest    = float(exp.get("interest", 0)),
        income_tax  = float(exp.get("income_tax", 0)),
    )
    bs_in = params.get("balance_sheet", {})
    gen.set_balance_sheet_inputs(
        cash               = float(bs_in.get("cash", 0)),
        receivables        = float(bs_in.get("receivables", 0)),
        inventory          = float(bs_in.get("inventory", 0)),
        prepaid            = float(bs_in.get("prepaid", 0)),
        other_current_a    = float(bs_in.get("other_current_a", 0)),
        fixed_assets_gross = float(bs_in.get("fixed_assets_gross", 0)),
        accumulated_dep    = float(bs_in.get("accumulated_dep", 0)),
        intangibles        = float(bs_in.get("intangibles", 0)),
        other_noncurrent_a = float(bs_in.get("other_noncurrent_a", 0)),
        accounts_payable   = float(bs_in.get("accounts_payable", 0)),
        short_term_loans   = float(bs_in.get("short_term_loans", 0)),
        gst_payable        = float(bs_in.get("gst_payable", 0)),
        tds_payable        = float(bs_in.get("tds_payable", 0)),
        other_current_l    = float(bs_in.get("other_current_l", 0)),
        long_term_loans    = float(bs_in.get("long_term_loans", 0)),
        other_noncurrent_l = float(bs_in.get("other_noncurrent_l", 0)),
        owner_capital      = float(bs_in.get("owner_capital", 0)),
        retained_earnings  = float(bs_in.get("retained_earnings", 0)),
    )
    result = gen.generate()
    return {
        "pl":           asdict(result.pl),
        "balance_sheet": asdict(result.bs),
        "ratios":       asdict(result.ratios),
        "observations": result.observations,
    }
