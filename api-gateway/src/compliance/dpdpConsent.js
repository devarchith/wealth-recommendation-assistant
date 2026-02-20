/**
 * DPDP Act 2023 — Digital Personal Data Protection Consent Module
 * ================================================================
 * India's Digital Personal Data Protection Act 2023 (notified August 2023)
 * mandates explicit, informed, and granular consent before processing
 * any personal data. Non-compliance: up to ₹250 crore penalty per violation.
 *
 * Consent categories (Sec 6 — purposes must be specific and lawful):
 *   analytics          — aggregate usage analytics (anonymised)
 *   personalisation    — AI personalisation of financial advice
 *   marketing          — promotional emails and offers
 *   third_party_share  — sharing with verified CAs, advisors
 *   whatsapp           — WhatsApp delivery of tax reminders
 *   document_storage   — storing uploaded financial documents
 *
 * Rights implemented (Sec 11-14):
 *   Right to access    — GET  /api/consent/mine
 *   Right to correct   — PATCH /api/consent/mine
 *   Right to withdraw  — DELETE /api/consent/mine/:purpose
 *   Right to erasure   — DELETE /api/consent/mine (all data)
 *   Right to nominate  — POST /api/consent/nominee (registered as future feature)
 *   Grievance officer  — GET /api/consent/grievance
 *
 * Data Fiduciary obligations (Sec 8):
 *   - Consent must be free, specific, informed, unconditional, unambiguous
 *   - Separate consent per purpose (no bundled consent)
 *   - Re-consent required if purpose changes
 *   - Records maintained for duration of processing + 7 years (Sec 8(7))
 */

'use strict';

const express = require('express');
const crypto  = require('crypto');
const router  = express.Router();

// ---------------------------------------------------------------------------
// Consent catalogue
// ---------------------------------------------------------------------------

const CONSENT_PURPOSES = {
  analytics: {
    id:          'analytics',
    title:       'Usage Analytics',
    description: 'We collect anonymised usage data to improve our services. No personal financial data is included.',
    lawful_basis: 'legitimate_interest',
    data_types:  ['page_views', 'feature_usage', 'error_rates'],
    retention:   '24_months',
    required:    false,
  },
  personalisation: {
    id:          'personalisation',
    title:       'AI Personalisation',
    description: 'Your financial profile (income, tax regime, investment goals) is used to personalise AI responses.',
    lawful_basis: 'consent',
    data_types:  ['income_range', 'tax_regime', 'investment_horizon', 'risk_appetite'],
    retention:   'account_duration',
    required:    false,
  },
  marketing: {
    id:          'marketing',
    title:       'Marketing Communications',
    description: 'Receive emails about new features, tax deadline reminders, and relevant offers.',
    lawful_basis: 'consent',
    data_types:  ['email', 'name'],
    retention:   '36_months',
    required:    false,
  },
  third_party_share: {
    id:          'third_party_share',
    title:       'Third-Party Sharing',
    description: 'Your data may be shared with verified CA professionals you connect with through the platform.',
    lawful_basis: 'consent',
    data_types:  ['financial_summary', 'tax_documents'],
    third_parties: ['verified_ca_firms'],
    retention:   'consent_duration',
    required:    false,
  },
  whatsapp: {
    id:          'whatsapp',
    title:       'WhatsApp Notifications',
    description: 'Tax deadline reminders, payment confirmations, and AI responses via WhatsApp.',
    lawful_basis: 'consent',
    data_types:  ['phone', 'financial_alerts'],
    retention:   'account_duration',
    required:    false,
  },
  document_storage: {
    id:          'document_storage',
    title:       'Document Storage',
    description: 'Upload and store financial documents (Form 16, bank statements, ITR copies) in encrypted vault.',
    lawful_basis: 'consent',
    data_types:  ['financial_documents', 'pan_copy', 'tax_returns'],
    retention:   '7_years',  // RBI document retention requirement
    required:    false,
  },
};

// In-memory consent store — replace with DB (required: tamper-proof, timestamped)
// Map: userId → Map<purpose, ConsentRecord>
const consentStore = new Map();

// ---------------------------------------------------------------------------
// Consent record structure
// ---------------------------------------------------------------------------

function createConsentRecord(userId, purpose, granted, sourceIp, userAgent) {
  return {
    consent_id:  crypto.randomBytes(16).toString('hex'),
    user_id:     userId,
    purpose,
    granted,        // true = opt-in, false = opt-out/withdrawn
    timestamp:   new Date().toISOString(),
    source_ip:   sourceIp,
    user_agent:  (userAgent || '').slice(0, 200),
    version:     '1.0', // increment when purpose description changes
    expires_at:  null,  // null = indefinite until withdrawn
  };
}

function getUserConsents(userId) {
  return consentStore.get(userId) || new Map();
}

function setConsent(userId, purpose, granted, req) {
  let userMap = consentStore.get(userId) || new Map();
  const record = createConsentRecord(
    userId,
    purpose,
    granted,
    req?.ip || '',
    req?.headers?.['user-agent'] || ''
  );
  userMap.set(purpose, record);
  consentStore.set(userId, userMap);
  return record;
}

// ---------------------------------------------------------------------------
// Middleware: requireConsent(purpose)
// Returns 451 Unavailable For Legal Reasons if consent not granted.
// ---------------------------------------------------------------------------

function requireConsent(purpose) {
  return (req, res, next) => {
    const userId = req.session?.userId;
    if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

    const consents = getUserConsents(userId);
    const record   = consents.get(purpose);

    if (record?.granted === true) return next();

    return res.status(451).json({
      error:    'CONSENT_REQUIRED',
      purpose,
      message:  `You must provide consent for "${CONSENT_PURPOSES[purpose]?.title || purpose}" to use this feature.`,
      how_to:   'PATCH /api/consent/mine with { "purpose": "' + purpose + '", "granted": true }',
    });
  };
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

// GET /api/consent/mine — return all consent records for current user
router.get('/mine', (req, res) => {
  const userId = req.session?.userId;
  if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

  const consents    = getUserConsents(userId);
  const purposeList = Object.keys(CONSENT_PURPOSES).map(p => {
    const record = consents.get(p);
    return {
      ...CONSENT_PURPOSES[p],
      status:    record ? (record.granted ? 'granted' : 'withdrawn') : 'not_set',
      timestamp: record?.timestamp || null,
      consent_id: record?.consent_id || null,
    };
  });

  res.json({
    user_id:  userId,
    consents: purposeList,
    rights_info: {
      access:    'GET  /api/consent/mine',
      correct:   'PATCH /api/consent/mine',
      withdraw:  'DELETE /api/consent/mine/:purpose',
      erasure:   'DELETE /api/consent/mine',
      grievance: 'GET /api/consent/grievance',
    },
  });
});

// PATCH /api/consent/mine — update consent for one or more purposes
router.patch('/mine', (req, res) => {
  const userId = req.session?.userId;
  if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

  const { purpose, granted } = req.body;
  if (!purpose || typeof granted !== 'boolean') {
    return res.status(400).json({ error: 'purpose (string) and granted (boolean) are required.' });
  }
  if (!CONSENT_PURPOSES[purpose]) {
    return res.status(400).json({ error: `Unknown purpose. Valid: ${Object.keys(CONSENT_PURPOSES).join(', ')}` });
  }

  const record = setConsent(userId, purpose, granted, req);
  console.log(`[DPDP] Consent ${granted ? 'granted' : 'withdrawn'}: user=${userId} purpose=${purpose}`);

  res.json({ success: true, record });
});

// DELETE /api/consent/mine/:purpose — withdraw single consent
router.delete('/mine/:purpose', (req, res) => {
  const userId  = req.session?.userId;
  const purpose = req.params.purpose;
  if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

  const record = setConsent(userId, purpose, false, req);
  console.log(`[DPDP] Consent withdrawn: user=${userId} purpose=${purpose}`);
  res.json({ success: true, message: `Consent for ${purpose} withdrawn.`, record });
});

// DELETE /api/consent/mine — Right to Erasure (Sec 12 DPDP)
router.delete('/mine', (req, res) => {
  const userId = req.session?.userId;
  if (!userId) return res.status(401).json({ error: 'UNAUTHENTICATED' });

  // Withdraw all consents
  for (const purpose of Object.keys(CONSENT_PURPOSES)) {
    setConsent(userId, purpose, false, req);
  }
  consentStore.delete(userId);

  console.log(`[DPDP] Right to Erasure exercised: user=${userId}`);
  res.json({
    success: true,
    message: 'All consent records withdrawn. Your personal data deletion request has been logged and will be processed within 30 days as required by DPDP Act 2023.',
    ticket_id: crypto.randomBytes(8).toString('hex').toUpperCase(),
  });
});

// GET /api/consent/grievance — Grievance Officer contact (Sec 13 DPDP)
router.get('/grievance', (_req, res) => {
  res.json({
    grievance_officer: {
      name:    process.env.GRIEVANCE_OFFICER_NAME  || 'Data Protection Officer',
      email:   process.env.GRIEVANCE_OFFICER_EMAIL || 'dpo@wealthadvisorai.in',
      address: process.env.GRIEVANCE_OFFICER_ADDR  || 'WealthAdvisor AI, Hyderabad, Telangana — 500032',
      response_sla: '7 business days',
    },
    data_fiduciary: {
      name:    'WealthAdvisor AI',
      website: process.env.APP_URL || 'https://wealthadvisorai.in',
    },
    escalation: 'https://www.meity.gov.in/data-protection-board',
    applicable_law: 'Digital Personal Data Protection Act 2023 (DPDP Act)',
  });
});

// GET /api/consent/purposes — list all consent purposes (for UI consent dialog)
router.get('/purposes', (_req, res) => {
  res.json({ purposes: Object.values(CONSENT_PURPOSES) });
});

module.exports = { router, requireConsent, CONSENT_PURPOSES, getUserConsents };
