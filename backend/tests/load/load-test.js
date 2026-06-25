import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";
import { ragMessages, nonRagMessages } from "./messages.js";

// ── Custom metrics ────────────────────────────────────────────────────────────
const ttft    = new Trend("ttft_ms", true);  // Time to First Token in ms — DoD metric
const errRate = new Rate("error_rate");

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: "2m",  target: 10 },  // ramp up to 10 VUs
    { duration: "10m", target: 10 },  // sustain 10 VUs — DoD window
    { duration: "30s", target: 0  },  // ramp down
  ],
  thresholds: {
    ttft_ms:    ["p(95)<3000"],  // DoD gate — workflow fails if not met
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

// ── TTFT measurement over SSE ─────────────────────────────────────────────────
// k6 http.post with responseType:"text" receives the full SSE body.
// We time from request send to response received and use this as a TTFT proxy
// (conservative upper bound — actual TTFT is lower).
// For a true TTFT measurement, replace with k6/experimental/streams (k6 >= v0.47):
// close the stream on the first "token" event instead of waiting for the full body.
function sendTurn(sessionId, message) {
  const params = {
    headers: {
      "Content-Type":   "application/json",
      "Accept":         "text/event-stream",
      "ZGC-Session-ID": sessionId,
      "ZGC-API-KEY":    API_KEY,
    },
    responseType: "text",
    timeout:      "20s",
  };

  const start   = Date.now();
  const res     = http.post(`${BASE_URL}/chat`, JSON.stringify({ message }), params);
  const elapsed = Date.now() - start;

  const ok = check(res, {
    "status 200":             (r) => r.status === 200,
    "body contains SSE data": (r) => r.body && r.body.includes("data:"),
    "no error event":         (r) => !r.body.includes('"type":"error"'),
  });

  errRate.add(!ok);
  if (ok) ttft.add(elapsed);
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
