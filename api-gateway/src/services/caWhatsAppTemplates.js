/**
 * CA WhatsApp Message Templates — Deadline Reminders & Compliance Alerts
 * ========================================================================
 * Generates WhatsApp message text for CA firms to send to their clients.
 * Integrates with the existing whatsapp.js webhook — messages are sent
 * via the Meta Cloud API v19.0 using the sendWAMessage() utility.
 *
 * Template categories:
 *  1. GST return deadline reminders (GSTR-1, GSTR-3B, GSTR-9)
 *  2. ITR filing deadline reminders
 *  3. Tax notice acknowledgement alerts
 *  4. Document collection requests
 *  5. Advance tax due date reminders
 *  6. Invoice payment reminders (CA fee)
 *  7. Compliance status updates
 *
 * Languages: English (active) | Telugu (translations present, Coming Soon)
 *
 * Usage:
 *   const { buildTemplate, sendCAReminder } = require('./caWhatsAppTemplates');
 *   const msg = buildTemplate('gst_deadline', { clientName, returnType, dueDate, daysLeft });
 *   await sendCAReminder(phoneNumber, msg);
 */

'use strict';

const axios = require('axios');

const WA_API_BASE  = process.env.WA_API_BASE  || 'https://graph.facebook.com/v19.0';
const WA_PHONE_ID  = process.env.WA_PHONE_ID  || '';
const WA_TOKEN     = process.env.WA_TOKEN     || '';

// ---------------------------------------------------------------------------
// Template definitions — English
// ---------------------------------------------------------------------------

const TEMPLATES_EN = {

  // --- GST ---
  gst_deadline: ({ clientName, returnType, period, dueDate, daysLeft, lateFee }) => {
    const urgency = daysLeft <= 0  ? '🔴 OVERDUE'
                  : daysLeft <= 3  ? '🔴 URGENT'
                  : daysLeft <= 7  ? '🟠 Due Soon'
                  : '🟢 Reminder';
    const lateNote = (lateFee && lateFee > 0)
      ? `\n⚠️ Late fee already accrued: ₹${lateFee.toLocaleString('en-IN')}`
      : '';
    return (
      `${urgency} | GST Filing Reminder\n\n` +
      `Dear ${clientName},\n\n` +
      `Your *${returnType}* for the period *${period}* is due on *${dueDate}*.\n` +
      (daysLeft > 0
        ? `You have *${daysLeft} day(s)* remaining to file.`
        : `Filing is *${Math.abs(daysLeft)} day(s) overdue*.`) +
      lateNote +
      `\n\nPlease ensure your sales/purchase data is ready and shared with us at the earliest.\n\n` +
      `For assistance, reply *HELP* or call your CA directly.\n\n` +
      `_Powered by WealthAdvisor AI — CA Portal_`
    );
  },

  gst_filed_confirm: ({ clientName, returnType, period, ackNo, filedDate }) => (
    `✅ GST Filing Confirmed\n\n` +
    `Dear ${clientName},\n\n` +
    `Your *${returnType}* for *${period}* has been successfully filed on *${filedDate}*.\n\n` +
    `*Acknowledgement No:* ${ackNo}\n\n` +
    `Keep this number for your records. No further action is required from your end.\n\n` +
    `_WealthAdvisor AI — CA Portal_`
  ),

  gst_late_fee_alert: ({ clientName, returnType, period, daysLate, lateFee }) => (
    `⚠️ Late Fee Alert — GST\n\n` +
    `Dear ${clientName},\n\n` +
    `Your *${returnType}* for *${period}* is *${daysLate} day(s) overdue*.\n\n` +
    `*Estimated Late Fee:* ₹${lateFee.toLocaleString('en-IN')}\n\n` +
    `Late fee continues to accumulate at ₹50/day. Please file immediately to limit the penalty.\n\n` +
    `Reply *FILE NOW* to start the process or call your CA.\n\n` +
    `_WealthAdvisor AI — CA Portal_`
  ),

  // --- ITR ---
  itr_deadline: ({ clientName, itrForm, ay, dueDate, daysLeft, isAudit }) => {
    const category = isAudit ? 'Audit Client' : 'Non-Audit';
    return (
      `📋 ITR Filing Reminder — ${ay}\n\n` +
      `Dear ${clientName},\n\n` +
      `Your Income Tax Return (*${itrForm}*) for *${ay}* [${category}] is due by *${dueDate}*.\n\n` +
      (daysLeft > 0
        ? `*${daysLeft} day(s) remaining.* Please complete document submission at the earliest.`
        : `⚠️ Deadline has passed. A *belated return* can still be filed by 31 December 2025 with interest u/s 234A.`) +
      `\n\nDocuments needed: Form 16, AIS/26AS, bank statements, investment proofs.\n\n` +
      `Reply *STATUS* to check your filing progress.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },

  itr_filed_confirm: ({ clientName, itrForm, ay, ackNo, filedDate, refundDue, taxPayable }) => {
    const financialNote = refundDue > 0
      ? `*Expected Refund:* ₹${refundDue.toLocaleString('en-IN')}`
      : taxPayable > 0
        ? `*Tax Paid:* ₹${taxPayable.toLocaleString('en-IN')}`
        : '';
    return (
      `✅ ITR Filed Successfully — ${ay}\n\n` +
      `Dear ${clientName},\n\n` +
      `Your *${itrForm}* for *${ay}* has been successfully filed on *${filedDate}*.\n\n` +
      `*Acknowledgement No:* ${ackNo}\n` +
      (financialNote ? financialNote + '\n' : '') +
      `\n*Next Step:* E-verify your return within 30 days via:\n` +
      `  • Net banking\n  • Aadhaar OTP\n  • DSC\n\n` +
      `Reply *VERIFY* for step-by-step e-verification guide.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },

  itr_docs_pending: ({ clientName, missingDocs }) => {
    const docList = missingDocs.slice(0, 5).map((d, i) => `  ${i + 1}. ${d}`).join('\n');
    return (
      `📂 Documents Pending — ITR Filing\n\n` +
      `Dear ${clientName},\n\n` +
      `We are in the process of preparing your Income Tax Return. The following documents are *pending*:\n\n` +
      docList +
      (missingDocs.length > 5 ? `\n  ... and ${missingDocs.length - 5} more` : '') +
      `\n\nPlease share these at the earliest to avoid last-minute delays.\n\n` +
      `You can WhatsApp the documents to this number or email to your CA directly.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },

  // --- Tax Notice ---
  notice_received: ({ clientName, noticeType, noticeDate, ay, responseDue, urgency }) => {
    const urgencyEmoji = urgency === 'critical' ? '🚨' : urgency === 'high' ? '⚠️' : '📋';
    return (
      `${urgencyEmoji} Income Tax Notice — Action Required\n\n` +
      `Dear ${clientName},\n\n` +
      `We have received / noted a tax notice on your behalf:\n\n` +
      `*Notice Type:* Section ${noticeType}\n` +
      `*Date of Notice:* ${noticeDate}\n` +
      `*Assessment Year:* ${ay}\n` +
      `*Response Due By:* ${responseDue}\n\n` +
      `Our CA team is preparing the response. Please do NOT respond directly to the department without consulting us.\n\n` +
      `We will share the draft response for your approval shortly.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },

  notice_response_ready: ({ clientName, noticeType, ay, draftReady, responseDue }) => (
    `✍️ Notice Response Ready for Review\n\n` +
    `Dear ${clientName},\n\n` +
    `The draft response to your Income Tax Notice (Section *${noticeType}*, *${ay}*) is ready.\n\n` +
    `*Draft Prepared On:* ${draftReady}\n` +
    `*Response Deadline:* ${responseDue}\n\n` +
    `Please review and approve the draft at the earliest so we can file before the deadline.\n\n` +
    `Reply *APPROVE* to proceed or *REVIEW* to schedule a call.\n\n` +
    `_WealthAdvisor AI — CA Portal_`
  ),

  // --- Advance Tax ---
  advance_tax: ({ clientName, installment, dueDate, estimatedAmount, daysLeft }) => {
    const installmentNames = { jun: '1st (15%)', sep: '2nd (45%)', dec: '3rd (75%)', mar: '4th (100%)' };
    const label = installmentNames[installment] || installment;
    return (
      `💰 Advance Tax Reminder — ${label} Instalment\n\n` +
      `Dear ${clientName},\n\n` +
      `The *${label} instalment* of Advance Tax is due on *${dueDate}*.\n\n` +
      (estimatedAmount
        ? `*Estimated Amount:* ₹${estimatedAmount.toLocaleString('en-IN')}\n\n`
        : '') +
      (daysLeft > 0
        ? `${daysLeft} day(s) remaining. `
        : `Payment is overdue — interest u/s 234B/C is applicable. `) +
      `Pay via Challan 280 (online or bank) and share the challan with us.\n\n` +
      `Reply *HOW* for payment instructions.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },

  // --- CA Invoice ---
  invoice_reminder: ({ clientName, invoiceNo, invoiceDate, amount, dueDate, daysLeft }) => (
    `🧾 Invoice Reminder — CA Professional Fees\n\n` +
    `Dear ${clientName},\n\n` +
    `This is a reminder for the following outstanding invoice:\n\n` +
    `*Invoice No:* ${invoiceNo}\n` +
    `*Invoice Date:* ${invoiceDate}\n` +
    `*Amount Due:* ₹${amount.toLocaleString('en-IN')} (incl. 18% GST)\n` +
    `*Payment Due By:* ${dueDate}\n\n` +
    (daysLeft >= 0
      ? `${daysLeft === 0 ? 'Payment is due *today*.' : `${daysLeft} day(s) remaining.`}`
      : `Payment is *${Math.abs(daysLeft)} day(s) overdue*.`) +
    `\n\nPayment methods: NEFT/RTGS, UPI, or Razorpay link (shared separately).\n\n` +
    `For queries, reply *INVOICE* or contact your CA.\n\n` +
    `_WealthAdvisor AI — CA Portal_`
  ),

  // --- General Compliance ---
  compliance_health: ({ clientName, healthScore, pendingItems, criticalItems }) => {
    const scoreEmoji = healthScore >= 80 ? '🟢' : healthScore >= 50 ? '🟡' : '🔴';
    const criticalNote = criticalItems > 0
      ? `\n⚠️ *${criticalItems} critical item(s)* require immediate attention.`
      : '';
    return (
      `${scoreEmoji} Monthly Compliance Summary\n\n` +
      `Dear ${clientName},\n\n` +
      `Here is your compliance health summary for this month:\n\n` +
      `*Health Score:* ${healthScore}/100 ${scoreEmoji}\n` +
      `*Pending Items:* ${pendingItems}` +
      criticalNote +
      `\n\nReply *DETAILS* to see the full compliance checklist or contact your CA for assistance.\n\n` +
      `_WealthAdvisor AI — CA Portal_`
    );
  },
};

// ---------------------------------------------------------------------------
// Telugu translations (present in codebase; Coming Soon — not activated)
// ---------------------------------------------------------------------------

const TEMPLATES_TE = {
  gst_deadline: ({ clientName, returnType, period, dueDate, daysLeft }) => (
    `GST రిటర్న్ గుర్తుచేపు\n\n` +
    `ప్రియమైన ${clientName},\n\n` +
    `మీ *${returnType}* (${period}) గడువు తేదీ *${dueDate}*.\n` +
    (daysLeft > 0 ? `${daysLeft} రోజులు మిగిలాయి.` : `గడువు దాటిపోయింది.`) +
    `\n\nదయచేసి మీ CA కి అవసరమైన డేటా అందించండి.\n\n` +
    `_WealthAdvisor AI — CA Portal_`
  ),
  itr_deadline: ({ clientName, itrForm, ay, dueDate, daysLeft }) => (
    `ITR దాఖలు గుర్తుచేపు\n\n` +
    `ప్రియమైన ${clientName},\n\n` +
    `మీ *${itrForm}* (${ay}) దాఖలు గడువు *${dueDate}*.\n` +
    (daysLeft > 0 ? `${daysLeft} రోజులు మిగిలాయి.` : `గడువు దాటిపోయింది.`) +
    `\n\n_WealthAdvisor AI — CA Portal_`
  ),
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Build a WhatsApp message from a named template.
 * @param {string} templateKey  - e.g. 'gst_deadline', 'itr_filed_confirm'
 * @param {object} data         - Template variables
 * @param {string} [locale]     - 'en' (default) | 'te' (Coming Soon)
 * @returns {string} Formatted message text
 */
function buildTemplate(templateKey, data, locale = 'en') {
  // Telugu is Coming Soon — fall back to English
  const templates = TEMPLATES_EN;
  const fn = templates[templateKey];
  if (!fn) {
    throw new Error(`Unknown CA WhatsApp template: ${templateKey}`);
  }
  return fn(data);
}

/**
 * Send a CA reminder message via Meta WhatsApp Cloud API.
 * Uses the same WA_API_BASE / WA_PHONE_ID / WA_TOKEN as whatsapp.js.
 * @param {string} toPhone   - E.164 format, e.g. '+919876543210'
 * @param {string} text      - Message body (already rendered)
 * @returns {Promise<object>} WhatsApp API response
 */
async function sendCAReminder(toPhone, text) {
  if (!WA_PHONE_ID || !WA_TOKEN) {
    console.warn('[CA-WA] WA_PHONE_ID / WA_TOKEN not configured — skipping send');
    return { skipped: true };
  }
  const url  = `${WA_API_BASE}/${WA_PHONE_ID}/messages`;
  const body = {
    messaging_product: 'whatsapp',
    to:                toPhone.replace(/\s+/g, ''),
    type:              'text',
    text:              { body: text, preview_url: false },
  };
  const resp = await axios.post(url, body, {
    headers: {
      Authorization: `Bearer ${WA_TOKEN}`,
      'Content-Type': 'application/json',
    },
    timeout: 10_000,
  });
  return resp.data;
}

/**
 * Send a bulk GST deadline reminder to multiple clients.
 * @param {Array<{phone, clientName, returnType, period, dueDate, daysLeft, lateFee}>} clients
 * @returns {Promise<Array<{phone, status, error?}>>}
 */
async function sendBulkGSTReminders(clients) {
  const results = [];
  for (const client of clients) {
    try {
      const text = buildTemplate('gst_deadline', client);
      await sendCAReminder(client.phone, text);
      results.push({ phone: client.phone, status: 'sent' });
      // Small delay to avoid rate limiting
      await new Promise(r => setTimeout(r, 200));
    } catch (err) {
      results.push({ phone: client.phone, status: 'error', error: err.message });
    }
  }
  return results;
}

/**
 * Send ITR deadline reminders for clients with pending filings.
 */
async function sendBulkITRReminders(clients) {
  const results = [];
  for (const client of clients) {
    try {
      const text = buildTemplate('itr_deadline', client);
      await sendCAReminder(client.phone, text);
      results.push({ phone: client.phone, status: 'sent' });
      await new Promise(r => setTimeout(r, 200));
    } catch (err) {
      results.push({ phone: client.phone, status: 'error', error: err.message });
    }
  }
  return results;
}

/** List all available template keys */
function listTemplates() {
  return Object.keys(TEMPLATES_EN);
}

module.exports = {
  buildTemplate,
  sendCAReminder,
  sendBulkGSTReminders,
  sendBulkITRReminders,
  listTemplates,
  TEMPLATES_EN,
  TEMPLATES_TE,   // exported for future activation
};
