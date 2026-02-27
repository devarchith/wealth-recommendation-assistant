/**
 * Session Manager — IP Whitelisting, Device Fingerprinting, Timeout
 * ==================================================================
 * Provides enterprise-grade session security:
 *
 *  1. IP Binding     — sessions are bound to the originating IP.
 *                      Requests from a new IP invalidate the session.
 *  2. IP Whitelist   — optional per-user trusted IP list (CA/Business plans)
 *  3. Idle Timeout   — sessions expire after configurable inactivity
 *  4. Absolute TTL   — hard 8-hour session cap regardless of activity
 *  5. Device Fp      — User-Agent fingerprint mismatch triggers re-auth
 *  6. Concurrent Limit — CA plan: max 5 concurrent sessions per user
 *  7. Session Audit  — every request updates last_active + IP log
 *
 * Usage:
 *   const { sessionSecurity } = require('./sessionManager');
 *   app.use(sessionSecurity);           // global
 *
 *   // Per-user IP whitelist (stored in user profile in DB):
 *   await setWhitelist(userId, ['203.0.113.10', '198.51.100.0/24']);
 */

'use strict';

const crypto = require('crypto');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const IDLE_TIMEOUT_MS      = parseInt(process.env.SESSION_IDLE_MS      || String(30 * 60 * 1000));  // 30 min
const ABSOLUTE_TTL_MS      = parseInt(process.env.SESSION_ABSOLUTE_MS  || String(8  * 60 * 60 * 1000)); // 8 hr
const MAX_SESSIONS_PER_USER= parseInt(process.env.MAX_SESSIONS_PER_USER|| '5');
const BIND_TO_IP           = process.env.SESSION_IP_BINDING !== 'false'; // default: true

// In-memory session registry — replace with Redis in production
// Map: userId → [{sessionId, ip, ua_fp, created_at, last_active}]
const sessionRegistry = new Map();

// Per-user IP whitelists — replace with DB
const ipWhitelists = new Map(); // userId → Set<string>

// ---------------------------------------------------------------------------
// CIDR helpers (IPv4 only — covers most Indian ISP cases)
// ---------------------------------------------------------------------------

function ipToCIDRInt(ip) {
  return ip.split('.').reduce((acc, octet) => (acc << 8) + parseInt(octet, 10), 0) >>> 0;
}

function isInCIDR(ip, cidr) {
  if (!cidr.includes('/')) return ip === cidr;
  const [base, bits] = cidr.split('/');
  const mask = (~0 << (32 - parseInt(bits, 10))) >>> 0;
  return (ipToCIDRInt(ip) & mask) === (ipToCIDRInt(base) & mask);
}

function isIPAllowed(ip, whitelist) {
  if (!whitelist || whitelist.size === 0) return true; // no whitelist = allow all
  for (const entry of whitelist) {
    if (isInCIDR(ip, entry)) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Device fingerprint (coarse — User-Agent hash)
// ---------------------------------------------------------------------------

function fingerprintUA(userAgent) {
  return crypto.createHash('sha256').update(userAgent || '').digest('hex').slice(0, 16);
}

// ---------------------------------------------------------------------------
// Session registry operations
// ---------------------------------------------------------------------------

function registerSession(userId, sessionId, ip, userAgent) {
  const sessions = sessionRegistry.get(userId) || [];

  // Enforce concurrent session limit
  if (sessions.length >= MAX_SESSIONS_PER_USER) {
    // Evict oldest session
    sessions.sort((a, b) => a.last_active - b.last_active);
    sessions.shift();
  }

  sessions.push({
    sessionId,
    ip,
    ua_fp:       fingerprintUA(userAgent),
    created_at:  Date.now(),
    last_active: Date.now(),
  });

  sessionRegistry.set(userId, sessions);
}

function touchSession(userId, sessionId, ip) {
  const sessions = sessionRegistry.get(userId) || [];
  const entry    = sessions.find(s => s.sessionId === sessionId);
  if (entry) {
    entry.last_active = Date.now();
    entry.ip          = ip; // track latest IP for audit
  }
}

function removeSession(userId, sessionId) {
  const sessions = (sessionRegistry.get(userId) || []).filter(s => s.sessionId !== sessionId);
  sessionRegistry.set(userId, sessions);
}

function getSessionEntry(userId, sessionId) {
  return (sessionRegistry.get(userId) || []).find(s => s.sessionId === sessionId);
}

// ---------------------------------------------------------------------------
// Main session security middleware
// ---------------------------------------------------------------------------

function sessionSecurity(req, res, next) {
  const session = req.session;
  if (!session?.userId) return next(); // unauthenticated — skip

  const userId    = session.userId;
  const ip        = req.ip || req.connection?.remoteAddress || '';
  const userAgent = req.headers['user-agent'] || '';
  const sessionId = session.id;

  // ── First visit after login: register session ──────────────────────────
  if (!session._registered) {
    registerSession(userId, sessionId, ip, userAgent);
    session._registered    = true;
    session._created_at    = Date.now();
    session._last_active   = Date.now();
    session._bound_ip      = ip;
    session._ua_fp         = fingerprintUA(userAgent);
    return next();
  }

  // ── Absolute TTL check ─────────────────────────────────────────────────
  if (session._created_at && Date.now() - session._created_at > ABSOLUTE_TTL_MS) {
    removeSession(userId, sessionId);
    return session.destroy(() => {
      res.clearCookie('connect.sid');
      res.status(401).json({ error: 'SESSION_EXPIRED', message: 'Session has exceeded 8-hour limit. Please log in again.' });
    });
  }

  // ── Idle timeout check ─────────────────────────────────────────────────
  if (session._last_active && Date.now() - session._last_active > IDLE_TIMEOUT_MS) {
    removeSession(userId, sessionId);
    return session.destroy(() => {
      res.clearCookie('connect.sid');
      res.status(401).json({ error: 'SESSION_IDLE_TIMEOUT', message: 'Session expired due to inactivity. Please log in again.' });
    });
  }

  // ── IP binding check ───────────────────────────────────────────────────
  if (BIND_TO_IP && session._bound_ip && session._bound_ip !== ip) {
    const whitelist = ipWhitelists.get(userId);
    if (!isIPAllowed(ip, whitelist)) {
      console.warn(`[SessionManager] IP mismatch for user ${userId}: bound=${session._bound_ip} current=${ip}`);
      removeSession(userId, sessionId);
      return session.destroy(() => {
        res.clearCookie('connect.sid');
        res.status(401).json({
          error:   'IP_MISMATCH',
          message: 'Session originated from a different IP. Please log in again.',
        });
      });
    }
  }

  // ── Device fingerprint check ───────────────────────────────────────────
  const currentFp = fingerprintUA(userAgent);
  if (session._ua_fp && session._ua_fp !== currentFp) {
    console.warn(`[SessionManager] UA fingerprint mismatch for user ${userId}`);
    removeSession(userId, sessionId);
    return session.destroy(() => {
      res.clearCookie('connect.sid');
      res.status(401).json({
        error:   'DEVICE_CHANGED',
        message: 'Browser or device changed. Please log in again.',
      });
    });
  }

  // ── IP whitelist check ─────────────────────────────────────────────────
  const whitelist = ipWhitelists.get(userId);
  if (whitelist && whitelist.size > 0 && !isIPAllowed(ip, whitelist)) {
    return res.status(403).json({
      error:   'IP_NOT_WHITELISTED',
      message: 'Your current IP is not in the allowed list for this account.',
    });
  }

  // ── All checks passed — refresh last_active ────────────────────────────
  session._last_active = Date.now();
  touchSession(userId, sessionId, ip);

  next();
}

// ---------------------------------------------------------------------------
// API helpers for IP whitelist management
// ---------------------------------------------------------------------------

function setWhitelist(userId, ips) {
  ipWhitelists.set(userId, new Set(ips));
}

function addToWhitelist(userId, ip) {
  const wl = ipWhitelists.get(userId) || new Set();
  wl.add(ip);
  ipWhitelists.set(userId, wl);
}

function removeFromWhitelist(userId, ip) {
  const wl = ipWhitelists.get(userId);
  if (wl) wl.delete(ip);
}

function getUserSessions(userId) {
  return sessionRegistry.get(userId) || [];
}

function terminateSession(userId, sessionId) {
  removeSession(userId, sessionId);
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  sessionSecurity,
  setWhitelist,
  addToWhitelist,
  removeFromWhitelist,
  getUserSessions,
  terminateSession,
  registerSession,
};
