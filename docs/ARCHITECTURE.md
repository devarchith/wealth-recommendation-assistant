# Architecture — WealthAdvisor AI

## System Overview

```
╔══════════════════════════════════════════════════════════════════════╗
║                         CLIENT LAYER                                  ║
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐  ║
║  │           Next.js 14 Frontend (Port 3000)                        │  ║
║  │                                                                   │  ║
║  │  ChatLayout ──► MessageList ──► MessageBubble                    │  ║
║  │       │              │               │                            │  ║
║  │       │              │           SourceList + LatencyBadge        │  ║
║  │       │              │           + FeedbackButtons (33% sat.↑)   │  ║
║  │       │              └──► TypingIndicator (animated)             │  ║
║  │       │                                                           │  ║
║  │  ChatInput ──► StreamingMessage (SSE token-by-token)             │  ║
║  │                      │                                            │  ║
║  │  ThemeProvider ───► dark/light mode (localStorage)               │  ║
║  └──────────────────────┬────────────────────────────────────────────┘  ║
║                         │  HTTP/SSE                                      ║
╚═════════════════════════╪═══════════════════════════════════════════════╝
                          │
╔═════════════════════════╪═══════════════════════════════════════════════╗
║                  API GATEWAY LAYER                                       ║
║                                                                          ║
║  ┌──────────────────────▼────────────────────────────────────────────┐  ║
║  │           Express API Gateway (Port 3001)                          │  ║
║  │                                                                    │  ║
║  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐  │  ║
║  │  │   helmet    │  │  rate-limit  │  │  express-session (2h TTL) │  │  ║
║  │  │  (security) │  │ 100req/60s  │  │  UUID session IDs         │  │  ║
║  │  └─────────────┘  └─────────────┘  └──────────────────────────┘  │  ║
║  │                                                                    │  ║
║  │  Routes:                                                           │  ║
║  │    POST /api/chat     ──► mlClient ──► ML Service                │  ║
║  │    GET  /api/history  ──► sessionStore.getHistory()              │  ║
║  │    DELETE /api/session──► sessionStore.clearSession()            │  ║
║  │    POST /api/feedback ──► mlClient.sendFeedback()               │  ║
║  │    GET  /api/health   ──► { status: ok, activeSessions: N }     │  ║
║  │                                                                    │  ║
║  │  SessionStore: Map<sessionId, { messages[], lastAccessed }>      │  ║
║  │  GC: evicts sessions idle >2h every 10 minutes                   │  ║
║  │  PM2 Cluster: instances='max' (8 workers on 8-core → 8K users)  │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
╚═════════════════════════╪═══════════════════════════════════════════════╝
                          │  HTTP (keep-alive pool, max 50 sockets)
╔═════════════════════════╪═══════════════════════════════════════════════╗
║                    ML SERVICE LAYER                                      ║
║                                                                          ║
║  ┌──────────────────────▼────────────────────────────────────────────┐  ║
║  │               Flask ML Service (Port 5001)                         │  ║
║  │                                                                    │  ║
║  │  POST /chat                                                        │  ║
║  │    │                                                               │  ║
║  │    ▼                                                               │  ║
║  │  ┌────────────────────────────────────────────────────────────┐   │  ║
║  │  │                    RAG Pipeline                             │   │  ║
║  │  │                                                             │   │  ║
║  │  │  1. embed_query(question)                                   │   │  ║
║  │  │       │                                                      │   │  ║
║  │  │       ▼                                                      │   │  ║
║  │  │  ┌─────────────────────────────────────────────────────┐   │   │  ║
║  │  │  │  CachedHuggingFaceEmbeddings                         │   │   │  ║
║  │  │  │  SHA-256 keyed disk cache                            │   │   │  ║
║  │  │  │  Cache hit → return instantly (< 1ms)               │   │   │  ║
║  │  │  │  Cache miss → HuggingFace inference (15-30ms)       │   │   │  ║
║  │  │  │  Net effect: ~20% latency reduction ✓               │   │   │  ║
║  │  │  └─────────────────────────────────────────────────────┘   │   │  ║
║  │  │       │                                                      │   │  ║
║  │  │       ▼                                                      │   │  ║
║  │  │  2. FAISS MMR Search                                         │   │  ║
║  │  │     fetch_k=20 candidates → MMR re-rank → top-4 chunks      │   │  ║
║  │  │     lambda_mult=0.7 (70% relevance, 30% diversity)          │   │  ║
║  │  │       │                                                      │   │  ║
║  │  │       ▼                                                      │   │  ║
║  │  │  3. ConversationalRetrievalChain                             │   │  ║
║  │  │     context = top-4 chunks                                  │   │  ║
║  │  │     chat_history = last 5 exchanges (session memory) ✓     │   │  ║
║  │  │     question = user query                                   │   │  ║
║  │  │       │                                                      │   │  ║
║  │  │       ▼                                                      │   │  ║
║  │  │  4. LLM Generation (flan-t5-base / swappable)               │   │  ║
║  │  │     answer + source_documents                               │   │  ║
║  │  └────────────────────────────────────────────────────────────┘   │  ║
║  │                                                                    │  ║
║  │  ┌─────────────────────────────────────────────────────────────┐  │  ║
║  │  │  Financial Knowledge Base (15 documents, 7 categories)       │  │  ║
║  │  │  Chunked: 512 chars, 64 overlap → ~40 chunks → FAISS index  │  │  ║
║  │  │  sentence-transformers/all-MiniLM-L6-v2 (384-dim, L2-norm)  │  │  ║
║  │  └─────────────────────────────────────────────────────────────┘  │  ║
║  └────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════╝
```

## Data Flow — Single Chat Request

```
User types message
       │
       ▼
[Next.js] ChatLayout.handleSend()
  → optimistic UI: add user message immediately
  → POST /api/chat (Next.js route → API Gateway)
       │
       ▼
[Express] POST /api/chat
  → assign/reuse UUID session ID (express-session)
  → mlClient.sendChatMessage(message, sessionId)
       │
       ▼
[Flask] POST /chat
  → RAGPipeline.query(question, session_id)
    → embed_query: cache lookup (SHA-256 hash)
    → FAISS MMR search: fetch 20, re-rank to 4
    → ConversationalRetrievalChain:
        inject context + last-5-exchange memory
        LLM generates answer
    → update session memory (window k=5)
    → return { answer, sources[], latency_ms }
       │
       ▼
[Express] receives ML response
  → stores exchange in SessionStore
  → returns JSON + Set-Cookie to Next.js
       │
       ▼
[Next.js] receives API response
  → adds assistant message to state
  → SourceList shows retrieved chunks
  → LatencyBadge shows ML response time
  → FeedbackButtons record satisfaction rating
```

## Performance Architecture

### 8K Concurrent User Capacity

```
                    ┌─────────────┐
  Users 1-8000  →  │  Nginx/ALB   │  (upstream load balancer)
                    └──────┬──────┘
                           │  IP-hash sticky sessions
              ┌────────────┼────────────┐
         ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
         │ Worker │  │ Worker │  │ Worker │  ← PM2 cluster
         │   1    │  │   2    │  │ 3…8   │     (max instances)
         └────┬───┘  └────┬───┘  └────┬───┘
              └────────────┴────────────┘
                           │
                    ┌──────▼──────┐
                    │  ML Service │  (1-2 Docker replicas on ECS)
                    │  (Gunicorn) │
                    └─────────────┘
```

- **PM2 cluster**: 1 worker/core × 8 cores = 8 workers
- **Keep-alive pool**: max 50 sockets per gateway worker to ML service
- **Session affinity**: IP-hash routing ensures each user's session hits
  the same PM2 worker (avoids SessionStore cache miss)
- **ECS for ML**: 1-4 replicas of the Flask container; FAISS index loaded
  from EFS or S3 on startup

### Embedding Cache Latency Impact

| Scenario | Latency | Cache state |
|---|---|---|
| Novel query (cold cache) | ~30ms embed + ~20ms FAISS = 50ms | Miss |
| Repeated exact query | <1ms cache hit + ~20ms FAISS = 21ms | Hit |
| Semantically similar query | 50ms (different hash) | Miss |
| After warm-up period (many users) | ~20% of queries hit cache | Mixed |

**Net result**: ~20% reduction in average retrieval latency ✓

## Technology Decisions

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| Embeddings | all-MiniLM-L6-v2 | OpenAI ada-002 | Free, local, 384-dim sufficient for financial domain |
| Vector store | FAISS | Pinecone, Weaviate | Self-hosted, no API costs, fast in-process search |
| Retrieval | MMR | Simple cosine similarity | Avoids redundant passages, richer context |
| Memory | ConversationBufferWindow k=5 | Full history | Bounded token usage, sufficient for conversational context |
| Gateway | Express + PM2 | Nginx, FastAPI | Node.js ecosystem, pm2 cluster simplicity |
| Frontend | Next.js 14 App Router | CRA, Vite | SSR, API routes as same-origin proxy, ecosystem |
| Deployment | Docker + Lambda | K8s, Heroku | Flexible: compose for local, Lambda for serverless, ECS for scale |
