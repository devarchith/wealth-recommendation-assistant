"""
Confidence Scorer with Human CA Escalation Trigger
===================================================
Assigns a confidence score (0.0–1.0) to each AI-generated answer based on:
  1. Retrieval quality: FAISS top-k similarity scores and MMR diversity
  2. Hallucination check: fact registry coverage from hallucination_detector
  3. Intent confidence: DistilBERT zero-shot classification probability
  4. Answer completeness: presence of key structural elements
  5. Query complexity: estimated from linguistic features

Escalation policy:
  - confidence < 0.50 → escalate to human CA review
  - confidence < 0.65 → add disclaimer + suggest CA consultation
  - confidence ≥ 0.65 → serve with normal disclaimer
  - hallucination detected → always escalate regardless of confidence

CA review queue (in-memory; production: Redis queue → CA review portal).
"""

import re
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

try:
    from hallucination_detector import check_answer
    HALLUCINATION_AVAILABLE = True
except ImportError:
    HALLUCINATION_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Thresholds
ESCALATE_THRESHOLD    = 0.50  # below → escalate to CA
DISCLAIMER_THRESHOLD  = 0.65  # below → add enhanced disclaimer
HIGH_CONFIDENCE       = 0.85  # above → minimal disclaimer

# Complexity signals that lower confidence
COMPLEXITY_KEYWORDS = {
    "high": [
        "notice", "scrutiny", "penalty", "prosecution", "144", "148", "263", "271",
        "revised return", "rectification", "search and seizure", "appeal",
        "tribunal", "high court", "itat", "compounding", "prosecution",
        "foreign income", "dtaa", "form 15ca", "form 15cb",
    ],
    "medium": [
        "carry forward", "set off", "loss adjustment", "indexation",
        "splitting income", "huf", "clubbing", "deemed income",
        "perquisite", "gratuity limit", "vrs exemption",
    ],
}

# Answer quality markers
QUALITY_MARKERS = {
    "positive": [
        r"section\s+\d",         # section references
        r"₹[\d,\.]+",            # rupee amounts
        r"\d+(?:\.\d+)?%",       # percentages
        r"fy\s*20\d{2}",         # fiscal year references
        r"form\s+\d+",           # form references
        r"schedule\s+\w+",       # schedule references
    ],
    "negative": [
        r"i don'?t know",
        r"i'?m not sure",
        r"cannot (provide|give|tell)",
        r"consult a (ca|tax|financial) (professional|advisor|expert)",
        r"beyond my (knowledge|scope|expertise)",
        r"this is not (tax|financial|legal) advice",
    ],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalSignals:
    """Signals from the RAG retrieval step."""
    top_similarity_score: float = 0.0   # cosine similarity of best chunk
    avg_similarity_score: float = 0.0   # avg across retrieved chunks
    num_chunks_retrieved: int   = 0
    chunk_diversity:      float = 0.0   # 1 - avg pairwise similarity (MMR proxy)
    has_exact_match:      bool  = False # any chunk contains exact query phrase

@dataclass
class ConfidenceResult:
    answer:           str
    query:            str
    category:         str
    confidence:       float
    components:       Dict[str, float]   # sub-scores per component
    escalate_to_ca:   bool
    add_disclaimer:   bool
    disclaimer_text:  str
    escalation_reason: Optional[str]
    hallucination:    Optional[Dict]
    processing_ms:    float


# ---------------------------------------------------------------------------
# CA Review Queue
# ---------------------------------------------------------------------------

_ca_review_queue: deque = deque(maxlen=500)  # ring buffer

def add_to_ca_queue(query: str, answer: str, reason: str, confidence: float):
    """Add a response to the CA review queue."""
    _ca_review_queue.appendleft({
        "id":         f"rev_{int(time.time() * 1000)}",
        "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query":      query,
        "answer":     answer[:500],  # truncate for queue storage
        "reason":     reason,
        "confidence": confidence,
        "status":     "pending",     # pending | approved | rejected | edited
    })

def get_ca_queue(limit: int = 50) -> List[Dict]:
    return list(_ca_review_queue)[:limit]


# ---------------------------------------------------------------------------
# Confidence Scorer
# ---------------------------------------------------------------------------

class ConfidenceScorer:

    def __init__(self):
        self._positive_patterns = [re.compile(p, re.IGNORECASE) for p in QUALITY_MARKERS["positive"]]
        self._negative_patterns = [re.compile(p, re.IGNORECASE) for p in QUALITY_MARKERS["negative"]]

    # ── Main entry point ─────────────────────────────────────────────────────

    def score(
        self,
        query:     str,
        answer:    str,
        category:  str = "general",
        retrieval: Optional[RetrievalSignals] = None,
        intent_confidence: float = 0.5,
    ) -> ConfidenceResult:
        start = time.time()

        components = {}

        # 1. Retrieval quality (0.0–1.0)
        components["retrieval"] = self._retrieval_score(retrieval)

        # 2. Intent confidence from DistilBERT
        components["intent"] = min(1.0, max(0.0, intent_confidence))

        # 3. Query complexity (lower confidence for complex queries)
        components["complexity_penalty"] = self._complexity_penalty(query, answer)

        # 4. Answer quality (structural completeness)
        components["answer_quality"] = self._answer_quality_score(answer)

        # 5. Answer length (very short = suspicious)
        components["length_score"] = self._length_score(answer)

        # 6. Hallucination check
        hall_result = None
        if HALLUCINATION_AVAILABLE:
            hall_result = check_answer(answer, category)
            components["hallucination_penalty"] = (
                -0.4 if hall_result["is_hallucination"] else 0.0
            )
        else:
            components["hallucination_penalty"] = 0.0

        # Weighted aggregate
        weights = {
            "retrieval":           0.30,
            "intent":              0.20,
            "answer_quality":      0.25,
            "length_score":        0.10,
            "complexity_penalty":  0.15,
        }
        base = sum(weights[k] * components[k] for k in weights)
        confidence = max(0.0, min(1.0, base + components["hallucination_penalty"]))

        # Escalation and disclaimer logic
        escalate     = False
        escalation_reason = None
        if hall_result and hall_result["is_hallucination"]:
            escalate = True
            escalation_reason = f"Hallucination detected (confidence {hall_result['confidence']:.2f}): {hall_result['explanation'][:200]}"
        elif confidence < ESCALATE_THRESHOLD:
            escalate = True
            escalation_reason = f"Low confidence score {confidence:.2f} — complex or uncertain query"

        if escalate:
            add_to_ca_queue(query, answer, escalation_reason or "hallucination", confidence)

        disclaimer = self._build_disclaimer(confidence, escalate, hall_result)

        return ConfidenceResult(
            answer           = answer,
            query            = query,
            category         = category,
            confidence       = round(confidence, 4),
            components       = {k: round(v, 4) for k, v in components.items()},
            escalate_to_ca   = escalate,
            add_disclaimer   = confidence < DISCLAIMER_THRESHOLD,
            disclaimer_text  = disclaimer,
            escalation_reason= escalation_reason,
            hallucination    = hall_result,
            processing_ms    = round((time.time() - start) * 1000, 2),
        )

    # ── Sub-scorers ──────────────────────────────────────────────────────────

    def _retrieval_score(self, retrieval: Optional[RetrievalSignals]) -> float:
        if retrieval is None:
            return 0.5   # unknown retrieval quality — neutral
        score = 0.0
        score += min(1.0, retrieval.top_similarity_score)         * 0.40
        score += min(1.0, retrieval.avg_similarity_score)         * 0.30
        score += min(1.0, retrieval.chunk_diversity)              * 0.15
        score += min(1.0, retrieval.num_chunks_retrieved / 4)     * 0.15
        return score

    def _complexity_penalty(self, query: str, answer: str) -> float:
        """Returns a multiplier 0.4–1.0 (lower for complex queries)."""
        combined = (query + " " + answer).lower()
        for kw in COMPLEXITY_KEYWORDS["high"]:
            if kw in combined:
                return 0.4
        for kw in COMPLEXITY_KEYWORDS["medium"]:
            if kw in combined:
                return 0.65
        return 1.0

    def _answer_quality_score(self, answer: str) -> float:
        """Check for structural quality markers."""
        positive = sum(1 for p in self._positive_patterns if p.search(answer))
        negative = sum(1 for p in self._negative_patterns if p.search(answer))
        # Positive markers increase quality; negative markers reduce it
        score = min(1.0, positive / max(2, len(self._positive_patterns) * 0.4))
        score -= min(0.5, negative * 0.15)
        return max(0.0, score)

    def _length_score(self, answer: str) -> float:
        """Penalise very short or very long answers."""
        tokens = len(answer.split())
        if tokens < 20:
            return 0.2
        elif tokens < 50:
            return 0.6
        elif tokens < 500:
            return 1.0
        else:
            return 0.8   # very long answers may be rambling

    def _build_disclaimer(self, confidence: float, escalate: bool, hall_result: Optional[Dict]) -> str:
        if escalate or (hall_result and hall_result.get("is_hallucination")):
            return (
                "⚠️ This answer has been flagged for human CA review. "
                "Please verify with a qualified Chartered Accountant before acting. "
                "Tax laws are subject to change — always check CBDT/GST Council notifications."
            )
        elif confidence < DISCLAIMER_THRESHOLD:
            return (
                "ℹ️ This answer involves complex tax considerations. "
                "For personalised advice, consult a qualified CA or tax professional. "
                "Information is based on FY 2024-25 rules — verify current applicability."
            )
        else:
            return (
                "This information is for general guidance only. "
                "Tax laws change; verify with official sources (incometax.gov.in, gst.gov.in)."
            )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_scorer: Optional[ConfidenceScorer] = None

def get_scorer() -> ConfidenceScorer:
    global _scorer
    if _scorer is None:
        _scorer = ConfidenceScorer()
    return _scorer


def score_answer(
    query:    str,
    answer:   str,
    category: str = "general",
    retrieval_scores: Optional[Dict] = None,
    intent_confidence: float = 0.5,
) -> Dict:
    """JSON-serialisable wrapper for Flask route integration."""
    scorer = get_scorer()
    signals = None
    if retrieval_scores:
        signals = RetrievalSignals(**retrieval_scores)

    result = scorer.score(query, answer, category, signals, intent_confidence)
    return {
        "confidence":       result.confidence,
        "escalate_to_ca":   result.escalate_to_ca,
        "add_disclaimer":   result.add_disclaimer,
        "disclaimer":       result.disclaimer_text,
        "escalation_reason": result.escalation_reason,
        "components":       result.components,
        "hallucination":    result.hallucination,
        "processing_ms":    result.processing_ms,
    }


if __name__ == "__main__":
    # Smoke test
    q  = "What is STCG tax rate on equity shares?"
    a1 = "Under Section 111A, Short-Term Capital Gains on equity shares and equity mutual funds are taxed at 20% (post-Budget 2024) if STT has been paid and shares are held for less than 12 months."
    a2 = "STCG on equity is 15%."  # wrong — should flag

    for ans in [a1, a2]:
        result = score_answer(q, ans, "capital_gains", intent_confidence=0.88)
        print(f"\nAnswer: {ans[:60]}...")
        print(f"Confidence: {result['confidence']} | Escalate: {result['escalate_to_ca']}")
        print(f"Disclaimer: {result['disclaimer']}")
