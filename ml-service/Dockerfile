# ── ML Service Dockerfile ───────────────────────────────────────────────────
# Multi-stage build: dependency layer cached separately from source code
# so that source changes don't invalidate the heavy pip-install layer.

# Stage 1 — dependency builder
FROM python:3.11-slim AS deps

WORKDIR /build

# Install system libraries needed by faiss-cpu and torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2 — runtime image
FROM python:3.11-slim AS runtime

LABEL maintainer="Devarchith Parashara Batchu <devarchithbatchu@gmail.com>"
LABEL description="WealthAdvisor AI — ML Service (Flask + LangChain + FAISS)"

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Runtime system deps (libgomp for faiss-cpu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY src/ ./src/
COPY data/ ./data/

# Create cache and index directories with appropriate permissions
RUN mkdir -p /app/embedding_cache /app/faiss_index \
    && chmod 755 /app/embedding_cache /app/faiss_index

# Non-root user for security
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Environment defaults (override via docker-compose / K8s secrets)
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    ML_SERVICE_PORT=5001 \
    FLASK_ENV=production \
    FLASK_DEBUG=0 \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    FAISS_INDEX_PATH=/app/faiss_index \
    EMBEDDING_CACHE_PATH=/app/embedding_cache \
    MEMORY_WINDOW_SIZE=5

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health')"

# Use gunicorn for production; single worker per container (scale via replicas)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5001", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "src.app:app"]
