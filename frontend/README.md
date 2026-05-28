# growth-chat-frontend

React + TypeScript + Vite chat widget, delivered as a `<growth-chat>` Custom Element with Shadow DOM.

## Development

```bash
npm install
npm run dev      # HMR dev server at http://localhost:5173
```

Open `http://localhost:5173` — the `<growth-chat>` element renders inside its Shadow DOM.

## Testing

```bash
npm test         # run all tests once (vitest)
npm run test:watch  # watch mode
npm run test:ui  # visual test UI in browser
```

33 tests across 5 suites covering the SSE adapter, web component lifecycle, and all UI components.

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
https://fly.storage.tigris.dev/growth-chat-assets/demo/index.html
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
| `growth-chat-assets/chat.js` | 1 minute |
| `growth-chat-assets/demo/index.html` | no-store |

Required GitHub secrets (in the `production` environment):

| Secret | Purpose |
| --- | --- |
| `TIGRIS_ACCESS_KEY_ID` | Object storage write access |
| `TIGRIS_SECRET_ACCESS_KEY` | Object storage write access |
| `VITE_API_KEY` | Baked into `chat.js`; injected into `demo/index.html` |

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
│   ├── sseAdapter.ts              # ChatModelAdapter: SSE streaming + fallback logic
│   └── __tests__/
│       └── sseAdapter.test.ts
└── components/
    ├── ChatWidget.tsx             # top-level widget: launcher, panel, GDPR, fallback routing
    ├── ChatThread.tsx             # message list + composer (uses @assistant-ui/react primitives)
    ├── GDPRNotice.tsx             # GDPR consent screen (persisted in sessionStorage)
    ├── FallbackView.tsx           # fallback screen shown when backend is unavailable
    └── __tests__/
        ├── ChatWidget.test.tsx
        ├── GDPRNotice.test.tsx
        └── FallbackView.test.tsx
demo/
└── index.html                     # standalone demo page (loads dist/chat.js)
```

## Attributes

| Attribute | Required | Description |
| --- | --- | --- |
| `api-url` | yes | Backend streaming endpoint URL |
| `fallback-url` | yes | Contact page URL displayed when chat is unavailable |
| `api-key` | yes | API key sent as `ZGC-API-KEY` header on every request |
| `data-gdpr-text` | no | Custom GDPR/privacy notice text |

## Custom Events

The element dispatches the following events (bubble + composed, cross shadow boundary):

| Event | When | Detail |
| --- | --- | --- |
| `zgc:gdpr_acknowledged` | User accepts GDPR notice | — |
| `zgc:qualification_state_changed` | Each `done` SSE event | `{ leadLevel, currentStage }` |
| `zgc:escalation_triggered` | Stage 3 proposal issued | `{ handoffReason }` |
