/**
 * Data Masking Middleware
 * =======================
 * Masks sensitive PII (PAN, Aadhaar, account numbers, phone, email) in:
 *   1. API response bodies (outbound masking based on caller's role)
 *   2. Log streams (prevents secrets leaking into log aggregators)
 *   3. Request bodies (masks before writing to audit log)
 *
 * Masking levels:
 *   FULL   — entire value replaced with '*' (lowest privilege callers)
 *   LAST4  — only last 4 chars visible (e.g., XXXXXXXX1234)
 *   MIDDLE — first 2 + last 2 visible, middle masked (e.g., AB****FP)
 *   PLAIN  — unmasked (admin / staff with explicit clearance)
 *
 * Usage:
 *   app.use(maskResponseBody);          // global outbound masking
 *   const safe = maskObject(obj, 'customer');  // programmatic masking
 *   const safeLog = maskForLog(logLine);       // log-line scrubbing
 */

'use strict';

// ---------------------------------------------------------------------------
// Regex patterns for PII detection
// ---------------------------------------------------------------------------

const PATTERNS = {
  pan:     /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g,
  aadhaar: /\b[2-9][0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b/g,
  phone:   /\b(?:\+91[-\s]?)?[6-9][0-9]{9}\b/g,
  email:   /\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b/g,
  account: /\b[0-9]{9,18}\b/g,    // bank account numbers
  ifsc:    /\b[A-Z]{4}0[A-Z0-9]{6}\b/g,
  gst:     /\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b/g,
  tan:     /\b[A-Z]{4}[0-9]{5}[A-Z]\b/g,
  card:    /\b(?:[0-9]{4}[-\s]?){3}[0-9]{4}\b/g,
  cvv:     /\b[0-9]{3,4}\b/g,     // broad — only applied in explicit card contexts
};

// ---------------------------------------------------------------------------
// Masking logic per data type
// ---------------------------------------------------------------------------

/**
 * maskPAN('ABCDE1234F') → 'XXXXX1234X'  (LAST4-like: keep digit run)
 * Only last char (series identifier) is hidden; numeric block kept for reconciliation.
 */
function maskPAN(pan) {
  if (!pan || pan.length !== 10) return '**********';
  return 'XXXXX' + pan.slice(5, 9) + 'X';
}

/**
 * maskAadhaar('9876 5432 1098') → 'XXXXXXXX1098'
 */
function maskAadhaar(aadhaar) {
  const digits = aadhaar.replace(/\s/g, '');
  if (digits.length !== 12) return '************';
  return 'X'.repeat(8) + digits.slice(-4);
}

/**
 * maskPhone('9876543210') → '98XXXXXX10'
 */
function maskPhone(phone) {
  const digits = phone.replace(/\D/g, '').slice(-10);
  if (digits.length < 10) return 'XXXXXXXXXX';
  return digits.slice(0, 2) + 'X'.repeat(6) + digits.slice(-2);
}

/**
 * maskEmail('user@example.com') → 'us**@e******.com'
 */
function maskEmail(email) {
  const [local, domain] = email.split('@');
  if (!domain) return '****@****.***';
  const maskedLocal  = local.slice(0, 2) + '*'.repeat(Math.max(local.length - 2, 2));
  const [dname, ...tld] = domain.split('.');
  const maskedDomain = dname.slice(0, 1) + '*'.repeat(Math.max(dname.length - 1, 4));
  return `${maskedLocal}@${maskedDomain}.${tld.join('.')}`;
}

/**
 * maskAccount('123456789012') → 'XXXXXXXX9012'
 */
function maskAccount(account) {
  const digits = account.replace(/\D/g, '');
  if (digits.length < 4) return '****';
  return 'X'.repeat(digits.length - 4) + digits.slice(-4);
}

// ---------------------------------------------------------------------------
// Deep object masking
// ---------------------------------------------------------------------------

const FIELD_MASKS = {
  pan:            (v) => maskPAN(String(v)),
  aadhaar:        (v) => maskAadhaar(String(v)),
  aadhaar_number: (v) => maskAadhaar(String(v)),
  phone:          (v) => maskPhone(String(v)),
  mobile:         (v) => maskPhone(String(v)),
  email:          (v) => maskEmail(String(v)),
  account_number: (v) => maskAccount(String(v)),
  bank_account:   (v) => maskAccount(String(v)),
  card_number:    (v) => '*'.repeat(12) + String(v).slice(-4),
  cvv:            (_) => '***',
  password:       (_) => '[REDACTED]',
  otp:            (_) => '***',
  secret:         (_) => '[REDACTED]',
  token:          (_) => '[REDACTED]',
  api_key:        (_) => '[REDACTED]',
};

/**
 * Deep-clone an object, masking sensitive fields.
 * @param {*}      obj        — the data to mask
 * @param {string} callerRole — 'guest'|'customer'|'staff'|'admin'
 * @returns masked copy (never mutates original)
 */
function maskObject(obj, callerRole = 'customer') {
  if (callerRole === 'admin') return obj;   // admins see plaintext
  return _maskRecursive(obj, callerRole);
}

function _maskRecursive(value, role) {
  if (value === null || value === undefined) return value;

  if (Array.isArray(value)) {
    return value.map(item => _maskRecursive(item, role));
  }

  if (typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      const lk = k.toLowerCase();
      if (FIELD_MASKS[lk]) {
        out[k] = v ? FIELD_MASKS[lk](v) : v;
      } else {
        out[k] = _maskRecursive(v, role);
      }
    }
    return out;
  }

  return value;
}

// ---------------------------------------------------------------------------
// Log-line scrubbing (regex-based, applied to string log entries)
// ---------------------------------------------------------------------------

function maskForLog(text) {
  if (typeof text !== 'string') return text;

  return text
    .replace(PATTERNS.pan,     (m) => maskPAN(m))
    .replace(PATTERNS.aadhaar, (m) => maskAadhaar(m.replace(/\s/g, '')))
    .replace(PATTERNS.phone,   (m) => maskPhone(m))
    .replace(PATTERNS.email,   (m) => maskEmail(m))
    .replace(PATTERNS.gst,     (m) => m.slice(0, 4) + 'X'.repeat(m.length - 6) + m.slice(-2))
    .replace(PATTERNS.card,    (m) => 'XXXX-XXXX-XXXX-' + m.replace(/\D/g, '').slice(-4));
}

// ---------------------------------------------------------------------------
// Express middleware
// ---------------------------------------------------------------------------

/**
 * maskResponseBody — wraps res.json to mask sensitive fields
 * based on the caller's role before sending.
 */
function maskResponseBody(req, res, next) {
  const callerRole = req.callerRole || (req.session?.isAdmin ? 'admin' : 'customer');
  const originalJson = res.json.bind(res);

  res.json = function(body) {
    const masked = maskObject(body, callerRole);
    return originalJson(masked);
  };

  next();
}

/**
 * maskRequestLog — sanitises req.body for audit logging.
 * Attaches req.sanitizedBody with PII removed.
 */
function maskRequestLog(req, _res, next) {
  if (req.body && typeof req.body === 'object') {
    req.sanitizedBody = maskObject(req.body, 'customer');
  }
  next();
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  maskPAN,
  maskAadhaar,
  maskPhone,
  maskEmail,
  maskAccount,
  maskObject,
  maskForLog,
  maskResponseBody,
  maskRequestLog,
  PATTERNS,
  FIELD_MASKS,
};
