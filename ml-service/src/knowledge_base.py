"""
Financial Knowledge Base
Provides a curated corpus of financial advisory content and document
chunking utilities used to build the FAISS vector index.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunk configuration
# ---------------------------------------------------------------------------

CHUNK_SIZE = 512          # characters per chunk
CHUNK_OVERLAP = 64        # overlap to preserve context across boundaries
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


# ---------------------------------------------------------------------------
# Raw financial knowledge corpus
# ---------------------------------------------------------------------------

RAW_DOCUMENTS: List[dict] = [
    # ---- Budgeting & Savings -----------------------------------------------
    {
        "title": "50/30/20 Budgeting Rule",
        "category": "budgeting",
        "content": (
            "The 50/30/20 rule is a simple budgeting framework: allocate 50% of "
            "after-tax income to needs (rent, groceries, utilities, minimum debt "
            "payments), 30% to wants (dining, entertainment, subscriptions), and 20% "
            "to savings and extra debt repayment. This rule works best for middle-income "
            "earners. Higher earners should consider increasing the savings percentage. "
            "Automate savings transfers on payday to enforce the rule passively. "
            "Review your budget quarterly as income and expenses change."
        ),
    },
    {
        "title": "Emergency Fund Basics",
        "category": "savings",
        "content": (
            "An emergency fund is 3–6 months of essential living expenses held in a "
            "liquid, low-risk account such as a high-yield savings account (HYSA). "
            "Start with a $1,000 starter fund to cover minor emergencies, then build "
            "to the full target. Keep the fund in a separate account to reduce "
            "temptation. Those with variable income (freelancers, contractors) should "
            "target 6–12 months. Do not invest emergency funds in stocks — capital "
            "preservation and liquidity are the priorities."
        ),
    },
    # ---- Investing ------------------------------------------------------------
    {
        "title": "Index Fund Investing",
        "category": "investing",
        "content": (
            "Index funds track a market benchmark (e.g., S&P 500, total market) and "
            "offer broad diversification at very low cost. The average expense ratio "
            "of index funds is 0.03–0.10%, far below the 0.5–1.5% of actively managed "
            "funds. Research consistently shows that over 10+ year periods, 85–90% of "
            "actively managed funds underperform their benchmark after fees. A simple "
            "three-fund portfolio (total US market, international, bonds) covers most "
            "investor needs. Prefer funds from Vanguard, Fidelity, or Schwab for the "
            "lowest costs. Rebalance annually or when allocations drift more than 5%."
        ),
    },
    {
        "title": "Dollar-Cost Averaging",
        "category": "investing",
        "content": (
            "Dollar-cost averaging (DCA) means investing a fixed dollar amount at "
            "regular intervals regardless of market price. DCA removes the emotional "
            "temptation to time the market and automatically buys more shares when "
            "prices are low. Studies show that lump-sum investing outperforms DCA "
            "roughly two-thirds of the time when cash is available, but DCA reduces "
            "regret risk and is optimal when investing ongoing income. Set up automatic "
            "contributions to your 401(k) or brokerage account to implement DCA "
            "effortlessly."
        ),
    },
    {
        "title": "Asset Allocation by Age",
        "category": "investing",
        "content": (
            "A common rule of thumb: subtract your age from 110 to get your stock "
            "allocation percentage (e.g., age 30 → 80% stocks, 20% bonds). Modern "
            "variants use 120 or 125 due to longer life expectancy. Target-date funds "
            "automate this glide path. Young investors with a 30+ year horizon can "
            "tolerate 90–100% equities. As retirement approaches, shift toward bonds "
            "and cash equivalents for capital preservation. Consider your risk "
            "tolerance alongside time horizon — an investor who panics and sells "
            "during downturns needs a more conservative allocation than their age "
            "alone suggests."
        ),
    },
    # ---- Retirement ----------------------------------------------------------
    {
        "title": "401(k) and IRA Contribution Limits",
        "category": "retirement",
        "content": (
            "For 2024: 401(k) employee contribution limit is $23,000 ($30,500 if age "
            "50+). Traditional and Roth IRA limit is $7,000 ($8,000 if 50+). Roth IRA "
            "income phase-out: $146,000–$161,000 (single), $230,000–$240,000 (married "
            "filing jointly). Always contribute at least enough to your 401(k) to "
            "capture the full employer match — this is an immediate 50–100% return on "
            "investment. Prioritize: (1) 401(k) to match, (2) max HSA if eligible, "
            "(3) max Roth IRA, (4) max 401(k) remainder, (5) taxable brokerage."
        ),
    },
    {
        "title": "Roth vs Traditional IRA",
        "category": "retirement",
        "content": (
            "Traditional IRA: contributions may be tax-deductible (reduces taxable "
            "income now), growth is tax-deferred, withdrawals in retirement are taxed "
            "as ordinary income. Required minimum distributions (RMDs) start at age 73. "
            "Roth IRA: contributions are after-tax (no current deduction), growth and "
            "qualified withdrawals are completely tax-free, no RMDs during owner's "
            "lifetime. Choose Roth if you expect to be in a higher tax bracket in "
            "retirement, or if you want maximum tax diversification. Roth is generally "
            "superior for young, lower-income earners early in their careers."
        ),
    },
    {
        "title": "Social Security Optimization",
        "category": "retirement",
        "content": (
            "You can claim Social Security as early as age 62 (reduced by up to 30%) "
            "or delay to age 70 (increased by 8% per year past full retirement age). "
            "Full retirement age (FRA) is 67 for those born after 1960. Delaying to 70 "
            "maximizes lifetime benefits if you expect to live past age 80. Couples "
            "should coordinate: the higher earner often delays to 70 for a larger "
            "survivor benefit. Working while claiming before FRA reduces benefits if "
            "earnings exceed the annual exempt amount ($22,320 in 2024)."
        ),
    },
    # ---- Debt Management -----------------------------------------------------
    {
        "title": "Debt Avalanche vs Snowball",
        "category": "debt",
        "content": (
            "Debt Avalanche: pay minimums on all debts, put extra cash toward the "
            "highest-interest debt first. Mathematically optimal — saves the most money "
            "in interest. Debt Snowball: pay minimums on all, attack the smallest balance "
            "first. Provides psychological wins that boost motivation. Research shows "
            "snowball users pay off debt faster in practice due to behavioral effects. "
            "Hybrid approach: if two debts have similar interest rates, pay the smaller "
            "balance for a quick win, then switch to avalanche. Never skip minimum "
            "payments — late fees and credit score damage negate any strategy."
        ),
    },
    {
        "title": "Mortgage and Housing Costs",
        "category": "debt",
        "content": (
            "Total housing costs (mortgage P&I, taxes, insurance, HOA) should not "
            "exceed 28% of gross monthly income (front-end ratio). Total debt payments "
            "including housing should stay below 36–43% (back-end ratio, varies by "
            "lender). A 20% down payment avoids private mortgage insurance (PMI, "
            "0.5–1.5% of loan annually). 15-year mortgages carry lower rates but "
            "higher payments; 30-year provides flexibility. Extra principal payments "
            "on a 30-year can significantly reduce total interest — even $100/month "
            "extra on a $300K loan saves ~$30K in interest."
        ),
    },
    # ---- Tax Planning ---------------------------------------------------------
    {
        "title": "Tax-Loss Harvesting",
        "category": "tax",
        "content": (
            "Tax-loss harvesting sells investments at a loss to offset capital gains, "
            "reducing your current tax bill. Losses offset short-term gains first "
            "(taxed as ordinary income), then long-term gains (taxed at 0%, 15%, or 20%). "
            "Up to $3,000 in net losses can be deducted against ordinary income annually; "
            "excess losses carry forward indefinitely. Beware the wash-sale rule: you "
            "cannot repurchase a substantially identical security within 30 days before "
            "or after the sale. Replace sold funds with similar-but-not-identical ETFs "
            "to maintain market exposure. Particularly valuable in taxable brokerage "
            "accounts for high-income investors."
        ),
    },
    {
        "title": "Health Savings Account (HSA) Strategy",
        "category": "tax",
        "content": (
            "An HSA offers a triple tax advantage: contributions are pre-tax, growth "
            "is tax-free, and withdrawals for qualified medical expenses are tax-free. "
            "2024 contribution limits: $4,150 (self-only HDHP), $8,300 (family HDHP), "
            "+$1,000 catch-up if 55+. The 'stealth IRA' strategy: contribute the max, "
            "invest aggressively in index funds, pay medical bills out-of-pocket, and "
            "save receipts. After age 65, withdrawals for any purpose are taxed as "
            "ordinary income (like a Traditional IRA), but qualified medical withdrawals "
            "remain tax-free forever. The HSA is the only account with a triple tax "
            "advantage — max it out if eligible."
        ),
    },
    # ---- Insurance ------------------------------------------------------------
    {
        "title": "Term vs Whole Life Insurance",
        "category": "insurance",
        "content": (
            "Term life insurance provides coverage for a fixed period (10, 20, or 30 "
            "years) at low cost. A healthy 30-year-old can get $500K of 20-year term "
            "coverage for ~$25/month. Whole life insurance combines a death benefit with "
            "a savings component (cash value) but costs 5–15x more than term. Most "
            "financial planners recommend 'buy term and invest the difference.' Whole "
            "life may be appropriate for estate planning or irrevocable trust strategies, "
            "but is rarely the best choice for pure insurance needs. Coverage need: "
            "10–12x annual income, or enough to replace income for dependents until "
            "they are self-sufficient."
        ),
    },
    # ---- Wealth Building ------------------------------------------------------
    {
        "title": "Net Worth Milestones",
        "category": "wealth",
        "content": (
            "Tracking net worth (assets minus liabilities) provides a holistic view of "
            "financial health. Key milestones: $0 net worth (debt-free), 1x salary saved "
            "by 30, 3x by 40, 6x by 50, 8x by 60 (Fidelity guidelines). The 4% rule "
            "for retirement: you can withdraw 4% of your portfolio annually with high "
            "confidence the money lasts 30 years. Example: $1M portfolio → $40K/year. "
            "Track net worth monthly using free tools (Personal Capital, Monarch Money). "
            "Focus on increasing income and savings rate, not just cutting expenses — "
            "there is a floor on expenses but no ceiling on income."
        ),
    },
    {
        "title": "Diversification and Portfolio Theory",
        "category": "investing",
        "content": (
            "Modern Portfolio Theory (MPT) shows that combining assets with low "
            "correlation reduces portfolio volatility without sacrificing expected "
            "return. An S&P 500 index covers 500 large US companies but is still "
            "heavily concentrated in technology (~30% as of 2024). Global diversification "
            "— adding international developed (VXUS) and emerging markets — reduces "
            "country-specific risk. Factor investing (small-cap value tilt, profitability "
            "factor) historically provides long-run return premium over pure market-cap "
            "weighting. REITs provide real estate exposure with REIT correlation to "
            "stocks rising during crises but offering diversification in stable periods."
        ),
    },
    {
        "title": "Behavioral Finance and Investor Psychology",
        "category": "investing",
        "content": (
            "Common cognitive biases that hurt investors: (1) Loss aversion — losses "
            "feel twice as painful as equivalent gains, causing panic selling. (2) "
            "Recency bias — over-weighting recent performance, chasing last year's "
            "winners. (3) Overconfidence — individual stock picking rarely beats index "
            "funds long-term. (4) Home bias — over-allocating to domestic stocks. "
            "Countermeasures: write an Investment Policy Statement (IPS) defining your "
            "strategy and rules. Automate contributions and rebalancing to remove "
            "discretion. Limit portfolio-checking to quarterly. Remember that time in "
            "the market beats timing the market — missing the 10 best days in a decade "
            "can cut returns by half."
        ),
    },
]


# ---------------------------------------------------------------------------
# Document chunking
# ---------------------------------------------------------------------------

@dataclass
class ChunkConfig:
    chunk_size: int = CHUNK_SIZE
    chunk_overlap: int = CHUNK_OVERLAP
    separators: List[str] = field(default_factory=lambda: SEPARATORS)


def build_documents(raw: List[dict] | None = None) -> List[Document]:
    """
    Convert raw knowledge-base entries into LangChain Document objects.
    Each raw entry maps to one Document; metadata carries title and category.
    """
    corpus = raw or RAW_DOCUMENTS
    docs = []
    for entry in corpus:
        doc = Document(
            page_content=entry["content"],
            metadata={
                "title": entry["title"],
                "category": entry["category"],
                "source": f"knowledge_base/{entry['category']}/{entry['title']}",
            },
        )
        docs.append(doc)
    logger.info("Built %d documents from raw corpus", len(docs))
    return docs


def chunk_documents(
    docs: List[Document],
    config: ChunkConfig | None = None,
) -> List[Document]:
    """
    Split documents into fixed-size chunks with overlap using a
    RecursiveCharacterTextSplitter.  Metadata is preserved on each chunk.
    """
    cfg = config or ChunkConfig()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=cfg.separators,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(
        "Chunked %d docs → %d chunks (size=%d, overlap=%d)",
        len(docs), len(chunks), cfg.chunk_size, cfg.chunk_overlap,
    )
    return chunks


def load_knowledge_base() -> List[Document]:
    """
    High-level helper: build + chunk the financial knowledge corpus.
    Returns a list of LangChain Documents ready for embedding.
    """
    raw_docs = build_documents()
    chunks = chunk_documents(raw_docs)
    return chunks
