"""
Automated F1 Score Evaluation Pipeline
=======================================
Evaluates WealthAdvisor AI accuracy against the 500-question Indian tax benchmark.
Targets F1 ≥ 0.92 (as published in PCCDA 2025 paper).

Metrics computed:
  Token-level F1     — precision/recall of answer token overlap (normalized)
  Exact Match (EM)   — 1 if answer is exactly correct (normalised)
  Key-Fact Coverage  — % of ground-truth key_facts found in model answer
  BERTScore F1       — semantic similarity via sentence-transformer embeddings
  ROUGE-L            — longest common subsequence recall

Evaluation modes:
  --live   : call the running ML service (requires ML_SERVICE_URL)
  --offline: run against answer cache file (for CI/CD without GPU)
  --sample N: evaluate on N random questions (default: all 500)

Output:
  results/eval_YYYY-MM-DD_HHmm.json  — per-question results
  results/summary_YYYY-MM-DD_HHmm.json — aggregate metrics

Usage:
  python f1_eval_pipeline.py --live --sample 50
  python f1_eval_pipeline.py --offline --cache results/answers.json
"""

import json
import re
import os
import sys
import time
import argparse
import string
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import Counter

# ---------------------------------------------------------------------------
# Optional dependencies (graceful degradation)
# ---------------------------------------------------------------------------

try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _ST_MODEL = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    BERTSCORE_AVAILABLE = True
except ImportError:
    BERTSCORE_AVAILABLE = False
    print("[eval] sentence-transformers not installed. BERTScore will be skipped.", file=sys.stderr)

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Load benchmark
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))
from tax_qa_benchmark import BENCHMARK, get_random_sample

# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Lowercase, remove punctuation and extra whitespace."""
    text = text.lower().strip()
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text)
    return text


def tokenize(text: str) -> List[str]:
    return normalize(text).split()

# ---------------------------------------------------------------------------
# Token-level F1
# ---------------------------------------------------------------------------

def token_f1(prediction: str, ground_truth: str) -> Tuple[float, float, float]:
    """
    Compute token-level precision, recall, and F1.
    Standard SQuAD-style metric.
    """
    pred_tokens = Counter(tokenize(prediction))
    gold_tokens = Counter(tokenize(ground_truth))

    common    = sum((pred_tokens & gold_tokens).values())
    num_pred  = sum(pred_tokens.values())
    num_gold  = sum(gold_tokens.values())

    if num_pred == 0 or num_gold == 0:
        return (1.0, 1.0, 1.0) if num_pred == num_gold else (0.0, 0.0, 0.0)

    precision = common / num_pred
    recall    = common / num_gold
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


# ---------------------------------------------------------------------------
# Exact Match
# ---------------------------------------------------------------------------

def exact_match(prediction: str, ground_truth: str) -> float:
    return float(normalize(prediction) == normalize(ground_truth))


# ---------------------------------------------------------------------------
# Key-fact coverage
# ---------------------------------------------------------------------------

def key_fact_coverage(prediction: str, key_facts: List[str]) -> float:
    """
    Fraction of key_facts that appear (as substrings, normalized) in prediction.
    """
    if not key_facts:
        return 1.0
    pred_norm = normalize(prediction)
    hits = sum(1 for fact in key_facts if normalize(fact) in pred_norm)
    return hits / len(key_facts)


# ---------------------------------------------------------------------------
# ROUGE-L
# ---------------------------------------------------------------------------

def lcs_length(x: List[str], y: List[str]) -> int:
    m, n = len(x), len(y)
    dp   = [[0] * (n + 1) for _ in range(2)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if x[i - 1] == y[j - 1]:
                dp[i % 2][j] = dp[(i - 1) % 2][j - 1] + 1
            else:
                dp[i % 2][j] = max(dp[(i - 1) % 2][j], dp[i % 2][j - 1])
    return dp[m % 2][n]


def rouge_l(prediction: str, ground_truth: str) -> float:
    pred_tokens = tokenize(prediction)
    gold_tokens = tokenize(ground_truth)
    if not pred_tokens or not gold_tokens:
        return 0.0
    lcs   = lcs_length(pred_tokens, gold_tokens)
    prec  = lcs / len(pred_tokens)
    rec   = lcs / len(gold_tokens)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


# ---------------------------------------------------------------------------
# BERTScore (semantic similarity)
# ---------------------------------------------------------------------------

def bertscore_f1(prediction: str, ground_truth: str) -> float:
    if not BERTSCORE_AVAILABLE:
        return -1.0
    embeddings = _ST_MODEL.encode([prediction, ground_truth])
    sim = float(st_util.cos_sim(embeddings[0], embeddings[1]))
    return max(0.0, sim)  # cosine ∈ [-1, 1] → clamp to [0, 1]


# ---------------------------------------------------------------------------
# ML service query
# ---------------------------------------------------------------------------

def query_ml_service(question: str, ml_url: str, timeout: int = 30) -> Optional[str]:
    """POST a question to the live ML service and return the answer text."""
    payload = json.dumps({"message": question, "session_id": "eval_pipeline"}).encode()
    req     = urllib.request.Request(
        f"{ml_url}/chat",
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("answer") or data.get("response") or data.get("message", "")
    except Exception as err:
        print(f"[eval] ML service error: {err}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Evaluate single question
# ---------------------------------------------------------------------------

def evaluate_one(question: Dict, prediction: str) -> Dict:
    ground_truth = question["answer"]
    key_facts    = question.get("key_facts", [])

    p, r, f1     = token_f1(prediction, ground_truth)
    em           = exact_match(prediction, ground_truth)
    kfc          = key_fact_coverage(prediction, key_facts)
    rl           = rouge_l(prediction, ground_truth)
    bs           = bertscore_f1(prediction, ground_truth)

    return {
        "id":           question["id"],
        "category":     question["category"],
        "difficulty":   question["difficulty"],
        "question":     question["question"],
        "ground_truth": ground_truth,
        "prediction":   prediction,
        "metrics": {
            "token_precision": round(p,   4),
            "token_recall":    round(r,   4),
            "token_f1":        round(f1,  4),
            "exact_match":     round(em,  4),
            "key_fact_coverage": round(kfc, 4),
            "rouge_l":         round(rl,  4),
            "bertscore_f1":    round(bs,  4) if bs >= 0 else None,
        },
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def aggregate(results: List[Dict]) -> Dict:
    def avg(key, sub="metrics"):
        vals = [r[sub][key] for r in results if r[sub].get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    by_cat  = {}
    by_diff = {}
    for r in results:
        cat  = r["category"]
        diff = r["difficulty"]
        by_cat.setdefault(cat,  []).append(r["metrics"]["token_f1"])
        by_diff.setdefault(diff, []).append(r["metrics"]["token_f1"])

    return {
        "total_questions": len(results),
        "overall": {
            "token_f1":          avg("token_f1"),
            "token_precision":   avg("token_precision"),
            "token_recall":      avg("token_recall"),
            "exact_match":       avg("exact_match"),
            "key_fact_coverage": avg("key_fact_coverage"),
            "rouge_l":           avg("rouge_l"),
            "bertscore_f1":      avg("bertscore_f1"),
        },
        "target_f1":          0.92,
        "target_met":         avg("token_f1") >= 0.92,
        "by_category":  {k: round(sum(v) / len(v), 4) for k, v in by_cat.items()},
        "by_difficulty":{k: round(sum(v) / len(v), 4) for k, v in by_diff.items()},
    }


# ---------------------------------------------------------------------------
# Main evaluation runner
# ---------------------------------------------------------------------------

def run_evaluation(
    questions:    List[Dict],
    ml_url:       Optional[str],
    answer_cache: Optional[Dict] = None,
) -> List[Dict]:
    results = []
    for i, q in enumerate(questions):
        if answer_cache and q["id"] in answer_cache:
            prediction = answer_cache[q["id"]]
        elif ml_url:
            print(f"[eval] {i+1}/{len(questions)} Querying: {q['id']}")
            prediction = query_ml_service(q["question"], ml_url)
            if prediction is None:
                prediction = ""
            time.sleep(0.1)  # be kind to the service
        else:
            prediction = ""  # offline mode with no cache

        results.append(evaluate_one(q, prediction))
        if (i + 1) % 50 == 0:
            f1_so_far = sum(r["metrics"]["token_f1"] for r in results) / len(results)
            print(f"[eval] Progress {i+1}/{len(questions)} — running F1: {f1_so_far:.4f}")

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WealthAdvisor AI — Tax Benchmark Evaluation")
    parser.add_argument("--live",    action="store_true", help="Query live ML service")
    parser.add_argument("--offline", action="store_true", help="Use cached answers")
    parser.add_argument("--cache",   type=str, help="Path to answer cache JSON")
    parser.add_argument("--sample",  type=int, default=0, help="Number of questions to sample (0=all)")
    parser.add_argument("--ml-url",  type=str, default=os.environ.get("ML_SERVICE_URL", "http://localhost:5001"))
    parser.add_argument("--out-dir", type=str, default="results")
    args = parser.parse_args()

    questions = get_random_sample(args.sample) if args.sample > 0 else BENCHMARK
    print(f"[eval] Evaluating {len(questions)} questions")

    answer_cache = None
    if args.cache and Path(args.cache).exists():
        with open(args.cache) as f:
            answer_cache = json.load(f)

    ml_url = args.ml_url if args.live else None

    start   = time.time()
    results = run_evaluation(questions, ml_url, answer_cache)
    elapsed = time.time() - start

    summary = aggregate(results)
    summary["elapsed_seconds"] = round(elapsed, 2)
    summary["avg_latency_ms"]  = round((elapsed / len(results)) * 1000, 1) if results else 0

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"eval_{ts}.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (out / f"summary_{ts}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print("\n=== Evaluation Summary ===")
    print(json.dumps(summary["overall"], indent=2))
    print(f"\nTarget F1 ≥ 0.92: {'✓ MET' if summary['target_met'] else '✗ NOT MET'}")
    print(f"Results saved to: {out}/eval_{ts}.json")


if __name__ == "__main__":
    main()
