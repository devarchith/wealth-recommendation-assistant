/**
 * Admin Dashboard Routes
 * GET /api/admin/metrics      — Revenue, active users, churn rate
 * GET /api/admin/users        — User list with plan breakdown
 * GET /api/admin/revenue      — Revenue breakdown by plan and period
 * GET /api/admin/queries      — Query volume stats (per day / per plan)
 * POST /api/admin/set-plan    — Manually override a user's plan
 *
 * All routes require ADMIN role (X-Admin-Key header or session.isAdmin).
 */

'use strict';

const express = require('express');
const router  = express.Router();

const ADMIN_KEY = process.env.ADMIN_API_KEY || 'admin-dev-key';

// ---------------------------------------------------------------------------
// In-memory analytics store — replace with time-series DB in production
// ---------------------------------------------------------------------------

// Simulated subscription data (replace with DB)
const _subscriptions = [
  { userId: 'phone_9876543210', plan: 'free',       since: '2024-11-01', active: true },
  { userId: 'phone_9123456789', plan: 'individual', since: '2024-12-15', active: true },
  { userId: 'phone_9000000001', plan: 'business',   since: '2025-01-03', active: true },
  { userId: 'phone_9000000002', plan: 'ca',         since: '2025-01-20', active: true },
  { userId: 'phone_9000000003', plan: 'individual', since: '2025-01-28', active: true },
  { userId: 'phone_9000000004', plan: 'business',   since: '2024-10-11', active: false }, // churned
  { userId: 'phone_9000000005', plan: 'individual', since: '2024-09-01', active: false }, // churned
];

const PLAN_PRICES = {
  free:       0,
  individual: 499,
  business:   1499,
  ca:         3999,
};

// Simulated daily query counts per plan
const _dailyQueryStats = {
  '2025-02-15': { free: 842, individual: 3210, business: 7890, ca: 2340 },
  '2025-02-16': { free: 910, individual: 3455, business: 8102, ca: 2511 },
  '2025-02-17': { free: 874, individual: 3320, business: 7654, ca: 2298 },
  '2025-02-18': { free: 995, individual: 3601, business: 8230, ca: 2678 },
  '2025-02-19': { free: 783, individual: 2987, business: 7234, ca: 2100 },
};

// ---------------------------------------------------------------------------
// Admin auth middleware
// ---------------------------------------------------------------------------

function requireAdmin(req, res, next) {
  const key = req.headers['x-admin-key'];
  if (key && key === ADMIN_KEY) return next();
  if (req.session?.isAdmin) return next();
  return res.status(403).json({ error: 'FORBIDDEN', message: 'Admin access required.' });
}

router.use(requireAdmin);

// ---------------------------------------------------------------------------
// GET /api/admin/metrics
// ---------------------------------------------------------------------------

router.get('/metrics', (req, res) => {
  const now      = new Date();
  const active   = _subscriptions.filter(s => s.active);
  const inactive = _subscriptions.filter(s => !s.active);

  // MRR
  const mrr = active.reduce((sum, s) => sum + (PLAN_PRICES[s.plan] || 0), 0);

  // Plan breakdown
  const planCounts = { free: 0, individual: 0, business: 0, ca: 0 };
  for (const s of active) planCounts[s.plan] = (planCounts[s.plan] || 0) + 1;

  // Churn rate (last 30 days) = churned / (churned + active_at_start)
  const thirtyDaysAgo = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const recentChurn   = inactive.filter(s => s.since >= thirtyDaysAgo).length;
  const churnRate     = active.length + recentChurn > 0
    ? ((recentChurn / (active.length + recentChurn)) * 100).toFixed(2)
    : '0.00';

  // 30-day new signups
  const newSignups = _subscriptions.filter(s => s.since >= thirtyDaysAgo).length;

  // Average Revenue Per User
  const arpu = active.length > 0 ? (mrr / active.length).toFixed(2) : '0.00';

  // Today's query volume
  const today     = now.toISOString().slice(0, 10);
  const todayStats = _dailyQueryStats[today] || { free: 0, individual: 0, business: 0, ca: 0 };
  const totalQueriestoday = Object.values(todayStats).reduce((a, b) => a + b, 0);

  res.json({
    timestamp: now.toISOString(),
    users: {
      total:    _subscriptions.length,
      active:   active.length,
      churned:  inactive.length,
      new_last_30d: newSignups,
    },
    revenue: {
      mrr_inr:  mrr,
      arr_inr:  mrr * 12,
      arpu_inr: parseFloat(arpu),
    },
    churn: {
      rate_percent: parseFloat(churnRate),
      count_last_30d: recentChurn,
    },
    plans: planCounts,
    queries: {
      today_total: totalQueriestoday,
      by_plan:     todayStats,
    },
  });
});

// ---------------------------------------------------------------------------
// GET /api/admin/users
// ---------------------------------------------------------------------------

router.get('/users', (req, res) => {
  const { plan, active } = req.query;
  let list = [..._subscriptions];

  if (plan)   list = list.filter(s => s.plan === plan);
  if (active !== undefined) list = list.filter(s => String(s.active) === active);

  res.json({
    total: list.length,
    users: list.map(s => ({
      user_id:    s.userId,
      plan:       s.plan,
      since:      s.since,
      active:     s.active,
      mrr_inr:    s.active ? PLAN_PRICES[s.plan] : 0,
    })),
  });
});

// ---------------------------------------------------------------------------
// GET /api/admin/revenue
// ---------------------------------------------------------------------------

router.get('/revenue', (req, res) => {
  // Monthly revenue breakdown
  const monthly = {};
  for (const s of _subscriptions) {
    if (!s.active) continue;
    const month = s.since.slice(0, 7); // YYYY-MM
    monthly[month] = (monthly[month] || 0) + PLAN_PRICES[s.plan];
  }

  // Revenue by plan
  const byPlan = {};
  for (const [plan, price] of Object.entries(PLAN_PRICES)) {
    const count = _subscriptions.filter(s => s.active && s.plan === plan).length;
    byPlan[plan] = { users: count, mrr_inr: count * price };
  }

  const totalMrr = Object.values(byPlan).reduce((s, p) => s + p.mrr_inr, 0);

  res.json({
    total_mrr_inr: totalMrr,
    total_arr_inr: totalMrr * 12,
    by_plan: byPlan,
    monthly_cohorts: monthly,
  });
});

// ---------------------------------------------------------------------------
// GET /api/admin/queries
// ---------------------------------------------------------------------------

router.get('/queries', (req, res) => {
  const dates   = Object.keys(_dailyQueryStats).sort();
  const totals  = dates.map(d => {
    const day = _dailyQueryStats[d];
    return {
      date:  d,
      total: Object.values(day).reduce((a, b) => a + b, 0),
      ...day,
    };
  });

  const avg = totals.length
    ? Math.round(totals.reduce((s, d) => s + d.total, 0) / totals.length)
    : 0;

  res.json({
    period_days: dates.length,
    average_daily_queries: avg,
    data: totals,
  });
});

// ---------------------------------------------------------------------------
// POST /api/admin/set-plan
// ---------------------------------------------------------------------------

router.post('/set-plan', (req, res) => {
  const { user_id, plan } = req.body;
  if (!user_id || !plan) {
    return res.status(400).json({ error: 'user_id and plan are required.' });
  }
  if (!PLAN_PRICES.hasOwnProperty(plan)) {
    return res.status(400).json({ error: `Invalid plan. Choose: ${Object.keys(PLAN_PRICES).join(', ')}` });
  }

  const existing = _subscriptions.find(s => s.userId === user_id);
  if (existing) {
    existing.plan   = plan;
    existing.active = true;
  } else {
    _subscriptions.push({
      userId: user_id,
      plan,
      since:  new Date().toISOString().slice(0, 10),
      active: true,
    });
  }

  console.log(`[Admin] Plan updated: ${user_id} → ${plan}`);
  res.json({ success: true, user_id, plan });
});

module.exports = router;
