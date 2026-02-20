/**
 * CA Review Portal — Validate and Correct AI Responses
 * ======================================================
 * Chartered Accountants can review AI-generated answers flagged by the
 * confidence scorer, approve correct answers, reject and provide corrections,
 * or escalate to senior CAs for complex matters.
 *
 * Routes (all require CA or Admin role):
 *   GET  /api/ca-review/queue         — pending reviews
 *   GET  /api/ca-review/:id           — single review item
 *   POST /api/ca-review/:id/approve   — approve AI answer as-is
 *   POST /api/ca-review/:id/reject    — reject with CA-corrected answer
 *   POST /api/ca-review/:id/escalate  — escalate to senior CA / partner
 *   GET  /api/ca-review/stats         — reviewer productivity dashboard
 *   GET  /api/ca-review/corrections   — approved corrections (RLHF training data)
 *
 * Review items come from two sources:
 *   1. Confidence scorer (auto-queue for confidence < 0.50)
 *   2. User flag (POST /api/chat/flag — user marks answer as wrong)
 *
 * Approved corrections feed the RLHF pipeline (rlhf_pipeline.py).
 */

'use strict';

const express   = require('express');
const crypto    = require('crypto');
const router    = express.Router();
const { requireAuth, requireRole } = require('../middleware/rbac');
const { auditLog } = require('../middleware/rbiAuditLogger');

// ---------------------------------------------------------------------------
// In-memory review queue — replace with DB in production
// ---------------------------------------------------------------------------

const reviewQueue  = new Map();  // id → ReviewItem
const corrections  = [];         // approved corrections for RLHF

function createReviewItem({
  query, ai_answer, category, confidence, source, user_id, hallucination_details,
}) {
  const id = crypto.randomBytes(8).toString('hex');
  const item = {
    id,
    query,
    ai_answer,
    category:   category   || 'general',
    confidence: confidence || 0.0,
    source,               // 'auto_confidence' | 'user_flag'
    user_id:    user_id   || 'system',
    created_at: new Date().toISOString(),
    status:     'pending', // pending | approved | rejected | escalated
    reviewer_id: null,
    reviewed_at: null,
    corrected_answer: null,
    reviewer_notes:   null,
    hallucination_details,
    escalated_to: null,
  };
  reviewQueue.set(id, item);
  return item;
}

// Seed some demo items for development
const _seeds = [
  {
    query:      'What is STCG tax rate on equity shares?',
    ai_answer:  'STCG on equity shares is taxed at 15% under Section 111A.',
    category:   'capital_gains',
    confidence: 0.32,
    source:     'auto_confidence',
    user_id:    'system',
    hallucination_details: { is_hallucination: true, findings: ['STCG rate should be 20% post-Budget 2024, not 15%'] },
  },
  {
    query:      'Can I claim both 80C and 80CCD(1B) deductions?',
    ai_answer:  'Yes, 80CCD(1B) provides additional ₹50,000 NPS deduction over 80C limit.',
    category:   'deductions',
    confidence: 0.62,
    source:     'auto_confidence',
    user_id:    'system',
    hallucination_details: null,
  },
];
_seeds.forEach(s => createReviewItem(s));

// ---------------------------------------------------------------------------
// Auth middleware — CA or Admin required
// ---------------------------------------------------------------------------

router.use(requireAuth);
router.use(requireRole('ca'));

// ---------------------------------------------------------------------------
// GET /api/ca-review/queue
// ---------------------------------------------------------------------------

router.get('/queue', (req, res) => {
  const { status = 'pending', category, limit = 50 } = req.query;
  let items = [...reviewQueue.values()];

  if (status)   items = items.filter(i => i.status === status);
  if (category) items = items.filter(i => i.category === category);

  // Sort: lowest confidence first (most urgent)
  items.sort((a, b) => a.confidence - b.confidence);

  res.json({
    total:    reviewQueue.size,
    pending:  [...reviewQueue.values()].filter(i => i.status === 'pending').length,
    items:    items.slice(0, parseInt(limit)).map(sanitiseItem),
  });
});

// ---------------------------------------------------------------------------
// GET /api/ca-review/stats
// ---------------------------------------------------------------------------

router.get('/stats', (req, res) => {
  const all = [...reviewQueue.values()];
  const byStatus = { pending: 0, approved: 0, rejected: 0, escalated: 0 };
  for (const item of all) byStatus[item.status] = (byStatus[item.status] || 0) + 1;

  const avgConfidence = all.length
    ? (all.reduce((s, i) => s + i.confidence, 0) / all.length).toFixed(3)
    : 0;

  res.json({
    total_in_queue:  all.length,
    by_status:       byStatus,
    avg_confidence:  parseFloat(avgConfidence),
    corrections_ready: corrections.length,
    queue_age_oldest: all.length
      ? all.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))[0].created_at
      : null,
  });
});

// ---------------------------------------------------------------------------
// GET /api/ca-review/:id
// ---------------------------------------------------------------------------

router.get('/:id', (req, res) => {
  const item = reviewQueue.get(req.params.id);
  if (!item) return res.status(404).json({ error: 'Review item not found.' });
  res.json(sanitiseItem(item));
});

// ---------------------------------------------------------------------------
// POST /api/ca-review/:id/approve
// ---------------------------------------------------------------------------

router.post('/:id/approve', (req, res) => {
  const item = reviewQueue.get(req.params.id);
  if (!item)                     return res.status(404).json({ error: 'Not found.' });
  if (item.status !== 'pending') return res.status(409).json({ error: `Item is already ${item.status}.` });

  const { notes } = req.body;
  const reviewerId = req.session.userId;

  item.status          = 'approved';
  item.reviewer_id     = reviewerId;
  item.reviewed_at     = new Date().toISOString();
  item.reviewer_notes  = notes || null;

  // Add to corrections for RLHF — approved AI answer is correct
  corrections.push({
    id:             item.id,
    query:          item.query,
    answer:         item.ai_answer,
    category:       item.category,
    label:          'positive',  // thumbs-up
    reviewer_id:    reviewerId,
    reviewed_at:    item.reviewed_at,
  });

  auditLog.record('data.profile.updated', req, {
    resource:    'ca_review',
    resource_id: item.id,
    action:      'approve',
    status:      'success',
  });

  res.json({ success: true, item: sanitiseItem(item) });
});

// ---------------------------------------------------------------------------
// POST /api/ca-review/:id/reject
// ---------------------------------------------------------------------------

router.post('/:id/reject', (req, res) => {
  const item = reviewQueue.get(req.params.id);
  if (!item)                     return res.status(404).json({ error: 'Not found.' });
  if (item.status !== 'pending') return res.status(409).json({ error: `Item is already ${item.status}.` });

  const { corrected_answer, notes } = req.body;
  if (!corrected_answer) {
    return res.status(400).json({ error: 'corrected_answer is required when rejecting.' });
  }

  const reviewerId = req.session.userId;
  item.status           = 'rejected';
  item.reviewer_id      = reviewerId;
  item.reviewed_at      = new Date().toISOString();
  item.corrected_answer = corrected_answer;
  item.reviewer_notes   = notes || null;

  // Add to RLHF training data — original is negative, correction is positive
  corrections.push(
    {
      id:          item.id + '_neg',
      query:       item.query,
      answer:      item.ai_answer,
      category:    item.category,
      label:       'negative',
      reviewer_id: reviewerId,
      reviewed_at: item.reviewed_at,
    },
    {
      id:          item.id + '_pos',
      query:       item.query,
      answer:      corrected_answer,
      category:    item.category,
      label:       'positive',
      reviewer_id: reviewerId,
      reviewed_at: item.reviewed_at,
    }
  );

  auditLog.record('data.profile.updated', req, {
    resource:    'ca_review',
    resource_id: item.id,
    action:      'reject',
    status:      'success',
  });

  res.json({ success: true, item: sanitiseItem(item) });
});

// ---------------------------------------------------------------------------
// POST /api/ca-review/:id/escalate
// ---------------------------------------------------------------------------

router.post('/:id/escalate', (req, res) => {
  const item = reviewQueue.get(req.params.id);
  if (!item) return res.status(404).json({ error: 'Not found.' });

  const { escalate_to, reason } = req.body;
  item.status      = 'escalated';
  item.escalated_to = escalate_to || 'senior_ca';
  item.reviewer_notes = reason || 'Requires senior CA review';
  item.reviewed_at  = new Date().toISOString();

  auditLog.record('data.profile.updated', req, {
    resource:    'ca_review',
    resource_id: item.id,
    action:      'escalate',
    status:      'success',
  });

  res.json({ success: true, item: sanitiseItem(item) });
});

// ---------------------------------------------------------------------------
// GET /api/ca-review/corrections  — RLHF training data export
// ---------------------------------------------------------------------------

router.get('/corrections', (req, res) => {
  const { since, limit = 500 } = req.query;
  let data = corrections;
  if (since) data = data.filter(c => c.reviewed_at >= since);
  res.json({ total: data.length, corrections: data.slice(-parseInt(limit)) });
});

// ---------------------------------------------------------------------------
// POST /api/chat/flag  — user-initiated flag (accessible without CA role)
// ---------------------------------------------------------------------------

function flagAnswer(query, ai_answer, category, user_id, reason) {
  return createReviewItem({
    query, ai_answer, category,
    confidence: 0.0,
    source:     'user_flag',
    user_id,
    hallucination_details: { user_reported: reason },
  });
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function sanitiseItem(item) {
  const { ...safe } = item;
  return safe;
}

module.exports = { router, createReviewItem, flagAnswer, corrections };
