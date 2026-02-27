/**
 * Two-Factor Authentication (2FA) Middleware
 * ============================================
 * Enforces OTP-based 2FA for all privileged user operations:
 *   - Plan upgrades and billing changes
 *   - CA client data access
 *   - Document vault operations
 *   - Admin dashboard routes
 *   - Profile PAN/Aadhaar updates
 *
 * Flow:
 *   1. Client hits protected endpoint
 *   2. Middleware checks session for `twofa_verified_at` (valid for 30 min)
 *   3. If absent/expired → 428 Precondition Required with challenge_id
 *   4. Client calls POST /api/auth/2fa/challenge → OTP sent via SMS/TOTP
 *   5. Client calls POST /api/auth/2fa/verify   → session marked verified
 *   6. Retry original request within 30-minute window
 *
 * Routes (registered on authRouter):
 *   POST /api/auth/2fa/challenge  — issue OTP
 *   POST /api/auth/2fa/verify     — verify OTP, stamp session
 *   DELETE /api/auth/2fa/session  — revoke 2FA session (logout-level action)
 */

'use strict';

const crypto  = require('crypto');
const express = require('express');
const router  = express.Router();

const TWOFA_VALIDITY_MS = 30 * 60 * 1000; // 30 minutes
const OTP_VALIDITY_MS   = 5  * 60 * 1000; // 5 minutes for challenge
const MAX_ATTEMPTS      = 5;

const MSG91_AUTH_KEY    = process.env.MSG91_AUTH_KEY    || '';
const MSG91_TEMPLATE_2FA= process.env.MSG91_TEMPLATE_2FA|| process.env.MSG91_TEMPLATE_ID || '';

// In-memory store — replace with Redis in production
const challengeStore = new Map(); // challengeId → { otp, phone, userId, expiresAt, attempts }

// ---------------------------------------------------------------------------
// OTP generation (reuses crypto approach from auth.js)
// ---------------------------------------------------------------------------

function generateOTP(length = 6) {
  const bytes = crypto.randomBytes(length);
  let otp = '';
  for (let i = 0; i < length; i++) otp += bytes[i] % 10;
  return otp;
}

async function sendOTP(phone, otp, purpose = '2FA') {
  if (!MSG91_AUTH_KEY) {
    console.log(`[2FA] OTP for ${phone}: ${otp} (MSG91 not configured)`);
    return true;
  }
  try {
    const fetch = (await import('node-fetch')).default;
    const res = await fetch('https://api.msg91.com/api/v5/otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', authkey: MSG91_AUTH_KEY },
      body: JSON.stringify({
        template_id: MSG91_TEMPLATE_2FA,
        mobile:      `91${phone}`,
        otp,
      }),
    });
    return res.ok;
  } catch (err) {
    console.error('[2FA] OTP send error:', err.message);
    return false;
  }
}

// ---------------------------------------------------------------------------
// POST /2fa/challenge
// ---------------------------------------------------------------------------

router.post('/challenge', async (req, res) => {
  const userId = req.session?.userId;
  if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

  const phone = req.session.phone || req.body.phone;
  if (!phone) {
    return res.status(400).json({
      error: 'PHONE_REQUIRED',
      message: 'Phone number required for 2FA. Update your profile to add a phone number.',
    });
  }

  const otp         = generateOTP();
  const challengeId = crypto.randomBytes(16).toString('hex');

  challengeStore.set(challengeId, {
    otp,
    phone,
    userId,
    expiresAt: Date.now() + OTP_VALIDITY_MS,
    attempts:  0,
  });

  const sent = await sendOTP(phone, otp);
  if (!sent) {
    challengeStore.delete(challengeId);
    return res.status(503).json({ error: 'OTP_SEND_FAILED', message: 'Could not send OTP. Try again.' });
  }

  // GC expired challenges
  for (const [id, ch] of challengeStore) {
    if (Date.now() > ch.expiresAt) challengeStore.delete(id);
  }

  res.json({
    challenge_id: challengeId,
    message:      `2FA OTP sent to +91${phone.slice(-4).padStart(phone.length, 'X')}. Valid for 5 minutes.`,
    expires_in:   300,
  });
});

// ---------------------------------------------------------------------------
// POST /2fa/verify
// ---------------------------------------------------------------------------

router.post('/verify', (req, res) => {
  const { challenge_id, otp } = req.body;
  const userId = req.session?.userId;

  if (!userId)      return res.status(401).json({ error: 'UNAUTHENTICATED' });
  if (!challenge_id || !otp) {
    return res.status(400).json({ error: 'challenge_id and otp are required.' });
  }

  const challenge = challengeStore.get(challenge_id);
  if (!challenge) {
    return res.status(400).json({ error: 'CHALLENGE_NOT_FOUND', message: 'OTP expired or invalid. Request a new one.' });
  }
  if (challenge.userId !== userId) {
    return res.status(403).json({ error: 'CHALLENGE_USER_MISMATCH' });
  }
  if (Date.now() > challenge.expiresAt) {
    challengeStore.delete(challenge_id);
    return res.status(400).json({ error: 'OTP_EXPIRED', message: 'OTP expired. Request a new one.' });
  }

  challenge.attempts++;
  if (challenge.attempts > MAX_ATTEMPTS) {
    challengeStore.delete(challenge_id);
    return res.status(429).json({ error: 'TOO_MANY_ATTEMPTS', message: 'Request a new OTP.' });
  }
  if (challenge.otp !== String(otp)) {
    return res.status(400).json({
      error: 'INCORRECT_OTP',
      attempts_remaining: MAX_ATTEMPTS - challenge.attempts,
    });
  }

  challengeStore.delete(challenge_id);

  // Stamp session
  req.session.twofa_verified_at = Date.now();
  req.session.twofa_phone       = challenge.phone;

  res.json({ success: true, message: '2FA verified. Elevated access granted for 30 minutes.' });
});

// ---------------------------------------------------------------------------
// DELETE /2fa/session  — revoke elevated access
// ---------------------------------------------------------------------------

router.delete('/session', (req, res) => {
  if (req.session) {
    delete req.session.twofa_verified_at;
    delete req.session.twofa_phone;
  }
  res.json({ success: true, message: '2FA session revoked.' });
});

// ---------------------------------------------------------------------------
// Middleware: require2FA
// Attach to routes that need elevated access.
// ---------------------------------------------------------------------------

function require2FA(req, res, next) {
  if (!req.session?.userId) {
    return res.status(401).json({ error: 'UNAUTHENTICATED' });
  }

  const verifiedAt = req.session.twofa_verified_at;
  if (verifiedAt && Date.now() - verifiedAt < TWOFA_VALIDITY_MS) {
    return next();
  }

  // Trigger challenge
  return res.status(428).json({
    error:   '2FA_REQUIRED',
    message: 'This action requires two-factor authentication. Request a challenge and verify your OTP.',
    steps: [
      'POST /api/auth/2fa/challenge  (sends OTP to your registered phone)',
      'POST /api/auth/2fa/verify     (submit challenge_id + otp)',
      'Retry the original request within 30 minutes.',
    ],
  });
}

module.exports = { router: router, require2FA };
