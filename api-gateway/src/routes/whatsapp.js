/**
 * WhatsApp Webhook Integration
 * Supports conversational tax queries in English and Telugu
 * via WhatsApp Business API (Meta Cloud API v19.0)
 *
 * Features:
 *   - Webhook verification (GET /api/whatsapp/webhook)
 *   - Incoming message handling (POST /api/whatsapp/webhook)
 *   - Language detection: English / Telugu
 *   - Routes to RAG pipeline for financial Q&A
 *   - Session-per-phone-number with 30-min expiry
 *   - Rich message formatting: text, list, button
 */

const express = require('express');
const router  = express.Router();
const crypto  = require('crypto');
const { createProxyMiddleware } = require('http-proxy-middleware');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const WA_VERIFY_TOKEN  = process.env.WA_VERIFY_TOKEN  || 'wealth-advisor-webhook-2024';
const WA_APP_SECRET    = process.env.WA_APP_SECRET    || '';
const WA_ACCESS_TOKEN  = process.env.WA_ACCESS_TOKEN  || '';
const WA_PHONE_NUMBER_ID = process.env.WA_PHONE_NUMBER_ID || '';
const ML_SERVICE_URL   = process.env.ML_SERVICE_URL   || 'http://localhost:5001';

const WA_API_BASE = `https://graph.facebook.com/v19.0/${WA_PHONE_NUMBER_ID}`;

// ---------------------------------------------------------------------------
// Session store (phone → {history, lang, lastActive})
// ---------------------------------------------------------------------------

const waSessions = new Map();
const WA_SESSION_TTL_MS = 30 * 60 * 1000; // 30 minutes

function getSession(phone) {
  const now = Date.now();
  const sess = waSessions.get(phone);
  if (sess && now - sess.lastActive < WA_SESSION_TTL_MS) {
    sess.lastActive = now;
    return sess;
  }
  const newSess = { phone, history: [], lang: 'en', lastActive: now };
  waSessions.set(phone, newSess);
  return newSess;
}

// GC stale sessions every 10 minutes
setInterval(() => {
  const now = Date.now();
  for (const [phone, sess] of waSessions.entries()) {
    if (now - sess.lastActive > WA_SESSION_TTL_MS) {
      waSessions.delete(phone);
    }
  }
}, 10 * 60 * 1000).unref();

// ---------------------------------------------------------------------------
// Language detection (Telugu Unicode block: U+0C00–U+0C7F)
// ---------------------------------------------------------------------------

function detectLanguage(text) {
  // Telugu Unicode range
  if (/[\u0C00-\u0C7F]/.test(text)) return 'te';
  // Telugu transliteration keywords
  const teluguKeywords = ['namaskaaram', 'namaste', 'pannu', 'aadaayam', 'vellu', 'cheppandi'];
  const lower = text.toLowerCase();
  if (teluguKeywords.some(kw => lower.includes(kw))) return 'te';
  return 'en';
}

// ---------------------------------------------------------------------------
// WhatsApp message sender
// ---------------------------------------------------------------------------

async function sendWAMessage(to, payload) {
  if (!WA_ACCESS_TOKEN || !WA_PHONE_NUMBER_ID) {
    console.warn('[WhatsApp] Credentials not configured — skipping send.');
    return;
  }
  try {
    const fetch = (await import('node-fetch')).default;
    const res = await fetch(`${WA_API_BASE}/messages`, {
      method:  'POST',
      headers: {
        'Authorization': `Bearer ${WA_ACCESS_TOKEN}`,
        'Content-Type':  'application/json',
      },
      body: JSON.stringify({ messaging_product: 'whatsapp', to, ...payload }),
    });
    if (!res.ok) {
      const err = await res.text();
      console.error('[WhatsApp] Send failed:', err);
    }
  } catch (err) {
    console.error('[WhatsApp] Send error:', err.message);
  }
}

function buildTextMessage(to, text) {
  return sendWAMessage(to, {
    type: 'text',
    text: { body: text, preview_url: false },
  });
}

function buildButtonMessage(to, body, buttons) {
  return sendWAMessage(to, {
    type: 'interactive',
    interactive: {
      type: 'button',
      body: { text: body },
      action: {
        buttons: buttons.map((b, i) => ({
          type: 'reply',
          reply: { id: `btn_${i}`, title: b.slice(0, 20) },
        })),
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Query the ML service RAG pipeline
// ---------------------------------------------------------------------------

async function queryMLService(question, sessionId) {
  try {
    const fetch = (await import('node-fetch')).default;
    const res = await fetch(`${ML_SERVICE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: `wa_${sessionId}` }),
      signal: AbortSignal.timeout(25_000),
    });
    if (!res.ok) throw new Error(`ML service HTTP ${res.status}`);
    const data = await res.json();
    return data.answer || 'I could not find a specific answer. Please consult a CA for personalised advice.';
  } catch (err) {
    console.error('[WhatsApp] ML query error:', err.message);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Message handlers by intent keyword
// ---------------------------------------------------------------------------

const GREETING_KEYWORDS_EN = ['hi', 'hello', 'hey', 'start', 'help'];
const GREETING_KEYWORDS_TE = ['హలో', 'నమస్కారం', 'నమస్తే', 'సహాయం'];

const MENU_EN = `*WealthAdvisor AI* — your financial assistant
Reply with a topic or ask any question:

1️⃣ Income Tax (ITR, TDS, Refund)
2️⃣ GST & Business
3️⃣ Investments & Savings
4️⃣ Budget Planning
5️⃣ Capital Gains

Or type your question directly!`;

const MENU_TE = `*WealthAdvisor AI* — మీ ఆర్థిక సహాయకుడు
ఒక అంశాన్ని ఎంచుకోండి లేదా ఏదైనా ప్రశ్న అడగండి:

1️⃣ ఆదాయపు పన్ను (ITR, TDS, రీఫండ్)
2️⃣ GST & వ్యాపారం
3️⃣ పెట్టుబడులు & పొదుపు
4️⃣ బడ్జెట్ ప్లానింగ్
5️⃣ మూలధన లాభాలు

లేదా నేరుగా మీ ప్రశ్న అడగండి!`;

function isGreeting(text, lang) {
  const lower = text.toLowerCase();
  if (lang === 'te') return GREETING_KEYWORDS_TE.some(k => text.includes(k)) || GREETING_KEYWORDS_EN.some(k => lower.includes(k));
  return GREETING_KEYWORDS_EN.some(k => lower.includes(k));
}

// ---------------------------------------------------------------------------
// Webhook verification (GET)
// ---------------------------------------------------------------------------

router.get('/webhook', (req, res) => {
  const mode      = req.query['hub.mode'];
  const token     = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode === 'subscribe' && token === WA_VERIFY_TOKEN) {
    console.log('[WhatsApp] Webhook verified.');
    return res.status(200).send(challenge);
  }
  res.sendStatus(403);
});

// ---------------------------------------------------------------------------
// Incoming messages (POST)
// ---------------------------------------------------------------------------

router.post('/webhook', async (req, res) => {
  // Verify signature
  if (WA_APP_SECRET) {
    const sig = req.headers['x-hub-signature-256'];
    const expected = 'sha256=' + crypto
      .createHmac('sha256', WA_APP_SECRET)
      .update(JSON.stringify(req.body))
      .digest('hex');
    if (!sig || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
      return res.sendStatus(403);
    }
  }

  // Acknowledge immediately (WhatsApp requires <5s response)
  res.sendStatus(200);

  try {
    const body = req.body;
    if (body.object !== 'whatsapp_business_account') return;

    for (const entry of (body.entry || [])) {
      for (const change of (entry.changes || [])) {
        const value = change.value;
        if (!value?.messages) continue;

        for (const message of value.messages) {
          if (message.type !== 'text') continue;

          const phone   = message.from;
          const text    = message.text?.body?.trim() || '';
          if (!text) continue;

          const session = getSession(phone);
          const lang    = detectLanguage(text);
          session.lang  = lang;

          console.log(`[WhatsApp] From: ${phone} | Lang: ${lang} | Msg: ${text.slice(0, 50)}`);

          // Mark as read
          sendWAMessage(phone, {
            type:       'reaction',
            reaction:   { message_id: message.id, emoji: '👀' },
          }).catch(() => {});

          let reply;

          if (isGreeting(text, lang)) {
            reply = lang === 'te' ? MENU_TE : MENU_EN;
            await buildTextMessage(phone, reply);
            continue;
          }

          // Topic shortcuts
          const topicMap: Record<string, string> = {
            '1': lang === 'te' ? 'ఆదాయపు పన్ను గురించి సమాచారం' : 'Tell me about income tax filing in India',
            '2': lang === 'te' ? 'GST గురించి చెప్పండి' : 'Explain GST for small businesses',
            '3': lang === 'te' ? 'పెట్టుబడులు మరియు పొదుపు గురించి' : 'Best investment options in India',
            '4': lang === 'te' ? 'నెలవారీ బడ్జెట్ ప్లానింగ్' : 'How to plan a monthly budget',
            '5': lang === 'te' ? 'మూలధన లాభాల పన్ను' : 'Capital gains tax on shares and mutual funds',
          };

          const queryText = topicMap[text] || text;

          // Query ML service
          const answer = await queryMLService(queryText, phone);

          if (!answer) {
            reply = lang === 'te'
              ? 'క్షమించండి, ప్రస్తుతం సేవ అందుబాటులో లేదు. తర్వాత ప్రయత్నించండి.'
              : 'Sorry, the service is temporarily unavailable. Please try again later.';
          } else {
            // Trim to WhatsApp 4096 char limit
            reply = answer.length > 4000 ? answer.slice(0, 3990) + '...\n\n_[Reply "more" for details]_' : answer;
            // Add disclaimer
            reply += lang === 'te'
              ? '\n\n_ఈ సమాచారం విద్యా ప్రయోజనాల కోసం మాత్రమే. వ్యక్తిగత సలహా కోసం CA ని సంప్రదించండి._'
              : '\n\n_This is for educational purposes only. Consult a CA for personalised advice._';
          }

          session.history.push({ role: 'user', text: queryText });
          session.history.push({ role: 'assistant', text: reply });

          await buildTextMessage(phone, reply);
        }
      }
    }
  } catch (err) {
    console.error('[WhatsApp] Handler error:', err);
  }
});

// ---------------------------------------------------------------------------
// Health / status endpoint
// ---------------------------------------------------------------------------

router.get('/status', (req, res) => {
  res.json({
    status:          'ok',
    active_sessions: waSessions.size,
    configured:      !!(WA_ACCESS_TOKEN && WA_PHONE_NUMBER_ID),
    webhook_url:     `${req.protocol}://${req.get('host')}/api/whatsapp/webhook`,
  });
});

module.exports = router;
