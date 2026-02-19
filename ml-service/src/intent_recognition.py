"""
BERT-Based Intent Recognition
Classifies user queries into four financial intent categories:
  budget | investment | tax | savings

Architecture (paper §3.2):
  Input text → BERT tokenizer → fine-tuned DistilBERT encoder →
  [CLS] pooled representation → softmax classifier → intent label + confidence

For inference efficiency a lightweight DistilBERT is used (66M params vs
BERT-base 110M) without sacrificing meaningful accuracy on the four-class
financial intent task.

In production the model weights are fine-tuned on the internal financial
query dataset; here we ship a rule-augmented zero-shot fallback that mirrors
the paper's intent taxonomy while the fine-tuned checkpoint is loaded when
INTENT_MODEL_PATH is set.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent taxonomy (paper Table 1)
# ---------------------------------------------------------------------------

INTENTS = ["budget", "investment", "tax", "savings"]

# DistilBERT checkpoint — override with fine-tuned path in production
MODEL_NAME = os.environ.get(
    "INTENT_MODEL_PATH",
    "distilbert-base-uncased",
)

# ---------------------------------------------------------------------------
# Keyword-rule prior (used as fallback and to augment BERT softmax)
# ---------------------------------------------------------------------------

_KEYWORD_PRIORS: Dict[str, List[str]] = {
    "budget": [
        "budget", "spend", "spending", "expense", "50/30/20", "50 30 20",
        "allocat", "monthly", "cost", "afford", "cash flow", "track",
        "categories", "needs", "wants", "bills", "utilities", "groceries",
    ],
    "investment": [
        "invest", "stock", "etf", "index fund", "portfolio", "return",
        "equity", "bond", "mutual fund", "asset allocation", "rebalance",
        "dividend", "brokerage", "crypto", "bitcoin", "vanguard", "fidelity",
        "reit", "s&p", "dca", "dollar cost", "risk",
    ],
    "tax": [
        "tax", "irs", "deduct", "refund", "w-2", "1099", "capital gain",
        "write off", "filing", "april 15", "tax bracket", "withholding",
        "roth conversion", "tax loss harvest", "estimated tax", "agi",
        "adjusted gross income", "schedule", "form",
    ],
    "savings": [
        "save", "saving", "emergency fund", "high yield", "hysa",
        "interest rate", "cd", "certificate of deposit", "401k", "ira",
        "roth", "retirement", "compound", "automatic", "goal",
        "sinking fund", "rainy day", "nest egg",
    ],
}


def _keyword_scores(text: str) -> Dict[str, float]:
    """Return normalized keyword hit scores for each intent."""
    lower = text.lower()
    raw: Dict[str, float] = {}
    for intent, keywords in _KEYWORD_PRIORS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        raw[intent] = float(hits)
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


# ---------------------------------------------------------------------------
# BERT-based encoder
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    intent: str
    confidence: float
    all_scores: Dict[str, float] = field(default_factory=dict)
    method: str = "bert"  # "bert" | "keyword_fallback"


class BERTIntentClassifier:
    """
    DistilBERT-based intent classifier for financial queries.

    On initialization the model is loaded once and reused (warm-start).
    If the transformers library is unavailable or the model fails to load,
    falls back to keyword-based scoring transparently.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._pipeline = None
        self._ready = False
        self._try_load()

    def _try_load(self) -> None:
        try:
            from transformers import pipeline as hf_pipeline  # noqa: PLC0415
            logger.info("Loading intent classification pipeline: %s", self.model_name)
            # Zero-shot classification works with any BERT-family model
            self._pipeline = hf_pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1,  # CPU
            )
            self._ready = True
            logger.info("Intent classifier loaded successfully.")
        except Exception as exc:
            logger.warning(
                "BERT intent classifier unavailable (%s); using keyword fallback.", exc
            )
            self._ready = False

    def classify(self, text: str) -> IntentResult:
        """
        Classify a financial query into one of four intent labels.

        Uses zero-shot BERT classification with candidate labels.
        Falls back to keyword scoring if BERT is unavailable.

        Args:
            text: Raw user query string.

        Returns:
            IntentResult with intent label, confidence, and all class scores.
        """
        if not text or not text.strip():
            return IntentResult(intent="budget", confidence=0.25, method="keyword_fallback")

        keyword_scores = _keyword_scores(text)

        if self._ready and self._pipeline:
            try:
                candidate_labels = [
                    "budget and spending management",
                    "investment and portfolio management",
                    "tax planning and filing",
                    "savings and retirement planning",
                ]
                label_to_intent = {
                    "budget and spending management": "budget",
                    "investment and portfolio management": "investment",
                    "tax planning and filing": "tax",
                    "savings and retirement planning": "savings",
                }

                result = self._pipeline(
                    text,
                    candidate_labels=candidate_labels,
                    hypothesis_template="This question is about {}.",
                )

                # Fuse BERT scores (80%) with keyword prior (20%)
                bert_scores: Dict[str, float] = {
                    label_to_intent[lbl]: score
                    for lbl, score in zip(result["labels"], result["scores"])
                }
                fused: Dict[str, float] = {
                    intent: 0.8 * bert_scores.get(intent, 0.0)
                            + 0.2 * keyword_scores.get(intent, 0.0)
                    for intent in INTENTS
                }

                best_intent = max(fused, key=lambda k: fused[k])
                return IntentResult(
                    intent=best_intent,
                    confidence=round(fused[best_intent], 4),
                    all_scores={k: round(v, 4) for k, v in fused.items()},
                    method="bert",
                )

            except Exception as exc:
                logger.warning("BERT inference failed (%s); falling back to keywords.", exc)

        # Keyword-only fallback
        best_intent = max(keyword_scores, key=lambda k: keyword_scores[k])
        return IntentResult(
            intent=best_intent,
            confidence=round(keyword_scores[best_intent], 4),
            all_scores={k: round(v, 4) for k, v in keyword_scores.items()},
            method="keyword_fallback",
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_classifier: Optional[BERTIntentClassifier] = None


def get_intent_classifier() -> BERTIntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = BERTIntentClassifier()
    return _classifier


def classify_intent(text: str) -> IntentResult:
    """
    Module-level convenience function.
    Returns an IntentResult for the given query text.
    """
    return get_intent_classifier().classify(text)
