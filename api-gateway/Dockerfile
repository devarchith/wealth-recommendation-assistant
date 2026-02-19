# ── API Gateway Dockerfile ──────────────────────────────────────────────────

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --production

FROM node:20-slim AS runtime
LABEL maintainer="Devarchith Parashara Batchu <devarchithbatchu@gmail.com>"
LABEL description="WealthAdvisor AI — API Gateway (Node.js + Express)"

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src/ ./src/
COPY ecosystem.config.js ./

RUN mkdir -p logs && \
    useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV NODE_ENV=production \
    API_GATEWAY_PORT=3001

EXPOSE 3001

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3001/api/health', r => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "src/server.js"]
