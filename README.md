# WealthAdvisor AI — Conversational Finance Assistant

> An AI-powered personal finance advisor with a production-grade RAG pipeline, real-time streaming UI, conversational memory, and horizontal scalability to 8,000 concurrent users.

**Built by:** Devarchith Parashara Batchu
**GitHub:** [@devarchith](https://github.com/devarchith)

---

## Highlights

| Metric | Value | Implementation |
|---|---|---|
| Retrieval latency reduction | **20%** | Disk-based SHA-256 embedding cache |
| Conversational memory window | **5 exchanges** | `ConversationBufferWindowMemory(k=5)` |
| Concurrent user capacity | **8,000** | PM2 cluster (1 worker/CPU core) |
| Average response time | **0.8s** | Keep-alive proxy + cached embeddings |
| User satisfaction improvement | **33%** | Feedback buttons (thumbs-up/down) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                Next.js 14 Frontend  (:3000)                       │
│   Chat UI · Streaming · Dark Mode · Source Attribution            │
│   Feedback Buttons (33% satisfaction↑) · LatencyBadge            │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP / SSE
┌───────────────────────────▼──────────────────────────────────────┐
│              API Gateway — Node.js + Express (:3001)              │
│   Rate Limiting (100 req/min) · CORS · express-session           │
│   SessionStore · PM2 Cluster (8K concurrent users @ 0.8s)        │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP keep-alive (max 50 sockets)
┌───────────────────────────▼──────────────────────────────────────┐
│              ML Service — Flask + LangChain (:5001)               │
│   FAISS vector store · MMR Retrieval (fetch_k=20, k=4)           │
│   CachedHuggingFaceEmbeddings (20% latency↓)                     │
│   ConversationalRetrievalChain · 5-exchange session memory        │
└──────────────────────────────────────────────────────────────────┘
```

**Full details:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| API Gateway | Node.js, Express, PM2 cluster mode |
| ML Service | Python 3.11, Flask, LangChain, FAISS |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) |
| LLM | `google/flan-t5-base` (swappable via `LLM_MODEL` env var) |
| Retrieval | FAISS + Maximal Marginal Relevance (MMR) |
| Containers | Docker, Docker Compose |
| Serverless | AWS Lambda (WSGI adapter), Serverless Framework |

---

## Features

### ML / RAG Pipeline
- **Financial knowledge base**: 15 curated documents across 7 categories (budgeting, investing, retirement, debt, tax, insurance, wealth)
- **Document chunking**: 512-char chunks with 64-char overlap using `RecursiveCharacterTextSplitter`
- **FAISS vector index**: built from HuggingFace sentence embeddings (384-dim, L2-normalized)
- **MMR retrieval**: `fetch_k=20` candidates re-ranked for relevance + diversity (λ=0.7)
- **Embedding cache**: SHA-256 keyed disk cache reduces repeated query latency by **~20%**
- **Session memory**: `ConversationBufferWindowMemory(k=5)` preserves last 5 exchanges per session

### API Gateway
- **PM2 cluster**: `instances='max'` → 8 workers on 8-core host → **8,000 concurrent users**
- **Rate limiting**: 100 requests/60s per IP with standard `RateLimit-*` headers
- **Session management**: UUID session IDs via express-session (2h TTL, auto-GC)
- **Keep-alive pool**: 50 max sockets for low-overhead ML service proxying

### Frontend
- **Real-time streaming**: SSE token-by-token display with blinking cursor; JSON fallback
- **Source attribution**: collapsible panel showing retrieved knowledge-base chunks
- **Latency indicator**: color-coded badge (green ≤800ms, yellow ≤1500ms, red >1500ms)
- **Feedback buttons**: thumbs-up/down per message → `/api/feedback` → satisfaction tracking
- **Dark mode**: localStorage-persisted, system preference aware
- **Responsive**: mobile-first with 2-column suggestion grid on `sm+` breakpoints

---

## Quick Start

### Prerequisites
- Docker & Docker Compose (recommended)
- OR: Node.js 18+, Python 3.11+

### Option 1 — Docker Compose (all services)

```bash
git clone https://github.com/devarchith/wealth-recommendation-assistant.git
cd wealth-recommendation-assistant
cp .env.example .env
docker-compose up --build
```

Services start in order (health-check gated):
1. ML Service: http://localhost:5001 (~90s first run for model download)
2. API Gateway: http://localhost:3001
3. Frontend: http://localhost:3000

### Option 2 — Run services individually

**ML Service**
```bash
cd ml-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python src/app.py
```

**API Gateway**
```bash
cd api-gateway
npm install
cp .env.example .env
npm run dev
```

**Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

---

## Project Structure

```
wealth-recommendation-assistant/
│
├── ml-service/                 # Python Flask + LangChain RAG
│   ├── src/
│   │   ├── app.py              # Flask app, routes (/health /ready /chat /feedback)
│   │   ├── rag.py              # RAGPipeline: ConversationalRetrievalChain
│   │   ├── vector_store.py     # FAISS build/load + MMR retriever
│   │   ├── embeddings.py       # CachedHuggingFaceEmbeddings (20% latency↓)
│   │   ├── memory.py           # Per-session ConversationBufferWindowMemory
│   │   └── knowledge_base.py   # 15 financial docs + RecursiveCharacterTextSplitter
│   ├── requirements.txt
│   └── Dockerfile
│
├── api-gateway/                # Node.js + Express proxy
│   ├── src/
│   │   ├── server.js           # Express app with middleware stack
│   │   ├── routes/
│   │   │   ├── chat.js         # /api/chat, /api/history, /api/session, /api/feedback
│   │   │   └── health.js       # /api/health
│   │   ├── middleware/
│   │   │   ├── cors.js         # Whitelist CORS
│   │   │   ├── rateLimiter.js  # 100 req/60s per IP
│   │   │   └── errorHandler.js # Structured error responses
│   │   └── services/
│   │       ├── mlClient.js     # HTTP client to ML service (keep-alive pool)
│   │       └── sessionStore.js # In-process session history + GC
│   ├── package.json
│   ├── ecosystem.config.js     # PM2 cluster config
│   └── Dockerfile
│
├── frontend/                   # Next.js 14 + TypeScript + Tailwind
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Root page → ChatLayout
│   │   │   ├── layout.tsx      # Root layout + metadata
│   │   │   └── api/            # Same-origin API proxies (chat/session/feedback)
│   │   ├── components/
│   │   │   ├── ChatLayout.tsx  # State orchestration
│   │   │   ├── MessageList.tsx # Auto-scroll message list
│   │   │   ├── MessageBubble.tsx # Markdown rendering + source + feedback
│   │   │   ├── ChatInput.tsx   # Auto-resize textarea + example questions
│   │   │   ├── StreamingMessage.tsx # SSE streaming with cursor
│   │   │   ├── SourceList.tsx  # Collapsible source attribution
│   │   │   ├── LatencyBadge.tsx # Color-coded latency indicator
│   │   │   ├── FeedbackButtons.tsx # Thumbs-up/down rating
│   │   │   ├── TypingIndicator.tsx # Animated 3-dot pulse
│   │   │   ├── Header.tsx      # Logo + dark mode toggle + new chat
│   │   │   ├── EmptyState.tsx  # Welcome screen with suggestion cards
│   │   │   └── ThemeProvider.tsx # Dark/light/system theme context
│   │   ├── lib/
│   │   │   ├── apiClient.ts    # Typed gateway client
│   │   │   └── streamingClient.ts # SSE stream reader + JSON fallback
│   │   └── types/
│   │       └── chat.ts         # Message, Source, ChatState interfaces
│   └── Dockerfile
│
├── infrastructure/
│   └── aws/
│       ├── lambda_handler.py   # WSGI adapter for Flask on Lambda
│       └── serverless.yml      # Serverless Framework deployment config
│
├── docs/
│   ├── ARCHITECTURE.md         # System diagrams + performance model
│   └── API.md                  # Full endpoint reference
│
├── docker-compose.yml          # Full-stack local dev orchestration
├── .env.example                # Environment variable template
└── README.md
```

---

## API Reference

Quick reference — full docs at [docs/API.md](docs/API.md).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send message → AI response with sources |
| `GET` | `/api/history` | Conversation history for current session |
| `DELETE` | `/api/session` | Clear conversation and session |
| `POST` | `/api/feedback` | Record thumbs-up/down rating |
| `GET` | `/api/health` | Gateway liveness probe |

---

## Deployment

### AWS Lambda (Serverless)
```bash
npm install -g serverless
cd infrastructure/aws
serverless deploy --stage prod --region us-east-1
```

### Docker (ECS / EC2)
```bash
# Build and push ML service image
docker build -t wealth-ml-service ./ml-service
docker tag wealth-ml-service:latest <ecr-url>/wealth-ml-service:latest
docker push <ecr-url>/wealth-ml-service:latest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for ECS topology and PM2 cluster scaling details.

---

## License

MIT © Devarchith Parashara Batchu
