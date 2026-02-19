"""
RAG Pipeline
Full Retrieval-Augmented Generation pipeline combining FAISS retrieval,
LangChain ConversationalRetrievalChain, and session-scoped memory.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from embeddings import get_embeddings
from memory import get_memory, evict_stale_sessions
from vector_store import build_vector_store, get_retriever

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System / finance prompt
# ---------------------------------------------------------------------------

FINANCE_PROMPT = PromptTemplate(
    input_variables=["context", "chat_history", "question"],
    template="""You are WealthAdvisor AI, an expert financial assistant. You provide
clear, accurate, and actionable personal finance guidance based on the provided context.

Guidelines:
- Be concise but complete; use bullet points for lists
- Always cite relevant financial figures (percentages, limits, rules)
- If a question falls outside the provided context, say so honestly
- Never provide specific investment advice for individual securities
- Recommend consulting a licensed financial advisor for complex situations

Context from knowledge base:
{context}

Conversation history:
{chat_history}

User question: {question}

WealthAdvisor AI answer:""",
)

# ---------------------------------------------------------------------------
# RAG Pipeline class
# ---------------------------------------------------------------------------

LLM_MODEL = os.environ.get("LLM_MODEL", "google/flan-t5-base")


class RAGPipeline:
    """
    End-to-end RAG pipeline for the WealthAdvisor AI assistant.

    Initialization (lazy, on first request):
    1. Load / build FAISS vector store from the financial knowledge base
    2. Initialize HuggingFace LLM (flan-t5-base by default; swap for GPT-4
       by setting LLM_MODEL env var and providing an OpenAI key)
    3. Build ConversationalRetrievalChain with MMR retriever + memory

    Per-query:
    1. Embed the user question (cache-first via CachedHuggingFaceEmbeddings)
    2. MMR-retrieve top-k relevant chunks from FAISS
    3. Inject retrieved context + session chat history into the prompt
    4. Generate an answer with the LLM
    5. Update session memory with this exchange
    """

    def __init__(self):
        self._vector_store = None
        self._retriever = None
        self._llm = None
        self._ready = False
        self._initialize()

    def _initialize(self) -> None:
        try:
            logger.info("Building / loading FAISS vector store …")
            self._vector_store = build_vector_store()

            logger.info("Initializing MMR retriever …")
            self._retriever = get_retriever(self._vector_store)

            logger.info("Loading LLM: %s …", LLM_MODEL)
            self._llm = self._build_llm()

            self._ready = True
            logger.info("RAG pipeline ready.")
        except Exception as exc:
            logger.error("RAG pipeline initialization failed: %s", exc)
            self._ready = False
            raise

    def _build_llm(self):
        """
        Build a lightweight seq2seq LLM pipeline (flan-t5-base).
        In production, replace with an OpenAI or Anthropic client by
        switching LLM_MODEL and providing the appropriate API key.
        """
        tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
        model = AutoModelForSeq2SeqLM.from_pretrained(LLM_MODEL)
        hf_pipeline = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            temperature=0.3,
            do_sample=True,
        )
        return HuggingFacePipeline(pipeline=hf_pipeline)

    def is_ready(self) -> bool:
        return self._ready

    def _build_chain(self, session_id: str) -> ConversationalRetrievalChain:
        """Build a ConversationalRetrievalChain with session memory."""
        memory = get_memory(session_id)
        chain = ConversationalRetrievalChain.from_llm(
            llm=self._llm,
            retriever=self._retriever,
            memory=memory,
            combine_docs_chain_kwargs={"prompt": FINANCE_PROMPT},
            return_source_documents=True,
            verbose=False,
        )
        return chain

    def query(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Run a full RAG query for a given session.

        Args:
            question: The user's natural language financial question.
            session_id: Opaque string identifying the conversation session.
                        Memory is scoped per session_id (window of 5 exchanges).

        Returns:
            dict with keys:
              - answer (str): LLM-generated response
              - sources (list[dict]): retrieved document metadata
              - session_id (str)
        """
        if not self._ready:
            raise RuntimeError("RAG pipeline not initialized")

        # Periodically evict stale sessions (every ~100 queries is fine)
        import random
        if random.random() < 0.01:
            evict_stale_sessions()

        chain = self._build_chain(session_id)

        try:
            result = chain({"question": question})
        except Exception as exc:
            logger.error(
                "Chain invocation failed (session=%s): %s", session_id, exc
            )
            raise

        answer: str = result.get("answer", "I'm unable to answer that right now.")
        source_docs: List[Any] = result.get("source_documents", [])

        sources = [
            {
                "title": doc.metadata.get("title", "Unknown"),
                "category": doc.metadata.get("category", "general"),
                "source": doc.metadata.get("source", ""),
                "snippet": doc.page_content[:200] + "…"
                if len(doc.page_content) > 200
                else doc.page_content,
            }
            for doc in source_docs
        ]

        # Deduplicate sources by title
        seen_titles = set()
        unique_sources = []
        for s in sources:
            if s["title"] not in seen_titles:
                unique_sources.append(s)
                seen_titles.add(s["title"])

        return {
            "answer": answer,
            "sources": unique_sources,
            "session_id": session_id,
        }
