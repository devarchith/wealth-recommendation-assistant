/**
 * Rice Mill WhatsApp Penalty Alerts — Telugu & English
 * =====================================================
 * Sends proactive compliance alerts to rice mill owners via WhatsApp.
 * Reuses the existing WA_API_BASE / WA_PHONE_ID / WA_TOKEN from whatsapp.js.
 *
 * Alert categories (English default — Telugu coming soon):
 *  1. GST late filing penalty (GSTR-1, GSTR-3B overdue)
 *  2. Cash payment violation (₹2L limit alert)
 *  3. Advance tax reminder (234B/C interest warning)
 *  4. FCI payment due (collection reminder)
 *  5. MSP compliance (paddy price alert)
 *  6. Working capital stress (cash runway warning)
 *  7. E-way bill reminder (vehicle dispatch)
 *  8. Milling efficiency alert (low outturn)
 *
 * Telugu translation status: COMING SOON (templates present, not active)
 *
 * Usage:
 *   const { buildRiceMillAlert, sendRiceMillAlert } = require('./ricemillWhatsApp');
 *   await sendRiceMillAlert('+919876543210', 'gst_penalty', data, 'en');
 */

'use strict';

const axios = require('axios');

const WA_API_BASE = process.env.WA_API_BASE  || 'https://graph.facebook.com/v19.0';
const WA_PHONE_ID = process.env.WA_PHONE_ID  || '';
const WA_TOKEN    = process.env.WA_TOKEN     || '';

// ---------------------------------------------------------------------------
// Template builders — English
// ---------------------------------------------------------------------------

const ALERTS_EN = {

  gst_penalty: ({ millName, returnType, daysLate, lateFee, dueDate }) => (
    `⚠️ GST Penalty Alert — ${millName}\n\n` +
    `Your *${returnType}* filing is *${daysLate} days overdue*.\n\n` +
    `*Late Fee Accumulated:* ₹${lateFee.toLocaleString('en-IN')}\n` +
    `*(₹50/day — max ₹10,000)*\n\n` +
    `File immediately on the GST portal to stop further penalty.\n` +
    `Due date was: ${dueDate}\n\n` +
    `Reply *HELP* to connect with your CA.\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),

  cash_payment_alert: ({ millName, farmerName, amount, excess }) => (
    `🚨 Cash Payment Limit Exceeded — ${millName}\n\n` +
    `A cash payment of *₹${amount.toLocaleString('en-IN')}* to farmer *${farmerName}* exceeds the ₹2 Lakh limit.\n\n` +
    `*Excess Amount:* ₹${excess.toLocaleString('en-IN')}\n` +
    `*Risk:* This amount will be *DISALLOWED* as business expense under Section 40A(3) of Income Tax Act.\n\n` +
    `✅ *Action:* Pay farmers via RTGS/NEFT/UPI for amounts above ₹2L.\n\n` +
    `Reply *CA* to get advice from your Chartered Accountant.\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),

  advance_tax: ({ millName, installment, dueDate, amount, daysLeft }) => (
    `💰 Advance Tax Reminder — ${millName}\n\n` +
    `*${installment} Instalment* of Advance Tax is due on *${dueDate}*.\n\n` +
    `*Estimated Amount:* ₹${amount.toLocaleString('en-IN')}\n` +
    (daysLeft > 0
      ? `*${daysLeft} days* remaining. Pay via Challan 280 (online NSDL portal).`
      : `⚠️ Deadline passed! Interest u/s 234B/234C is now accruing at 1% per month.`) +
    `\n\nReply *HOW* for payment instructions.\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),

  fci_payment_followup: ({ millName, dueAmount, daysPending, lotDetails }) => (
    `📋 FCI Payment Follow-up — ${millName}\n\n` +
    `FCI milling dues of *₹${dueAmount.toLocaleString('en-IN')}* are pending for *${daysPending} days*.\n` +
    (lotDetails ? `Lot details: ${lotDetails}\n` : '') +
    `\nStandard FCI payment cycle: 30–45 days after CMR delivery.\n` +
    (daysPending > 45
      ? `⚠️ Payment is overdue. Submit *FPF (FCI Payment Follow-up)* form at district office.`
      : `Payment is within normal cycle. Follow up if not received in ${45 - daysPending} days.`) +
    `\n\nReply *FCI* for escalation procedure.\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),

  msp_compliance: ({ millName, variety, purchasePrice, mspRate }) => {
    const subMSP = purchasePrice < mspRate;
    return (
      `${subMSP ? '🚨' : '✅'} MSP Compliance Alert — ${millName}\n\n` +
      `*Variety:* ${variety}\n` +
      `*Your Purchase Price:* ₹${purchasePrice}/qtl\n` +
      `*MSP 2024-25:* ₹${mspRate}/qtl\n\n` +
      (subMSP
        ? `⚠️ *RISK:* Purchasing below MSP violates APMC Act in AP/TS. Penalty may apply.\n` +
          `Pay minimum ₹${mspRate}/qtl and maintain Form-F receipts.`
        : `✅ Compliant. Ensure Form-F (APMC purchase receipt) is maintained for each lot.`) +
      `\n\n_WealthAdvisor AI — Rice Mill Compliance_`
    );
  },

  working_capital_stress: ({ millName, stressLevel, cashRunway, fciDues, recommendation }) => {
    const emoji = stressLevel === 'critical' ? '🔴' : stressLevel === 'high' ? '🟠' : '🟡';
    return (
      `${emoji} Working Capital Alert — ${millName}\n\n` +
      `*Stress Level:* ${stressLevel.toUpperCase()}\n` +
      `*Cash Runway:* ${cashRunway} days\n` +
      (fciDues > 0 ? `*FCI Receivable:* ₹${fciDues.toLocaleString('en-IN')}\n` : '') +
      `\n${recommendation}\n\n` +
      `Reply *WCSUMMARY* for detailed working capital report.\n\n` +
      `_WealthAdvisor AI — Rice Mill Compliance_`
    );
  },

  ewaybill_reminder: ({ millName, vehicleNo, destination, valueOfGoods, generatedAt }) => (
    `📦 E-Way Bill Reminder — ${millName}\n\n` +
    `Please generate E-Way Bill before dispatching:\n\n` +
    `*Vehicle:* ${vehicleNo}\n` +
    `*Destination:* ${destination}\n` +
    `*Consignment Value:* ₹${valueOfGoods.toLocaleString('en-IN')}\n` +
    `*Generated:* ${generatedAt || 'Not yet generated ⚠️'}\n\n` +
    `Movement without E-Way Bill: Penalty = min(₹10,000 or goods value) under Section 129 CGST.\n\n` +
    `Generate at: ewaybillgst.gov.in\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),

  milling_efficiency: ({ millName, lotId, actualOutturn, standardOutturn, shortfall }) => (
    `📉 Milling Efficiency Alert — ${millName}\n\n` +
    `*Lot:* ${lotId}\n` +
    `*Actual Outturn:* ${actualOutturn}%\n` +
    `*Standard:* ${standardOutturn}%\n` +
    `*Shortfall:* ${shortfall}% below standard\n\n` +
    `Low outturn increases cost and may attract FCI rejection of CMR delivery.\n\n` +
    `Check: rubber roller pressure, moisture level of paddy, machine calibration.\n\n` +
    `_WealthAdvisor AI — Rice Mill Compliance_`
  ),
};

// ---------------------------------------------------------------------------
// Template builders — Telugu (COMING SOON — templates present, not active)
// ---------------------------------------------------------------------------

const ALERTS_TE = {

  gst_penalty: ({ millName, returnType, daysLate, lateFee, dueDate }) => (
    `⚠️ GST జరిమానా హెచ్చరిక — ${millName}\n\n` +
    `మీ *${returnType}* ఫైలింగ్ *${daysLate} రోజులు* ఆలస్యమైంది.\n\n` +
    `*సేకరించిన జరిమానా:* ₹${lateFee.toLocaleString('en-IN')}\n` +
    `*(₹50/రోజు — గరిష్టం ₹10,000)*\n\n` +
    `మరింత జరిమానాను నిలిపివేయడానికి GST పోర్టల్‌లో వెంటనే ఫైల్ చేయండి.\n` +
    `గడువు తేదీ: ${dueDate}\n\n` +
    `మీ CA తో సంప్రదించడానికి *HELP* రిప్లై చేయండి.\n\n` +
    `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),

  cash_payment_alert: ({ millName, farmerName, amount, excess }) => (
    `🚨 నగదు చెల్లింపు హద్దు దాటింది — ${millName}\n\n` +
    `రైతు *${farmerName}* కి *₹${amount.toLocaleString('en-IN')}* నగదు చెల్లింపు ₹2 లక్షల పరిమితిని మించింది.\n\n` +
    `*అదనపు మొత్తం:* ₹${excess.toLocaleString('en-IN')}\n` +
    `*రిస్క్:* ఆదాయపు పన్ను చట్టం సెక్షన్ 40A(3) కింద ఈ మొత్తం వ్యాపార ఖర్చుగా *తిరస్కరించబడుతుంది*.\n\n` +
    `✅ *చర్య:* ₹2 లక్షలు మించే మొత్తాలకు RTGS/NEFT/UPI ద్వారా చెల్లించండి.\n\n` +
    `సలహా కోసం *CA* అని రిప్లై చేయండి.\n\n` +
    `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),

  advance_tax: ({ millName, installment, dueDate, amount, daysLeft }) => (
    `💰 అడ్వాన్స్ పన్ను గుర్తుచేపు — ${millName}\n\n` +
    `*${installment} వాయిదా* అడ్వాన్స్ పన్ను గడువు *${dueDate}*.\n\n` +
    `*అంచనా మొత్తం:* ₹${amount.toLocaleString('en-IN')}\n` +
    (daysLeft > 0
      ? `*${daysLeft} రోజులు* మిగిలాయి. NSDL పోర్టల్‌లో Challan 280 ద్వారా చెల్లించండి.`
      : `⚠️ గడువు దాటిపోయింది! సెక్షన్ 234B/234C కింద నెలకు 1% వడ్డీ వస్తోంది.`) +
    `\n\nచెల్లింపు సూచనల కోసం *HOW* రిప్లై చేయండి.\n\n` +
    `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),

  fci_payment_followup: ({ millName, dueAmount, daysPending, lotDetails }) => (
    `📋 FCI చెల్లింపు ఫాలో-అప్ — ${millName}\n\n` +
    `FCI మిల్లింగ్ బకాయిలు *₹${dueAmount.toLocaleString('en-IN')}* పెండింగ్‌లో ఉన్నాయి — *${daysPending} రోజులు*.\n` +
    (lotDetails ? `లాట్ వివరాలు: ${lotDetails}\n` : '') +
    `\nFCI చెల్లింపు సాధారణంగా CMR డెలివరీ తర్వాత 30–45 రోజులలో వస్తుంది.\n` +
    (daysPending > 45
      ? `⚠️ చెల్లింపు ఆలస్యమైంది. జిల్లా FCI కార్యాలయంలో FPF ఫారమ్ సమర్పించండి.`
      : `చెల్లింపు సాధారణ సమయంలో ఉంది. ${45 - daysPending} రోజులలో రాకపోతే ఫాలో-అప్ చేయండి.`) +
    `\n\n_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),

  msp_compliance: ({ millName, variety, purchasePrice, mspRate }) => {
    const subMSP = purchasePrice < mspRate;
    return (
      `${subMSP ? '🚨' : '✅'} MSP కంప్లయన్స్ హెచ్చరిక — ${millName}\n\n` +
      `*వెరైటీ:* ${variety}\n` +
      `*మీ కొనుగోలు ధర:* ₹${purchasePrice}/క్విం\n` +
      `*MSP 2024-25:* ₹${mspRate}/క్విం\n\n` +
      (subMSP
        ? `⚠️ *రిస్క్:* MSP కంటే తక్కువ ధరకు కొనుగోలు AP/TS APMC చట్టం ఉల్లంఘన. జరిమానా వర్తించవచ్చు.\n` +
          `కనిష్టంగా ₹${mspRate}/క్విం చెల్లించండి మరియు Form-F రసీదులు నిర్వహించండి.`
        : `✅ కంప్లయంట్. ప్రతి లాట్‌కు Form-F (APMC కొనుగోలు రసీదు) నిర్వహించండి.`) +
      `\n\n_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
    );
  },

  working_capital_stress: ({ millName, stressLevel, cashRunway, fciDues, recommendation }) => {
    const emoji = stressLevel === 'critical' ? '🔴' : stressLevel === 'high' ? '🟠' : '🟡';
    const levelMap = { critical: 'క్రిటికల్', high: 'అధికం', moderate: 'మధ్యస్థం', low: 'తక్కువ', healthy: 'మంచిది' };
    return (
      `${emoji} వర్కింగ్ క్యాపిటల్ హెచ్చరిక — ${millName}\n\n` +
      `*స్థితి:* ${levelMap[stressLevel] || stressLevel}\n` +
      `*నగదు రన్‌వే:* ${cashRunway} రోజులు\n` +
      (fciDues > 0 ? `*FCI బకాయి:* ₹${fciDues.toLocaleString('en-IN')}\n` : '') +
      `\n${recommendation}\n\n` +
      `వివరణాత్మక నివేదిక కోసం *WCSUMMARY* రిప్లై చేయండి.\n\n` +
      `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
    );
  },

  ewaybill_reminder: ({ millName, vehicleNo, destination, valueOfGoods }) => (
    `📦 ఈ-వే బిల్ గుర్తుచేపు — ${millName}\n\n` +
    `సరుకు పంపడానికి ముందు ఈ-వే బిల్ జనరేట్ చేయండి:\n\n` +
    `*వాహనం:* ${vehicleNo}\n` +
    `*గమ్యస్థానం:* ${destination}\n` +
    `*విలువ:* ₹${valueOfGoods.toLocaleString('en-IN')}\n\n` +
    `ఈ-వే బిల్ లేకుండా రవాణా: సెక్షన్ 129 CGST కింద ₹10,000 జరిమానా.\n` +
    `ewaybillgst.gov.in లో జనరేట్ చేయండి.\n\n` +
    `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),

  milling_efficiency: ({ millName, lotId, actualOutturn, standardOutturn, shortfall }) => (
    `📉 మిల్లింగ్ సామర్థ్య హెచ్చరిక — ${millName}\n\n` +
    `*లాట్:* ${lotId}\n` +
    `*వాస్తవ అవుట్‌టర్న్:* ${actualOutturn}%\n` +
    `*ప్రమాణం:* ${standardOutturn}%\n` +
    `*తక్కువ:* ${shortfall}% తక్కువగా ఉంది\n\n` +
    `తక్కువ అవుట్‌టర్న్ ఖర్చులను పెంచి FCI CMR డెలివరీ తిరస్కరణకు దారి తీయవచ్చు.\n\n` +
    `తనిఖీ: రబ్బర్ రోలర్ ప్రెషర్, వరి తేమ, మిషన్ క్యాలిబ్రేషన్.\n\n` +
    `_WealthAdvisor AI — రైస్ మిల్ కంప్లయన్స్_`
  ),
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Build a rice mill alert message.
 * @param {string} alertKey   - e.g. 'gst_penalty', 'cash_payment_alert'
 * @param {object} data       - Template variables
 * @param {string} [locale]   - 'en' (English, default) | 'te' (Telugu, coming soon)
 * @returns {string} Formatted WhatsApp message
 */
function buildRiceMillAlert(alertKey, data, locale = 'en') {
  const templates = locale === 'te' ? ALERTS_TE : ALERTS_EN;
  const fn = templates[alertKey] || ALERTS_EN[alertKey];
  if (!fn) throw new Error(`Unknown rice mill alert: ${alertKey}`);
  return fn(data);
}

/**
 * Send a rice mill alert via Meta WhatsApp Cloud API.
 * Reuses WA_API_BASE/WA_PHONE_ID/WA_TOKEN from environment (same as whatsapp.js).
 */
async function sendRiceMillAlert(toPhone, alertKey, data, locale = 'en') {
  const text = buildRiceMillAlert(alertKey, data, locale);
  if (!WA_PHONE_ID || !WA_TOKEN) {
    console.warn('[RiceMill-WA] WA credentials not configured — skipping send');
    return { skipped: true, text };
  }
  const resp = await axios.post(
    `${WA_API_BASE}/${WA_PHONE_ID}/messages`,
    {
      messaging_product: 'whatsapp',
      to:   toPhone.replace(/\s+/g, ''),
      type: 'text',
      text: { body: text, preview_url: false },
    },
    {
      headers: { Authorization: `Bearer ${WA_TOKEN}`, 'Content-Type': 'application/json' },
      timeout: 10_000,
    }
  );
  return resp.data;
}

/**
 * Send penalty alerts to multiple mills.
 * @param {Array<{phone, alertKey, data, locale}>} mills
 */
async function sendBulkRiceMillAlerts(mills) {
  const results = [];
  for (const mill of mills) {
    try {
      await sendRiceMillAlert(mill.phone, mill.alertKey, mill.data, mill.locale || 'en');
      results.push({ phone: mill.phone, status: 'sent', alertKey: mill.alertKey });
      await new Promise(r => setTimeout(r, 250));   // rate limit
    } catch (err) {
      results.push({ phone: mill.phone, status: 'error', error: err.message });
    }
  }
  return results;
}

/** List available alert keys */
function listAlerts() {
  return Object.keys(ALERTS_EN);
}

module.exports = {
  buildRiceMillAlert,
  sendRiceMillAlert,
  sendBulkRiceMillAlerts,
  listAlerts,
  ALERTS_EN,
  ALERTS_TE,
};
