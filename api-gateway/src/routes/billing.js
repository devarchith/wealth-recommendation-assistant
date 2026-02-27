/**
 * Billing Routes — Razorpay Integration
 * POST /api/billing/create-order   — Create Razorpay subscription order
 * POST /api/billing/verify          — Verify payment signature
 * POST /api/billing/webhook         — Razorpay webhook events
 * GET  /api/billing/plans           — Return pricing plans
 * GET  /api/billing/usage           — Return current user's usage stats
 */

'use strict';

const express  = require('express');
const router   = express.Router();
const crypto   = require('crypto');
const { PLANS, getPlan, getUpgradeSuggestion } = require('../services/subscriptionPlans');
const { usageTracker } = require('../services/usageTracker');

const RAZORPAY_KEY_ID     = process.env.RAZORPAY_KEY_ID     || '';
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';
const RAZORPAY_WEBHOOK_SECRET = process.env.RAZORPAY_WEBHOOK_SECRET || '';

// In production replace with a real DB lookup
function getUserPlan(userId) {
  return 'free'; // Default; override from DB
}

// ---------------------------------------------------------------------------
// GET /api/billing/plans
// ---------------------------------------------------------------------------
router.get('/plans', (req, res) => {
  const plansArray = Object.values(PLANS).map(p => ({
    id:              p.id,
    name:            p.name,
    tagline:         p.tagline || '',
    price_inr:       p.price_inr,
    price_inr_annual:p.price_inr_annual,
    queries_per_day: p.queries_per_day,
    queries_per_month: p.queries_per_month,
    features:        p.features,
    limits:          p.limits,
  }));
  res.json({ plans: plansArray });
});

// ---------------------------------------------------------------------------
// POST /api/billing/create-order
// ---------------------------------------------------------------------------
router.post('/create-order', async (req, res, next) => {
  try {
    const { plan_id, billing_cycle = 'monthly' } = req.body;
    const plan = getPlan(plan_id);

    if (plan.price_inr === 0) {
      return res.json({ order_id: null, plan_id, message: 'Free plan — no payment required.' });
    }

    if (!RAZORPAY_KEY_ID || !RAZORPAY_KEY_SECRET) {
      return res.status(503).json({
        error: 'RAZORPAY_NOT_CONFIGURED',
        message: 'Razorpay credentials not set. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env',
      });
    }

    const amount  = billing_cycle === 'annual' ? plan.price_inr_annual * 100 : plan.price_inr * 100; // paise
    const receipt = `receipt_${Date.now()}`;

    // Dynamically require Razorpay to avoid startup crash if not installed
    let Razorpay;
    try {
      Razorpay = require('razorpay');
    } catch {
      return res.status(503).json({ error: 'RAZORPAY_SDK_MISSING', message: 'npm install razorpay' });
    }

    const rzpay = new Razorpay({ key_id: RAZORPAY_KEY_ID, key_secret: RAZORPAY_KEY_SECRET });
    const order = await rzpay.orders.create({
      amount,
      currency: 'INR',
      receipt,
      notes:    { plan_id, billing_cycle, user_id: req.session?.id || 'anon' },
    });

    res.json({
      order_id:   order.id,
      amount,
      currency:   'INR',
      key_id:     RAZORPAY_KEY_ID,
      plan_id,
      billing_cycle,
    });
  } catch (err) {
    next(err);
  }
});

// ---------------------------------------------------------------------------
// POST /api/billing/verify
// ---------------------------------------------------------------------------
router.post('/verify', (req, res) => {
  const { order_id, payment_id, signature, plan_id } = req.body;
  if (!order_id || !payment_id || !signature) {
    return res.status(400).json({ error: 'Missing required fields.' });
  }

  const expected = crypto
    .createHmac('sha256', RAZORPAY_KEY_SECRET)
    .update(`${order_id}|${payment_id}`)
    .digest('hex');

  if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))) {
    return res.status(400).json({ error: 'SIGNATURE_MISMATCH', message: 'Payment verification failed.' });
  }

  // TODO: Update user plan in database
  console.log(`[Billing] Payment verified: ${payment_id} → plan: ${plan_id}`);
  res.json({ success: true, plan_id, payment_id });
});

// ---------------------------------------------------------------------------
// POST /api/billing/webhook  (Razorpay server webhook)
// ---------------------------------------------------------------------------
router.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['x-razorpay-signature'];
  const body = req.body.toString();

  if (RAZORPAY_WEBHOOK_SECRET) {
    const expected = crypto
      .createHmac('sha256', RAZORPAY_WEBHOOK_SECRET)
      .update(body)
      .digest('hex');
    if (!sig || !crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig))) {
      return res.status(400).json({ error: 'invalid signature' });
    }
  }

  let event;
  try {
    event = JSON.parse(body);
  } catch {
    return res.status(400).json({ error: 'invalid JSON' });
  }

  const eventType = event.event;
  console.log(`[Billing] Webhook event: ${eventType}`);

  switch (eventType) {
    case 'payment.captured':
      // TODO: Activate subscription for user
      break;
    case 'subscription.activated':
      // TODO: Update user subscription status
      break;
    case 'subscription.cancelled':
      // TODO: Downgrade user to free
      break;
    case 'payment.failed':
      // TODO: Notify user + retry logic
      break;
  }

  res.json({ status: 'ok' });
});

// ---------------------------------------------------------------------------
// GET /api/billing/usage
// ---------------------------------------------------------------------------
router.get('/usage', (req, res) => {
  const userId  = req.session?.id || 'anon';
  const planId  = getUserPlan(userId);
  const plan    = getPlan(planId);
  const usage   = usageTracker.getUsage(userId);

  res.json({
    plan_id:         planId,
    plan_name:       plan.name,
    queries_today:   usage.queries_today,
    queries_this_month: usage.queries_this_month,
    limit_per_day:   plan.queries_per_day,
    limit_per_month: plan.queries_per_month,
    reset_at:        usage.reset_at,
  });
});

module.exports = router;
