"""
Evaluation Metrics Module
Tracks and logs retrieval quality and end-to-end RAG pipeline performance
metrics as described in the PCCDA 2025 paper evaluation section (§5).

Metrics tracked (paper Table 4):
  Retrieval quality:
    Precision@k   — fraction of retrieved chunks that are relevant
    Recall@k      — fraction of relevant chunks that were retrieved
    F1@k          — harmonic mean of precision and recall (target: 0.92)
    MRR           — Mean Reciprocal Rank of first relevant result
    NDCG@k        — Normalized Discounted Cumulative Gain
    Hit Rate      — fraction of queries where top-1 result is relevant

  Response quality (LLM output):
    BLEU-1        — 1-gram overlap with reference answers
    ROUGE-L       — longest common subsequence-based overlap
    Faithfulness  — fraction of answer claims supported by retrieved context
    Answer Relevance — cosine similarity of answer to original question embedding

  Pipeline latency:
    embed_latency_ms   — embedding computation time
    retrieve_latency_ms — FAISS search time
    llm_latency_ms     — LLM generation time
    total_latency_ms   — end-to-end wall time

Metrics are stored in-memory (rolling window of 1000 evaluations) and
exported as JSON for monitoring dashboards or offline analysis.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

METRICS_LOG_PATH = "./evaluation_metrics.jsonl"
ROLLING_WINDOW = 1000   # Keep last N evaluation records in memory


# ---------------------------------------------------------------------------
# Per-query evaluation record
# ---------------------------------------------------------------------------

@dataclass
class RetrievalEvaluation:
    """Ground-truth relevance labels + retrieval scores for one query."""
    query: str
    retrieved_titles: List[str]         # titles of returned chunks (ordered)
    relevant_titles: List[str]          # ground-truth relevant chunk titles
    k: int = 4

    @property
    def precision_at_k(self) -> float:
        if not self.retrieved_titles:
            return 0.0
        hits = sum(1 for t in self.retrieved_titles[:self.k] if t in self.relevant_titles)
        return round(hits / self.k, 4)

    @property
    def recall_at_k(self) -> float:
        if not self.relevant_titles:
            return 0.0
        hits = sum(1 for t in self.retrieved_titles[:self.k] if t in self.relevant_titles)
        return round(hits / len(self.relevant_titles), 4)

    @property
    def f1_at_k(self) -> float:
        p = self.precision_at_k
        r = self.recall_at_k
        if p + r == 0:
            return 0.0
        return round(2 * p * r / (p + r), 4)

    @property
    def reciprocal_rank(self) -> float:
        for i, title in enumerate(self.retrieved_titles):
            if title in self.relevant_titles:
                return round(1.0 / (i + 1), 4)
        return 0.0

    @property
    def ndcg_at_k(self) -> float:
        """NDCG@k with binary relevance (1 if relevant, 0 if not)."""
        dcg = 0.0
        for i, title in enumerate(self.retrieved_titles[:self.k]):
            rel = 1 if title in self.relevant_titles else 0
            dcg += rel / math.log2(i + 2)  # i+2 because log2(1)=0

        # Ideal DCG: all relevant docs first
        ideal_k = min(len(self.relevant_titles), self.k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))
        return round(dcg / idcg, 4) if idcg > 0 else 0.0

    @property
    def hit_rate(self) -> float:
        """1 if the top retrieved chunk is relevant, else 0."""
        if not self.retrieved_titles:
            return 0.0
        return 1.0 if self.retrieved_titles[0] in self.relevant_titles else 0.0


@dataclass
class ResponseEvaluation:
    """LLM response quality metrics for one query-answer pair."""
    query: str
    answer: str
    reference_answer: Optional[str] = None    # if available
    context_chunks: List[str] = field(default_factory=list)

    bleu_1: float = 0.0
    rouge_l: float = 0.0
    faithfulness: float = 0.0     # % of answer sentences supported by context
    answer_relevance: float = 0.0  # cosine sim of answer embedding to query emb


@dataclass
class LatencyRecord:
    embed_ms: float
    retrieve_ms: float
    llm_ms: float
    total_ms: float
    intent: str = ""
    session_id: str = ""
    cached_embedding: bool = False


@dataclass
class EvaluationRecord:
    timestamp: float
    query: str
    session_id: str
    intent: str
    retrieval: Optional[RetrievalEvaluation] = None
    response: Optional[ResponseEvaluation] = None
    latency: Optional[LatencyRecord] = None


# ---------------------------------------------------------------------------
# Simple ROUGE-L and BLEU-1 implementations (no external deps)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def _bleu_1(hypothesis: str, reference: str) -> float:
    hyp = _tokenize(hypothesis)
    ref_set = set(_tokenize(reference))
    if not hyp:
        return 0.0
    hits = sum(1 for w in hyp if w in ref_set)
    return round(hits / len(hyp), 4)


def _lcs_length(a: List[str], b: List[str]) -> int:
    """Compute LCS length using space-efficient DP."""
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    for i in range(m):
        curr = [0] * (n + 1)
        for j in range(n):
            if a[i] == b[j]:
                curr[j + 1] = prev[j] + 1
            else:
                curr[j + 1] = max(curr[j], prev[j + 1])
        prev = curr
    return prev[n]


def _rouge_l(hypothesis: str, reference: str) -> float:
    hyp = _tokenize(hypothesis)
    ref = _tokenize(reference)
    if not hyp or not ref:
        return 0.0
    lcs = _lcs_length(hyp, ref)
    precision = lcs / len(hyp)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _faithfulness(answer: str, context_chunks: List[str]) -> float:
    """
    Approximate faithfulness: fraction of answer sentences that have
    at least one overlapping 3-gram with the retrieved context.
    """
    sentences = [s.strip() for s in answer.split('.') if s.strip()]
    if not sentences:
        return 0.0
    context = " ".join(context_chunks).lower()
    context_tokens = _tokenize(context)
    context_trigrams = set(
        tuple(context_tokens[i:i+3]) for i in range(len(context_tokens) - 2)
    )
    supported = 0
    for sent in sentences:
        tokens = _tokenize(sent)
        sent_trigrams = {tuple(tokens[i:i+3]) for i in range(len(tokens) - 2)}
        if sent_trigrams & context_trigrams:
            supported += 1
    return round(supported / len(sentences), 4)


# ---------------------------------------------------------------------------
# Metrics store
# ---------------------------------------------------------------------------

class MetricsStore:
    """
    In-memory rolling window store for evaluation records.
    Exports aggregate statistics for monitoring dashboards.
    """

    def __init__(self, window: int = ROLLING_WINDOW, log_path: str = METRICS_LOG_PATH):
        self._records: Deque[EvaluationRecord] = deque(maxlen=window)
        self._log_path = log_path
        self._total_queries = 0

    def record(
        self,
        query: str,
        session_id: str,
        intent: str,
        retrieved_titles: List[str],
        relevant_titles: List[str],
        answer: str,
        context_chunks: List[str],
        latency: LatencyRecord,
        reference_answer: Optional[str] = None,
    ) -> EvaluationRecord:
        """
        Create and store a full evaluation record for one query-answer pair.
        Computes all metrics automatically.
        """
        retrieval_eval = RetrievalEvaluation(
            query=query,
            retrieved_titles=retrieved_titles,
            relevant_titles=relevant_titles,
        )

        response_eval = ResponseEvaluation(
            query=query,
            answer=answer,
            reference_answer=reference_answer,
            context_chunks=context_chunks,
        )
        if reference_answer:
            response_eval.bleu_1 = _bleu_1(answer, reference_answer)
            response_eval.rouge_l = _rouge_l(answer, reference_answer)
        response_eval.faithfulness = _faithfulness(answer, context_chunks)

        record = EvaluationRecord(
            timestamp=time.time(),
            query=query,
            session_id=session_id,
            intent=intent,
            retrieval=retrieval_eval,
            response=response_eval,
            latency=latency,
        )

        self._records.append(record)
        self._total_queries += 1
        self._append_to_log(record)

        logger.debug(
            "Eval recorded: intent=%s P@4=%.3f R@4=%.3f F1=%.3f faith=%.3f latency=%.0fms",
            intent,
            retrieval_eval.precision_at_k,
            retrieval_eval.recall_at_k,
            retrieval_eval.f1_at_k,
            response_eval.faithfulness,
            latency.total_ms,
        )
        return record

    def _append_to_log(self, record: EvaluationRecord) -> None:
        try:
            with open(self._log_path, "a") as fh:
                fh.write(json.dumps({
                    "timestamp": record.timestamp,
                    "session_id": record.session_id,
                    "intent": record.intent,
                    "p@4": record.retrieval.precision_at_k if record.retrieval else None,
                    "r@4": record.retrieval.recall_at_k if record.retrieval else None,
                    "f1@4": record.retrieval.f1_at_k if record.retrieval else None,
                    "mrr": record.retrieval.reciprocal_rank if record.retrieval else None,
                    "ndcg@4": record.retrieval.ndcg_at_k if record.retrieval else None,
                    "hit_rate": record.retrieval.hit_rate if record.retrieval else None,
                    "bleu_1": record.response.bleu_1 if record.response else None,
                    "rouge_l": record.response.rouge_l if record.response else None,
                    "faithfulness": record.response.faithfulness if record.response else None,
                    "embed_ms": record.latency.embed_ms if record.latency else None,
                    "retrieve_ms": record.latency.retrieve_ms if record.latency else None,
                    "llm_ms": record.latency.llm_ms if record.latency else None,
                    "total_ms": record.latency.total_ms if record.latency else None,
                    "cached_embedding": record.latency.cached_embedding if record.latency else None,
                }) + "\n")
        except Exception as exc:
            logger.warning("Failed to write metrics log: %s", exc)

    def aggregate(self) -> Dict:
        """
        Return aggregate statistics over the rolling window.
        These are the metrics reported in paper Table 4.
        """
        if not self._records:
            return {"total_queries": 0}

        retrieval_records = [r for r in self._records if r.retrieval]
        response_records  = [r for r in self._records if r.response]
        latency_records   = [r for r in self._records if r.latency]

        def avg(values: List[float]) -> float:
            return round(sum(values) / len(values), 4) if values else 0.0

        p_vals = [r.retrieval.precision_at_k for r in retrieval_records]
        r_vals = [r.retrieval.recall_at_k    for r in retrieval_records]
        f1_vals = [r.retrieval.f1_at_k       for r in retrieval_records]
        mrr_vals = [r.retrieval.reciprocal_rank for r in retrieval_records]
        ndcg_vals = [r.retrieval.ndcg_at_k   for r in retrieval_records]
        hit_vals = [r.retrieval.hit_rate      for r in retrieval_records]

        faith_vals = [r.response.faithfulness for r in response_records]

        embed_vals    = [r.latency.embed_ms    for r in latency_records]
        retrieve_vals = [r.latency.retrieve_ms for r in latency_records]
        llm_vals      = [r.latency.llm_ms      for r in latency_records]
        total_vals    = [r.latency.total_ms    for r in latency_records]
        cached_count  = sum(1 for r in latency_records if r.latency.cached_embedding)

        intent_dist: Dict[str, int] = {}
        for r in self._records:
            intent_dist[r.intent] = intent_dist.get(r.intent, 0) + 1

        return {
            "total_queries": self._total_queries,
            "window_size": len(self._records),
            "retrieval": {
                "precision_at_4":   avg(p_vals),
                "recall_at_4":      avg(r_vals),
                "f1_at_4":          avg(f1_vals),    # target: 0.92 (paper §5.2)
                "mrr":              avg(mrr_vals),
                "ndcg_at_4":        avg(ndcg_vals),
                "hit_rate":         avg(hit_vals),
                "sample_count":     len(retrieval_records),
            },
            "response": {
                "faithfulness":     avg(faith_vals),
                "sample_count":     len(response_records),
            },
            "latency_ms": {
                "embed_avg":        avg(embed_vals),
                "retrieve_avg":     avg(retrieve_vals),
                "llm_avg":          avg(llm_vals),
                "total_avg":        avg(total_vals),  # target: ≤800ms (paper §5.1)
                "cached_embedding_count": cached_count,
                "cache_hit_rate":   round(cached_count / len(latency_records), 4) if latency_records else 0,
            },
            "intent_distribution": intent_dist,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_metrics_store: Optional[MetricsStore] = None


def get_metrics_store() -> MetricsStore:
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = MetricsStore()
    return _metrics_store
