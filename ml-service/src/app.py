"""
WealthAdvisor AI - ML Service
Flask application entry point with health check and chat endpoints.
"""

import os
import logging
import time
from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["http://localhost:3001", "http://localhost:3000"])

# Lazy-load the RAG pipeline to avoid cold-start delays at import time
_rag_pipeline = None


def get_rag_pipeline():
    """Return (or initialize) the singleton RAG pipeline."""
    global _rag_pipeline
    if _rag_pipeline is None:
        logger.info("Initializing RAG pipeline on first request …")
        from rag import RAGPipeline  # noqa: PLC0415
        _rag_pipeline = RAGPipeline()
        logger.info("RAG pipeline ready.")
    return _rag_pipeline


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Lightweight liveness probe used by load balancers and Docker."""
    return jsonify(
        {
            "status": "ok",
            "service": "ml-service",
            "timestamp": time.time(),
            "version": "1.0.0",
        }
    )


@app.route("/ready", methods=["GET"])
def ready():
    """
    Readiness probe — checks whether the FAISS index and embeddings
    are loaded and the service can actually serve traffic.
    """
    try:
        pipeline = get_rag_pipeline()
        ready_flag = pipeline.is_ready()
        code = 200 if ready_flag else 503
        return jsonify({"ready": ready_flag}), code
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return jsonify({"ready": False, "error": str(exc)}), 503


# ---------------------------------------------------------------------------
# Chat endpoint (stubbed here; full implementation added in a later commit)
# ---------------------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    """
    POST /chat
    Body: { "message": str, "session_id": str }
    Returns: { "answer": str, "sources": list, "latency_ms": float }
    """
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    session_id = (body.get("session_id") or "default").strip()

    if not message:
        return jsonify({"error": "message is required"}), 400

    start = time.perf_counter()

    try:
        pipeline = get_rag_pipeline()
        result = pipeline.query(message, session_id=session_id)
    except Exception as exc:
        logger.error("Chat error for session %s: %s", session_id, exc)
        return jsonify({"error": "Internal error — please try again."}), 500

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return jsonify(
        {
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "latency_ms": latency_ms,
            "session_id": session_id,
        }
    )


# ---------------------------------------------------------------------------
# Feedback endpoint (records thumbs-up/down for satisfaction tracking)
# ---------------------------------------------------------------------------

@app.route("/feedback", methods=["POST"])
def feedback():
    """Record user feedback (contributes to the 33% satisfaction metric)."""
    body = request.get_json(silent=True) or {}
    rating = body.get("rating")  # "up" or "down"
    session_id = body.get("session_id", "unknown")
    message_id = body.get("message_id", "unknown")

    if rating not in ("up", "down"):
        return jsonify({"error": "rating must be 'up' or 'down'"}), 400

    logger.info(
        "Feedback received: session=%s message=%s rating=%s",
        session_id, message_id, rating,
    )
    # In production this would write to a metrics store (e.g. DynamoDB/Redis)
    return jsonify({"recorded": True})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("ML_SERVICE_PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info("Starting ML service on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
