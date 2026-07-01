---
description: "Operations runbook for the Growth Chat frontend widget — CDN delivery, deploy pipeline, cache behaviour, and failure modes."
---

# Frontend Widget

The frontend is a `<growth-chat>` Web Component — a single self-contained JavaScript bundle (`chat.js`) built at deploy time and served from a CDN. There is no runtime server. The widget embeds on the company's host website via a single `<script>` tag.

---

## How It Works

1. The host website loads `chat.js` from the CDN.
2. The bundle registers the `<growth-chat>` Custom Element and mounts React inside a Shadow DOM.
3. On first interaction, the widget shows a GDPR data notice and, on acceptance, opens an SSE connection to the backend API (`POST /chat`).
4. If the backend is unavailable (network error, 4xx/5xx on the first request, or stream timeout), the widget permanently switches to fallback mode and links the visitor to the `fallback-url`.

---

## Platform

| Parameter | Value |
| --- | --- |
| Artifact | `frontend/dist/chat.js` — single IIFE bundle |
| Storage | Object storage (S3-compatible), Frankfurt region |
| Distribution | CDN (public read) |
| Cache TTL | 1 minute — new deploys are visible to visitors within 1–2 minutes |
| Demo page | Served from the same bucket at `/demo/index.html` with no-cache headers |

---

## Deploy Pipeline

**Trigger:** Automatic on push to `main` touching `frontend/**`.

**Pipeline stages:**

```text
1. Frontend unit tests   → npm test (Vitest)
2. Vite build            → npm run build → dist/chat.js
3. Upload to CDN         → aws s3 cp to the CDN bucket
4. Upload demo page      → patched with production URLs, uploaded as no-cache
```

**To trigger manually:** `workflow_dispatch` on `deploy-frontend.yml` from the GitHub Actions UI.

**Build-time configuration** (injected from the GitHub Actions `production` environment — not in source control):

| Category | What is injected |
| --- | --- |
| API URL | The backend streaming endpoint URL |
| Fallback URL | The contact page visitors are sent to when the AI is unavailable |
| GDPR notice | The consent text shown to first-time visitors (requires legal sign-off) |
| API key | The widget authentication key passed in every request header |

See `frontend/.env.example` for the full variable reference.

---

## Cache Behaviour

The bundle is served with a 1-minute `max-age` cache header. After a deploy:

- Visitors who loaded the page within the last minute may still have the old bundle cached in the browser — this clears naturally.
- If you need to force an immediate refresh for all visitors, contact the CDN team to purge the `/chat.js` object.

The demo page is served with `no-store`, so it always reflects the latest deploy.

---

## Failure Modes

| Failure | Visitor experience | Action |
| --- | --- | --- |
| `chat.js` fails to load (404 or CDN outage) | Widget does not appear; host page is unaffected | Check the CDN bucket for the file; re-run `deploy-frontend.yml` |
| Backend unavailable on first request | Widget switches to fallback mode; visitor is linked to `fallback-url` | Investigate the backend (see [Backend API runbook](./ops-backend.md)) |
| Stream timeout on first request | Same as above — fallback mode activates | Investigate backend latency or rate-limiting |
| Backend recovers mid-session | Fallback state is permanent for that browser session; visitor must reload the page | No operator action needed |

The fallback path is intentionally silent from the operator's perspective — it requires no intervention. The `fallback-url` contact form operates independently of the AI backend.

---

## Embedding on the Host Website

The widget is embedded with two lines on the host website. The exact URLs and key are managed by the team.

```html
<script src="<CDN_URL>/chat.js" defer></script>
<growth-chat
  api-url="<BACKEND_URL>"
  fallback-url="<CONTACT_FORM_URL>"
></growth-chat>
```

Optional attributes:

| Attribute | Default | Description |
| --- | --- | --- |
| `position` | `bottom-right` | Widget position on screen |
| `proactive-delay-ms` | `45000` | Delay before the proactive message appears (milliseconds) |
| `proactive-message` | `"Have a question about AI engineering?"` | Proactive prompt text |

These attributes are set at the host website level, not in the widget bundle.
