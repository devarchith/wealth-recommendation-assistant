# WealthAdvisor AI — Conversational Finance Assistant

> An AI-powered personal finance advisor with BERT-based intent recognition, financial NER, FinBERT sentiment analysis, LinUCB reinforcement learning, a production-grade RAG pipeline, and a multi-tab interactive UI — built to match the research published at PCCDA 2025.

**Author:** Devarchith Parashara Batchu
**GitHub:** [@devarchith](https://github.com/devarchith)

---

## Published Research

> **"Wealth Recommendation Conversational Finance Assistant using NLP, Transformers, and LangChain"**
> *Proceedings of the International Conference on Pervasive Computing and Communication in the Digital Age (PCCDA 2025)*
> **Author:** Devarchith Parashara Batchu

### Abstract

Personal financial management remains inaccessible to millions of individuals due to the complexity of financial terminology, the cost of professional advisory services, and the lack of personalized, context-aware guidance. This paper presents **WealthAdvisor AI**, a conversational finance assistant that combines Retrieval-Augmented Generation (RAG) with a multi-stage NLP pipeline — including BERT-based intent recognition, transformer-powered financial Named Entity Recognition (NER), FinBERT sentiment analysis, and a contextual multi-armed bandit reinforcement learning layer — to deliver personalized, factually grounded financial advice in real time. The system achieves **F1@4 = 0.92** on the four-intent financial query benchmark, reduces retrieval latency by **20%** through an embedding cache layer, serves up to **8,000 concurrent users** at **0.8s average response time** under PM2 cluster mode, and improves measured user satisfaction by **33%** through feedback-driven RL adaptation and a multi-tab interactive dashboard covering budgeting, investment portfolio construction, and tax deadline management.

---

## Internal Benchmarks (Paper Table 4)

> **Note:** All figures below are **internal benchmarks** measured on held-out test datasets described in the paper (PCCDA 2025). They reflect system performance under controlled evaluation conditions and are **not guarantees** of accuracy or performance on arbitrary real-world queries.

| Metric | Benchmark Value | Evaluation Method |
|---|---|---|
| F1@4 retrieval score | **0.92** | Precision@4 × Recall@4 harmonic mean on held-out query set |
| Precision@4 | **0.91** | Relevant chunks / k=4 retrieved (MMR) |
| Recall@4 | **0.93** | Relevant retrieved / total relevant |
| MRR | **0.87** | Mean Reciprocal Rank |
| NDCG@4 | **0.89** | Normalized Discounted Cumulative Gain |
| Faithfulness | **0.88** | 3-gram overlap: answer vs context |
| Retrieval latency reduction | **20%** | SHA-256 disk embedding cache (repeated queries) |
| Conversational memory window | **5 exchanges** | `ConversationBufferWindowMemory(k=5)` |
| Concurrent user capacity | **8,000** | PM2 cluster, 1 worker/CPU core (load test) |
| Average response time | **0.8s** | Keep-alive proxy + cached embeddings (load test) |
| User satisfaction improvement | **33%** | LinUCB RL + feedback buttons (A/B test, n=120) |
| Intent classification accuracy | **94.2%** | DistilBERT zero-shot + keyword prior (test set) |
| NER entity coverage | **7 types** | STOCK, CRYPTO, TAX_TERM, ACCOUNT, AMOUNT, TIME_PERIOD, FUND |

---

## Architecture (Paper Figure 2)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          CLIENT LAYER (Port 3000)                            ║
║                                                                               ║
║  ┌──────────────────────────────────────────────────────────────────────┐    ║
║  │                    Next.js 14 Frontend                                │    ║
║  │                                                                       │    ║
║  │  ┌──────┐  ┌──────────────────────┐  ┌───────────┐  ┌──────────┐   │    ║
║  │  │ Chat │  │ Budget (50/30/20 +   │  │ Invest    │  │ Tax      │   │    ║
║  │  │  AI  │  │ real-time alerts)    │  │ (risk     │  │ (bracket │   │    ║
║  │  │      │  │                      │  │ profiles) │  │ calc +   │   │    ║
║  │  │Strm. │  │ 9 category tracker   │  │ 3 risk    │  │ deadline │   │    ║
║  │  │SSE   │  │ Spending alert pings │  │ presets   │  │ reminders│   │    ║
║  │  │Srcs. │  │ Income input live    │  │ ETF recs  │  │ 8 events │   │    ║
║  │  │Latcy.│  │                      │  │ DCA/TLH   │  │          │   │    ║
║  │  │Fdbk. │  │                      │  │           │  │          │   │    ║
║  │  └──────┘  └──────────────────────┘  └───────────┘  └──────────┘   │    ║
║  └──────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                   │ HTTP / SSE
╔══════════════════════════════════╪═════════════════════════════════════════╗
║              API GATEWAY (Port 3001) — Express + PM2 Cluster                ║
║  Rate Limit 100/min · CORS · express-session · SessionStore GC             ║
║  Keep-alive pool (50 sockets) · 8K users @ 0.8s · Zero-downtime reload    ║
╚══════════════════════════════════╪═════════════════════════════════════════╝
                                   │ HTTP proxy
╔══════════════════════════════════╪═════════════════════════════════════════╗
║                ML SERVICE (Port 5001) — Flask + LangChain                   ║
║                                                                              ║
║   User Query                                                                 ║
║       │                                                                      ║
║       ├──► [1] BERT Intent Recognition (DistilBERT zero-shot)               ║
║       │         budget | investment | tax | savings  (94.2% accuracy)       ║
║       │                                                                      ║
║       ├──► [2] Financial NER (spaCy EntityRuler + regex gazetteer)          ║
║       │         STOCK · CRYPTO · TAX_TERM · ACCOUNT · AMOUNT ·             ║
║       │         TIME_PERIOD · FUND                                          ║
║       │                                                                      ║
║       ├──► [3] FinBERT Sentiment Analysis                                   ║
║       │         polarity · anxiety · urgency · confidence                   ║
║       │         → response_style preset (5 styles)                          ║
║       │                                                                      ║
║       ├──► [4] LinUCB RL Strategy Selection                                 ║
║       │         context(11-dim) → UCB scores → action:                      ║
║       │         retrieval_only | intent_boosted | sentiment_adapted |        ║
║       │         entity_focused | full_pipeline                              ║
║       │                                                                      ║
║       └──► [5] RAG Pipeline (ConversationalRetrievalChain)                  ║
║                 │                                                            ║
║                 ├─ CachedHuggingFaceEmbeddings (20% latency↓)              ║
║                 ├─ FAISS MMR (fetch_k=20 → top-4, λ=0.7)                  ║
║                 ├─ ConversationBufferWindowMemory (k=5 exchanges)           ║
║                 └─ LLM generation → answer + sources                        ║
║                                                                              ║
║   [6] Evaluation Metrics Logger                                              ║
║       Precision@4 · Recall@4 · F1@4(0.92) · MRR · NDCG@4                  ║
║       BLEU-1 · ROUGE-L · Faithfulness · Latency breakdown                  ║
║       → JSONL log + GET /metrics endpoint                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## NLP Pipeline (Paper §3)

### §3.2 — BERT Intent Recognition
- **Model**: DistilBERT zero-shot classification (`distilbert-base-uncased`)
- **Classes**: `budget` | `investment` | `tax` | `savings`
- **Score fusion**: 80% BERT + 20% keyword-prior smoothing
- **Accuracy**: 94.2% on held-out financial query test set
- **Fallback**: keyword-only scoring when model unavailable

### §3.3 — Financial NER (7 Entity Types)
| Entity Type | Examples |
|---|---|
| `STOCK` | AAPL, Tesla, NVDA, JPMorgan |
| `CRYPTO` | BTC, ETH, Bitcoin, Ethereum |
| `TAX_TERM` | W-2, 1099, capital gains, AMT, AGI |
| `ACCOUNT` | 401(k), Roth IRA, HSA, 529 |
| `FUND` | VTI, VOO, SPY, VTSAX, QQQ |
| `AMOUNT` | $5,000, 10%, $500/month |
| `TIME_PERIOD` | April 15, Q1 2024, FY2024 |

- **Primary**: spaCy EntityRuler with injected gazetteer patterns
- **Fallback**: regex + curated gazetteer (no spaCy dep)

### §3.4 — FinBERT Sentiment Analysis
- **Model**: `ProsusAI/finbert` (BERT fine-tuned on financial text)
- **Dimensions**: polarity × anxiety × urgency × confidence
- **Response styles**: `reassure_and_educate` | `concise_expert` | `urgent_action` | `encouraging` | `balanced`
- **Impact**: 12% satisfaction improvement from tone personalization (paper §5.3)

### §3.5 — LinUCB Reinforcement Learning
- **Algorithm**: Contextual multi-armed bandit (Linear Upper Confidence Bound)
- **Context**: 11-dim vector (intent 4-hot + sentiment signals + session stats)
- **Actions**: 5 retrieval/response strategies
- **Reward**: explicit thumbs-up/down + implicit follow-up signals
- **Convergence**: optimal policy per user profile within 5–10 interactions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| API Gateway | Node.js, Express, PM2 cluster mode |
| ML Service | Python 3.11, Flask, LangChain, FAISS |
| Intent Recognition | DistilBERT zero-shot classification |
| NER | spaCy EntityRuler + regex gazetteer |
| Sentiment | ProsusAI/FinBERT |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Retrieval | FAISS + Maximal Marginal Relevance (MMR) |
| RL Layer | LinUCB contextual bandit (numpy) |
| Containers | Docker, Docker Compose |
| Serverless | AWS Lambda (WSGI), Serverless Framework |

---

## Features

### ML / RAG Pipeline (Paper §3)
- BERT intent classification → 4 financial intents at 94.2% accuracy
- 7-type financial NER → enriched retrieval context
- FinBERT sentiment → 5 response style presets
- LinUCB RL → adaptive strategy selection, converges in 5–10 turns
- FAISS vector index + MMR retrieval (fetch_k=20, k=4, λ=0.7)
- Embedding cache: 20% latency reduction on repeated/similar queries
- 5-exchange conversational memory per session

### Frontend (Paper §4)
- **AI Chat tab**: streaming SSE responses, source attribution, latency badge, feedback buttons
- **Budget tab**: 50/30/20 allocation, 9 spending categories, real-time alerts (warning/critical)
- **Investment tab**: 3 risk profiles, dynamic allocation bar, age/horizon inputs, ETF recommendations
- **Tax tab**: 2024 bracket estimator, 8 filing deadlines with live countdown, pulsing urgency alerts

### Infrastructure
- Docker Compose: health-check gated startup order, persistent FAISS/cache volumes
- PM2 cluster: `instances='max'` → 8K concurrent users, zero-downtime rolling reload
- AWS Lambda: custom WSGI adapter + serverless.yml, no external dependencies

---

## Quick Start

```bash
git clone https://github.com/devarchith/wealth-recommendation-assistant.git
cd wealth-recommendation-assistant
cp .env.example .env
docker-compose up --build
```

| Service | URL | First-run note |
|---|---|---|
| Frontend | http://localhost:3000 | Starts after gateway health check |
| API Gateway | http://localhost:3001 | Starts after ML service health check |
| ML Service | http://localhost:5001 | ~90s first run (model downloads) |

**Individual services:** See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#quick-start)

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | RAG query → answer + sources + latency |
| `GET` | `/api/history` | Conversation history for session |
| `DELETE` | `/api/session` | Clear session and conversation |
| `POST` | `/api/feedback` | Thumbs-up/down → LinUCB reward signal |
| `GET` | `/api/health` | Gateway liveness + active session count |
| `GET` | `/health` | ML service liveness |
| `GET` | `/metrics` | Aggregate evaluation metrics (P, R, F1, latency) |

Full docs: [docs/API.md](docs/API.md)

---

## Evaluation (Paper §5)

```
GET http://localhost:5001/metrics
```

```json
{
  "retrieval": {
    "precision_at_4": 0.91,
    "recall_at_4": 0.93,
    "f1_at_4": 0.92,
    "mrr": 0.87,
    "ndcg_at_4": 0.89,
    "hit_rate": 0.94
  },
  "response": {
    "faithfulness": 0.88
  },
  "latency_ms": {
    "embed_avg": 22.4,
    "retrieve_avg": 18.1,
    "llm_avg": 680.0,
    "total_avg": 720.5,
    "cache_hit_rate": 0.21
  }
}
```

---

## Project Structure

```
wealth-recommendation-assistant/
├── ml-service/src/
│   ├── app.py                  # Flask + /health /ready /chat /feedback /metrics
│   ├── rag.py                  # ConversationalRetrievalChain orchestration
│   ├── intent_recognition.py   # DistilBERT zero-shot intent classifier (§3.2)
│   ├── ner_extractor.py        # 7-type financial NER (§3.3)
│   ├── sentiment_analysis.py   # FinBERT + response style presets (§3.4)
│   ├── rl_recommender.py       # LinUCB contextual bandit (§3.5)
│   ├── evaluation_metrics.py   # P@4, R@4, F1@4, MRR, NDCG, faithfulness (§5)
│   ├── vector_store.py         # FAISS build/load + MMR retriever
│   ├── embeddings.py           # CachedHuggingFaceEmbeddings (20% latency↓)
│   ├── memory.py               # Per-session ConversationBufferWindowMemory
│   └── knowledge_base.py       # 15 financial docs + RecursiveCharacterTextSplitter
│
├── api-gateway/src/
│   ├── server.js               # Express + helmet + session + PM2 cluster
│   ├── routes/chat.js          # /api/chat /api/history /api/session /api/feedback
│   ├── middleware/             # cors.js · rateLimiter.js · errorHandler.js
│   └── services/               # mlClient.js · sessionStore.js
│
├── frontend/src/
│   ├── app/                    # Next.js App Router + same-origin API proxies
│   ├── components/
│   │   ├── tabs/
│   │   │   ├── TabBar.tsx      # 4-tab navigation (Chat | Budget | Invest | Tax)
│   │   │   ├── BudgetTab.tsx   # 50/30/20 tracker + real-time spending alerts
│   │   │   ├── InvestmentTab.tsx # Risk profiles + ETF allocations + DCA/TLH
│   │   │   └── TaxTab.tsx      # 2024 brackets + 8 deadline reminders
│   │   ├── ChatLayout.tsx · MessageList.tsx · MessageBubble.tsx
│   │   ├── StreamingMessage.tsx · SourceList.tsx · LatencyBadge.tsx
│   │   ├── FeedbackButtons.tsx · TypingIndicator.tsx · Header.tsx
│   │   └── ThemeProvider.tsx · EmptyState.tsx
│   └── lib/apiClient.ts · streamingClient.ts
│
├── infrastructure/aws/
│   ├── lambda_handler.py       # WSGI adapter for Lambda
│   └── serverless.yml          # Serverless Framework config
├── docs/ARCHITECTURE.md · docs/API.md
├── docker-compose.yml
└── .env.example
```

---

## India Market Focus

WealthAdvisor AI is purpose-built for the Indian financial ecosystem:

| Domain | Coverage |
|---|---|
| **Income Tax** | New vs Old regime comparison, ITR-1/2/3/4 guidance, deduction optimizer (80C/80D/HRA), TDS Form 26AS reconciliation |
| **Capital Gains** | Post-Budget 2024 rates — STCG 111A @20%, LTCG 112A @12.5% (₹1.25L exempt), debt MF rules |
| **Advance Tax** | Quarterly schedule (Jun/Sep/Dec/Mar), Sec 234B/234C interest calculator |
| **GST** | GSTR-1/GSTR-3B filing assistant, HSN/SAC rate lookup, ITC reconciliation, late fee calculator |
| **Payroll** | EPF (12%+12%), ESIC (0.75%+3.25%), salary TDS Sec 192, CTC breakdown |
| **Gold Shop** | 3% GST + 5% making charges, TCS 206C(1F) >₹2L, hallmarking |
| **Real Estate** | Stamp duty (6 states), TDS 194IA >₹50L, GST on under-construction |
| **Freelancers** | Sec 44ADA presumptive (50%), foreign remittance Form 15CA/15CB, DTAA rates |
| **CA Tools** | Multi-client dashboard, bulk ITR, tax notice templates (143/148/271), document vault |
| **Language** | English + Telugu bilingual (UI + WhatsApp bot) |

---

## Pricing Plans

### Plan Comparison

| Feature | Free | Individual ₹499/mo | Business ₹1,499/mo | CA Professional ₹3,999/mo |
|---|:---:|:---:|:---:|:---:|
| AI Chat queries | 10/day | 100/day | 500/day | Unlimited |
| US Tax calculator | ✅ | ✅ | ✅ | ✅ |
| Budget planner | ✅ | ✅ | ✅ | ✅ |
| India Tax dashboard (ITR + TDS) | ❌ | ✅ | ✅ | ✅ |
| Capital gains calculator | ❌ | ✅ | ✅ | ✅ |
| Deduction optimizer (80C/80D/HRA) | ❌ | ✅ | ✅ | ✅ |
| WhatsApp bot (EN + Telugu) | ❌ | ✅ | ✅ | ✅ |
| PDF export | ❌ | ✅ | ✅ | ✅ |
| GST Filing Assistant (GSTR-1/3B) | ❌ | ❌ | ✅ | ✅ |
| Payroll module (PF + ESI + TDS) | ❌ | ❌ | ✅ | ✅ |
| Inventory management | ❌ | ❌ | ✅ | ✅ |
| P&L + Balance Sheet generator | ❌ | ❌ | ✅ | ✅ |
| CA Client Management (100 clients) | ❌ | ❌ | ❌ | ✅ |
| Bulk ITR generation workflow | ❌ | ❌ | ❌ | ✅ |
| Tax Notice Response Templates | ❌ | ❌ | ❌ | ✅ |
| Document Vault (encrypted) | ❌ | ❌ | ❌ | ✅ |
| Audit Trail Logging | ❌ | ❌ | ❌ | ✅ |
| REST API access | ❌ | ❌ | ❌ | ✅ |
| Support | Community | Email | Priority Email | Dedicated Phone |
| Annual billing (save ~20%) | — | ₹4,788/yr | ₹14,388/yr | ₹38,388/yr |

### Razorpay Integration

Payments are processed via Razorpay. Configure your credentials in `.env`:

```env
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=your_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
RAZORPAY_PLAN_INDIVIDUAL=plan_individual_499
RAZORPAY_PLAN_BUSINESS=plan_business_1499
RAZORPAY_PLAN_CA=plan_ca_3999
```

Payment flow: `POST /api/billing/create-order` → Razorpay checkout → `POST /api/billing/verify` (HMAC SHA256 signature check) → plan activated.

### Authentication

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Phone OTP (MSG91)
MSG91_AUTH_KEY=your_msg91_key
MSG91_TEMPLATE_ID=your_template_id

# Session
SESSION_SECRET=your_strong_random_secret
APP_URL=https://yourdomain.com
```

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/google` | GET | Initiate Google OAuth 2.0 |
| `/api/auth/google/callback` | GET | OAuth callback — creates session |
| `/api/auth/otp/send` | POST | Send 6-digit OTP to Indian mobile |
| `/api/auth/otp/verify` | POST | Verify OTP — creates session |
| `/api/auth/me` | GET | Current authenticated user |
| `/api/auth/logout` | POST | Destroy session |

---

## Legal Disclaimer

> **WealthAdvisor AI is for educational and informational purposes only.**

- This system is **not** a registered Investment Advisor under SEBI (Investment Advisers) Regulations, 2013.
- This system is **not** a Chartered Accountant under the Institute of Chartered Accountants of India (ICAI).
- Responses generated by the AI **do not constitute** professional tax advice, financial planning advice, legal advice, or any form of regulated financial services.
- **Always consult a qualified CA, SEBI-registered Investment Adviser, or licensed financial planner** before making investment, tax, or financial decisions.
- All benchmark figures (F1@4, latency, satisfaction improvement, etc.) are **internal measurements on controlled test datasets**. They are not guarantees of real-world performance on your specific queries.
- The system operates under India's **Digital Personal Data Protection (DPDP) Act 2023** for data handling.

---

## Privacy Reset

Users can selectively overwrite their data with anonymised placeholders via the **Data Privacy Center** (Settings → Privacy tab), exercising their right to erasure under DPDP Act 2023 Sec 13. The reset is in-place — your account and login remain intact.

API: `POST /api/privacy/reset` — see [docs/API.md](docs/API.md) for schema.

---

## License

MIT © Devarchith Parashara Batchu
