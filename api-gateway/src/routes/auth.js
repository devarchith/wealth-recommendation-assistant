/**
 * Authentication Routes
 * Supports:
 *   1. Google OAuth 2.0 (Passport.js)
 *   2. Phone OTP (SMS via MSG91 / Twilio)
 *   3. Session management (express-session)
 *
 * Routes:
 *   GET  /api/auth/google           — Initiate Google OAuth
 *   GET  /api/auth/google/callback  — OAuth callback
 *   POST /api/auth/otp/send         — Send OTP to phone number
 *   POST /api/auth/otp/verify       — Verify OTP
 *   GET  /api/auth/me               — Get current user
 *   POST /api/auth/logout           — Logout
 */

'use strict';

const express  = require('express');
const router   = express.Router();
const crypto   = require('crypto');

// In production: use passport-google-oauth20, MSG91 SDK, and a real DB.
// This module provides the route skeleton + OTP logic without external deps.

const GOOGLE_CLIENT_ID     = process.env.GOOGLE_CLIENT_ID     || '';
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || '';
const MSG91_AUTH_KEY       = process.env.MSG91_AUTH_KEY        || '';
const MSG91_TEMPLATE_ID    = process.env.MSG91_TEMPLATE_ID     || '';
const OTP_VALIDITY_MS      = 10 * 60 * 1000; // 10 minutes

// In-memory OTP store — replace with Redis in production
const otpStore = new Map(); // phone → {otp, expiresAt, attempts}

// Simulated user store — replace with DB
const userStore = new Map();

// ---------------------------------------------------------------------------
// OTP utilities
// ---------------------------------------------------------------------------

function generateOTP(length = 6) {
  const digits = '0123456789';
  let otp = '';
  const randomBytes = crypto.randomBytes(length);
  for (let i = 0; i < length; i++) {
    otp += digits[randomBytes[i] % 10];
  }
  return otp;
}

async function sendOTPSMS(phone, otp) {
  if (!MSG91_AUTH_KEY) {
    // Development: log OTP to console
    console.log(`[Auth] OTP for ${phone}: ${otp} (MSG91 not configured)`);
    return true;
  }
  try {
    const fetch = (await import('node-fetch')).default;
    const res = await fetch(`https://api.msg91.com/api/v5/otp`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'authkey': MSG91_AUTH_KEY,
      },
      body: JSON.stringify({
        template_id: MSG91_TEMPLATE_ID,
        mobile:      `91${phone}`,
        otp,
      }),
    });
    return res.ok;
  } catch (err) {
    console.error('[Auth] OTP send error:', err.message);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Google OAuth — skeleton (requires passport + passport-google-oauth20)
// ---------------------------------------------------------------------------

router.get('/google', (req, res) => {
  if (!GOOGLE_CLIENT_ID) {
    return res.status(503).json({
      error: 'GOOGLE_OAUTH_NOT_CONFIGURED',
      message: 'Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env to enable Google login.',
    });
  }
  const params = new URLSearchParams({
    client_id:     GOOGLE_CLIENT_ID,
    redirect_uri:  `${process.env.APP_URL || 'http://localhost:3001'}/api/auth/google/callback`,
    response_type: 'code',
    scope:         'openid email profile',
    state:         crypto.randomBytes(16).toString('hex'),
  });
  res.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
});

router.get('/google/callback', async (req, res) => {
  const { code, state } = req.query;
  if (!code) return res.redirect('/?auth=error');

  try {
    const fetch = (await import('node-fetch')).default;
    // Exchange code for tokens
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id:     GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri:  `${process.env.APP_URL || 'http://localhost:3001'}/api/auth/google/callback`,
        grant_type:    'authorization_code',
      }),
    });
    const tokens = await tokenRes.json();
    if (!tokens.id_token) return res.redirect('/?auth=error');

    // Decode id_token (JWT — base64 payload)
    const payload = JSON.parse(
      Buffer.from(tokens.id_token.split('.')[1], 'base64url').toString()
    );
    const userId  = payload.sub;
    const email   = payload.email;
    const name    = payload.name;

    // Upsert user
    if (!userStore.has(userId)) {
      userStore.set(userId, {
        id:       userId,
        email,
        name,
        plan:     'free',
        created_at: new Date().toISOString(),
        auth_method: 'google',
      });
    }

    req.session.userId    = userId;
    req.session.userEmail = email;
    req.session.userName  = name;
    req.session.plan      = userStore.get(userId).plan;

    res.redirect('/?auth=success');
  } catch (err) {
    console.error('[Auth] Google callback error:', err.message);
    res.redirect('/?auth=error');
  }
});

// ---------------------------------------------------------------------------
// Phone OTP
// ---------------------------------------------------------------------------

router.post('/otp/send', async (req, res) => {
  const { phone } = req.body;
  if (!phone || !/^[6-9]\d{9}$/.test(phone)) {
    return res.status(400).json({ error: 'Invalid Indian phone number (10 digits, starts with 6-9).' });
  }

  const existing = otpStore.get(phone);
  if (existing && Date.now() - (existing.expiresAt - OTP_VALIDITY_MS) < 60_000) {
    return res.status(429).json({ error: 'OTP already sent. Wait 60 seconds before retrying.' });
  }

  const otp = generateOTP();
  otpStore.set(phone, { otp, expiresAt: Date.now() + OTP_VALIDITY_MS, attempts: 0 });

  const sent = await sendOTPSMS(phone, otp);
  if (!sent) {
    return res.status(503).json({ error: 'Failed to send OTP. Try again.' });
  }

  res.json({ success: true, message: `OTP sent to +91${phone}. Valid for 10 minutes.` });
});

router.post('/otp/verify', (req, res) => {
  const { phone, otp } = req.body;
  if (!phone || !otp) {
    return res.status(400).json({ error: 'phone and otp are required.' });
  }

  const record = otpStore.get(phone);
  if (!record) {
    return res.status(400).json({ error: 'OTP not found or expired. Request a new one.' });
  }
  if (Date.now() > record.expiresAt) {
    otpStore.delete(phone);
    return res.status(400).json({ error: 'OTP expired. Request a new one.' });
  }

  record.attempts++;
  if (record.attempts > 5) {
    otpStore.delete(phone);
    return res.status(429).json({ error: 'Too many attempts. Request a new OTP.' });
  }
  if (record.otp !== String(otp)) {
    return res.status(400).json({ error: 'Incorrect OTP.', attempts_remaining: 5 - record.attempts });
  }

  otpStore.delete(phone);

  // Upsert user
  const userId = `phone_${phone}`;
  if (!userStore.has(userId)) {
    userStore.set(userId, {
      id:          userId,
      phone,
      plan:        'free',
      created_at:  new Date().toISOString(),
      auth_method: 'otp',
    });
  }

  req.session.userId = userId;
  req.session.phone  = phone;
  req.session.plan   = userStore.get(userId).plan;

  res.json({ success: true, user_id: userId, plan: 'free' });
});

// ---------------------------------------------------------------------------
// Current user
// ---------------------------------------------------------------------------

router.get('/me', (req, res) => {
  if (!req.session?.userId) {
    return res.status(401).json({ authenticated: false });
  }
  const user = userStore.get(req.session.userId) || {};
  res.json({
    authenticated: true,
    user_id:       req.session.userId,
    email:         req.session.userEmail || user.email,
    name:          req.session.userName  || user.name,
    phone:         req.session.phone     || user.phone,
    plan:          req.session.plan      || user.plan || 'free',
  });
});

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

router.post('/logout', (req, res) => {
  req.session.destroy(() => {
    res.clearCookie('connect.sid');
    res.json({ success: true });
  });
});

module.exports = router;
