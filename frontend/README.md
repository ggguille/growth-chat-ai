# growth-chat-frontend

React + TypeScript + Vite chat widget, delivered as a `<growth-chat>` Custom Element with Shadow DOM.

## Development

```bash
npm install
npm run dev      # HMR dev server at http://localhost:5173
```

Open `http://localhost:5173` — the `<growth-chat>` element renders inside its Shadow DOM.

## Build

```bash
npm run build    # type-check + IIFE bundle → dist/chat.js
```

## Embed

Two lines of HTML, no framework required on the host page:

```html
<script src="<CDN_URL>/chat.js" defer></script>
<growth-chat api-url="<VITE_API_URL>"></growth-chat>
```

## Deployment

The built `dist/chat.js` is uploaded to Fly Tigris object storage via CI/CD. The CDN URL and bucket are configured in the workflow — not in source.

Required GitHub secrets (in the `production` environment):

| Secret | Purpose |
| --- | --- |
| `TIGRIS_ACCESS_KEY_ID` | Object storage write access |
| `TIGRIS_SECRET_ACCESS_KEY` | Object storage write access |

Required build-time env vars (set in the workflow; copy `frontend/.env.example` for local development):

| Variable | Description |
| --- | --- |
| `VITE_API_URL` | Backend chat endpoint |
| `VITE_FALLBACK_URL` | Contact form URL shown when chat is unavailable |
| `VITE_GDPR_NOTICE_TEXT` | GDPR/cookie notice displayed in the widget |

CI/CD triggers automatically on push to `main` when `frontend/` changes.

## Structure

```text
src/
├── main.ts                    # registers <growth-chat> custom element
├── GrowthChat.ts              # Web Component: Shadow DOM + React lifecycle
└── components/
    └── ChatWidget.tsx         # React component (placeholder — Phase 2 target)
```

## Attributes

| Attribute | Required | Description |
| --- | --- | --- |
| `api-url` | yes | Backend streaming endpoint URL |
