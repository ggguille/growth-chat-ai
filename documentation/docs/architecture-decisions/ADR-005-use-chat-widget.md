---
description: "ADR-005: Decision to use @assistant-ui/react wrapped as a Custom Element (<growth-chat>) with Shadow DOM for the chat widget — covers alternatives considered (helixml, vanilla JS, iFrame, Vercel AI SDK), rationale for Web Component encapsulation, and constraints on the build pipeline and backend SSE format."
---

# ADR-005 — Use assistant-ui wrapped as a Web Component for the chat widget

**Status:** Accepted
**Date:** 2026-05-10
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Frontend Lead

---

## Context

The chat system requires a frontend widget that is embedded on the company landing page and must integrate with any web stack the host site uses. Building a chat widget from scratch is solved work — streaming token rendering, auto-scroll, accessibility, typing indicators, and responsive layout are well-understood problems that several mature open source libraries already handle. The engineering value of this project is in the backend: the LangGraph qualification graph, the RAG layer, and the handoff logic. The widget is a delivery vehicle for that backend, not a differentiator in itself.

Three requirements shape the widget decision:

1. **Open source with a permissive licence** — the widget must be freely modifiable and deployable without commercial restriction.
2. **React-based** — the team wants to build on a mainstream component model that is easy to extend, restyle, and reason about.
3. **Integrates into any host site without framework coupling** — the company site stack is not specified; the widget must work on WordPress, Webflow, Next.js, or static HTML with equal ease and without requiring the host page to have React installed.

A fourth requirement flows from the PRD: the widget must render streaming tokens
in real time (TTFT < 3s, PRD NFR 6.1), which rules out any approach that buffers
the full response before rendering.

---

## Decision

**We will use `@assistant-ui/react` as the chat UI library, wrapped in a thin
Web Component (`<growth-chat>`) that mounts React into a Shadow DOM and exposes
a script-tag integration path for any host site.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **`@assistant-ui/react` + Web Component wrapper — Chosen** | MIT-licenced React chat library with native LangGraph integration, wrapped in a Custom Element with Shadow DOM for universal embedding | Strongest feature set for production AI chat; LangGraph integration matches the backend; composable primitives allow full UI customisation | — Chosen |
| `@helixml/chat-widget` | Lighter React component also packaged as a standalone IIFE script tag; OpenAI-compatible API | Self-contained, smaller bundle, no wrapper needed | Designed for direct OpenAI-compatible endpoints; adapting it to the custom LangGraph streaming backend requires more modification than using assistant-ui from the start; fewer community resources and less active development |
| Vanilla JS widget (from scratch) | Custom element with no framework dependency; minimal bundle | Full control; no framework overhead (~0KB beyond product code) | Rebuilds solved problems (streaming rendering, auto-scroll, accessibility, markdown parsing); estimated 3–4× engineering effort vs. assistant-ui for equivalent quality; no meaningful performance advantage for a widget that loads lazily after page interaction |
| iFrame embed | Host page embeds the widget in a sandboxed iframe served from a separate origin | Zero CSS/JS conflict risk; simple embed code | Poor UX for a floating chat bubble (position, z-index, resize events across origin boundary); cannot access host page context (referrer, page title) for analytics; CSP restrictions on many host sites block third-party iframes |
| Vercel AI SDK + Next.js | First-party streaming UI for Next.js apps | Strong DX and streaming support | Tightly coupled to Vercel infrastructure; requires the host site to be a Next.js app, violating the stack-agnostic requirement |

---

## Rationale

### Why `assistant-ui`

`@assistant-ui/react` is the most complete open source React library for production
AI chat as of 2026. It handles the technically difficult parts of a streaming chat
interface — real-time token rendering without UI flicker, auto-scroll that does not
fight user scroll position, accessibility (ARIA roles, keyboard navigation), and
markdown rendering — as battle-tested primitives. Its composable architecture
(inspired by shadcn/ui and Radix) means every visual element can be replaced or
extended without forking the library.

The specific reason to prefer it over alternatives for this project is its
**first-class LangGraph runtime integration**. The backend is built on LangGraph
(ADR-002). `@assistant-ui/react` exposes a runtime adapter model; a LangGraph
runtime adapter connects the widget directly to the streaming graph output without
a custom serialisation layer. This eliminates a non-trivial integration surface
that would otherwise need to be built and maintained.

### Why a Web Component wrapper rather than a React component directly

A React component alone does not satisfy the stack-agnostic integration requirement.
The host site may not have React installed, and even if it does, version conflicts
between the host site React and the widget React are a real operational risk.

Wrapping the React component in a Custom Element with Shadow DOM solves both
problems cleanly:

- **Stack agnostic:** `customElements.define()` is a browser standard. The widget
  registers as `<growth-chat>` and works in any HTML page with a single script tag.
- **React isolation:** React mounts inside the Shadow DOM via `createRoot()`.
  The host page is unaware of it. No version conflicts, no CSS leakage in either
  direction.
- **CSS encapsulation:** Shadow DOM prevents the host page's global CSS from
  restyling the widget and prevents the widget's styles from affecting the host
  page. This is critical for reliable appearance across the variety of host sites
  the widget might be embedded on.

The wrapper itself is a thin layer — approximately 80–120 lines of TypeScript.
It is not a framework; it is glue code that:

1. Registers the `<growth-chat>` Custom Element.
2. Creates a Shadow DOM on the element.
3. Injects a `<div>` into the shadow root.
4. Calls `createRoot(div).render(<ChatWidget ...props />)` where `props` are
   read from the Custom Element's HTML attributes.
5. Calls `root.unmount()` in `disconnectedCallback` for clean teardown.

### Integration contract for host sites

The complete integration is two lines of HTML:

```html
<script src="https://widget.domain.com/chat.js" defer></script>
<growth-chat api-url="https://api.domain.com/chat"></growth-chat>
```

The `chat.js` bundle is served from the company CDN. It registers the custom
element and self-initialises. No npm install, no build step, no framework
requirement on the host side.

---

## Consequences

### Positive

- Streaming token rendering, auto-scroll, accessibility, and markdown support are
  handled by a maintained open source library rather than built from scratch.
- LangGraph runtime adapter eliminates a custom streaming serialisation layer.
- Shadow DOM encapsulation guarantees consistent widget appearance regardless of
  host site CSS.
- `<growth-chat api-url="...">` works in any stack — WordPress, Webflow, static
  HTML, Next.js — with no dependency on React being present on the host page.
- The wrapper layer is thin (~100 lines) and transparent; the assistant-ui
  components can be customised, replaced, or extended without touching the
  wrapper.

### Negative / Trade-offs

- **Bundle size.** The widget bundle includes React + react-dom (~44KB gzipped)
  plus `@assistant-ui/react` and the wrapper. Estimated total: **150–200KB gzipped**
  (unverified — measure during Phase 1 build and record the actual value here).
  The bundle is loaded lazily (the `<script>` tag has `defer`; the widget is not
  interactive until after the host page has loaded). The PRD widget load target
  is < 1 second non-blocking (PRD NFR 6.1); lazy loading satisfies the
  non-blocking requirement. Bundle size should be measured and tracked; if it
  exceeds 250KB gzipped, evaluate tree-shaking and code-splitting options before
  considering a different library.
- **React inside Shadow DOM has known edge cases.** React event delegation
  attaches listeners to `document` by default. Inside a closed Shadow DOM,
  events do not bubble to `document`, which breaks React's synthetic event
  system. The fix is to render into an open Shadow DOM (`mode: "open"`) and
  pass the shadow root as the event delegation target — supported in React 17+
  via the `ReactDOM.createRoot(container, { identifierPrefix })` API. This must
  be implemented correctly in the wrapper or events will silently fail.
- **LangGraph runtime adapter.** `@assistant-ui/react` does not ship a
  LangGraph runtime adapter out of the box as of the decision date. The team
  must implement one against the `assistant-ui` runtime interface. Estimated
  effort: 1–2 days. This is the most significant implementation risk of the
  chosen approach.
- **Shadow DOM styling hooks are limited.** The host site cannot restyle the
  widget interior via global CSS. Styling must be done via CSS custom properties
  exposed through the Shadow DOM boundary (`::part` and CSS variables). This is
  intentional for encapsulation, but means that a host site requesting visual
  customisation must be given explicit styling hooks rather than being able to
  override CSS directly.

### Constraints on future decisions

- The production build pipeline must output a single self-contained IIFE bundle
  (`chat.js`) suitable for CDN distribution. Vite with `lib` mode or esbuild
  with IIFE format are the appropriate build tools; the choice is an
  implementation detail not requiring an ADR.
- The LangGraph backend streaming endpoint must emit Server-Sent Events (SSE)
  in a format compatible with the `assistant-ui` runtime adapter interface.
  The SSE format must be defined and agreed between frontend and backend
  engineers before Phase 2 integration begins.
- If the host site uses a strict Content Security Policy, the CSP must explicitly
  allow loading scripts from the widget CDN origin. This is a deployment concern
  for the company marketing team, not an engineering constraint on the widget itself.

---

## Compliance Notes

- The widget loads from a CDN (`widget.domain.com`). GDPR compliance requires
  that the widget displays a data notice on first interaction (PRD NFR 6.3)
  before any visitor data is transmitted to the backend API. This is a product
  behaviour requirement implemented in the widget UI layer, not a hosting concern.
- The Shadow DOM does not affect GDPR obligations — data submitted through the
  widget (email, conversation content) follows the same processing rules as any
  other form submission on the site.

---

## Review Triggers

This decision should be revisited if:

- Actual bundle size exceeds 250KB gzipped after Phase 1 build and tree-shaking
  optimisation does not bring it below that threshold.
- `@assistant-ui/react` introduces a breaking change to its runtime adapter
  interface that makes the LangGraph adapter non-trivial to maintain.
- The React-inside-Shadow-DOM event delegation workaround produces persistent
  event handling bugs that are not resolvable within the assistant-ui component
  model.
- The host site integration requirement changes to require server-side rendering
  of the widget initial state, which Shadow DOM does not support in its current
  form.

---

## References

- [PRD Section 4.1 M1 — Conversational interface requirements](../product-requirements/index.md#product-requirements-document-prd-4-feature-scope-moscow-41-must-have-mvp-v1)
- [PRD Section 6.1 NFR — Widget load time < 1 second non-blocking](../product-requirements/index.md#product-requirements-document-prd-6-non-functional-requirements-61-performance)
- [PRD Section 4.4 W4 — No third-party chat platform integrations](../product-requirements/index.md#product-requirements-document-prd-4-feature-scope-moscow-44-wont-have-explicitly-out-of-scope)
- [ADR-002 — Use LangGraph for Conversation Orchestration](./ADR-002-conversation-orchestrator.md) — establishes the backend streaming interface this widget must connect to
- [`@assistant-ui/react` repository](https://github.com/assistant-ui/assistant-ui)
- [MDN Web Components documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
- [React event delegation and Shadow DOM](https://github.com/facebook/react/issues/9242)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
