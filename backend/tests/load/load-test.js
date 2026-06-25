import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";
import { ragMessages, nonRagMessages } from "./messages.js";

// ── Custom metrics ────────────────────────────────────────────────────────────
const ttft    = new Trend("ttft_ms", true);  // Time to First Token — DoD metric (p95 < 3000ms)
const errRate = new Rate("error_rate");

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: "2m",  target: 10 },  // ramp up to 10 VUs
    { duration: "10m", target: 10 },  // sustain 10 VUs — DoD window
    { duration: "30s", target: 0  },  // ramp down
  ],
  thresholds: {
    ttft_ms:    ["p(95)<3000"],  // DoD gate — p95 TTFT < 3s
    error_rate: ["rate<0.05"],   // < 5% error rate
  },
};

// ── Config (injected by GitHub Actions as environment variables) ───────────────
const BASE_URL = __ENV.BASE_URL;  // required — set in workflow
const API_KEY  = __ENV.API_KEY;   // required — set from GitHub secret

// ── Helpers ───────────────────────────────────────────────────────────────────
function pickMessage() {
  if (Math.random() < 0.6) {
    return ragMessages[Math.floor(Math.random() * ragMessages.length)];
  }
  return nonRagMessages[Math.floor(Math.random() * nonRagMessages.length)];
}

// ── TTFT measurement ──────────────────────────────────────────────────────────
// k6 does not support true streaming reads with http module.
// We use http_req_waiting (TTFB — time to first byte) as the TTFT proxy:
// this is the time from request sent to the moment the server starts sending
// the response body, which in a streaming SSE endpoint equals the time to the
// first token chunk. This is a standard, accurate proxy for TTFT in k6.
//
// After the response is fully received we validate the SSE body and record
// http_req_waiting as ttft_ms. The full-response timeout is set to 120s so
// long LLM responses are not killed mid-stream.
function sendTurn(sessionId, message) {
  const params = {
    headers: {
      "Content-Type":   "application/json",
      "Accept":         "text/event-stream",
      "ZGC-Session-ID": sessionId,
      "ZGC-API-KEY":    API_KEY,
    },
    responseType: "text",
    timeout:      "120s",  // full-response timeout — LLM streams can take 30–60s
  };

  const res = http.post(`${BASE_URL}/chat`, JSON.stringify({ message }), params);

  // http_req_waiting = time from request sent to first byte received (TTFB).
  // For a streaming SSE endpoint this equals time-to-first-token.
  const measuredTTFT = res.timings.waiting;

  const ok = check(res, {
    "status 200":             (r) => r.status === 200,
    "body contains SSE data": (r) => r.body && r.body.includes("data:"),
    "no error event":         (r) => !r.body || !r.body.includes('"type":"error"'),
  });

  errRate.add(!ok);

  // Only record TTFT for successful responses
  if (res.status === 200) {
    ttft.add(measuredTTFT);
  }
}

// ── Main VU scenario ──────────────────────────────────────────────────────────
export default function () {
  const sessionId = uuidv4();
  const turns     = 5 + Math.floor(Math.random() * 3);  // 5–7 turns per session

  for (let i = 0; i < turns; i++) {
    sendTurn(sessionId, pickMessage());
    if (i < turns - 1) {
      sleep(15 + Math.random() * 15);  // 15–30s between turns (realistic cadence)
    }
  }
}