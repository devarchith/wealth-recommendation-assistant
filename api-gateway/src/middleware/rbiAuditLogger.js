/**
 * RBI Compliance Audit Logger
 * ============================
 * Produces an immutable, tamper-evident audit trail for all financial
 * operations — satisfying RBI IT Framework (2011), IS Audit Guidelines,
 * and SEBI Cybersecurity Circular requirements.
 *
 * Log entry structure (JSONL, one per line):
 *   seq          — monotonic sequence number
 *   ts           — ISO-8601 timestamp (UTC)
 *   event        — event type (see AUDIT_EVENTS)
 *   actor        — userId performing the action
 *   actor_role   — role at time of action
 *   resource     — resource type / endpoint
 *   resource_id  — specific record/session ID
 *   action       — HTTP method or operation name
 *   status       — 'success' | 'failure' | 'denied'
 *   ip           — client IP (IPv4/IPv6)
 *   user_agent   — browser/app identifier
 *   request_id   — X-Request-ID header for request tracing
 *   details      — sanitised details (no PII)
 *   prev_hash    — SHA-256 of previous log entry (hash chain)
 *   entry_hash   — SHA-256 of this entry (sans entry_hash field)
 *
 * Usage:
 *   const { auditLog, AuditMiddleware } = require('./rbiAuditLogger');
 *
 *   // Manual event
 *   auditLog.record('payment.verified', req, { plan_id: 'individual' });
 *
 *   // Route middleware — logs all requests
 *   router.post('/verify', AuditMiddleware('payment'), handler);
 */

'use strict';

const crypto = require('crypto');
const fs     = require('fs');
const path   = require('path');
const os     = require('os');

// ---------------------------------------------------------------------------
// Event catalogue
// ---------------------------------------------------------------------------

const AUDIT_EVENTS = {
  // Auth
  'auth.login.google':   'User authenticated via Google OAuth',
  'auth.login.otp':      'User authenticated via phone OTP',
  'auth.logout':         'User session terminated',
  'auth.otp.sent':       'OTP dispatched to mobile',
  'auth.otp.failed':     'OTP verification failed',
  'auth.session.expired':'Session expired by timeout',

  // Billing & Payments
  'billing.order.created':   'Razorpay order initiated',
  'billing.payment.verified':'Payment signature verified',
  'billing.webhook.received':'Razorpay webhook event processed',
  'billing.plan.upgraded':   'User plan upgraded',
  'billing.plan.downgraded': 'User plan downgraded (churn)',

  // Data Access
  'data.profile.read':       'User profile data accessed',
  'data.profile.updated':    'User profile data modified',
  'data.tax.calculated':     'Tax computation performed',
  'data.itr.generated':      'ITR draft generated',
  'data.document.uploaded':  'Document added to vault',
  'data.document.downloaded':'Document retrieved from vault',
  'data.document.deleted':   'Document removed from vault',
  'data.export.pdf':         'Financial report exported to PDF',

  // Admin
  'admin.plan.override':     'Admin manually overrode user plan',
  'admin.user.viewed':       'Admin accessed user record',
  'admin.metrics.viewed':    'Admin accessed analytics dashboard',

  // Security
  'security.access.denied':  'Access denied — insufficient role',
  'security.rate.limited':   'Request rate-limited',
  'security.ip.blocked':     'Request from blocked IP',
  'security.2fa.required':   '2FA challenge triggered',
  'security.2fa.passed':     '2FA verification passed',
  'security.2fa.failed':     '2FA verification failed',
};

// ---------------------------------------------------------------------------
// Audit log writer
// ---------------------------------------------------------------------------

class RBIAuditLogger {
  constructor(options = {}) {
    this._seq      = 0;
    this._prevHash = '0'.repeat(64);  // genesis hash
    this._logDir   = options.logDir || path.join(process.cwd(), 'audit-logs');
    this._maxSize  = options.maxFileSizeBytes || 50 * 1024 * 1024; // 50 MB rotate
    this._inMemory = [];  // ring buffer for /api/admin/audit endpoint
    this._bufferMax = 1000;
    this._stream   = null;

    this._ensureLogDir();
    this._openStream();
  }

  // ── Setup ────────────────────────────────────────────────────────────────

  _ensureLogDir() {
    if (!fs.existsSync(this._logDir)) {
      fs.mkdirSync(this._logDir, { recursive: true });
    }
  }

  _logFilePath() {
    const date = new Date().toISOString().slice(0, 10);
    return path.join(this._logDir, `audit-${date}.jsonl`);
  }

  _openStream() {
    const filePath = this._logFilePath();
    this._stream = fs.createWriteStream(filePath, { flags: 'a' });
    this._currentFile = filePath;
    this._stream.on('error', (err) => {
      console.error('[Audit] Log stream error:', err.message);
    });
  }

  // ── Core write ────────────────────────────────────────────────────────────

  _computeHash(entry) {
    const payload = JSON.stringify(entry, Object.keys(entry).filter(k => k !== 'entry_hash').sort());
    return crypto.createHash('sha256').update(payload, 'utf8').digest('hex');
  }

  record(event, req, details = {}) {
    this._seq++;
    const session   = req?.session || {};
    const userId    = session.userId    || 'anon';
    const userRole  = session.plan
      ? { free:'customer', individual:'individual', business:'business', ca:'ca' }[session.plan] || 'customer'
      : (session.isAdmin ? 'admin' : (session.isStaff ? 'staff' : 'guest'));

    const entry = {
      seq:         this._seq,
      ts:          new Date().toISOString(),
      event,
      actor:       userId,
      actor_role:  userRole,
      resource:    req?.path    || details.resource    || '',
      resource_id: details.resource_id || session.userId || '',
      action:      req?.method  || details.action      || '',
      status:      details.status     || 'success',
      ip:          req?.ip      || req?.connection?.remoteAddress || '',
      user_agent:  req?.headers?.['user-agent']?.slice(0, 200) || '',
      request_id:  req?.headers?.['x-request-id'] || '',
      details:     _sanitiseDetails(details),
      prev_hash:   this._prevHash,
    };

    entry.entry_hash = this._computeHash(entry);
    this._prevHash   = entry.entry_hash;

    // Write to JSONL file
    const line = JSON.stringify(entry) + '\n';
    if (this._stream && !this._stream.destroyed) {
      this._stream.write(line);
    }

    // Rotate file if needed
    if (this._seq % 500 === 0) this._maybeRotate();

    // Ring buffer for API queries
    this._inMemory.push(entry);
    if (this._inMemory.length > this._bufferMax) {
      this._inMemory.shift();
    }

    // Console log for structured loggers
    console.log(`[AUDIT] ${entry.ts} seq=${entry.seq} event=${event} actor=${userId} status=${entry.status}`);

    return entry;
  }

  _maybeRotate() {
    if (!this._currentFile) return;
    try {
      const stat = fs.statSync(this._currentFile);
      const today = new Date().toISOString().slice(0, 10);
      const expected = path.join(this._logDir, `audit-${today}.jsonl`);
      if (stat.size >= this._maxSize || this._currentFile !== expected) {
        this._stream.end();
        this._openStream();
      }
    } catch { /* ignore stat errors */ }
  }

  // ── Query interface ───────────────────────────────────────────────────────

  getLast(n = 100) {
    return this._inMemory.slice(-n);
  }

  getByActor(userId, n = 100) {
    return this._inMemory.filter(e => e.actor === userId).slice(-n);
  }

  getByEvent(event, n = 100) {
    return this._inMemory.filter(e => e.event === event).slice(-n);
  }

  // ── Chain integrity verification ─────────────────────────────────────────

  verifyChain(entries) {
    let prevHash = '0'.repeat(64);
    const errors = [];
    for (const e of entries) {
      const { entry_hash, ...rest } = e;
      const expected = this._computeHash(rest);
      if (expected !== entry_hash) {
        errors.push({ seq: e.seq, ts: e.ts, error: 'hash_mismatch' });
      }
      if (e.prev_hash !== prevHash) {
        errors.push({ seq: e.seq, ts: e.ts, error: 'chain_broken' });
      }
      prevHash = entry_hash;
    }
    return { valid: errors.length === 0, errors };
  }
}

// ---------------------------------------------------------------------------
// Express middleware factory
// ---------------------------------------------------------------------------

function AuditMiddleware(resourceType) {
  return (req, res, next) => {
    const start = Date.now();
    const originalEnd = res.end.bind(res);

    res.end = function(...args) {
      const status = res.statusCode < 400 ? 'success' : 'failure';
      auditLog.record(`${resourceType}.${req.method.toLowerCase()}`, req, {
        status,
        resource:    resourceType,
        latency_ms:  Date.now() - start,
        http_status: res.statusCode,
      });
      return originalEnd(...args);
    };

    next();
  };
}

// ---------------------------------------------------------------------------
// Sanitise details — remove any PII / credentials
// ---------------------------------------------------------------------------

const REDACT_KEYS = new Set([
  'password', 'otp', 'secret', 'token', 'api_key', 'key_secret',
  'pan', 'aadhaar', 'card_number', 'cvv', 'account_number',
]);

function _sanitiseDetails(details) {
  const out = {};
  for (const [k, v] of Object.entries(details)) {
    if (REDACT_KEYS.has(k.toLowerCase())) {
      out[k] = '[REDACTED]';
    } else if (typeof v === 'string' && v.length > 200) {
      out[k] = v.slice(0, 200) + '…';
    } else {
      out[k] = v;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

const auditLog = new RBIAuditLogger();

module.exports = { auditLog, AuditMiddleware, AUDIT_EVENTS, RBIAuditLogger };
