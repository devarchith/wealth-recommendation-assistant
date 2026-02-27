/**
 * k6 Load Test — WealthAdvisor AI
 * =================================
 * Simulates 8,000 concurrent users as published in the PCCDA 2025 paper.
 * Tests the full API gateway + ML service stack under production-like load.
 *
 * Prerequisites:
 *   brew install k6   (macOS)
 *   apt install k6    (Debian/Ubuntu)
 *
 * Run:
 *   k6 run tests/load/k6_load_test.js
 *   k6 run --vus 100 --duration 60s tests/load/k6_load_test.js  (quick smoke)
 *   k6 run --out json=results/k6_results.json tests/load/k6_load_test.js
 *
 * Test scenarios (staged ramp):
 *   Stage 1: 0 → 500  VUs over 2 minutes   (warm-up)
 *   Stage 2: 500 → 2000 VUs over 3 minutes  (ramp up)
 *   Stage 3: 2000 → 8000 VUs over 5 minutes (peak load)
 *   Stage 4: 8000 VUs for 10 minutes        (sustained peak)
 *   Stage 5: 8000 → 0 VUs over 2 minutes   (ramp down)
 *
 * Success thresholds (from paper Table 4):
 *   http_req_duration p(95) < 1200ms   (target: 0.8s average)
 *   http_req_duration p(99) < 2000ms
 *   http_req_failed         < 1%
 *   http_reqs               > 1000/s   (throughput)
 */

import http    from 'k6/http';
import ws      from 'k6/ws';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------

const chatLatency     = new Trend('chat_response_ms');
const healthLatency   = new Trend('health_check_ms');
const sessionReuse    = new Counter('session_reuse');
const aiErrors        = new Counter('ai_errors');
const hallucinationHit = new Counter('hallucination_detected');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const BASE_URL    = __ENV.BASE_URL    || 'http://localhost:3001';
const ML_URL      = __ENV.ML_URL      || 'http://localhost:5001';
const TEST_MODE   = __ENV.TEST_MODE   || 'full'; // 'smoke' | 'load' | 'stress' | 'full'

// ---------------------------------------------------------------------------
// Load stage configurations
// ---------------------------------------------------------------------------

const STAGE_CONFIGS = {
  smoke: {
    stages: [
      { duration: '30s', target: 10 },
      { duration: '1m',  target: 10 },
      { duration: '30s', target: 0  },
    ],
    thresholds: {
      http_req_duration: ['p(95)<2000'],
      http_req_failed:   ['rate<0.05'],
    },
  },
  load: {
    stages: [
      { duration: '2m', target: 500  },
      { duration: '5m', target: 2000 },
      { duration: '3m', target: 0    },
    ],
    thresholds: {
      http_req_duration: ['p(95)<1500', 'p(99)<3000'],
      http_req_failed:   ['rate<0.02'],
    },
  },
  stress: {
    stages: [
      { duration: '2m',  target: 2000 },
      { duration: '5m',  target: 5000 },
      { duration: '3m',  target: 8000 },
      { duration: '5m',  target: 8000 },
      { duration: '2m',  target: 0    },
    ],
    thresholds: {
      http_req_duration: ['p(95)<2000', 'p(99)<4000'],
      http_req_failed:   ['rate<0.05'],
    },
  },
  full: {
    stages: [
      { duration: '2m',  target: 500  },  // warm-up
      { duration: '3m',  target: 2000 },  // ramp
      { duration: '5m',  target: 8000 },  // to peak
      { duration: '10m', target: 8000 },  // sustained peak (paper: 8K concurrent)
      { duration: '2m',  target: 0    },  // ramp down
    ],
    thresholds: {
      http_req_duration:    ['p(95)<1200', 'p(99)<2000'],
      http_req_failed:      ['rate<0.01'],
      chat_response_ms:     ['p(95)<1500', 'avg<800'],  // paper target: 0.8s avg
    },
  },
};

const config = STAGE_CONFIGS[TEST_MODE] || STAGE_CONFIGS.full;

export const options = {
  stages:     config.stages,
  thresholds: config.thresholds,
};

// ---------------------------------------------------------------------------
// Test data — realistic Indian finance queries
// ---------------------------------------------------------------------------

const CHAT_QUERIES = [
  // Tax queries
  'What is the income tax slab for 12 lakh income under new regime?',
  'How do I calculate HRA exemption for rent paid in Hyderabad?',
  'What is STCG tax rate on equity shares in FY 2024-25?',
  'Can I claim 80C deduction under new tax regime?',
  'When is advance tax due date for September quarter?',
  'What is the TDS rate for professional fees under 194J?',
  'How to calculate capital gains on ELSS mutual fund sold after 3 years?',
  'What documents needed for HRA claim in ITR?',
  // GST queries
  'What is GST rate on restaurant bill in AC restaurant?',
  'How to file GSTR-3B for monthly return above 5 crore turnover?',
  'Can I claim ITC on motor vehicle used for business?',
  'What is due date for GSTR-1 for quarterly filer?',
  // Investment queries
  'What is the difference between ELSS and PPF?',
  'How to calculate returns on SIP investment?',
  'What is the risk profile for aggressive investment?',
  'Recommend ETFs for long-term wealth building',
  // Budget queries
  'Help me plan budget with 50 30 20 rule for 80000 salary',
  'How much should I save for emergency fund?',
  // Sector queries
  'What is GST on gold jewellery purchase of 2 lakh?',
  'How much stamp duty for property purchase in Hyderabad?',
];

const SESSION_IDS = Array.from({ length: 1000 }, (_, i) => `load_test_session_${i}`);

// ---------------------------------------------------------------------------
// Main test function
// ---------------------------------------------------------------------------

export default function() {
  const sessionId = randomItem(SESSION_IDS);
  const query     = randomItem(CHAT_QUERIES);

  // ── Scenario distribution ────────────────────────────────────────────────
  const roll = Math.random();

  if (roll < 0.60) {
    // 60%: Chat query (primary use case)
    group('chat_query', () => testChat(sessionId, query));
  } else if (roll < 0.75) {
    // 15%: Health check (monitoring)
    group('health_check', () => testHealth());
  } else if (roll < 0.85) {
    // 10%: Auth flow
    group('auth_flow', () => testAuth(sessionId));
  } else if (roll < 0.92) {
    // 7%: Billing/plans page
    group('billing_plans', () => testBillingPlans());
  } else {
    // 8%: ML service direct (internal service test)
    group('ml_direct', () => testMLService(query));
  }

  sleep(Math.random() * 2 + 0.5); // 0.5–2.5s think time (realistic user pacing)
}

// ---------------------------------------------------------------------------
// Scenario implementations
// ---------------------------------------------------------------------------

function testChat(sessionId, query) {
  const payload = JSON.stringify({ message: query, session_id: sessionId });
  const params  = {
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': sessionId,
    },
    timeout: '30s',
  };

  const start = Date.now();
  const res   = http.post(`${BASE_URL}/api/chat`, payload, params);
  const dur   = Date.now() - start;

  chatLatency.add(dur);

  const ok = check(res, {
    'chat status 200':        (r) => r.status === 200,
    'chat has answer':        (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.answer === 'string' && body.answer.length > 0;
      } catch { return false; }
    },
    'chat response under 5s': (r) => dur < 5000,
  });

  if (!ok) aiErrors.add(1);

  // Check for hallucination flag in response
  try {
    const body = JSON.parse(res.body);
    if (body.hallucination_detected) hallucinationHit.add(1);
  } catch {}
}

function testHealth() {
  const start = Date.now();
  const res   = http.get(`${BASE_URL}/api/health`, { timeout: '5s' });
  const dur   = Date.now() - start;

  healthLatency.add(dur);

  check(res, {
    'health status 200': (r) => r.status === 200,
    'health response < 200ms': () => dur < 200,
  });
}

function testAuth(sessionId) {
  // Check current auth state
  const res = http.get(`${BASE_URL}/api/auth/me`, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '10s',
  });

  check(res, {
    'auth/me responds': (r) => r.status === 200 || r.status === 401,
  });
}

function testBillingPlans() {
  const res = http.get(`${BASE_URL}/api/billing/plans`, { timeout: '10s' });

  check(res, {
    'plans status 200': (r) => r.status === 200,
    'plans has data':   (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.plans) && body.plans.length >= 4;
      } catch { return false; }
    },
  });
}

function testMLService(query) {
  const payload = JSON.stringify({ message: query, session_id: 'load_ml_direct' });
  const res     = http.post(`${ML_URL}/chat`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });

  check(res, {
    'ml service 200': (r) => r.status === 200,
  });
}

// ---------------------------------------------------------------------------
// Setup: warm up connection pool
// ---------------------------------------------------------------------------

export function setup() {
  console.log(`Load test starting: ${TEST_MODE} mode, target 8K VUs`);
  console.log(`API Gateway: ${BASE_URL}`);
  console.log(`ML Service: ${ML_URL}`);

  // Verify services are up before ramping
  const health = http.get(`${BASE_URL}/api/health`, { timeout: '10s' });
  if (health.status !== 200) {
    throw new Error(`API Gateway not healthy: ${health.status}. Aborting load test.`);
  }
  console.log('Services healthy. Starting ramp.');
}

// ---------------------------------------------------------------------------
// Teardown: print summary
// ---------------------------------------------------------------------------

export function teardown(data) {
  console.log('Load test complete. Check k6 summary for thresholds.');
}
