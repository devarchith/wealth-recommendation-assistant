/**
 * Subscription Plans — Three-Tier Pricing Model
 * Individual / Business / CA (Chartered Accountant)
 * India-focused with Razorpay integration hooks
 */

'use strict';

const PLANS = {
  free: {
    id:           'free',
    name:         'Free',
    price_inr:    0,
    price_inr_annual: 0,
    queries_per_day: 10,
    queries_per_month: 100,
    features: [
      'AI Chat (10 queries/day)',
      'US Tax calculator',
      'Budget planner',
      'Basic investment guide',
    ],
    limits: {
      india_tax:      false,
      gst_assistant:  false,
      ca_portal:      false,
      whatsapp:       false,
      priority_support: false,
      document_vault: false,
      export_pdf:     false,
      api_access:     false,
    },
    razorpay_plan_id: null,
  },

  individual: {
    id:           'individual',
    name:         'Individual',
    tagline:      'Perfect for salaried professionals and investors',
    price_inr:    499,          // per month
    price_inr_annual: 4_788,   // ₹399/month billed annually (20% off)
    queries_per_day: 100,
    queries_per_month: 2_000,
    features: [
      'All Free features',
      'Unlimited AI queries',
      'India Tax dashboard (ITR + TDS + advance tax)',
      'Capital gains calculator',
      'Deduction optimizer (80C, 80D, HRA)',
      'Investment tab (risk profiles + ETF recs)',
      'WhatsApp bot (English + Telugu)',
      'PDF export',
      'Email support',
    ],
    limits: {
      india_tax:      true,
      gst_assistant:  false,
      ca_portal:      false,
      whatsapp:       true,
      priority_support: false,
      document_vault: false,
      export_pdf:     true,
      api_access:     false,
    },
    razorpay_plan_id: process.env.RAZORPAY_PLAN_INDIVIDUAL || 'plan_individual_499',
  },

  business: {
    id:           'business',
    name:         'Business',
    tagline:      'For SMEs, freelancers, and small businesses',
    price_inr:    1_499,
    price_inr_annual: 14_388,
    queries_per_day: 500,
    queries_per_month: 10_000,
    features: [
      'All Individual features',
      'GST Filing Assistant (GSTR-1, GSTR-3B)',
      'GST Calculator with HSN lookup',
      'Payroll module (PF + ESI + TDS)',
      'Inventory management (retail + gold shop)',
      'Accounts Payable / Receivable tracker',
      'P&L and Balance Sheet generator',
      'Business Dashboard',
      'WhatsApp bot with business templates',
      'Priority email support',
    ],
    limits: {
      india_tax:      true,
      gst_assistant:  true,
      ca_portal:      false,
      whatsapp:       true,
      priority_support: true,
      document_vault: false,
      export_pdf:     true,
      api_access:     false,
    },
    razorpay_plan_id: process.env.RAZORPAY_PLAN_BUSINESS || 'plan_business_1499',
  },

  ca: {
    id:           'ca',
    name:         'CA Professional',
    tagline:      'Built for Chartered Accountants and accounting firms',
    price_inr:    3_999,
    price_inr_annual: 38_388,
    queries_per_day: -1,       // Unlimited
    queries_per_month: -1,
    max_clients:  100,
    features: [
      'All Business features',
      'CA Client Management Dashboard (up to 100 clients)',
      'Bulk ITR generation workflow',
      'Tax Notice Response Templates (143(1), 143(2), 148…)',
      'Document Vault (encrypted client files)',
      'Client Billing & Invoice Generation',
      'Audit Trail Logging',
      'Multi-staff access (up to 5 users)',
      'REST API access',
      'Dedicated phone support',
    ],
    limits: {
      india_tax:      true,
      gst_assistant:  true,
      ca_portal:      true,
      whatsapp:       true,
      priority_support: true,
      document_vault: true,
      export_pdf:     true,
      api_access:     true,
    },
    razorpay_plan_id: process.env.RAZORPAY_PLAN_CA || 'plan_ca_3999',
  },
};

const PLAN_ORDER = ['free', 'individual', 'business', 'ca'];

function getPlan(planId) {
  return PLANS[planId] || PLANS.free;
}

function canAccessFeature(planId, feature) {
  const plan = getPlan(planId);
  return plan.limits[feature] === true;
}

function isWithinQueryLimit(planId, queriesUsedToday) {
  const plan = getPlan(planId);
  if (plan.queries_per_day === -1) return true;
  return queriesUsedToday < plan.queries_per_day;
}

function getUpgradeSuggestion(planId, attemptedFeature) {
  const current   = PLAN_ORDER.indexOf(planId);
  const upgrades  = PLAN_ORDER.slice(current + 1);
  const suggested = upgrades.find(p => PLANS[p].limits[attemptedFeature]);
  if (!suggested) return null;
  const plan = PLANS[suggested];
  return {
    plan_id:   plan.id,
    name:      plan.name,
    price_inr: plan.price_inr,
    message:   `Upgrade to ${plan.name} (₹${plan.price_inr}/month) to unlock ${attemptedFeature.replace(/_/g,' ')}.`,
  };
}

module.exports = { PLANS, PLAN_ORDER, getPlan, canAccessFeature, isWithinQueryLimit, getUpgradeSuggestion };
