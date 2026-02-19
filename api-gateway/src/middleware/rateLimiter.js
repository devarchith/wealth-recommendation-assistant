'use strict';

const rateLimit = require('express-rate-limit');

/**
 * Rate limiter: 100 requests per 60-second window per IP.
 * Chosen to support 8K concurrent users while preventing abuse.
 *
 * At 8,000 concurrent users averaging 1 request per ~5 minutes each,
 * peak RPS ≈ 27. This limit provides generous headroom for burst traffic.
 */
const rateLimiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10),
  max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100', 10),
  standardHeaders: true,  // Return rate limit info in RateLimit-* headers
  legacyHeaders: false,
  message: {
    error: 'Too many requests — please wait before sending another message.',
    retryAfter: 60,
  },
  keyGenerator: (req) =>
    req.headers['x-forwarded-for']?.split(',')[0].trim() || req.ip,
  skip: (req) => req.path === '/health', // Never rate-limit health checks
});

module.exports = { rateLimiter };
