"""
RLHF Pipeline — Thumbs-Up/Down Weekly Retraining
=================================================
Implements a Reinforcement Learning from Human Feedback (RLHF) pipeline
that uses thumbs-up/down signals from users and CA reviewers to improve
the RAG retrieval and response ranking over time.

Components:
  1. FeedbackCollector  — collects raw thumbs-up/down + CA corrections
  2. RewardModel        — converts feedback to scalar rewards
  3. LinUCBUpdater      — updates LinUCB bandit weights from rewards
  4. RetrievalFeedback  — reranks FAISS results based on historical feedback
  5. WeeklyReport       — produces retraining summary + metrics delta

Pipeline flow (runs weekly via scheduler or POST /ml/rlhf/trigger):
  1. Load feedback collected since last run
  2. Compute rewards for each (query, answer, action) triple
  3. Update LinUCB arm weights (written to rl_weights.json)
  4. Update retrieval preference scores (written to retrieval_prefs.json)
  5. Emit weekly report with improvement metrics

Reward function:
  thumbs_up   →  +1.0
  thumbs_down →  -0.5
  ca_approved →  +1.5  (expert positive signal, higher weight)
  ca_rejected →  -1.0  (expert negative, original answer)
  ca_corrected → +1.5  (expert positive for corrected answer)
"""

import json
import os
import time
import hashlib
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEIGHTS_FILE      = Path(os.environ.get("RL_WEIGHTS_FILE",     "rl_weights.json"))
PREFS_FILE        = Path(os.environ.get("RETRIEVAL_PREFS_FILE", "retrieval_prefs.json"))
FEEDBACK_FILE     = Path(os.environ.get("FEEDBACK_FILE",        "feedback_store.jsonl"))
REPORTS_DIR       = Path(os.environ.get("REPORTS_DIR",          "rlhf_reports"))

ALPHA    = 1.0   # LinUCB exploration parameter
GAMMA    = 0.9   # reward discount for older feedback
MIN_SAMPLES_PER_ARM = 5  # minimum before arm weight update


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class SignalType(str, Enum):
    THUMBS_UP    = "thumbs_up"
    THUMBS_DOWN  = "thumbs_down"
    CA_APPROVED  = "ca_approved"
    CA_REJECTED  = "ca_rejected"
    CA_CORRECTED = "ca_corrected"

REWARD_MAP = {
    SignalType.THUMBS_UP:    1.0,
    SignalType.THUMBS_DOWN: -0.5,
    SignalType.CA_APPROVED:  1.5,
    SignalType.CA_REJECTED: -1.0,
    SignalType.CA_CORRECTED: 1.5,
}

@dataclass
class FeedbackRecord:
    id:           str
    ts:           float
    session_id:   str
    query:        str
    answer:       str
    action:       str           # LinUCB arm name
    intent:       str           # budget | investment | tax | savings
    signal:       SignalType
    reward:       float = 0.0
    user_id:      Optional[str] = None
    reviewer_id:  Optional[str] = None
    correction:   Optional[str] = None

@dataclass
class ArmStats:
    arm:          str
    n_samples:    int   = 0
    total_reward: float = 0.0
    avg_reward:   float = 0.0
    A:            List[List[float]] = field(default_factory=lambda: [[1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                                                      [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                                                      [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                                                                      [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
                                                                      [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
                                                                      [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
                                                                      [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
                                                                      [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                                                      [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
                                                                      [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
                                                                      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]])
    b:            List[float]  = field(default_factory=lambda: [0.0] * 11)


# ---------------------------------------------------------------------------
# Feedback Collector
# ---------------------------------------------------------------------------

class FeedbackCollector:
    """Persists user and CA feedback to JSONL file for batch processing."""

    def __init__(self, feedback_file: Path = FEEDBACK_FILE):
        self._file = feedback_file
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        session_id: str,
        query:      str,
        answer:     str,
        action:     str,
        intent:     str,
        signal:     SignalType,
        user_id:    Optional[str] = None,
        reviewer_id: Optional[str] = None,
        correction: Optional[str] = None,
    ) -> FeedbackRecord:
        record = FeedbackRecord(
            id          = hashlib.sha256(f"{session_id}{query}{time.time()}".encode()).hexdigest()[:16],
            ts          = time.time(),
            session_id  = session_id,
            query       = query,
            answer      = answer[:500],
            action      = action,
            intent      = intent,
            signal      = signal,
            reward      = REWARD_MAP[signal],
            user_id     = user_id,
            reviewer_id = reviewer_id,
            correction  = correction,
        )
        with self._file.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        return record

    def load_since(self, since_ts: float) -> List[FeedbackRecord]:
        if not self._file.exists():
            return []
        records = []
        with self._file.open() as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d["ts"] >= since_ts:
                        d["signal"] = SignalType(d["signal"])
                        records.append(FeedbackRecord(**d))
                except Exception:
                    continue
        return records

    def load_all(self) -> List[FeedbackRecord]:
        return self.load_since(0.0)


# ---------------------------------------------------------------------------
# Reward Model — applies discount and expert weighting
# ---------------------------------------------------------------------------

class RewardModel:
    def compute(self, record: FeedbackRecord, now: float) -> float:
        base  = record.reward
        age_s = max(0, now - record.ts)
        age_w = max(1, age_s / (7 * 24 * 3600))   # weeks since event
        discount = GAMMA ** (age_w - 1)
        return base * discount


# ---------------------------------------------------------------------------
# LinUCB Updater
# ---------------------------------------------------------------------------

class LinUCBUpdater:
    """
    Updates LinUCB arm parameters from a batch of feedback records.
    Reads/writes arm state from JSON file for persistence across runs.
    """

    ARMS = [
        "retrieval_only",
        "intent_boosted",
        "sentiment_adapted",
        "entity_focused",
        "full_pipeline",
    ]

    def __init__(self, weights_file: Path = WEIGHTS_FILE):
        self._file = weights_file
        self._arms = self._load()

    def _load(self) -> Dict[str, ArmStats]:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                return {k: ArmStats(**v) for k, v in data.items()}
            except Exception:
                pass
        return {arm: ArmStats(arm=arm) for arm in self.ARMS}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(
            {k: asdict(v) for k, v in self._arms.items()}, indent=2
        ))

    def update(self, records: List[FeedbackRecord], reward_model: RewardModel) -> Dict:
        now = time.time()
        updates = defaultdict(lambda: {"n": 0, "reward_sum": 0.0})

        for rec in records:
            if rec.action not in self._arms:
                continue
            reward = reward_model.compute(rec, now)
            updates[rec.action]["n"]          += 1
            updates[rec.action]["reward_sum"] += reward

        # Update arm stats (simplified — production: full matrix update with context)
        changes = {}
        for arm_name, data in updates.items():
            arm = self._arms[arm_name]
            old_avg = arm.avg_reward
            arm.n_samples    += data["n"]
            arm.total_reward += data["reward_sum"]
            arm.avg_reward    = arm.total_reward / max(1, arm.n_samples)
            changes[arm_name] = {
                "n_new":      data["n"],
                "avg_before": round(old_avg, 4),
                "avg_after":  round(arm.avg_reward, 4),
                "delta":      round(arm.avg_reward - old_avg, 4),
            }

        self._save()
        return changes

    def get_rankings(self) -> List[Dict]:
        return sorted(
            [{"arm": k, "avg_reward": round(v.avg_reward, 4), "n_samples": v.n_samples}
             for k, v in self._arms.items()],
            key=lambda x: x["avg_reward"],
            reverse=True,
        )


# ---------------------------------------------------------------------------
# Retrieval Preference Updater
# ---------------------------------------------------------------------------

class RetrievalFeedback:
    """Tracks which knowledge-base chunks received positive/negative feedback."""

    def __init__(self, prefs_file: Path = PREFS_FILE):
        self._file  = prefs_file
        self._prefs = self._load()

    def _load(self) -> Dict[str, Dict]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self._prefs, indent=2))

    def update(self, records: List[FeedbackRecord]):
        for rec in records:
            key = hashlib.md5(rec.query.lower().encode()).hexdigest()
            entry = self._prefs.setdefault(key, {
                "query_hash": key,
                "positive":   0,
                "negative":   0,
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            if rec.reward > 0:
                entry["positive"] += 1
            else:
                entry["negative"] += 1
            entry["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save()

    def preference_score(self, query: str) -> float:
        """Returns 0.0–1.0 preference score for a query's previous feedback."""
        key   = hashlib.md5(query.lower().encode()).hexdigest()
        entry = self._prefs.get(key)
        if not entry:
            return 0.5  # neutral default
        total = entry["positive"] + entry["negative"]
        if total == 0:
            return 0.5
        return entry["positive"] / total


# ---------------------------------------------------------------------------
# Weekly RLHF Run
# ---------------------------------------------------------------------------

class RLHFPipeline:

    def __init__(self):
        self._collector  = FeedbackCollector()
        self._reward     = RewardModel()
        self._linucb     = LinUCBUpdater()
        self._retrieval  = RetrievalFeedback()
        self._last_run   = 0.0

    def run(self, since_ts: Optional[float] = None) -> Dict:
        if since_ts is None:
            # Default: last 7 days
            since_ts = time.time() - 7 * 24 * 3600

        print(f"[RLHF] Loading feedback since {time.strftime('%Y-%m-%d', time.gmtime(since_ts))}")
        records = self._collector.load_since(since_ts)
        print(f"[RLHF] Loaded {len(records)} feedback records")

        if not records:
            return {"status": "no_new_feedback", "records": 0}

        # Compute rewards and update models
        arm_changes = self._linucb.update(records, self._reward)
        self._retrieval.update(records)
        self._last_run = time.time()

        # Build report
        signal_counts = defaultdict(int)
        intent_rewards = defaultdict(list)
        for r in records:
            signal_counts[r.signal.value] += 1
            reward = self._reward.compute(r, time.time())
            intent_rewards[r.intent].append(reward)

        avg_reward_by_intent = {
            intent: round(statistics.mean(rewards), 4)
            for intent, rewards in intent_rewards.items()
        }

        report = {
            "run_at":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "period_start":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since_ts)),
            "records_processed": len(records),
            "signal_breakdown": dict(signal_counts),
            "avg_reward_by_intent": avg_reward_by_intent,
            "arm_updates": arm_changes,
            "top_arm_ranking": self._linucb.get_rankings(),
            "status": "success",
        }

        # Persist report
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"rlhf_{int(self._last_run)}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"[RLHF] Report saved: {report_path}")
        return report

    def record_feedback(self, session_id, query, answer, action, intent, signal_str, **kwargs):
        """Convenience method for Flask route."""
        signal = SignalType(signal_str)
        return self._collector.record(session_id, query, answer, action, intent, signal, **kwargs)

    def get_preference_score(self, query: str) -> float:
        return self._retrieval.preference_score(query)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_pipeline: Optional[RLHFPipeline] = None

def get_pipeline() -> RLHFPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RLHFPipeline()
    return _pipeline


# ---------------------------------------------------------------------------
# Flask API wrapper
# ---------------------------------------------------------------------------

def rlhf_feedback(data: Dict) -> Dict:
    """Called from /feedback endpoint after thumbs-up/down."""
    pipeline = get_pipeline()
    try:
        rec = pipeline.record_feedback(
            session_id  = data.get("session_id", "anon"),
            query       = data.get("query", ""),
            answer      = data.get("answer", ""),
            action      = data.get("action", "full_pipeline"),
            intent      = data.get("intent", "general"),
            signal_str  = data.get("signal", "thumbs_up"),
            user_id     = data.get("user_id"),
        )
        return {"recorded": True, "id": rec.id, "reward": rec.reward}
    except Exception as e:
        return {"recorded": False, "error": str(e)}


def rlhf_run_weekly() -> Dict:
    """Called by scheduler or POST /ml/rlhf/trigger."""
    return get_pipeline().run()


if __name__ == "__main__":
    # Test the pipeline
    pipe = RLHFPipeline()

    # Simulate some feedback
    signals = [
        ("session_1", "What is STCG rate?", "20% u/s 111A", "full_pipeline", "tax", "thumbs_up"),
        ("session_2", "What is LTCG rate?", "It's 10%",     "intent_boosted",  "tax", "thumbs_down"),
        ("session_3", "How to file GSTR?",  "File on 20th", "retrieval_only",  "gst", "ca_approved"),
    ]
    for args in signals:
        pipe.record_feedback(*args)

    report = pipe.run()
    print(json.dumps(report, indent=2))
