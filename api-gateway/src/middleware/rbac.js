/**
 * Role-Based Access Control (RBAC) Middleware
 * ============================================
 * Roles (lowest → highest privilege):
 *   guest      — unauthenticated visitors (10 free queries/day)
 *   customer   — logged-in free-plan user
 *   individual — paid Individual plan
 *   business   — paid Business plan
 *   ca         — CA Professional plan
 *   staff      — internal support agents (no billing access)
 *   admin      — full system access
 *
 * Usage:
 *   const { requireAuth, requireRole, requirePlanFeature } = require('./rbac');
 *
 *   router.get('/sensitive', requireAuth, requireRole('ca'), handler);
 *   router.get('/gst',       requireAuth, requirePlanFeature('gst_assistant'), handler);
 */

'use strict';

const { canAccessFeature } = require('../services/subscriptionPlans');

// ---------------------------------------------------------------------------
// Role hierarchy — higher index = more privilege
// ---------------------------------------------------------------------------

const ROLE_ORDER = ['guest', 'customer', 'individual', 'business', 'ca', 'staff', 'admin'];

// Map plan IDs → roles
const PLAN_ROLE_MAP = {
  free:       'customer',
  individual: 'individual',
  business:   'business',
  ca:         'ca',
};

// Features that require specific minimum roles (in addition to plan limits)
const FEATURE_ROLE_REQUIREMENTS = {
  ca_portal:      'ca',
  api_access:     'ca',
  document_vault: 'ca',
  admin_metrics:  'admin',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Determine caller's role from session.
 * Staff / Admin roles are set by an internal flag (not from the plan).
 */
function getCallerRole(req) {
  const session = req.session || {};
  if (session.isAdmin)     return 'admin';
  if (session.isStaff)     return 'staff';
  if (!session.userId)     return 'guest';

  const plan = session.plan || 'free';
  return PLAN_ROLE_MAP[plan] || 'customer';
}

function roleIndex(role) {
  const idx = ROLE_ORDER.indexOf(role);
  return idx === -1 ? 0 : idx;
}

function hasMinimumRole(callerRole, requiredRole) {
  return roleIndex(callerRole) >= roleIndex(requiredRole);
}

// ---------------------------------------------------------------------------
// Middleware factories
// ---------------------------------------------------------------------------

/**
 * requireAuth — rejects unauthenticated (guest) requests.
 */
function requireAuth(req, res, next) {
  if (!req.session?.userId) {
    return res.status(401).json({
      error: 'UNAUTHENTICATED',
      message: 'Please log in to access this resource.',
    });
  }
  next();
}

/**
 * requireRole(minRole) — requires caller's role ≥ minRole.
 * Example: requireRole('business') rejects free/individual plan users.
 */
function requireRole(minRole) {
  return (req, res, next) => {
    const callerRole = getCallerRole(req);
    if (!hasMinimumRole(callerRole, minRole)) {
      return res.status(403).json({
        error:    'INSUFFICIENT_ROLE',
        message:  `This action requires ${minRole} role or higher. Your role: ${callerRole}.`,
        required: minRole,
        current:  callerRole,
      });
    }
    next();
  };
}

/**
 * requirePlanFeature(feature) — checks subscription plan limits.
 * Returns 402 Payment Required with upgrade suggestion if feature is locked.
 */
function requirePlanFeature(feature) {
  const { getUpgradeSuggestion } = require('../services/subscriptionPlans');
  return (req, res, next) => {
    const planId = req.session?.plan || 'free';
    if (canAccessFeature(planId, feature)) return next();

    const upgrade = getUpgradeSuggestion(planId, feature);
    return res.status(402).json({
      error:    'FEATURE_LOCKED',
      message:  `${feature.replace(/_/g,' ')} is not available on your current plan.`,
      feature,
      plan:     planId,
      upgrade,
    });
  };
}

/**
 * requireAdmin — shorthand for admin-only routes.
 * Accepts either admin session flag or X-Admin-Key header.
 */
function requireAdmin(req, res, next) {
  const adminKey = process.env.ADMIN_API_KEY || 'admin-dev-key';
  const headerKey = req.headers['x-admin-key'];

  if (headerKey === adminKey || req.session?.isAdmin) return next();

  return res.status(403).json({
    error:   'FORBIDDEN',
    message: 'Admin access required.',
  });
}

/**
 * requireStaff — allows staff or admin.
 */
function requireStaff(req, res, next) {
  if (req.session?.isStaff || req.session?.isAdmin) return next();
  return requireAdmin(req, res, next);
}

/**
 * attachRole — non-blocking middleware that attaches role to req.
 * Use at the top of routes to make role available downstream.
 */
function attachRole(req, _res, next) {
  req.callerRole = getCallerRole(req);
  req.planId     = req.session?.plan || 'free';
  next();
}

/**
 * auditAccess — logs who accessed what (for compliance).
 * Attach before sensitive route handlers.
 */
function auditAccess(resourceType) {
  return (req, _res, next) => {
    const role   = getCallerRole(req);
    const userId = req.session?.userId || 'anon';
    console.log(
      `[RBAC] ${new Date().toISOString()} | ${req.method} ${req.path} | ` +
      `user=${userId} role=${role} resource=${resourceType} ip=${req.ip}`
    );
    next();
  };
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  ROLE_ORDER,
  PLAN_ROLE_MAP,
  getCallerRole,
  hasMinimumRole,
  requireAuth,
  requireRole,
  requirePlanFeature,
  requireAdmin,
  requireStaff,
  attachRole,
  auditAccess,
};
