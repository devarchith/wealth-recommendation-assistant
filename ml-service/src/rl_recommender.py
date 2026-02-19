"""
Reinforcement Learning Module — Adaptive Recommendation Engine
Implements a contextual multi-armed bandit (LinUCB) for dynamically
selecting the best recommendation strategy per user session.

Paper §3.5: "A reinforcement learning layer selects among competing
retrieval-and-response strategies based on historical feedback signals.
The bandit observes implicit (session length, follow-up rate) and explicit
(thumbs-up/down) rewards, converging to the optimal policy per user profile
within 5–10 interactions."

Architecture:
  State (context vector):
    - intent one-hot (budget, investment, tax, savings)
    - sentiment signals (anxiety, urgency, confidence, polarity)
    - session statistics (exchange count, prior avg feedback)

  Actions (recommendation strategies):
    A0 — retrieval_only:    pure FAISS MMR, no strategy adjustment
    A1 — intent_boosted:    re-rank chunks toward detected intent category
    A2 — sentiment_adapted: apply response_style preset from sentiment
    A3 — entity_focused:    prioritize chunks matching extracted entities
    A4 — full_pipeline:     A1 + A2 + A3 combined (highest overhead)

  Algorithm: LinUCB (linear upper confidence bound)
    - Maintains per-action ridge regression weight vectors
    - Exploration bonus: α * sqrt(x^T A^{-1} x) encourages under-tried actions
    - Updates on each explicit feedback signal (thumbs-up/down)
"""

from __future__ import annotations

import json
import logging
import math
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACTIONS = [
    "retrieval_only",
    "intent_boosted",
    "sentiment_adapted",
    "entity_focused",
    "full_pipeline",
]
N_ACTIONS = len(ACTIONS)

# Context feature dimension:
#   4 (intent one-hot) + 4 (anxiety/urgency/confidence/polarity) + 3 (session stats)
CONTEXT_DIM = 11

# LinUCB exploration parameter (higher = more exploration)
ALPHA = float(os.environ.get("RL_ALPHA", "0.5"))

# Path to persist bandit weights across restarts
WEIGHTS_PATH = os.environ.get("RL_WEIGHTS_PATH", "./rl_weights.pkl")


# ---------------------------------------------------------------------------
# Context vector builder
# ---------------------------------------------------------------------------

def build_context_vector(
    intent: str,
    anxiety_level: str,
    urgency_level: str,
    confidence_level: str,
    polarity: str,
    exchange_count: int,
    avg_feedback: float,   # -1 to 1: mean of thumbs ratings this session
) -> np.ndarray:
    """
    Encode the current interaction context as a fixed-length feature vector.

    Returns a (CONTEXT_DIM,) float64 numpy array.
    """
    # Intent one-hot: [budget, investment, tax, savings]
    intent_vec = np.zeros(4, dtype=np.float64)
    intent_idx = {"budget": 0, "investment": 1, "tax": 2, "savings": 3}
    intent_vec[intent_idx.get(intent, 0)] = 1.0

    # Sentiment signals
    anxiety_val = {"high": 1.0, "medium": 0.5, "low": 0.0}.get(anxiety_level, 0.0)
    urgency_val = {"high": 1.0, "medium": 0.5, "low": 0.0}.get(urgency_level, 0.0)
    conf_val = 1.0 if confidence_level == "high" else 0.0
    polarity_val = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}.get(polarity, 0.5)

    # Session statistics
    session_len = min(exchange_count / 10.0, 1.0)   # normalize to [0,1]
    avg_fb_norm = (avg_feedback + 1.0) / 2.0         # normalize [-1,1] → [0,1]

    return np.concatenate([
        intent_vec,
        [anxiety_val, urgency_val, conf_val, polarity_val],
        [session_len, avg_fb_norm, 1.0],              # 1.0 = bias term
    ])


# ---------------------------------------------------------------------------
# LinUCB bandit
# ---------------------------------------------------------------------------

@dataclass
class ActionStats:
    """Per-action ridge regression matrices."""
    A: np.ndarray = field(default_factory=lambda: np.eye(CONTEXT_DIM, dtype=np.float64))
    b: np.ndarray = field(default_factory=lambda: np.zeros(CONTEXT_DIM, dtype=np.float64))

    @property
    def theta(self) -> np.ndarray:
        """Ridge regression weight vector: A^{-1} b."""
        return np.linalg.solve(self.A, self.b)


class LinUCBBandit:
    """
    Linear Upper Confidence Bound bandit for strategy selection.

    For each request:
      1. Build context vector x from intent + sentiment + session stats
      2. Score each action: score_a = theta_a^T x + alpha * sqrt(x^T A_a^{-1} x)
      3. Select action with highest UCB score
      4. On feedback: update A_a += x x^T, b_a += reward * x
    """

    def __init__(self, alpha: float = ALPHA):
        self.alpha = alpha
        self._stats: List[ActionStats] = [ActionStats() for _ in range(N_ACTIONS)]
        self._total_selections = [0] * N_ACTIONS
        self._load()

    def _load(self) -> None:
        path = Path(WEIGHTS_PATH)
        if path.exists():
            try:
                with open(path, "rb") as fh:
                    data = pickle.load(fh)
                    self._stats = data["stats"]
                    self._total_selections = data["selections"]
                logger.info("LinUCB weights loaded from %s", WEIGHTS_PATH)
            except Exception as exc:
                logger.warning("Failed to load RL weights (%s); starting fresh.", exc)

    def _save(self) -> None:
        try:
            path = Path(WEIGHTS_PATH)
            with open(path, "wb") as fh:
                pickle.dump({
                    "stats": self._stats,
                    "selections": self._total_selections,
                }, fh)
        except Exception as exc:
            logger.warning("Failed to save RL weights: %s", exc)

    def select_action(self, context: np.ndarray) -> tuple[int, str, Dict[str, float]]:
        """
        Select the action with the highest UCB score.

        Returns:
            action_index, action_name, ucb_scores_dict
        """
        ucb_scores: Dict[str, float] = {}
        for i, stats in enumerate(self._stats):
            theta = stats.theta
            mean = float(theta @ context)
            A_inv = np.linalg.inv(stats.A)
            uncertainty = self.alpha * math.sqrt(float(context @ A_inv @ context))
            ucb_scores[ACTIONS[i]] = round(mean + uncertainty, 4)

        best_idx = max(range(N_ACTIONS), key=lambda i: ucb_scores[ACTIONS[i]])
        self._total_selections[best_idx] += 1
        return best_idx, ACTIONS[best_idx], ucb_scores

    def update(self, action_idx: int, context: np.ndarray, reward: float) -> None:
        """
        Update the bandit for action `action_idx` with observed reward.

        Args:
            action_idx: Index of the action that was taken.
            context: Context vector used when the action was selected.
            reward: Observed reward signal.
                    Explicit: thumbs-up = +1.0, thumbs-down = -1.0
                    Implicit: follow-up question = +0.3, session end = 0.0
        """
        stats = self._stats[action_idx]
        stats.A += np.outer(context, context)
        stats.b += reward * context
        self._save()
        logger.debug(
            "LinUCB updated: action=%s reward=%.2f total_selections=%s",
            ACTIONS[action_idx], reward, self._total_selections,
        )

    def get_stats(self) -> Dict:
        return {
            "actions": ACTIONS,
            "total_selections": self._total_selections,
            "alpha": self.alpha,
            "context_dim": CONTEXT_DIM,
        }


# ---------------------------------------------------------------------------
# Session-scoped RL state
# ---------------------------------------------------------------------------

@dataclass
class SessionRLState:
    """Tracks per-session RL context for feedback attribution."""
    session_id: str
    exchange_count: int = 0
    feedback_sum: float = 0.0
    feedback_count: int = 0
    last_action_idx: Optional[int] = None
    last_context: Optional[np.ndarray] = None

    @property
    def avg_feedback(self) -> float:
        return self.feedback_sum / self.feedback_count if self.feedback_count else 0.0


_session_rl_states: Dict[str, SessionRLState] = {}
_bandit: Optional[LinUCBBandit] = None


def get_bandit() -> LinUCBBandit:
    global _bandit
    if _bandit is None:
        _bandit = LinUCBBandit()
    return _bandit


def get_session_rl_state(session_id: str) -> SessionRLState:
    if session_id not in _session_rl_states:
        _session_rl_states[session_id] = SessionRLState(session_id=session_id)
    return _session_rl_states[session_id]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class StrategyResult:
    action: str
    action_idx: int
    ucb_scores: Dict[str, float]
    context_vector: List[float]


def select_strategy(
    session_id: str,
    intent: str,
    anxiety_level: str,
    urgency_level: str,
    confidence_level: str,
    polarity: str,
) -> StrategyResult:
    """
    Select the best recommendation strategy for the current interaction.

    Updates session exchange count and computes context vector using
    per-session feedback history for the avg_feedback feature.

    Args:
        session_id: Identifies the user session for state continuity.
        intent, anxiety_level, urgency_level, confidence_level, polarity:
            Outputs from intent_recognition and sentiment_analysis modules.

    Returns:
        StrategyResult with the selected action name and UCB diagnostics.
    """
    bandit = get_bandit()
    state = get_session_rl_state(session_id)
    state.exchange_count += 1

    context = build_context_vector(
        intent=intent,
        anxiety_level=anxiety_level,
        urgency_level=urgency_level,
        confidence_level=confidence_level,
        polarity=polarity,
        exchange_count=state.exchange_count,
        avg_feedback=state.avg_feedback,
    )

    action_idx, action_name, ucb_scores = bandit.select_action(context)

    # Store for feedback attribution
    state.last_action_idx = action_idx
    state.last_context = context

    logger.debug(
        "RL selected: session=%s action=%s ucb=%s",
        session_id, action_name, ucb_scores,
    )

    return StrategyResult(
        action=action_name,
        action_idx=action_idx,
        ucb_scores=ucb_scores,
        context_vector=context.tolist(),
    )


def record_feedback(session_id: str, rating: str) -> None:
    """
    Record explicit user feedback and update the bandit model.

    Args:
        session_id: Session that produced the rated response.
        rating: "up" (reward=+1.0) or "down" (reward=-1.0).
    """
    bandit = get_bandit()
    state = get_session_rl_state(session_id)

    if state.last_action_idx is None or state.last_context is None:
        logger.warning("No RL state to update for session %s", session_id)
        return

    reward = 1.0 if rating == "up" else -1.0
    state.feedback_sum += reward
    state.feedback_count += 1

    bandit.update(state.last_action_idx, state.last_context, reward)
    logger.info(
        "RL feedback: session=%s action=%s reward=%.1f avg_feedback=%.2f",
        session_id, ACTIONS[state.last_action_idx], reward, state.avg_feedback,
    )
