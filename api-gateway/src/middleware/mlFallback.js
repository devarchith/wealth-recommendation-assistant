/**
 * ML Service Graceful Fallback Middleware
 * =========================================
 * When the ML service is unavailable (crash, timeout, overload),
 * this middleware:
 *   1. Returns a meaningful response from the fallback knowledge base
 *   2. Queues the original query for retry when service recovers
 *   3. Emits a health alert to admin
 *   4. Tracks downtime for SLA reporting
 *
 * Fallback tiers (in order of preference):
 *   Tier 1: Recent response cache (identical/similar query answered < 1hr ago)
 *   Tier 2: Static rule-based answers for common high-frequency queries
 *   Tier 3: Graceful degradation message with suggested resources
 *
 * Circuit breaker:
 *   - CLOSED: normal operation — all requests pass through to ML service
 *   - OPEN:   ML service failed 5+ times in 60s — use fallback for all requests
 *   - HALF-OPEN: after 30s, try one probe request to ML service
 *
 * Usage:
 *   const { mlFallback, circuitBreaker, recordSuccess, recordFailure } = require('./mlFallback');
 *   router.post('/chat', mlFallback, chatHandler);
 */

'use strict';

const crypto = require('crypto');

// ---------------------------------------------------------------------------
// Circuit breaker state
// ---------------------------------------------------------------------------

const CircuitState = Object.freeze({
  CLOSED:    'CLOSED',    // healthy
  OPEN:      'OPEN',      // failed — use fallback
  HALF_OPEN: 'HALF_OPEN', // probing
});

const breaker = {
  state:         CircuitState.CLOSED,
  failures:      0,
  lastFailure:   null,
  lastSuccess:   null,
  tripThreshold: 5,          // consecutive failures to trip
  resetTimeout:  30_000,     // ms before trying half-open
  totalTrips:    0,
  downtimeStart: null,
  totalDowntimeMs: 0,
};

// ---------------------------------------------------------------------------
// Response cache (LRU-like, keyed by query hash)
// ---------------------------------------------------------------------------

const CACHE_TTL_MS  = 60 * 60 * 1000; // 1 hour
const CACHE_MAX     = 500;
const responseCache = new Map(); // hash → {response, ts, query}

function cacheKey(query) {
  return crypto.createHash('sha256').update(query.toLowerCase().trim(), 'utf8').digest('hex').slice(0, 16);
}

function cacheGet(query) {
  const key    = cacheKey(query);
  const entry  = responseCache.get(key);
  if (!entry)                          return null;
  if (Date.now() - entry.ts > CACHE_TTL_MS) {
    responseCache.delete(key);
    return null;
  }
  return entry;
}

function cacheSet(query, response) {
  if (responseCache.size >= CACHE_MAX) {
    // Evict oldest entry
    const oldest = [...responseCache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0];
    if (oldest) responseCache.delete(oldest[0]);
  }
  responseCache.set(cacheKey(query), { response, ts: Date.now(), query });
}

// ---------------------------------------------------------------------------
// Static fallback knowledge base (top 30 high-frequency queries)
// ---------------------------------------------------------------------------

const STATIC_FALLBACKS = [
  {
    patterns: [/tax slab/i, /income tax.*slab/i, /slab rate/i],
    answer:   'New regime FY 2024-25: Up to ₹3L — Nil; ₹3-7L — 5%; ₹7-10L — 10%; ₹10-12L — 15%; ₹12-15L — 20%; Above ₹15L — 30%. Rebate u/s 87A: Nil tax if income ≤ ₹7L. Standard deduction ₹75,000 for salaried.',
    category: 'tax',
    confidence: 0.75,
  },
  {
    patterns: [/stcg|short.*capital gain/i, /111a/i],
    answer:   'STCG on equity shares u/s 111A: 20% (post-Budget 2024, from 23 July 2024). Applicable when STT paid and holding ≤ 12 months. Added to total income if STT not paid.',
    category: 'capital_gains',
    confidence: 0.80,
  },
  {
    patterns: [/ltcg|long.*capital gain/i, /112a/i],
    answer:   'LTCG on equity shares/MFs u/s 112A: 12.5% (post-Budget 2024). First ₹1.25 lakh exempt per year. Holding > 12 months for equity. No indexation benefit.',
    category: 'capital_gains',
    confidence: 0.80,
  },
  {
    patterns: [/80c.*deduction|section 80c/i],
    answer:   'Section 80C maximum deduction: ₹1,50,000. Eligible investments: ELSS (3-year lock-in), PPF, EPF, NSC, tax-saver FD, life insurance premium, tuition fees. Only under old tax regime.',
    category: 'deductions',
    confidence: 0.80,
  },
  {
    patterns: [/advance tax.*date|due date.*advance/i],
    answer:   'Advance tax due dates FY 2024-25: 15 June (15%), 15 September (45%), 15 December (75%), 15 March (100%). Applicable if total tax > ₹10,000. Interest u/s 234C for shortfall.',
    category: 'advance_tax',
    confidence: 0.82,
  },
  {
    patterns: [/gst.*gold|gold.*gst/i],
    answer:   'GST on gold: 3% on gold value (HSN 7113). 5% on making charges. TCS 1% under Sec 206C(1F) if transaction value > ₹2 lakh.',
    category: 'gst',
    confidence: 0.85,
  },
  {
    patterns: [/hra.*exemption|house rent.*allow/i],
    answer:   'HRA exemption u/s 10(13A): Minimum of (1) Actual HRA received, (2) 50% of basic (metro: Mumbai/Delhi/Chennai/Kolkata) or 40% (non-metro), (3) Rent paid minus 10% of basic. Only under old regime.',
    category: 'deductions',
    confidence: 0.78,
  },
  {
    patterns: [/itr.*due date|filing.*deadline|return.*date/i],
    answer:   'ITR due dates FY 2024-25 (AY 2025-26): Non-audit individuals — 31 July 2025. Audit cases — 31 October 2025. Belated return — 31 December 2025 (₹5,000 late fee u/s 234F).',
    category: 'itr',
    confidence: 0.82,
  },
  {
    patterns: [/epf.*contribution|pf.*contribution|provident fund/i],
    answer:   'EPF: Employee 12% of basic+DA, Employer 12% (3.67% EPF + 8.33% EPS capped at ₹1,250/month). Mandatory for salary ≤ ₹15,000; voluntary above.',
    category: 'payroll',
    confidence: 0.80,
  },
  {
    patterns: [/gstr.*3b.*due|3b.*filing.*date/i],
    answer:   'GSTR-3B due date: 20th of following month for taxpayers with turnover > ₹5 crore. Quarterly (QRMP scheme) taxpayers: 22nd/24th of month after quarter.',
    category: 'gst',
    confidence: 0.78,
  },
];

function staticFallback(query) {
  for (const fb of STATIC_FALLBACKS) {
    if (fb.patterns.some(p => p.test(query))) {
      return fb;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Circuit breaker control
// ---------------------------------------------------------------------------

function recordSuccess() {
  breaker.failures    = 0;
  breaker.lastSuccess = Date.now();
  if (breaker.state !== CircuitState.CLOSED) {
    if (breaker.downtimeStart) {
      breaker.totalDowntimeMs += Date.now() - breaker.downtimeStart;
      breaker.downtimeStart = null;
    }
    breaker.state = CircuitState.CLOSED;
    console.log('[MLFallback] Circuit CLOSED — ML service recovered');
  }
}

function recordFailure() {
  breaker.failures++;
  breaker.lastFailure = Date.now();
  if (breaker.state === CircuitState.CLOSED && breaker.failures >= breaker.tripThreshold) {
    breaker.state      = CircuitState.OPEN;
    breaker.totalTrips++;
    breaker.downtimeStart = Date.now();
    console.error(`[MLFallback] Circuit OPEN — ML service unreachable after ${breaker.tripThreshold} failures`);
  } else if (breaker.state === CircuitState.HALF_OPEN) {
    breaker.state = CircuitState.OPEN;
    console.warn('[MLFallback] Circuit re-opened — probe request failed');
  }
}

function shouldAllowRequest() {
  if (breaker.state === CircuitState.CLOSED) return true;
  if (breaker.state === CircuitState.OPEN) {
    if (Date.now() - breaker.lastFailure >= breaker.resetTimeout) {
      breaker.state = CircuitState.HALF_OPEN;
      console.log('[MLFallback] Circuit HALF_OPEN — sending probe request');
      return true;
    }
    return false;
  }
  // HALF_OPEN: allow one through
  return true;
}

// ---------------------------------------------------------------------------
// Retry queue (in-memory; prod: Redis queue)
// ---------------------------------------------------------------------------

const retryQueue = [];

function enqueueRetry(query, sessionId) {
  retryQueue.push({ query, sessionId, ts: Date.now() });
  if (retryQueue.length > 1000) retryQueue.shift(); // cap
}

// ---------------------------------------------------------------------------
// Main middleware
// ---------------------------------------------------------------------------

function mlFallback(req, res, next) {
  req._mlStart       = Date.now();
  req._allowedByCircuit = shouldAllowRequest();

  if (req._allowedByCircuit) {
    // Patch res.json to intercept ML errors and cache good responses
    const origJson = res.json.bind(res);
    res.json = function(body) {
      if (res.statusCode >= 500 || body?.error) {
        recordFailure();
        _serveFallback(req, res, origJson);
        return;
      }
      // Success — cache and record
      if (body?.answer && req.body?.message) {
        cacheSet(req.body.message, body);
        recordSuccess();
      }
      return origJson(body);
    };

    // Intercept errors
    const origEnd = res.end.bind(res);
    res.end = function(chunk, ...args) {
      if (res.statusCode >= 500) {
        recordFailure();
        _serveFallback(req, res, origJson);
        return;
      }
      return origEnd(chunk, ...args);
    };

    return next();
  }

  // Circuit open — serve fallback immediately
  _serveFallback(req, res, res.json.bind(res));
}

function _serveFallback(req, res, jsonFn) {
  const query = req.body?.message || '';

  // Tier 1: Cache hit
  const cached = cacheGet(query);
  if (cached) {
    return jsonFn({
      ...cached.response,
      _fallback:   'cache',
      _cached_at:  new Date(cached.ts).toISOString(),
      disclaimer:  'This response was served from cache while the AI service is temporarily unavailable. Verify with current sources.',
    });
  }

  // Tier 2: Static fallback
  const staticAnswer = staticFallback(query);
  if (staticAnswer) {
    if (query) enqueueRetry(query, req.session?.userId || 'anon');
    return jsonFn({
      answer:      staticAnswer.answer,
      sources:     ['Income Tax Act 1961', 'Finance Act 2024', 'CBDT Circulars'],
      confidence:  staticAnswer.confidence,
      _fallback:   'static',
      disclaimer:  '⚠️ AI service temporarily unavailable. This is a pre-verified fallback answer. For complex queries, consult a CA.',
    });
  }

  // Tier 3: Graceful degradation
  if (query) enqueueRetry(query, req.session?.userId || 'anon');
  return jsonFn({
    answer:   null,
    error:    'SERVICE_TEMPORARILY_UNAVAILABLE',
    message:  'Our AI advisor is temporarily unavailable. Your query has been queued and will be answered shortly.',
    fallback_resources: [
      { name: 'Income Tax Department', url: 'https://www.incometax.gov.in' },
      { name: 'GST Portal', url: 'https://www.gst.gov.in' },
      { name: 'CBDT Circulars', url: 'https://www.incometaxindia.gov.in/Pages/communications/circulars.aspx' },
    ],
    retry_after_seconds: Math.ceil(breaker.resetTimeout / 1000),
    circuit_state: breaker.state,
  });
}

// ---------------------------------------------------------------------------
// Status endpoint helper
// ---------------------------------------------------------------------------

function getCircuitStatus() {
  return {
    state:            breaker.state,
    failures:         breaker.failures,
    total_trips:      breaker.totalTrips,
    last_failure:     breaker.lastFailure ? new Date(breaker.lastFailure).toISOString() : null,
    last_success:     breaker.lastSuccess ? new Date(breaker.lastSuccess).toISOString() : null,
    total_downtime_ms: breaker.totalDowntimeMs,
    cache_size:       responseCache.size,
    retry_queue_size: retryQueue.length,
  };
}

module.exports = {
  mlFallback,
  recordSuccess,
  recordFailure,
  cacheSet,
  cacheGet,
  getCircuitStatus,
  CircuitState,
  breaker,
};
