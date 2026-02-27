# API Documentation — WealthAdvisor AI

## Base URLs

| Environment | API Gateway | ML Service |
|---|---|---|
| Local (Docker) | `http://localhost:3001` | `http://localhost:5001` |
| Local (bare) | `http://localhost:3001` | `http://localhost:5001` |
| Production | `https://api.your-domain.com` | Internal (not exposed) |

> **Note**: The frontend communicates with the API Gateway only.
> The ML Service is internal and should not be exposed publicly in production.

---

## API Gateway Endpoints

### POST /api/chat

Send a user message and receive an AI-generated financial answer.

**Request**
```json
POST /api/chat
Content-Type: application/json

{
  "message": "What is the 50/30/20 budgeting rule?"
}
```

**Response** `200 OK`
```json
{
  "answer": "The 50/30/20 rule is a budgeting framework...",
  "sources": [
    {
      "title": "50/30/20 Budgeting Rule",
      "category": "budgeting",
      "source": "knowledge_base/budgeting/50/30/20 Budgeting Rule",
      "snippet": "The 50/30/20 rule is a simple budgeting framework..."
    }
  ],
  "latency_ms": 342.5,
  "gateway_latency_ms": 350,
  "session_id": "a1b2c3d4-...",
  "message_id": "e5f6g7h8-..."
}
```

**Error Responses**

| Status | Code | Description |
|--------|------|-------------|
| `400` | - | `message` field missing or empty |
| `429` | - | Rate limit exceeded (100 req/60s per IP) |
| `503` | `ML_UNAVAILABLE` | ML service is down |
| `504` | `ML_TIMEOUT` | ML inference exceeded 30s |

---

### GET /api/history

Retrieve the conversation history for the current session.

**Request**
```
GET /api/history
```

**Response** `200 OK`
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the 50/30/20 rule?",
      "timestamp": "2024-01-15T10:30:00.000Z"
    },
    {
      "role": "assistant",
      "content": "The 50/30/20 rule...",
      "sources": [...],
      "latency_ms": 342.5,
      "timestamp": "2024-01-15T10:30:01.000Z"
    }
  ],
  "session_id": "a1b2c3d4-..."
}
```

---

### DELETE /api/session

Clear conversation history and destroy the current session.

**Request**
```
DELETE /api/session
```

**Response** `200 OK`
```json
{ "cleared": true }
```

---

### POST /api/feedback

Record a thumbs-up or thumbs-down rating for an AI response.
Ratings contribute to the user satisfaction tracking metric.

**Request**
```json
POST /api/feedback
Content-Type: application/json

{
  "message_id": "e5f6g7h8-...",
  "rating": "up"
}
```

**Response** `200 OK`
```json
{ "recorded": true }
```

**Validation**: `rating` must be `"up"` or `"down"`.

---

### GET /api/health

Liveness probe for monitoring and load balancer health checks.

**Request**
```
GET /api/health
```

**Response** `200 OK`
```json
{
  "status": "ok",
  "service": "api-gateway",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "activeSessions": 42
}
```

---

## ML Service Endpoints (Internal)

### GET /health

```json
{
  "status": "ok",
  "service": "ml-service",
  "timestamp": 1705316200.123,
  "version": "1.0.0"
}
```

### GET /ready

Returns `200` when the FAISS index is loaded and the pipeline is ready.
Returns `503` during initialization (cold start).

```json
{ "ready": true }
```

### POST /chat

```json
// Request
{ "message": "string", "session_id": "string" }

// Response
{
  "answer": "string",
  "sources": [...],
  "latency_ms": 342.5,
  "session_id": "string"
}
```

### POST /feedback

```json
// Request
{ "session_id": "string", "message_id": "string", "rating": "up|down" }

// Response
{ "recorded": true }
```

---

## Rate Limiting

The API Gateway applies per-IP rate limiting:

| Header | Description |
|--------|-------------|
| `RateLimit-Limit` | Maximum requests per window (100) |
| `RateLimit-Remaining` | Remaining requests in current window |
| `RateLimit-Reset` | Unix timestamp when window resets |

When the limit is exceeded, the server returns `429 Too Many Requests`:
```json
{
  "error": "Too many requests — please wait before sending another message.",
  "retryAfter": 60
}
```

---

## Session Management

Sessions are cookie-based (Express session via `connect.sid` cookie).

- **Lifetime**: 2 hours from last activity
- **Memory**: Gateway stores up to 20 messages per session
- **ML memory**: 5-exchange sliding window in ConversationBufferWindowMemory
- **Clearing**: `DELETE /api/session` destroys both the gateway session
  and triggers ML service memory eviction on the next session boundary

---

## Error Response Format

All errors follow a consistent JSON schema:

```json
{
  "error": "Human-readable error description",
  "code": "ERROR_CODE"
}
```

Error codes: `NOT_FOUND`, `CORS_ERROR`, `ML_TIMEOUT`, `ML_UNAVAILABLE`, `INTERNAL_ERROR`
