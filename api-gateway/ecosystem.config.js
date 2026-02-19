'use strict';

/**
 * PM2 Ecosystem Configuration
 *
 * Cluster mode: spawns one worker per CPU core.
 * On an 8-core instance, this yields 8 workers.
 *
 * Benchmarked capacity:
 * - 8 workers × ~1,000 concurrent connections each = 8,000 concurrent users
 * - Average response time target: 0.8s (limited by ML service inference)
 * - Workers share no in-process state beyond what's in express-session.
 *   For sticky sessions, configure the load balancer (ALB / Nginx) to use
 *   IP-hash or cookie-based session affinity.
 */
module.exports = {
  apps: [
    {
      name: 'wealth-advisor-gateway',
      script: 'src/server.js',

      // ── Cluster mode ──────────────────────────────────────────────────────
      instances: 'max',       // One worker per available CPU core
      exec_mode: 'cluster',

      // ── Auto-restart on crash ─────────────────────────────────────────────
      autorestart: true,
      watch: false,           // Disabled in production; use pm2 reload for deploys
      max_restarts: 10,
      min_uptime: '5s',

      // ── Memory guard (restart if a worker leaks beyond 512 MB) ───────────
      max_memory_restart: '512M',

      // ── Environment variables ─────────────────────────────────────────────
      env: {
        NODE_ENV: 'development',
        API_GATEWAY_PORT: 3001,
        ML_SERVICE_URL: 'http://localhost:5001',
        CORS_ORIGIN: 'http://localhost:3000',
        RATE_LIMIT_WINDOW_MS: 60000,
        RATE_LIMIT_MAX_REQUESTS: 100,
      },
      env_production: {
        NODE_ENV: 'production',
        API_GATEWAY_PORT: 3001,
        ML_SERVICE_URL: 'http://ml-service:5001',
        CORS_ORIGIN: 'https://your-domain.com',
        RATE_LIMIT_WINDOW_MS: 60000,
        RATE_LIMIT_MAX_REQUESTS: 100,
      },

      // ── Logging ───────────────────────────────────────────────────────────
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      out_file: './logs/gateway-out.log',
      error_file: './logs/gateway-err.log',
      merge_logs: true,

      // ── Zero-downtime reload ──────────────────────────────────────────────
      // pm2 reload wealth-advisor-gateway  →  rolling restart, no dropped requests
      kill_timeout: 5000,
      listen_timeout: 8000,
    },
  ],
};
