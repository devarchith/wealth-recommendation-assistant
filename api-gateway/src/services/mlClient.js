'use strict';

/**
 * ML Service HTTP client.
 * Abstracts all communication with the Flask ML service.
 */

const http = require('http');
const https = require('https');

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://localhost:5001';

// Keep-alive agents for connection reuse (reduces TCP handshake overhead)
const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 50 });
const httpsAgent = new https.Agent({ keepAlive: true, maxSockets: 50 });

/**
 * Post a chat message to the ML service.
 *
 * @param {string} message  - User's question text
 * @param {string} sessionId - Session identifier for memory scoping
 * @returns {Promise<{answer: string, sources: Array, latency_ms: number}>}
 */
async function sendChatMessage(message, sessionId) {
  const url = new URL('/chat', ML_SERVICE_URL);
  const isHttps = url.protocol === 'https:';

  const body = JSON.stringify({ message, session_id: sessionId });

  return new Promise((resolve, reject) => {
    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'X-Session-ID': sessionId,
      },
      agent: isHttps ? httpsAgent : httpAgent,
      timeout: 30000, // 30s — LLM inference can be slow on CPU
    };

    const req = (isHttps ? https : http).request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (res.statusCode >= 400) {
            reject(new Error(parsed.error || `ML service error ${res.statusCode}`));
          } else {
            resolve(parsed);
          }
        } catch (err) {
          reject(new Error(`Failed to parse ML service response: ${err.message}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('ML service request timed out'));
    });

    req.write(body);
    req.end();
  });
}

/**
 * Record user feedback in the ML service.
 */
async function sendFeedback(sessionId, messageId, rating) {
  const url = new URL('/feedback', ML_SERVICE_URL);
  const body = JSON.stringify({ session_id: sessionId, message_id: messageId, rating });

  return new Promise((resolve, reject) => {
    const options = {
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
      agent: httpAgent,
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { resolve({ recorded: false }); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

module.exports = { sendChatMessage, sendFeedback };
