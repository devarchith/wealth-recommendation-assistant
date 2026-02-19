"""
Named Entity Recognition (NER) — Financial Domain
Extracts structured financial entities from user queries to enrich
the RAG retrieval context and enable targeted response generation.

Entity types (paper §3.3):
  STOCK       — ticker symbols and company names (AAPL, Tesla, SPY)
  CRYPTO      — cryptocurrency names and symbols (Bitcoin, BTC, ETH)
  TAX_TERM    — IRS forms, tax concepts (W-2, 1099, capital gains)
  ACCOUNT     — financial account types (401k, Roth IRA, HSA, brokerage)
  AMOUNT      — monetary values ($5,000, 10%, $500/month)
  TIME_PERIOD — temporal references (2024, Q1, by April 15, this year)
  FUND        — mutual funds / ETFs (VTSAX, VTI, QQQ, S&P 500)

Architecture:
  Primary: spaCy NER pipeline with custom financial entity ruler patterns
  Fallback: regex + curated gazetteer for environments without spaCy
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity type constants
# ---------------------------------------------------------------------------

ENTITY_TYPES = ["STOCK", "CRYPTO", "TAX_TERM", "ACCOUNT", "AMOUNT", "TIME_PERIOD", "FUND"]

# ---------------------------------------------------------------------------
# Financial gazetteers
# ---------------------------------------------------------------------------

_STOCKS = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "TSLA": "Tesla", "NVDA": "NVIDIA", "META": "Meta",
    "BRK.B": "Berkshire Hathaway", "JPM": "JPMorgan", "V": "Visa",
    "JNJ": "Johnson & Johnson", "WMT": "Walmart", "PG": "Procter & Gamble",
}

_CRYPTO = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "Binance Coin",
    "ADA": "Cardano", "SOL": "Solana", "XRP": "Ripple", "DOGE": "Dogecoin",
    "DOT": "Polkadot", "AVAX": "Avalanche", "MATIC": "Polygon",
    "bitcoin": "Bitcoin", "ethereum": "Ethereum", "crypto": None,
    "cryptocurrency": None, "defi": "DeFi",
}

_TAX_TERMS = {
    "W-2": "Wage and Tax Statement",
    "W2": "Wage and Tax Statement",
    "1099": "Miscellaneous Income",
    "1099-NEC": "Nonemployee Compensation",
    "1040": "US Individual Income Tax Return",
    "Schedule C": "Profit or Loss from Business",
    "Schedule D": "Capital Gains and Losses",
    "capital gains": None,
    "capital loss": None,
    "standard deduction": None,
    "itemized deduction": None,
    "AMT": "Alternative Minimum Tax",
    "MAGI": "Modified Adjusted Gross Income",
    "AGI": "Adjusted Gross Income",
    "tax bracket": None,
    "tax credit": None,
    "earned income credit": None,
    "FICA": "Federal Insurance Contributions Act",
}

_ACCOUNTS = {
    "401k": "401(k)", "401(k)": "401(k)", "403b": "403(b)",
    "roth ira": "Roth IRA", "traditional ira": "Traditional IRA",
    "ira": "IRA", "hsa": "Health Savings Account",
    "fsa": "Flexible Spending Account", "529": "529 Education Plan",
    "brokerage": None, "taxable account": None, "sep ira": "SEP-IRA",
    "simple ira": "SIMPLE IRA", "pension": None,
}

_FUNDS = {
    "VTSAX": "Vanguard Total Stock Market Index Fund",
    "VFIAX": "Vanguard 500 Index Fund",
    "VTI": "Vanguard Total Stock Market ETF",
    "VOO": "Vanguard S&P 500 ETF",
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "VXUS": "Vanguard Total International Stock ETF",
    "FSKAX": "Fidelity Total Market Index Fund",
    "FXAIX": "Fidelity 500 Index Fund",
    "S&P 500": None,
    "s&p500": None,
    "total market": None,
    "index fund": None,
    "etf": None,
    "mutual fund": None,
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"""
    (?:
        \$\s*[\d,]+(?:\.\d{1,2})?[kKmMbB]?  # $5,000  $10k  $1.5M
        |
        [\d,]+(?:\.\d{1,2})?\s*(?:dollars?|usd)  # 5000 dollars
        |
        \d+(?:\.\d+)?\s*%  # 10%  0.5%
        |
        \$[\d,]+(?:\.\d{1,2})?\s*/\s*(?:month|year|week)  # $500/month
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_TIME_RE = re.compile(
    r"""
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|
           jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|
           nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?
        |
        april\s+15  # Tax deadline
        |
        Q[1-4]\s*\d{4}  # Q1 2024
        |
        (?:FY|fiscal\s+year)\s*\d{4}  # FY2024
        |
        \d{4}  # standalone year 2024
        |
        this\s+(?:year|month|quarter)
        |
        next\s+(?:year|month|quarter)
        |
        \d+\s+(?:year|month|week|day)s?
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_TICKER_RE = re.compile(r"\b([A-Z]{1,5})(?:\.[A-Z])?\b")


# ---------------------------------------------------------------------------
# Entity dataclass
# ---------------------------------------------------------------------------

@dataclass
class FinancialEntity:
    text: str
    entity_type: str
    canonical: Optional[str] = None  # standardized name if known
    start: int = 0
    end: int = 0


@dataclass
class NERResult:
    entities: List[FinancialEntity] = field(default_factory=list)
    entity_map: Dict[str, List[str]] = field(default_factory=dict)
    method: str = "regex_gazetteer"

    def summary(self) -> str:
        if not self.entities:
            return "No financial entities detected."
        parts = []
        for etype, values in self.entity_map.items():
            parts.append(f"{etype}: {', '.join(values)}")
        return "; ".join(parts)


# ---------------------------------------------------------------------------
# NER engine
# ---------------------------------------------------------------------------

class FinancialNER:
    """
    Financial Named Entity Recognizer.

    Primary method: spaCy pipeline with a custom EntityRuler that injects
    gazetteer patterns for financial terms (loaded on first call).
    Fallback: pure-Python regex + gazetteer lookup (no spaCy required).
    """

    def __init__(self):
        self._nlp = None
        self._try_load_spacy()

    def _try_load_spacy(self) -> None:
        try:
            import spacy  # noqa: PLC0415
            self._nlp = spacy.blank("en")
            ruler = self._nlp.add_pipe("entity_ruler")

            patterns = []
            for ticker in _STOCKS:
                patterns.append({"label": "STOCK", "pattern": ticker})
            for name in _STOCKS.values():
                patterns.append({"label": "STOCK", "pattern": name})
            for symbol in _CRYPTO:
                patterns.append({"label": "CRYPTO", "pattern": symbol})
            for term in _TAX_TERMS:
                patterns.append({"label": "TAX_TERM", "pattern": term})
            for acct in _ACCOUNTS:
                patterns.append({"label": "ACCOUNT", "pattern": acct})
            for fund in _FUNDS:
                patterns.append({"label": "FUND", "pattern": fund})

            ruler.add_patterns(patterns)
            logger.info("spaCy financial EntityRuler loaded (%d patterns).", len(patterns))
        except Exception as exc:
            logger.warning("spaCy unavailable (%s); using regex/gazetteer fallback.", exc)
            self._nlp = None

    def _gazetteer_lookup(self, text: str) -> List[FinancialEntity]:
        """Scan text against all gazetteers and regex patterns."""
        lower = text.lower()
        entities: List[FinancialEntity] = []

        def _add(match_text: str, etype: str, canonical: Optional[str] = None):
            entities.append(FinancialEntity(text=match_text, entity_type=etype, canonical=canonical))

        # Gazetteers
        for ticker, name in _STOCKS.items():
            if ticker in text or (name and name.lower() in lower):
                _add(ticker, "STOCK", name)

        for symbol, name in _CRYPTO.items():
            if symbol in lower:
                _add(symbol, "CRYPTO", name)

        for term, definition in _TAX_TERMS.items():
            if term.lower() in lower:
                _add(term, "TAX_TERM", definition)

        for acct, canonical in _ACCOUNTS.items():
            if acct.lower() in lower:
                _add(acct, "ACCOUNT", canonical)

        for fund, name in _FUNDS.items():
            if fund.lower() in lower:
                _add(fund, "FUND", name)

        # Regex patterns
        for m in _AMOUNT_RE.finditer(text):
            _add(m.group(), "AMOUNT")

        for m in _TIME_RE.finditer(text):
            _add(m.group(), "TIME_PERIOD")

        return entities

    def extract(self, text: str) -> NERResult:
        """
        Extract financial entities from a query string.

        Returns:
            NERResult with entity list and entity_map (type → [texts]) dict.
        """
        if not text.strip():
            return NERResult()

        entities: List[FinancialEntity] = []
        method = "regex_gazetteer"

        if self._nlp:
            try:
                doc = self._nlp(text)
                for ent in doc.ents:
                    entities.append(FinancialEntity(
                        text=ent.text,
                        entity_type=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char,
                    ))
                method = "spacy_ruler"
            except Exception as exc:
                logger.warning("spaCy extraction failed (%s); falling back.", exc)

        if not entities:
            entities = self._gazetteer_lookup(text)

        # Deduplicate by (text, entity_type)
        seen = set()
        unique = []
        for ent in entities:
            key = (ent.text.lower(), ent.entity_type)
            if key not in seen:
                seen.add(key)
                unique.append(ent)

        # Build entity_map
        entity_map: Dict[str, List[str]] = {}
        for ent in unique:
            entity_map.setdefault(ent.entity_type, []).append(ent.text)

        return NERResult(entities=unique, entity_map=entity_map, method=method)


# ---------------------------------------------------------------------------
# Singleton + convenience function
# ---------------------------------------------------------------------------

_ner: Optional[FinancialNER] = None


def get_ner() -> FinancialNER:
    global _ner
    if _ner is None:
        _ner = FinancialNER()
    return _ner


def extract_entities(text: str) -> NERResult:
    """Module-level convenience wrapper for entity extraction."""
    return get_ner().extract(text)
