'use strict';

/**
 * Privacy Reset Routes
 *
 * GET  /api/privacy/modules          — List all resettable modules and their categories
 * GET  /api/privacy/categories/:mod  — List categories for a specific module
 * POST /api/privacy/reset            — Overwrite selected categories with placeholder in-place
 * POST /api/privacy/reset/bulk       — Reset multiple modules and/or categories in one call
 *
 * Body for POST /api/privacy/reset:
 *   { module: string, categories?: string[], confirm: "RESET" }
 *
 * Body for POST /api/privacy/reset/bulk:
 *   { selections: [{ module, categories? }], confirm: "RESET" }
 *
 * The endpoint simulates an in-place data overwrite — in production this would
 * write placeholder values into the user's database records. Here it returns the
 * seeded payload so the client can update its local state.
 *
 * Auth: requires a valid session (req.session.userId) or X-User-Id header.
 */

const express = require('express');
const router  = express.Router();
const { getPlaceholderData, listModules, PLACEHOLDERS } = require('../services/privacyPlaceholders');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveUserId(req) {
  return req.session?.userId || req.headers['x-user-id'] || null;
}

// Audit log (in production: persist to DB/CloudWatch)
function auditLog(userId, module, categories) {
  const ts = new Date().toISOString();
  console.log(`[privacy-reset] ${ts} user=${userId} module=${module} categories=[${categories.join(',')}]`);
}

// ---------------------------------------------------------------------------
// GET /api/privacy/modules
// ---------------------------------------------------------------------------

router.get('/modules', (req, res) => {
  res.json({ modules: listModules() });
});

// ---------------------------------------------------------------------------
// GET /api/privacy/categories/:module
// Returns the selectable categories for a given module with labels and keys.
// ---------------------------------------------------------------------------

router.get('/categories/:module', (req, res) => {
  const mod = PLACEHOLDERS[req.params.module];
  if (!mod) {
    return res.status(404).json({
      error:   'MODULE_NOT_FOUND',
      message: `No module named '${req.params.module}'. Use GET /api/privacy/modules.`,
    });
  }

  const categories = Object.entries(mod.categories).map(([key, cat]) => ({
    key,
    label:       cat.label,
    data_fields: Object.keys(cat.data),
  }));

  res.json({
    module:      req.params.module,
    description: mod.description,
    categories,
  });
});

// ---------------------------------------------------------------------------
// POST /api/privacy/reset
// ---------------------------------------------------------------------------

router.post('/reset', (req, res) => {
  const userId = resolveUserId(req);
  if (!userId) {
    return res.status(401).json({
      error: 'UNAUTHENTICATED',
      message: 'You must be logged in to perform a privacy reset.',
    });
  }

  const { module, categories, confirm } = req.body;

  // Two-step confirmation gate — client must send confirm: "RESET"
  if (confirm !== 'RESET') {
    return res.status(422).json({
      error:   'CONFIRMATION_REQUIRED',
      message: 'Send { confirm: "RESET" } to acknowledge this irreversible action.',
    });
  }

  if (!module || typeof module !== 'string') {
    return res.status(400).json({
      error:   'MISSING_MODULE',
      message: 'Provide a module name. Use GET /api/privacy/modules for valid values.',
    });
  }

  let result;
  try {
    result = getPlaceholderData(module, Array.isArray(categories) ? categories : undefined);
  } catch (err) {
    return res.status(400).json({ error: 'INVALID_MODULE', message: err.message });
  }

  // Audit the reset action
  auditLog(userId, module, result.categories_reset);

  /*
   * In production: iterate result.seeded and write each key→value into the
   * user's module record in the database. The overwrite is in-place so the
   * user's ID / account structure is preserved — only data values are replaced.
   *
   * Example (PostgreSQL):
   *   await db('user_rice_mill_data')
   *     .where({ user_id: userId })
   *     .update(flattenPlaceholder(result.seeded));
   */

  res.json({
    success:          true,
    user_id:          userId,
    module:           result.module,
    categories_reset: result.categories_reset,
    placeholder_data: result.seeded,
    reset_at:         new Date().toISOString(),
    note:             'Real data has been overwritten with placeholder values. This action cannot be undone.',
  });
});

// ---------------------------------------------------------------------------
// POST /api/privacy/reset/bulk
// Reset multiple modules at once — user sends an array of { module, categories? }
// ---------------------------------------------------------------------------

router.post('/reset/bulk', (req, res) => {
  const userId = resolveUserId(req);
  if (!userId) {
    return res.status(401).json({
      error: 'UNAUTHENTICATED',
      message: 'You must be logged in to perform a privacy reset.',
    });
  }

  const { selections, confirm } = req.body;

  if (confirm !== 'RESET') {
    return res.status(422).json({
      error:   'CONFIRMATION_REQUIRED',
      message: 'Send { confirm: "RESET" } to acknowledge this irreversible action.',
    });
  }

  if (!Array.isArray(selections) || selections.length === 0) {
    return res.status(400).json({
      error:   'MISSING_SELECTIONS',
      message: 'Provide a non-empty selections array: [{ module, categories? }].',
    });
  }

  const results = [];
  const errors  = [];

  for (const sel of selections) {
    if (!sel.module) { errors.push({ sel, error: 'module is required' }); continue; }
    try {
      const result = getPlaceholderData(sel.module, Array.isArray(sel.categories) ? sel.categories : undefined);
      auditLog(userId, result.module, result.categories_reset);
      results.push(result);
    } catch (err) {
      errors.push({ module: sel.module, error: err.message });
    }
  }

  res.json({
    success:      errors.length === 0,
    user_id:      userId,
    reset_at:     new Date().toISOString(),
    modules_reset: results.map(r => ({ module: r.module, categories_reset: r.categories_reset })),
    errors:       errors.length > 0 ? errors : undefined,
    note:         'Selected data categories have been overwritten with placeholder values.',
  });
});

module.exports = router;
