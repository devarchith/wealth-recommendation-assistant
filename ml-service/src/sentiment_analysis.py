"""
Sentiment Analysis Pipeline — Response Personalization
Analyzes the emotional tone and financial anxiety level of user queries
to personalize the assistant's response style and recommendations.

Paper §3.4: "Sentiment-aware response generation adjusts tone based on
user anxiety signals — reassuring language for worried users, data-driven
brevity for confident users — improving satisfaction by 12% in A/B tests."

Sentiment dimensions:
  1. Polarity:  positive | neutral | negative  (overall emotional tone)
  2. Anxiety:   high | medium | low            (financial stress signal)
  3. Urgency:   high | medium | low            (time-pressure signal)
  4. Confidence: high | low                   (user's self-assessed knowledge)

Pipeline:
  Primary: FinBERT (ProsusAI/finbert) — domain-adapted BERT for finance
  Fallback: VADER-inspired lexicon scoring (no model download required)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lexicon-based scoring (VADER-inspired, finance-tuned)
# ---------------------------------------------------------------------------

_POSITIVE_LEXICON = [
    "excited", "great", "wonderful", "optimistic", "confident", "happy",
    "growth", "profit", "gain", "return", "opportunity", "bullish",
    "ahead", "plan", "goal", "achieve", "improve", "learn",
    "interested", "curious", "ready",
]

_NEGATIVE_LEXICON = [
    "worried", "anxious", "scared", "afraid", "stressed", "confused",
    "loss", "debt", "broke", "struggling", "problem", "help", "panic",
    "crash", "recession", "inflation", "layoff", "fired", "bankrupt",
    "overwhelmed", "desperate", "stuck",
]

_ANXIETY_LEXICON = [
    "scared", "terrified", "panic", "anxious", "anxiety", "worried",
    "nervous", "overwhelmed", "hopeless", "desperate", "can't afford",
    "cannot afford", "running out", "losing money", "in trouble",
    "bad decision", "made a mistake", "emergency",
]

_URGENCY_LEXICON = [
    "asap", "immediately", "right now", "urgent", "deadline", "soon",
    "this week", "today", "by tomorrow", "before april", "before filing",
    "running out of time", "need to know now", "quickly", "fast",
]

_LOW_CONFIDENCE_LEXICON = [
    "don't know", "do not know", "confused", "not sure", "unsure",
    "no idea", "beginner", "newbie", "just starting", "never invested",
    "first time", "what is", "can you explain", "help me understand",
    "i don't understand", "what does", "what are",
]

_HIGH_CONFIDENCE_LEXICON = [
    "i know", "i understand", "i already", "i have been", "experienced",
    "advanced", "i want to optimize", "compare", "which is better",
    "tax-loss harvest", "backdoor roth", "asset location",
]


def _score_lexicon(text: str, lexicon: List[str]) -> int:
    lower = text.lower()
    return sum(1 for term in lexicon if term in lower)


# ---------------------------------------------------------------------------
# Response style presets (paper Table 3)
# ---------------------------------------------------------------------------

RESPONSE_STYLES: Dict[str, Dict] = {
    "reassure_and_educate": {
        "description": "High anxiety / low confidence — use empathetic, simple language",
        "tone_prefix": "I understand this can feel overwhelming. Let me break this down simply. ",
        "max_bullet_points": 3,
        "use_examples": True,
        "include_next_step": True,
    },
    "concise_expert": {
        "description": "Low anxiety / high confidence — data-driven, minimal preamble",
        "tone_prefix": "",
        "max_bullet_points": 5,
        "use_examples": False,
        "include_next_step": False,
    },
    "urgent_action": {
        "description": "High urgency — prioritize actionable steps, flag deadlines",
        "tone_prefix": "Given the time constraint, here's what matters most: ",
        "max_bullet_points": 3,
        "use_examples": False,
        "include_next_step": True,
    },
    "encouraging": {
        "description": "Positive sentiment — affirm progress, expand on opportunities",
        "tone_prefix": "Great question! ",
        "max_bullet_points": 5,
        "use_examples": True,
        "include_next_step": True,
    },
    "balanced": {
        "description": "Neutral baseline",
        "tone_prefix": "",
        "max_bullet_points": 4,
        "use_examples": True,
        "include_next_step": True,
    },
}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SentimentResult:
    polarity: str           # "positive" | "neutral" | "negative"
    polarity_score: float   # -1.0 to 1.0
    anxiety_level: str      # "high" | "medium" | "low"
    urgency_level: str      # "high" | "medium" | "low"
    confidence_level: str   # "high" | "low"
    response_style: str     # key into RESPONSE_STYLES
    method: str = "lexicon"
    raw_scores: Dict[str, float] = field(default_factory=dict)

    def get_style_config(self) -> Dict:
        return RESPONSE_STYLES.get(self.response_style, RESPONSE_STYLES["balanced"])


# ---------------------------------------------------------------------------
# FinBERT-based sentiment classifier
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """
    Two-stage sentiment analyzer for financial queries.

    Stage 1 (FinBERT): ProsusAI/finbert — domain-adapted sentiment model
    trained on financial news and reports; outputs positive/neutral/negative.

    Stage 2 (lexicon): Independently scores anxiety, urgency, and user
    confidence from curated financial lexicons.

    The combination determines the response_style preset injected into
    the RAG prompt template for personalized answer generation.
    """

    def __init__(self):
        self._pipeline = None
        self._try_load()

    def _try_load(self) -> None:
        try:
            from transformers import pipeline as hf_pipeline  # noqa: PLC0415
            logger.info("Loading FinBERT sentiment pipeline …")
            self._pipeline = hf_pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                device=-1,
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT sentiment pipeline ready.")
        except Exception as exc:
            logger.warning(
                "FinBERT unavailable (%s); using lexicon fallback.", exc
            )
            self._pipeline = None

    def _lexicon_polarity(self, text: str) -> tuple[str, float]:
        pos = _score_lexicon(text, _POSITIVE_LEXICON)
        neg = _score_lexicon(text, _NEGATIVE_LEXICON)
        total = pos + neg or 1
        score = (pos - neg) / total
        if score > 0.1:
            return "positive", round(score, 3)
        if score < -0.1:
            return "negative", round(score, 3)
        return "neutral", round(score, 3)

    def _map_finbert_label(self, label: str, score: float) -> tuple[str, float]:
        label_lower = label.lower()
        if "positive" in label_lower:
            return "positive", score
        if "negative" in label_lower:
            return "negative", -score
        return "neutral", 0.0

    def _determine_response_style(
        self,
        polarity: str,
        anxiety: str,
        urgency: str,
        confidence: str,
    ) -> str:
        if anxiety == "high" or confidence == "low":
            return "reassure_and_educate"
        if urgency == "high":
            return "urgent_action"
        if polarity == "positive":
            return "encouraging"
        if confidence == "high":
            return "concise_expert"
        return "balanced"

    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze the emotional tone and stress signals of a financial query.

        Returns a SentimentResult with polarity, anxiety, urgency,
        confidence levels, and the recommended response_style preset.
        """
        if not text.strip():
            return SentimentResult(
                polarity="neutral", polarity_score=0.0,
                anxiety_level="low", urgency_level="low",
                confidence_level="high", response_style="balanced",
            )

        # ── Polarity (FinBERT or lexicon) ────────────────────────────────
        polarity_score = 0.0
        polarity = "neutral"
        method = "lexicon"

        if self._pipeline:
            try:
                out = self._pipeline(text[:512])[0]
                polarity, polarity_score = self._map_finbert_label(
                    out["label"], out["score"]
                )
                method = "finbert"
            except Exception as exc:
                logger.warning("FinBERT inference error (%s); falling back.", exc)

        if method == "lexicon":
            polarity, polarity_score = self._lexicon_polarity(text)

        # ── Anxiety ──────────────────────────────────────────────────────
        anxiety_hits = _score_lexicon(text, _ANXIETY_LEXICON)
        anxiety_level = "high" if anxiety_hits >= 2 else ("medium" if anxiety_hits == 1 else "low")

        # ── Urgency ──────────────────────────────────────────────────────
        urgency_hits = _score_lexicon(text, _URGENCY_LEXICON)
        urgency_level = "high" if urgency_hits >= 2 else ("medium" if urgency_hits == 1 else "low")

        # ── User confidence ───────────────────────────────────────────────
        low_conf_hits = _score_lexicon(text, _LOW_CONFIDENCE_LEXICON)
        high_conf_hits = _score_lexicon(text, _HIGH_CONFIDENCE_LEXICON)
        confidence_level = "low" if low_conf_hits > high_conf_hits else "high"

        # ── Response style ────────────────────────────────────────────────
        response_style = self._determine_response_style(
            polarity, anxiety_level, urgency_level, confidence_level
        )

        return SentimentResult(
            polarity=polarity,
            polarity_score=polarity_score,
            anxiety_level=anxiety_level,
            urgency_level=urgency_level,
            confidence_level=confidence_level,
            response_style=response_style,
            method=method,
            raw_scores={
                "polarity_score": polarity_score,
                "anxiety_hits": float(anxiety_hits),
                "urgency_hits": float(urgency_hits),
                "low_confidence_hits": float(low_conf_hits),
                "high_confidence_hits": float(high_conf_hits),
            },
        )


# ---------------------------------------------------------------------------
# Singleton + convenience function
# ---------------------------------------------------------------------------

_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


def analyze_sentiment(text: str) -> SentimentResult:
    """Module-level convenience function for sentiment analysis."""
    return get_sentiment_analyzer().analyze(text)
