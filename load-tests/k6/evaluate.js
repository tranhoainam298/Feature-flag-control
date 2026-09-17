import http from 'k6/http';
import { check, sleep } from 'k6';

// k6 Load Test for FlagOps Server Evaluation & Ruleset ETag/304 Endpoints
// Targets:
// - POST /eval/v1/flags/{flag_key}/evaluate (with Redis cache): p99 < 30ms
// - GET /eval/v1/ruleset (200 Full Ruleset): p99 < 30ms
// - GET /eval/v1/ruleset (304 Not Modified): p99 < 10ms

export const options = {
  scenarios: {
    evaluate_flag: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
      exec: 'evaluateSingleFlag',
      tags: { scenario: 'evaluate' },
    },
    ruleset_full: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      exec: 'fetchFullRuleset',
      tags: { scenario: 'ruleset_200' },
    },
    ruleset_cached_304: {
      executor: 'constant-vus',
      vus: 15,
      duration: '30s',
      exec: 'fetchCachedRuleset304',
      tags: { scenario: 'ruleset_304' },
    },
  },
  thresholds: {
    'http_req_duration{scenario:evaluate}': ['p(95)<20', 'p(99)<30'],
    'http_req_duration{scenario:ruleset_200}': ['p(95)<25', 'p(99)<35'],
    'http_req_duration{scenario:ruleset_304}': ['p(95)<5', 'p(99)<10'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = __ENV.API_KEY || 'fo_srv_test_key_for_k6';
const FLAG_KEY = __ENV.FLAG_KEY || 'feature-dark-mode';

const headers = {
  'Content-Type': 'application/json',
  'X-FlagOps-Key': API_KEY,
};

export function setup() {
  // Fetch initial ruleset to obtain valid ETag
  const res = http.get(`${BASE_URL}/eval/v1/ruleset`, { headers });
  const etag = res.headers['ETag'] || res.headers['etag'] || 'W/"1"';
  return { etag };
}

export function evaluateSingleFlag() {
  const payload = JSON.stringify({
    targetingKey: `user_${Math.floor(Math.random() * 10000)}`,
    attributes: {
      country: 'VN',
      tier: 'pro',
      is_beta: true,
    },
  });

  const res = http.post(`${BASE_URL}/eval/v1/flags/${FLAG_KEY}/evaluate`, payload, { headers });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has value': (r) => r.json('value') !== undefined,
  });
  sleep(0.01);
}

export function fetchFullRuleset() {
  const res = http.get(`${BASE_URL}/eval/v1/ruleset`, { headers });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has rulesetVersion': (r) => r.json('rulesetVersion') !== undefined,
  });
  sleep(0.02);
}

export function fetchCachedRuleset304(data) {
  const reqHeaders = {
    ...headers,
    'If-None-Match': data.etag,
  };
  const res = http.get(`${BASE_URL}/eval/v1/ruleset`, { headers: reqHeaders });
  check(res, {
    'status is 304': (r) => r.status === 304,
  });
  sleep(0.005);
}
