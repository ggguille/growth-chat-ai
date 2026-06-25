import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";
import { open } from "k6/experimental/streams";  // requires k6 >= v0.47
import { ragMessages, nonRagMessages } from "./messages.js";

// ── Custom metrics ────────────────────────────────────────────────────────────
const ttft    = new Trend("ttft_ms", true);  // True TTFT in ms — DoD metric (p95 < 3000ms)
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

// ── True TTFT measurement via SSE streaming ───────────────────────────────────
// Uses k6/experimental/streams to read the SSE response chunk by chunk.
// We stop reading as soon as we receive the first "data:" line — that is the
// true TTFT (time from request send to first token delivered to client).
// The stream is then cancelled so we don't wait for the full response.
async function sendTurn(sessionId, message) {
  const start = Date.now();

  let firstTokenReceived = false;
  let measuredTTFT       = null;
  let statusOk           = false;
  let hasErrorEvent      = false;
  let gotSseData         = false;

  const url    = `${BASE_URL}/chat`;
  const body   = JSON.stringify({ message });
  const params = {
    method:  "POST",
    headers: {
      "Content-Type":   "application/json",
      "Accept":         "text/event-stream",
      "ZGC-Session-ID": sessionId,
      "ZGC-API-KEY":    API_KEY,
    },
    // No responseType here — we read the stream manually
    timeout: "60s",  // generous timeout; TTFT is measured internally
  };

  try {
    const stream = await open(url, params);
    statusOk = stream.status === 200;

    const reader = stream.body.getReader();
    const decoder = new TextDecoder();

    // Read chunks until we see the first SSE data line
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });

      if (chunk.includes('"type":"error"')) {
        hasErrorEvent = true;
      }

      if (!firstTokenReceived && chunk.includes("data:")) {
        measuredTTFT       = Date.now() - start;
        firstTokenReceived = true;
        gotSseData         = true;
        // Cancel the rest of the stream — we have what we need for TTFT
        await reader.cancel();
        break;
      }
    }
  } catch (e) {
    // Stream open/read error — counts as a failure
    hasErrorEvent = true;
  }

  const ok = check(null, {
    "status 200":             () => statusOk,
    "body contains SSE data": () => gotSseData,
    "no error event":         () => !hasErrorEvent,
  });

  errRate.add(!ok);

  if (firstTokenReceived && measuredTTFT !== null) {
    ttft.add(measuredTTFT);
  }
}

// ── Main VU scenario ──────────────────────────────────────────────────────────
export default async function () {
  const sessionId = uuidv4();
  const turns     = 5 + Math.floor(Math.random() * 3);  // 5–7 turns per session

  for (let i = 0; i < turns; i++) {
    await sendTurn(sessionId, pickMessage());
    if (i < turns - 1) {
      sleep(15 + Math.random() * 15);  // 15–30s between turns (realistic cadence)
    }
  }
}