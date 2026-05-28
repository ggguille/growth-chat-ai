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

After building, open `demo/index.html` in a browser (or `npx serve .` → `/demo/`) to see the widget embedded in a mock landing page.

```bash
npm run build
npx serve .
# open http://localhost:3000/demo/
```

The demo requires the backend running at `http://localhost:8000/chat`. See the root README for backend setup.

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

The built `dist/chat.js` is uploaded to Fly Tigris object storage via CI/CD. The CDN URL and bucket are configured in the workflow — not in source.

Required GitHub secrets (in the `production` environment):

| Secret | Purpose |
| --- | --- |
| `TIGRIS_ACCESS_KEY_ID` | Object storage write access |
| `TIGRIS_SECRET_ACCESS_KEY` | Object storage write access |

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
