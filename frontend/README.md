# growth-chat-frontend

React + TypeScript + Vite chat widget, delivered as a `<growth-chat>` Custom Element with Shadow DOM.

## Development

```bash
npm install
npm run dev      # HMR dev server at http://localhost:5173
```

Open `http://localhost:5173` — the `<growth-chat>` element renders inside its Shadow DOM.

## Testing

### Unit tests (Vitest)

```bash
npm test            # run all tests once
npm run test:watch  # watch mode
npm run test:ui     # visual test UI in browser
```

33 tests across 5 suites covering the SSE adapter, web component lifecycle, and all UI components.

### E2E tests (Playwright)

```bash
# Install Playwright browsers (first time only)
npx playwright install chromium

# Set required env vars (mirrors what the CI workflow hardcodes / pulls from secrets)
export VITE_API_URL=https://growth-chat-api.fly.dev/chat
export VITE_FALLBACK_URL=https://www.example.com/contact
export VITE_GDPR_NOTICE_TEXT=''
export VITE_API_KEY=<your-api-key>

npm run test:e2e                         # all 5 tests (headless Chromium)
npm run test:e2e -- --grep "E2E-02"      # single test by ID
npm run test:e2e:headed                  # headed mode for debugging
npm run test:e2e:report                  # open HTML report from last run
npm run test:e2e:ui                      # interactive Playwright UI
```

5 tests in `e2e/chat.spec.ts` covering widget load, SSE streaming, backend unavailability (mocked 503), rate limiting (mocked 429), and a multi-turn hot-lead conversation reaching Stage 3. Tests run against the staging API with a local Vite dev server serving the widget from source. See `documentation/docs/e2e-tests-plan.md` for the full test design rationale.

## Build

```bash
npm run build    # type-check + IIFE bundle → dist/chat.js
```

## Demo

**Local:** build the widget, then open `demo/index.html` in a browser (or `npx serve .` → `/demo/`).

```bash
npm run build
npx serve .
# open http://localhost:3000/demo/
```

The local demo requires the backend running at `http://localhost:8000/chat`. See the root README for backend setup.

**Cloud:** after deploying, the demo is live at:

```text
https://growth-chat-assets.fly.storage.tigris.dev/demo/index.html
```

The source file keeps local dev values (`../dist/chat.js`, `localhost:8000`). CI patches them with the CDN URL, production API URL, and API key before uploading — the source is never modified.

## Embed

Two lines of HTML, no framework required on the host page:

```html
<script src="<CDN_URL>/chat.js" defer></script>
<growth-chat
  api-url="<API_URL>"
  fallback-url="<CONTACT_URL>"
  api-key="<API_KEY>"
  data-gdpr-text="This chat is powered by AI…"
></growth-chat>
```

## Deployment

CI/CD builds `dist/chat.js`, patches `demo/index.html` with production values, and uploads both to Fly Tigris object storage. The CDN URL and bucket name are configured in the workflow — not in source.

Assets after deploy:

| Path | Cache |
| --- | --- |
| `https://growth-chat-assets.fly.storage.tigris.dev/chat.js` | 1 minute |
| `https://growth-chat-assets.fly.storage.tigris.dev/demo/index.html` | no-store |

Required GitHub secrets (in the `production` environment):

| Secret | Purpose |
| --- | --- |
| `TIGRIS_ACCESS_KEY_ID` | Object storage write access |
| `TIGRIS_SECRET_ACCESS_KEY` | Object storage write access |
| `VITE_API_KEY` | Baked into `chat.js`; injected into `demo/index.html` |

The E2E workflow reuses the same `production` environment secret and hardcoded values already used by `deploy-frontend.yml` — no new secrets are required:

| Name | Kind | Value |
| --- | --- | --- |
| `VITE_API_KEY` | Secret (existing) | Same `VITE_API_KEY` used by the frontend deploy |
| `VITE_API_URL` | Hardcoded in workflow | `https://growth-chat-api.fly.dev/chat` |
| `VITE_FALLBACK_URL` | Hardcoded in workflow | `https://www.example.com/contact` |
| `VITE_GDPR_NOTICE_TEXT` | Hardcoded in workflow | `''` (uses default built-in copy) |

The E2E workflow runs automatically on push/PR when `frontend/**` changes, and supports manual dispatch via **Actions → E2E Tests → Run workflow** with an optional `grep` input to target a single test.

Required build-time env vars (set in the workflow; copy `frontend/.env.example` for local development):

| Variable | Required | Description |
| --- | --- | --- |
| `VITE_API_URL` | yes | Backend chat endpoint |
| `VITE_FALLBACK_URL` | yes | Contact form URL shown when chat is unavailable |
| `VITE_API_KEY` | yes | API key sent as `ZGC-API-KEY` header |
| `VITE_GDPR_NOTICE_TEXT` | no | GDPR/privacy notice text displayed in the widget |
| `VITE_STREAM_TIMEOUT_MS` | no | First-token timeout before fallback activates (default: 10000) |

CI/CD triggers automatically on push to `main` when `frontend/` changes.

## Structure

```text
src/
├── main.ts                        # registers <growth-chat> custom element
├── GrowthChat.ts                  # Web Component: Shadow DOM, session ID, attribute lifecycle
├── GrowthChat.test.ts             # component registration and attribute tests
├── test-setup.ts                  # @testing-library/jest-dom matchers
├── styles/
│   └── widget.css                 # all widget styles (injected into shadow root at runtime)
├── lib/
│   ├── sseAdapter.ts              # ChatModelAdapter: SSE streaming, fallback, 429 handling
│   └── __tests__/
│       └── sseAdapter.test.ts
└── components/
    ├── ChatWidget.tsx             # top-level widget: launcher, proactive prompt, panel routing
    ├── ChatThread.tsx             # message list + composer + turn-level error display
    ├── GDPRNotice.tsx             # GDPR consent screen (persisted in sessionStorage)
    ├── FallbackView.tsx           # fallback screen shown when backend is unavailable
    └── __tests__/
        ├── ChatWidget.test.tsx
        ├── GDPRNotice.test.tsx
        └── FallbackView.test.tsx
e2e/
├── helpers/
│   └── sse.ts                     # SSE response body parser for Playwright assertions
└── chat.spec.ts                   # 5 E2E tests (E2E-01 through E2E-05)
demo/
└── index.html                     # standalone demo page (loads dist/chat.js)
playwright.config.ts               # Playwright config (Chromium, Vite dev server webServer)
test-page.html                     # E2E fixture page; api-url/fallback-url injected via query params
```

## Attributes

| Attribute | Required | Default | Description |
| --- | --- | --- | --- |
| `api-url` | yes | — | Backend streaming endpoint URL |
| `fallback-url` | yes | — | Contact page URL displayed when chat is unavailable |
| `api-key` | yes | — | API key sent as `ZGC-API-KEY` header on every request |
| `data-gdpr-text` | no | Built-in copy | Custom GDPR/privacy notice text |
| `proactive-delay-ms` | no | `45000` | Milliseconds before the proactive prompt bubble appears; set to a low value (e.g. `2000`) in test fixtures |

## Custom Events

The element dispatches the following events (bubble + composed, cross shadow boundary):

| Event | When | Detail |
| --- | --- | --- |
| `zgc:gdpr_acknowledged` | User accepts GDPR notice | — |
| `zgc:qualification_state_changed` | Each `done` SSE event | `{ leadLevel, currentStage }` |
| `zgc:escalation_triggered` | Stage 3 proposal issued | `{ handoffReason }` |
