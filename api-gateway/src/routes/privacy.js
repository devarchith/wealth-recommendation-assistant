'use strict';

/**
 * Privacy Reset Routes
 *
 * GET  /api/privacy/modules          — List all resettable modules and their categories
 * POST /api/privacy/reset            — Overwrite real data with placeholder in-place
 *
 * Body for POST /api/privacy/reset:
 *   { module: string, categories?: string[], confirm: "RESET" }
 *
 * The endpoint simulates an in-place data overwrite — in production this would
 * write placeholder values into the user's database records. Here it returns the
 * seeded payload so the client can update its local state.
 *
 * Auth: requires a valid session (req.session.userId) or X-User-Id header.
 */

const express = require('express');
const router  = express.Router();
const { getPlaceholderData, listModules } = require('../services/privacyPlaceholders');

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

module.exports = router;
