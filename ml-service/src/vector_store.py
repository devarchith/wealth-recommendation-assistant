"""
FAISS Vector Store
Builds, persists, and loads the FAISS index over the financial knowledge base.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from langchain.schema import Document
from langchain_community.vectorstores import FAISS

from embeddings import get_embeddings
from knowledge_base import load_knowledge_base

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.environ.get("FAISS_INDEX_PATH", "./faiss_index")


def build_vector_store(
    docs: Optional[List[Document]] = None,
    index_path: str = FAISS_INDEX_PATH,
    force_rebuild: bool = False,
) -> FAISS:
    """
    Build (or load from disk) the FAISS vector store.

    If a persisted index exists at `index_path` and `force_rebuild` is False,
    the index is loaded from disk (fast path). Otherwise, the full knowledge
    base is embedded and a new index is created and saved.

    Args:
        docs: Optional pre-built list of Documents. Defaults to load_knowledge_base().
        index_path: Directory for persisted FAISS index files.
        force_rebuild: If True, rebuilds the index even if one exists on disk.

    Returns:
        A LangChain FAISS vector store ready for similarity search.
    """
    index_dir = Path(index_path)
    index_file = index_dir / "index.faiss"

    embeddings = get_embeddings()

    # --- Fast path: load from disk ---
    if index_file.exists() and not force_rebuild:
        logger.info("Loading FAISS index from disk: %s", index_path)
        try:
            store = FAISS.load_local(
                index_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("FAISS index loaded (%d vectors)", store.index.ntotal)
            return store
        except Exception as exc:
            logger.warning(
                "Failed to load existing index (%s); rebuilding …", exc
            )

    # --- Slow path: embed documents and build index ---
    if docs is None:
        logger.info("Loading financial knowledge base …")
        docs = load_knowledge_base()

    logger.info("Building FAISS index from %d document chunks …", len(docs))
    store = FAISS.from_documents(docs, embeddings)

    # Persist to disk for subsequent fast loads
    index_dir.mkdir(parents=True, exist_ok=True)
    store.save_local(index_path)
    logger.info(
        "FAISS index built and saved to %s (%d vectors)",
        index_path, store.index.ntotal,
    )
    return store


def get_retriever(
    store: FAISS,
    k: int = 4,
    fetch_k: int = 20,
    lambda_mult: float = 0.7,
):
    """
    Return an MMR (Maximal Marginal Relevance) retriever from the vector store.

    MMR balances relevance and diversity in retrieved chunks:
    - Avoids returning near-duplicate passages
    - Produces richer context for the LLM
    - lambda_mult=0.7 weights relevance 70%, diversity 30%

    Args:
        store: Initialized FAISS vector store.
        k: Number of chunks to return per query.
        fetch_k: Candidate pool size before MMR re-ranking.
        lambda_mult: Relevance vs diversity balance (0=max diversity, 1=max relevance).
    """
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": fetch_k,
            "lambda_mult": lambda_mult,
        },
    )
