'use strict';

/**
 * Chat routes — proxy to the ML service with session management.
 *
 * POST /api/chat    → send message, receive AI response
 * DELETE /api/session → clear conversation history for this session
 * POST /api/feedback  → record thumbs-up/down rating
 */

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { sendChatMessage, sendFeedback } = require('../services/mlClient');
const { sessionStore } = require('../services/sessionStore');

const router = express.Router();

// ── POST /api/chat ──────────────────────────────────────────────────────────

router.post('/chat', async (req, res, next) => {
  const { message } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required and must be a non-empty string' });
  }

  // Assign or reuse a session ID (Express session-backed)
  if (!req.session.sessionId) {
    req.session.sessionId = uuidv4();
  }
  const sessionId = req.session.sessionId;

  try {
    const start = Date.now();
    const mlResponse = await sendChatMessage(message.trim(), sessionId);
    const gatewayLatencyMs = Date.now() - start;

    // Persist conversation exchange in the gateway's own session store
    // (mirrors what the ML service stores in memory, useful for session replay)
    sessionStore.addMessage(sessionId, {
      role: 'user',
      content: message.trim(),
      timestamp: new Date().toISOString(),
    });
    sessionStore.addMessage(sessionId, {
      role: 'assistant',
      content: mlResponse.answer,
      sources: mlResponse.sources || [],
      latency_ms: mlResponse.latency_ms,
      timestamp: new Date().toISOString(),
    });

    return res.json({
      answer: mlResponse.answer,
      sources: mlResponse.sources || [],
      latency_ms: mlResponse.latency_ms,
      gateway_latency_ms: gatewayLatencyMs,
      session_id: sessionId,
      message_id: uuidv4(),
    });
  } catch (err) {
    next(err);
  }
});

// ── GET /api/history ────────────────────────────────────────────────────────

router.get('/history', (req, res) => {
  const sessionId = req.session.sessionId;
  if (!sessionId) {
    return res.json({ messages: [], session_id: null });
  }
  const messages = sessionStore.getHistory(sessionId);
  return res.json({ messages, session_id: sessionId });
});

// ── DELETE /api/session ─────────────────────────────────────────────────────

router.delete('/session', (req, res) => {
  const sessionId = req.session.sessionId;
  if (sessionId) {
    sessionStore.clearSession(sessionId);
  }
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to clear session' });
    }
    return res.json({ cleared: true });
  });
});

// ── POST /api/feedback ──────────────────────────────────────────────────────

router.post('/feedback', async (req, res, next) => {
  const { rating, message_id: messageId } = req.body;
  const sessionId = req.session.sessionId || 'anonymous';

  if (!['up', 'down'].includes(rating)) {
    return res.status(400).json({ error: "rating must be 'up' or 'down'" });
  }

  try {
    const result = await sendFeedback(sessionId, messageId, rating);
    return res.json(result);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
