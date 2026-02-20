'use strict';

/**
 * WealthAdvisor AI — API Gateway
 * Express server entry point with middleware, routes, and startup logic.
 */

const express = require('express');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const session = require('express-session');
const dotenv = require('dotenv');

dotenv.config();

const { corsMiddleware } = require('./middleware/cors');
const { rateLimiter } = require('./middleware/rateLimiter');
const { errorHandler, notFoundHandler } = require('./middleware/errorHandler');
const chatRoutes      = require('./routes/chat');
const healthRoutes    = require('./routes/health');
const whatsappRoutes  = require('./routes/whatsapp');
const authRoutes      = require('./routes/auth');
const billingRoutes   = require('./routes/billing');
const adminRoutes     = require('./routes/admin');
const privacyRoutes   = require('./routes/privacy');

const app = express();

// ── Security & utility middleware ──────────────────────────────────────────
app.use(helmet({
  contentSecurityPolicy: false, // Handled by Next.js frontend
  crossOriginEmbedderPolicy: false,
}));
app.use(compression());
app.use(express.json({ limit: '10kb' }));
app.use(express.urlencoded({ extended: true, limit: '10kb' }));
app.use(morgan('combined'));

// ── CORS ───────────────────────────────────────────────────────────────────
app.use(corsMiddleware);

// ── Session (used for conversation history store) ──────────────────────────
app.use(session({
  secret: process.env.SESSION_SECRET || 'wealth-advisor-secret-dev',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 2 * 60 * 60 * 1000, // 2 hours
  },
}));

// ── Rate limiting ──────────────────────────────────────────────────────────
app.use('/api/', rateLimiter);

// ── Routes ─────────────────────────────────────────────────────────────────
app.use('/api', healthRoutes);
app.use('/api', chatRoutes);
app.use('/api/whatsapp', whatsappRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/billing', billingRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/privacy', privacyRoutes);

// ── 404 and error handlers ─────────────────────────────────────────────────
app.use(notFoundHandler);
app.use(errorHandler);

// ── Start ──────────────────────────────────────────────────────────────────
const PORT = parseInt(process.env.API_GATEWAY_PORT || '3001', 10);

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`[api-gateway] Listening on port ${PORT}`);
    console.log(`[api-gateway] ML Service URL: ${process.env.ML_SERVICE_URL || 'http://localhost:5001'}`);
  });
}

module.exports = app;
